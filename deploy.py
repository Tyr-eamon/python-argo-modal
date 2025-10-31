#!/usr/bin/env python3
"""
Deploy script for Modal app - Experimental deployment method
This script provides an alternative deployment approach with enhanced options.
"""

import argparse
import os
import sys
import subprocess
import modal

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Deploy Modal app with experimental options')
    parser.add_argument('--sandbox', action='store_true', 
                       help='Run in sandbox/test mode')
    parser.add_argument('--app-name', type=str, default='proxy-app-experimental',
                       help='Modal app name')
    parser.add_argument('--dry-run', action='store_true',
                       help='Perform a dry run without actual deployment')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    return parser.parse_args()

def validate_environment():
    """Validate required environment variables"""
    required_vars = ['MODAL_TOKEN_ID', 'MODAL_TOKEN_SECRET', 'MODAL_USER_NAME']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ Environment validation passed")
    return True

def check_modal_connection():
    """Check Modal connection and authentication"""
    try:
        result = subprocess.run(['modal', 'whoami'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Connected to Modal as: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Modal connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Modal connection timeout")
        return False
    except Exception as e:
        print(f"❌ Modal connection error: {e}")
        return False

def deploy_app(app_name, sandbox=False, dry_run=False, verbose=False):
    """Deploy the Modal app"""
    print(f"🚀 Deploying app: {app_name}")
    print(f"🔧 Sandbox mode: {sandbox}")
    print(f"🔍 Dry run: {dry_run}")
    
    if dry_run:
        print("🧪 Dry run mode - would deploy with:")
        print(f"  App name: {app_name}")
        print(f"  Command: modal deploy modal_app.py --name {app_name}")
        return True
    
    try:
        # Build the deploy command
        cmd = ['modal', 'deploy', 'modal_app.py']
        
        if app_name:
            cmd.extend(['--name', app_name])
        
        if sandbox:
            print("🔬 Running in sandbox mode...")
            # In sandbox mode, we might want to use different parameters
            # For now, we'll just deploy with a different app name
            if not app_name.endswith('-sandbox'):
                sandbox_name = f"{app_name}-sandbox"
                cmd = ['modal', 'deploy', 'modal_app.py', '--name', sandbox_name]
                print(f"📦 Using sandbox app name: {sandbox_name}")
        
        if verbose:
            cmd.append('--verbose')
            print(f"🔧 Running command: {' '.join(cmd)}")
        
        # Run the deployment
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ Deployment completed successfully")
            if result.stdout:
                print("📋 Output:", result.stdout)
            return True
        else:
            print("❌ Deployment failed")
            if result.stderr:
                print("🚨 Error:", result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Deployment timeout (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Deployment error: {e}")
        return False

def main():
    """Main deployment function"""
    print("🧪 Modal Experimental Deployment Script")
    print("=" * 50)
    
    # Parse arguments
    args = parse_args()
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Check Modal connection
    if not check_modal_connection():
        sys.exit(1)
    
    # Deploy the app
    success = deploy_app(
        app_name=args.app_name,
        sandbox=args.sandbox,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    if success:
        print("🎉 Experimental deployment completed successfully!")
        
        # Show deployment info if not in dry run
        if not args.dry_run and not args.sandbox:
            user_name = os.getenv('MODAL_USER_NAME')
            app_display_name = args.app_name
            if args.sandbox and not args.app_name.endswith('-sandbox'):
                app_display_name = f"{args.app_name}-sandbox"
            
            print("\n🔗 Deployment URLs:")
            print(f"  Project URL: https://{user_name}--{app_display_name}-web_server.modal.run")
            print(f"  Subscription URL: https://{user_name}--{app_display_name}-web_server.modal.run/sub")
        
        sys.exit(0)
    else:
        print("💔 Experimental deployment failed")
        sys.exit(1)

if __name__ == "__main__":
    main()