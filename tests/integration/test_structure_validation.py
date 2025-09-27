"""
Test that validates the structure and basic functionality without requiring full backend setup.
"""

import pytest
import sys
from pathlib import Path


@pytest.mark.integration
class TestStructureValidation:
    """Test basic structure validation."""
    
    def test_files_exist(self):
        """Test that all required files exist."""
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        
        required_files = [
            "data/chat_proxy_models.py",
            "util/load_balancer.py", 
            "blocks/chat_proxy/__init__.py",
            "blocks/chat_proxy/blocks.py",
            "blocks/chat_proxy/_config.py",
            "server/routers/openai_proxy.py",
        ]
        
        for file_path in required_files:
            full_path = base_path / file_path
            assert full_path.exists(), f"Required file missing: {file_path}"
        
        print(f"✅ All {len(required_files)} required files exist")
    
    def test_config_files_exist(self):
        """Test that configuration files exist."""
        base_path = Path(__file__).parent.parent.parent
        
        config_files = [
            "autogpt_platform/backend/.env.chat_proxy.default",
            "scripts/setup-chat-proxy.sh",
            "docs/content/platform/chat-proxy-guide.md",
        ]
        
        for file_path in config_files:
            full_path = base_path / file_path
            assert full_path.exists(), f"Config file missing: {file_path}"
        
        print(f"✅ All {len(config_files)} config files exist")
    
    def test_test_files_exist(self):
        """Test that test files exist."""
        test_dir = Path(__file__).parent
        
        test_files = [
            "conftest.py",
            "test_openai_compatibility.py",
            "test_browser_automation.py", 
            "test_load_balancer.py",
            "test_chat_proxy_e2e.py",
            "run_tests.py",
            "pytest.ini",
            ".env.test.example",
        ]
        
        for file_path in test_files:
            full_path = test_dir / file_path
            assert full_path.exists(), f"Test file missing: {file_path}"
        
        print(f"✅ All {len(test_files)} test files exist")
    
    def test_python_syntax_validation(self):
        """Test that all Python files have valid syntax."""
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        
        python_files = [
            "data/chat_proxy_models.py",
            "util/load_balancer.py",
            "blocks/chat_proxy/blocks.py",
            "blocks/chat_proxy/_config.py",
            "server/routers/openai_proxy.py",
        ]
        
        for file_path in python_files:
            full_path = base_path / file_path
            
            # Read and compile the file to check syntax
            with open(full_path, 'r') as f:
                content = f.read()
            
            try:
                compile(content, str(full_path), 'exec')
                print(f"✅ {file_path} has valid syntax")
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {file_path}: {e}")
    
    def test_test_syntax_validation(self):
        """Test that all test files have valid syntax."""
        test_dir = Path(__file__).parent
        
        test_files = [
            "conftest.py",
            "test_openai_compatibility.py",
            "test_browser_automation.py",
            "test_load_balancer.py", 
            "test_chat_proxy_e2e.py",
            "run_tests.py",
        ]
        
        for file_path in test_files:
            full_path = test_dir / file_path
            
            # Read and compile the file to check syntax
            with open(full_path, 'r') as f:
                content = f.read()
            
            try:
                compile(content, str(full_path), 'exec')
                print(f"✅ {file_path} has valid syntax")
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {file_path}: {e}")
    
    def test_imports_structure(self):
        """Test that import statements are structured correctly."""
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        
        # Check that files contain expected import patterns
        load_balancer_file = base_path / "util/load_balancer.py"
        with open(load_balancer_file, 'r') as f:
            content = f.read()
        
        # Should import from backend.data
        assert "from backend.data.chat_proxy_models import" in content
        print("✅ Load balancer imports are structured correctly")
        
        # Check openai_proxy imports
        openai_proxy_file = base_path / "server/routers/openai_proxy.py"
        with open(openai_proxy_file, 'r') as f:
            content = f.read()
        
        # Should have FastAPI imports
        assert "from fastapi import" in content
        print("✅ OpenAI proxy imports are structured correctly")
    
    def test_configuration_structure(self):
        """Test that configuration files are structured correctly."""
        base_path = Path(__file__).parent.parent.parent
        
        # Check .env.chat_proxy.default structure
        env_file = base_path / "autogpt_platform/backend/.env.chat_proxy.default"
        with open(env_file, 'r') as f:
            content = f.read()
        
        required_env_vars = [
            "STAGEHAND_API_KEY",
            "BROWSERBASE_PROJECT_ID",
            "ZAI_EMAIL",
            "ZAI_PASSWORD",
            "DEFAULT_LOAD_BALANCING_STRATEGY",
        ]
        
        for var in required_env_vars:
            assert var in content, f"Missing environment variable: {var}"
        
        print(f"✅ Environment configuration contains all {len(required_env_vars)} required variables")
    
    def test_documentation_structure(self):
        """Test that documentation is structured correctly."""
        base_path = Path(__file__).parent.parent.parent
        
        # Check documentation file
        doc_file = base_path / "docs/content/platform/chat-proxy-guide.md"
        with open(doc_file, 'r') as f:
            content = f.read()
        
        required_sections = [
            "# AutoGPT Chat Proxy Guide",
            "## 🌟 Key Features",
            "## 🚀 Quick Start",
            "## 📡 API Endpoints",
            "## 🎯 Model Mapping",
        ]
        
        for section in required_sections:
            assert section in content, f"Missing documentation section: {section}"
        
        print(f"✅ Documentation contains all {len(required_sections)} required sections")
    
    def test_setup_script_structure(self):
        """Test that setup script is structured correctly."""
        base_path = Path(__file__).parent.parent.parent
        
        # Check setup script
        setup_file = base_path / "scripts/setup-chat-proxy.sh"
        with open(setup_file, 'r') as f:
            content = f.read()
        
        required_elements = [
            "#!/bin/bash",
            "AutoGPT Chat Proxy Setup",
            ".env.chat_proxy",
            "poetry add stagehand",
        ]
        
        for element in required_elements:
            assert element in content, f"Missing setup script element: {element}"
        
        print(f"✅ Setup script contains all {len(required_elements)} required elements")


