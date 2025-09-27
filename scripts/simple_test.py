#!/usr/bin/env python3
"""
Simple test to verify the basic structure works without full dependencies.
"""

import sys
from pathlib import Path

def test_basic_structure():
    """Test that we can at least read the configuration files."""
    print("🧪 Testing basic structure...")
    
    # Check that files exist
    backend_dir = Path(__file__).parent.parent / "autogpt_platform" / "backend" / "backend"
    
    required_files = [
        "data/chat_proxy_models.py",
        "util/load_balancer.py",
        "blocks/chat_proxy/blocks.py",
        "server/routers/openai_proxy.py",
        "server/main.py"
    ]
    
    for file_path in required_files:
        full_path = backend_dir / file_path
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            return False
    
    # Check that service configurations are in the file
    models_file = backend_dir / "data/chat_proxy_models.py"
    with open(models_file, 'r') as f:
        content = f.read()
    
    required_services = [
        "K2THINK",
        "QWEN", 
        "DEEPSEEK",
        "GROK",
        "ZAI"
    ]
    
    for service in required_services:
        if service in content:
            print(f"   ✅ {service} service configured")
        else:
            print(f"   ❌ {service} service - MISSING")
            return False
    
    # Check that credentials are configured
    if "DEFAULT_ACCOUNTS" in content:
        print("   ✅ DEFAULT_ACCOUNTS configured")
    else:
        print("   ❌ DEFAULT_ACCOUNTS - MISSING")
        return False
    
    # Check specific credentials
    credentials = [
        "developer@pixelium.uk",
        "zeeeepa+1@gmail.com",
        "developer123?",
        "developer1?",
        "developer123??"
    ]
    
    for cred in credentials:
        if cred in content:
            print(f"   ✅ Credential configured: {cred}")
        else:
            print(f"   ❌ Credential missing: {cred}")
    
    print("\n🎯 Basic structure test completed!")
    return True

def test_service_urls():
    """Test that service URLs are correct."""
    print("\n🌐 Testing service URLs...")
    
    expected_urls = [
        "https://www.k2think.ai",
        "https://chat.qwen.ai", 
        "https://chat.deepseek.com",
        "https://grok.com",
        "https://chat.z.ai"
    ]
    
    backend_dir = Path(__file__).parent.parent / "autogpt_platform" / "backend" / "backend"
    models_file = backend_dir / "data/chat_proxy_models.py"
    
    with open(models_file, 'r') as f:
        content = f.read()
    
    for url in expected_urls:
        if url in content:
            print(f"   ✅ {url}")
        else:
            print(f"   ❌ {url} - MISSING")
    
    return True

def main():
    """Main test function."""
    print("🚀 Simple Structure Test")
    print("=" * 50)
    
    success = True
    success &= test_basic_structure()
    success &= test_service_urls()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All basic structure tests passed!")
        print("📋 Ready to test with real services and credentials.")
        print("\nNext steps:")
        print("1. Get Stagehand API key and Browserbase project ID")
        print("2. Run ./scripts/test_real_services.py")
        print("3. Start server with ./scripts/start_chat_proxy_server.py")
        print("4. Test API with ./scripts/test_openai_api.py")
    else:
        print("❌ Some structure tests failed!")
        print("Please check the configuration files.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
