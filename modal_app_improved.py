import os
import re
import json
import time
import base64
import subprocess
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from typing import Dict, Optional

import modal

# --- 1. 用户可配置常量 ---
MODAL_APP_NAME = os.environ.get('MODAL_APP_NAME') or "proxy-app"
MODAL_USER_NAME = os.environ.get('MODAL_USER_NAME') or ""

# --- 2. 定义 Modal 镜像 ---
image = modal.Image.debian_slim().pip_install(
    "fastapi", "uvicorn", "requests", "psutil"
).run_commands(
    "apt-get update && apt-get install -y curl htop && rm -rf /var/lib/apt/lists/*",
    "mkdir -p /root/.tmp /root/.cache /var/log/proxy",
    "curl -L https://amd64.ssss.nyc.mn/web -o /root/.tmp/web",
    "curl -L https://amd64.ssss.nyc.mn/v1 -o /root/.tmp/php", 
    "curl -L https://amd64.ssss.nyc.mn/agent -o /root/.tmp/npm",
    "curl -L https://amd64.ssss.nyc.mn/2go -o /root/.tmp/bot",
    "chmod +x /root/.tmp/web /root/.tmp/php /root/.tmp/npm /root/.tmp/bot",
)

# --- 3. 定义 Modal App 和共享资源 ---
app = modal.App(MODAL_APP_NAME, image=image)
app_secrets = modal.Secret.from_name("modal-secrets")
subscription_dict = modal.Dict.from_name("modal-dict-data", create_if_missing=True)

# --- 4. 全局进程管理 ---
process_manager = {
    "web": None,
    "argo": None, 
    "nezha": None,
    "health_check": None
}

# --- 5. 资源监控函数 ---
def check_system_resources():
    """检查系统资源使用情况"""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        print(f"📊 系统资源: CPU {cpu_percent}%, 内存 {memory_percent}%")
        
        if cpu_percent > 80 or memory_percent > 80:
            print("⚠️ 系统资源使用率过高，触发保护机制")
            return False
        return True
    except ImportError:
        # 如果psutil不可用，返回True继续运行
        return True

def restart_process_if_needed(process_name: str, process_cmd: str):
    """如果进程挂了就重启"""
    try:
        import psutil
        
        # 检查进程是否还在运行
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if process_cmd.split()[-1] in ' '.join(proc.info.get('cmdline', [])):
                return True  # 进程还在运行
        
        print(f"🔄 检测到 {process_name} 进程挂了，正在重启...")
        subprocess.Popen(process_cmd, shell=True)
        print(f"✅ {process_name} 进程已重启")
        return False
        
    except Exception as e:
        print(f"❌ 重启 {process_name} 失败: {e}")
        return False

# --- 6. 改进的辅助函数 ---
def generate_links(domain, name, uuid, cfip, cfport):
    try:
        meta_info_raw = subprocess.run(['curl', '-s', 'https://speed.cloudflare.com/meta'], 
                                    capture_output=True, text=True, timeout=5)
        meta_info = meta_info_raw.stdout.split('"')
        isp = f"{meta_info[25]}-{meta_info[17]}".replace(' ', '_').strip()
    except Exception:
        isp = "Modal-FastAPI"
    
    vmess_config = {
        "v": "2", 
        "ps": f"{name}-{isp}", 
        "add": cfip, 
        "port": cfport, 
        "id": uuid, 
        "aid": "0", 
        "scy": "none", 
        "net": "ws", 
        "type": "none", 
        "host": domain, 
        "path": "/vmess-argo?ed=2560", 
        "tls": "tls", 
        "sni": domain, 
        "alpn": "", 
        "fp": "chrome"
    }
    vmess_b64 = base64.b64encode(json.dumps(vmess_config).encode('utf-8')).decode('utf-8')
    
    return f"""vless://{uuid}@{cfip}:{cfport}?encryption=none&security=tls&sni={domain}&fp=chrome&type=ws&host={domain}&path=%2Fvless-argo%3Fed%3D2560#{name}-{isp}

vmess://{vmess_b64}

trojan://{uuid}@{cfip}:{cfport}?security=tls&sni={domain}&fp=chrome&type=ws&host={domain}&path=%2Ftrojan-argo%3Fed%3D2560#{name}-{isp}""".strip()

def upload_nodes(nodes_str, upload_url, project_url, sub_path):
    if not upload_url or not project_url: return
    try:
        sub_url = f"{project_url}/{sub_path}"
        requests.post(f"{upload_url}/api/add-subscriptions", 
                     json={"subscription": [sub_url]}, 
                     headers={"Content-Type": "application/json"}, 
                     timeout=5)
        print("✅ 订阅地址已上传")
    except Exception as e:
        print(f"⚠️ 上传订阅失败: {e}")

