#!/usr/bin/env python3
"""
部署修复版本的Modal应用 - 解决Hiddify并发测速问题
"""

import argparse
import subprocess
import sys
import os

def deploy_fixed_version():
    """部署修复版本"""
    print("🔧 部署修复版本 - 解决Hiddify并发测速问题")
    print("=" * 50)
    
    # 检查修复版本文件是否存在
    if not os.path.exists("modal_app_fixed.py"):
        print("❌ modal_app_fixed.py 文件不存在")
        return False
    
    try:
        # 备份原文件
        if os.path.exists("modal_app.py"):
            subprocess.run(["cp", "modal_app.py", "modal_app_backup.py"], check=True)
            print("✅ 已备份原 modal_app.py")
        
        # 替换为修复版本
        subprocess.run(["cp", "modal_app_fixed.py", "modal_app.py"], check=True)
        print("✅ 已替换为修复版本")
        
        # 部署到Modal
        print("🚀 开始部署到Modal...")
        result = subprocess.run(["modal", "deploy", "modal_app.py"], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ 修复版本部署成功!")
            print("📋 主要改进:")
            print("  - 限制并发连接数 (100个总连接)")
            print("  - 减少缓冲区大小 (防止内存溢出)")
            print("  - 优化握手并发 (4个并发)")
            print("  - 添加连接空闲超时")
            print("  - 拒绝私有IP连接")
            print("  - 改进日志级别 (减少开销)")
            print("\n🛡️ 现在可以应对Hiddify的并发测速了!")
            return True
        else:
            print("❌ 部署失败:")
            print(result.stderr)
            # 恢复原文件
            if os.path.exists("modal_app_backup.py"):
                subprocess.run(["cp", "modal_app_backup.py", "modal_app.py"])
                print("🔄 已恢复原文件")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 部署超时")
        return False
    except Exception as e:
        print(f"❌ 部署出错: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='部署修复版本的Modal应用')
    parser.add_argument('--restore', action='store_true', 
                       help='恢复到原版本')
    args = parser.parse_args()
    
    if args.restore:
        if os.path.exists("modal_app_backup.py"):
            subprocess.run(["cp", "modal_app_backup.py", "modal_app.py"], check=True)
            print("✅ 已恢复到原版本")
            
            # 重新部署原版本
            print("🚀 重新部署原版本...")
            result = subprocess.run(["modal", "deploy", "modal_app.py"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ 原版本重新部署成功")
            else:
                print("❌ 原版本重新部署失败")
        else:
            print("❌ 没有找到备份文件")
    else:
        success = deploy_fixed_version()
        if not success:
            sys.exit(1)

if __name__ == "__main__":
    main()