@pytest.mark.integration
class TestBasicFunctionality:
    """Test basic functionality without external dependencies."""
    
    def test_enum_definitions(self):
        """Test that enum definitions are valid."""
        # Test that we can at least parse the enum definitions
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        models_file = base_path / "data/chat_proxy_models.py"
        
        with open(models_file, 'r') as f:
            content = f.read()
        
        # Should contain enum definitions
        assert "class ChatServiceType" in content
        assert "class LoadBalancingStrategy" in content
        assert "class AccountStatus" in content
        
        print("✅ Enum definitions are present")
    
    def test_class_definitions(self):
        """Test that class definitions are present."""
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        
        # Check load balancer classes
        load_balancer_file = base_path / "util/load_balancer.py"
        with open(load_balancer_file, 'r') as f:
            content = f.read()
        
        assert "class ChatProxyLoadBalancer" in content
        assert "class AccountHealth" in content
        
        print("✅ Load balancer classes are defined")
        
        # Check block classes
        blocks_file = base_path / "blocks/chat_proxy/blocks.py"
        with open(blocks_file, 'r') as f:
            content = f.read()
        
        assert "class ChatProxyLoginBlock" in content
        assert "class ChatProxySendMessageBlock" in content
        assert "class ChatProxyHealthCheckBlock" in content
        
        print("✅ Chat proxy block classes are defined")
    
    def test_api_endpoint_definitions(self):
        """Test that API endpoints are defined."""
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        
        openai_proxy_file = base_path / "server/routers/openai_proxy.py"
        with open(openai_proxy_file, 'r') as f:
            content = f.read()
        
        # Should contain API endpoint definitions
        assert "chat/completions" in content
        assert "/models" in content
        assert "/health" in content
        assert "/stats" in content
        
        print("✅ API endpoints are defined")
    
    def test_model_mappings(self):
        """Test that model mappings are defined."""
        base_path = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend" / "backend"
        
        openai_proxy_file = base_path / "server/routers/openai_proxy.py"
        with open(openai_proxy_file, 'r') as f:
            content = f.read()
        
        # Should contain model mappings
        assert "MODEL_SERVICE_MAPPING" in content
        assert "gpt-3.5-turbo" in content
        assert "qwen-max" in content
        assert "deepseek-chat" in content
        
        print("✅ Model mappings are defined")