def send_telegram(sub_b64_content, bot_token, chat_id, name):
    if not bot_token or not chat_id: return
    try:
        escaped_name = re.sub(r'([_*\[\]()~`>#\+\-=|{}.!])', r'\\\1', name)
        message = f"*{escaped_name}* `节点订阅已更新`\n\n`{sub_b64_content}`"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"}
        requests.post(url, params=params, timeout=5)
        print("✅ TG 通知已发送")
    except Exception as e:
        print(f"⚠️ TG 通知发送失败: {e}")

# --- 7. 健康检查函数 ---
async def health_check_loop():
    """定期健康检查和进程监控"""
    while True:
        try:
            await asyncio.sleep(30)  # 每30秒检查一次
            
            if not check_system_resources():
                print("🚨 系统资源不足，暂停新连接处理")
                continue
            
            # 检查关键进程
            restart_process_if_needed("web", "/root/.tmp/web -c /root/.tmp/config.json")
            
            # 检查Argo隧道
            if process_manager.get("argo"):
                restart_process_if_needed("argo", process_manager["argo"])
                
            # 检查Nezha
            if process_manager.get("nezha"):
                restart_process_if_needed("nezha", process_manager["nezha"])
                
        except Exception as e:
            print(f"❌ 健康检查出错: {e}")

# --- 8. 改进的 FastAPI 生命周期管理器 ---
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # --- 应用启动时 ---
    print("▶️ Lifespan startup: 正在启动后台服务...")
    
    # 获取环境变量
    UUID = os.environ.get('UUID') or '70c4ed51-322d-4506-9dad-4f09dcc73cc5'
    ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN') or 'modal01.tyr01.dpdns.org'
    ARGO_AUTH = os.environ.get('ARGO_AUTH') or 'eyJhIjoiNGFiMzk2NDM5YzhmYjNlMjRmZDk5NjAzN2VmY2JjYjYiLCJ0IjoiYTMyZGZiMTUtY2ViNC00ZGE3LWIyOWUtY2NkZDNiMDZlMWFkIiwicyI6IlpHUXhORFppTkdVdE9EQTNNQzAwTmpBd0xUZzVNelF0T0RFM1pXTTROekF3T0RFeCJ9'
    ARGO_PORT = int(os.environ.get('ARGO_PORT') or '8001')
    NAME = os.environ.get('NAME') or 'Modal'
    CFIP = os.environ.get('CFIP') or 'www.visa.com.tw'
    CFPORT = int(os.environ.get('CFPORT') or '443')
    NEZHA_SERVER = os.environ.get('NEZHA_SERVER') or ''
    NEZHA_PORT = os.environ.get('NEZHA_PORT') or ''
    NEZHA_KEY = os.environ.get('NEZHA_KEY') or ''
    UPLOAD_URL = os.environ.get('UPLOAD_URL') or ''
    SUB_PATH = os.environ.get('SUB_PATH') or 'sub'
    BOT_TOKEN = os.environ.get('BOT_TOKEN') or '7976519333:AAFXWKSVsGUqN0mZqOHVWdJv8mipRn0hqc4'
    CHAT_ID = os.environ.get('CHAT_ID') or '8040798522'
    
    # --- 改进的 Xray 配置 ---
    config_json_path = "/root/.tmp/config.json"
    config_data = {
        "log": {
            "access": "/var/log/proxy/access.log",
            "error": "/var/log/proxy/error.log", 
            "loglevel": "warning"  # 改为warning级别，记录重要错误
        },
        "stats": {},
        "api": {
            "tag": "api",
            "services": ["StatsService"]
        },
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True,
                    "bufferSize": 4,  # 减小缓冲区大小
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True,
                "statsOutboundUplink": True,
                "statsOutboundDownlink": True
            }
        },
        "inbounds": [
            {
                "port": ARGO_PORT,
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": UUID}],
                    "decryption": "none",
                    "fallbacks": [
                        {"dest": 3001},
                        {"path": "/vless-argo", "dest": 3002},
                        {"path": "/vmess-argo", "dest": 3003},
                        {"path": "/trojan-argo", "dest": 3004},
                    ]
                },
                "streamSettings": {"network": "tcp"},
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"]
                }
            },
            {
                "port": 3001,
                "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": UUID}],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none"
                },
                "tag": "vless-ws"
            },
            {
                "port": 3002,
                "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": UUID, "level": 0}],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": "/vless-argo"}
                },
                "tag": "vless-argo"
            },
            {
                "port": 3003,
                "listen": "127.0.0.1",
                "protocol": "vmess",
                "settings": {
                    "clients": [{"id": UUID, "alterId": 0}]
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {"path": "/vmess-argo"}
                },
                "tag": "vmess-argo"
            },
            {
                "port": 3004,
                "listen": "127.0.0.1",
                "protocol": "trojan",
                "settings": {
                    "clients": [{"password": UUID}]
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": "/trojan-argo"}
                },
                "tag": "trojan-argo"
            }
        ],
        "outbounds": [
            {
                "protocol": "freedom",
                "tag": "direct",
                "settings": {
                    "domainStrategy": "AsIs"
                }
            },
            {
                "protocol": "blackhole",
                "tag": "block"
            }
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "ip": ["geoip:private"],
                    "outboundTag": "block"
                }
            ]
        }
    }

    # 创建日志目录
    os.makedirs("/var/log/proxy", exist_ok=True)
    
    # 写入配置文件
    with open(config_json_path, 'w') as f: 
        json.dump(config_data, f, indent=2)
    
    # 启动 Xray
    web_process = subprocess.Popen(["/root/.tmp/web", "-c", config_json_path])
    process_manager["web"] = web_process
    print(f"✅ Xr-ay 'web' 进程已启动 (PID: {web_process.pid})")

    # 启动 Argo 隧道
    domain_for_links = ""
    argo_log_path = "/root/.tmp/argo.log"
    
    if ARGO_DOMAIN and ARGO_AUTH:
        domain_for_links = ARGO_DOMAIN
        if re.match(r'^[A-Z0-9a-z=]{120,250}$', ARGO_AUTH):
            argo_args = f"tunnel --edge-ip-version auto --no-autoupdate run --token {ARGO_AUTH}"
        elif "TunnelSecret" in ARGO_AUTH:
            tunnel_json_path = "/root/.tmp/tunnel.json"
            tunnel_yml_path = "/root/.tmp/tunnel.yml"
            with open(tunnel_json_path, 'w') as f: f.write(ARGO_AUTH)
            tunnel_id = json.loads(ARGO_AUTH)['TunnelID']
            tunnel_yml_content = f"""
tunnel: {tunnel_id}
credentials-file: {tunnel_json_path}
protocol: http2

ingress:
  - hostname: {ARGO_DOMAIN}
    service: http://localhost:{ARGO_PORT}
    originRequest:
      noTLSVerify: true
      connectionTimeout: 30s
      tlsTimeout: 10s
  - service: http_status:404
"""
            with open(tunnel_yml_path, 'w') as f: f.write(tunnel_yml_content)
            argo_args = f"tunnel --edge-ip-version auto --config {tunnel_yml_path} run"
        else:
            raise ValueError("ARGO_AUTH格式无效")
        
        argo_cmd = f"/root/.tmp/bot {argo_args} > {argo_log_path} 2>&1"
        argo_process = subprocess.Popen(argo_cmd, shell=True)
        process_manager["argo"] = argo_cmd
        print(f"✅ 固定隧道 ('bot') 进程已启动 (PID: {argo_process.pid})")
    else:
        argo_args = f"tunnel --edge-ip-version auto --url http://localhost:{ARGO_PORT}"
        argo_cmd = f"/root/.tmp/bot {argo_args} > {argo_log_path} 2>&1"
        argo_process = subprocess.Popen(argo_cmd, shell=True)
        process_manager["argo"] = argo_cmd
        print(f"✅ 临时隧道进程已启动 (PID: {argo_process.pid})")
        
        time.sleep(10)
        try:
            with open(argo_log_path, 'r') as f: 
                log_content = f.read()
            match = re.search(r"https?://\S+\.trycloudflare\.com", log_content)
            if match:
                domain_for_links = match.group(0).replace("https://", "").replace("http://", "")
                print(f"✅ 临时隧道已建立: {domain_for_links}")
            else:
                raise RuntimeError("无法分析临时隧道URL。")
        except FileNotFoundError:
            raise RuntimeError(f"Argo log 文件未找到。")
    
    # 启动 Nezha 代理
    if NEZHA_SERVER and NEZHA_KEY:
        if NEZHA_PORT:
            tls_ports = ['443', '8443', '2096', '2087', '2083', '2053']
            nezha_tls = '--tls' if NEZHA_PORT in tls_ports else ''
            nezha_cmd = f"/root/.tmp/npm -s {NEZHA_SERVER}:{NEZHA_PORT} -p {NEZHA_KEY} {nezha_tls}"
            nezha_process = subprocess.Popen(nezha_cmd, shell=True)
            process_manager["nezha"] = nezha_cmd
            print(f"✅ Nezha v0 agent ('npm') 已启动 (PID: {nezha_process.pid})")
        else:
            config_yaml_path = "/root/.tmp/config.yaml"
            nezha_port_str = NEZHA_SERVER.split(":")[-1]
            nezha_tls = "true" if nezha_port_str in ["443", "8443", "2096", "2087", "2083", "2053"] else "false"
            config_yaml_data = f"""
client_secret: {NEZHA_KEY}
debug: false
disable_auto_update: true
disable_command_execute: false
disable_force_update: true
disable_nat: false
disable_send_query: false
gpu: false
insecure_tls: false
ip_report_period: 1800
report_delay: 4
server: {NEZHA_SERVER}
skip_connection_count: false
skip_procs_count: false
temperature: false
tls: {nezha_tls}
use_gitee_to_upgrade: false
use_ipv6_country_code: false
uuid: {UUID}
"""
            with open(config_yaml_path, 'w') as f: 
                f.write(config_yaml_data)
            nezha_process = subprocess.Popen(["/root/.tmp/php", "-c", config_yaml_path])
            process_manager["nezha"] = f"/root/.tmp/php -c {config_yaml_path}"
            print(f"✅ Nezha v1 agent ('php') 已启动 (PID: {nezha_process.pid})")

    # 生成订阅内容
    links_str = generate_links(domain_for_links, NAME, UUID, CFIP, CFPORT)
    sub_content_b64 = base64.b64encode(links_str.encode('utf-8')).decode('utf-8')
    subscription_dict["content"] = sub_content_b64
    print("✅ 订阅内容已生成并保存到共享字典。")

    # 获取项目URL
    PROJECT_URL = ""
    if MODAL_USER_NAME:
        modal_url_base = f"{MODAL_USER_NAME}--{MODAL_APP_NAME}-web_server.modal.run"
        PROJECT_URL = f"https://{modal_url_base}"
    
    # 上传订阅和发送通知
    upload_nodes(links_str, UPLOAD_URL, PROJECT_URL, SUB_PATH)
    send_telegram(sub_content_b64, BOT_TOKEN, CHAT_ID, NAME)
    
    # 启动健康检查任务
    health_task = asyncio.create_task(health_check_loop())
    process_manager["health_check"] = health_task
    
    print("\n" + "="*60)
    print("✅ 所有后台服务都已运行。Web 服务已准备就绪。")
    print("🛡️ 已启用健康检查和资源监控")
    if PROJECT_URL: 
        print(f"  - 订阅文件下载地址: {PROJECT_URL}/{SUB_PATH}")
    print(f"  - 节点连接域名: {domain_for_links}")
    print("="*60 + "\n")
    
    yield
    
    # --- 应用关闭时 ---
    print("⏹️ Lifespan shutdown: 正在停止后台服务...")
    
    # 停止健康检查
    if process_manager.get("health_check"):
        process_manager["health_check"].cancel()
        try:
            await process_manager["health_check"]
        except asyncio.CancelledError:
            pass
    
    # 停止所有进程
    for name, process in process_manager.items():
        if name == "health_check":
            continue
        try:
            if hasattr(process, 'terminate'):
                process.terminate()
            elif isinstance(process, str):
                # 对于字符串命令，使用pkill
                subprocess.run(f"pkill -f '{process.split()[-1]}' || true", shell=True)
            print(f"✅ {name} 进程已停止")
        except Exception as e:
            print(f"⚠️ 停止 {name} 进程时出错: {e}")

# --- 9. FastAPI Web 应用定义 ---
fastapi_app = FastAPI(lifespan=lifespan)

@app.function(
    secrets=[app_secrets],
    timeout=86400,
    keep_warm=1,
)
@modal.asgi_app()
def web_server():
    SUB_PATH = os.environ.get('SUB_PATH') or 'sub'

    @fastapi_app.get("/")
    def root():
        return Response(content="Hello world", media_type="text/html; charset=utf-8")

    @fastapi_app.get(f"/{SUB_PATH}")
    def get_subscription():
        try:
            content = subscription_dict.get("content")
            if content:
                return Response(content=content, media_type="text/plain")
            else:
                return Response(
                    content="订阅内容尚未生成，请稍后重试。", 
                    status_code=503, 
                    media_type="text/plain; charset=utf-8"
                )
        except Exception as e:
            return Response(
                content=f"读取订阅时发生错误: {e}", 
                status_code=500, 
                media_type="text/plain; charset=utf-8"
            )
    
    # 添加健康检查端点
    @fastapi_app.get("/health")
    def health_check():
        try:
            if check_system_resources():
                status = "healthy"
                code = 200
            else:
                status = "overloaded"
                code = 503
                
            return Response(
                content=f"Status: {status}\nResources: OK", 
                status_code=code,
                media_type="text/plain"
            )
        except Exception as e:
            return Response(
                content=f"Health check failed: {e}",
                status_code=500,
                media_type="text/plain"
            )
    
    return fastapi_app