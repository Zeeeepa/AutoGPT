#!/usr/bin/env python3
"""
Test runner for chat proxy integration tests.
Provides comprehensive test execution with proper setup and reporting.
"""

import os
import sys
import asyncio
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any


def setup_environment():
    """Set up the test environment."""
    # Add the backend directory to Python path
    backend_dir = Path(__file__).parent.parent.parent / "autogpt_platform" / "backend"
    sys.path.insert(0, str(backend_dir))
    
    # Load test environment variables if available
    test_env_file = Path(__file__).parent / ".env.test"
    if test_env_file.exists():
        print(f"Loading test environment from {test_env_file}")
        with open(test_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value
    else:
        print("No .env.test file found - using default test configuration")


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "httpx",
        "openai",
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
        return False
    
    return True


def get_test_categories():
    """Get available test categories."""
    return {
        "unit": {
            "description": "Unit tests (no external dependencies)",
            "markers": "integration and not real_services",
            "fast": True
        },
        "integration": {
            "description": "Integration tests (may require some services)",
            "markers": "integration",
            "fast": False
        },
        "real_services": {
            "description": "Real service tests (requires credentials and services)",
            "markers": "real_services",
            "fast": False
        },
        "e2e": {
            "description": "End-to-end tests (full pipeline)",
            "markers": "real_services and slow",
            "fast": False
        },
        "all": {
            "description": "All tests",
            "markers": "",
            "fast": False
        }
    }


def build_pytest_command(
    category: str = "unit",
    verbose: bool = True,
    capture: str = "no",
    parallel: bool = False,
    specific_test: str = None,
    extra_args: List[str] = None
) -> List[str]:
    """Build pytest command with appropriate arguments."""
    cmd = ["python", "-m", "pytest"]
    
    # Add test directory
    test_dir = Path(__file__).parent
    cmd.append(str(test_dir))
    
    # Add specific test if provided
    if specific_test:
        cmd.append(f"::{specific_test}")
    
    # Add markers based on category
    categories = get_test_categories()
    if category in categories and categories[category]["markers"]:
        cmd.extend(["-m", categories[category]["markers"]])
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    
    # Add capture setting
    cmd.extend(["-s" if capture == "no" else f"--capture={capture}"])
    
    # Add parallel execution if requested
    if parallel:
        try:
            import pytest_xdist
            cmd.extend(["-n", "auto"])
        except ImportError:
            print("⚠️ pytest-xdist not installed, running tests sequentially")
    
    # Add extra arguments
    if extra_args:
        cmd.extend(extra_args)
    
    # Add common pytest options
    cmd.extend([
        "--tb=short",  # Shorter traceback format
        "--strict-markers",  # Strict marker checking
        "--disable-warnings",  # Disable warnings for cleaner output
    ])
    
    return cmd


def run_tests(
    category: str = "unit",
    verbose: bool = True,
    capture: str = "no",
    parallel: bool = False,
    specific_test: str = None,
    dry_run: bool = False,
    extra_args: List[str] = None
) -> int:
    """Run tests with specified configuration."""
    categories = get_test_categories()
    
    if category not in categories:
        print(f"❌ Invalid category: {category}")
        print(f"Available categories: {', '.join(categories.keys())}")
        return 1
    
    print(f"🧪 Running {category} tests: {categories[category]['description']}")
    
    # Build command
    cmd = build_pytest_command(
        category=category,
        verbose=verbose,
        capture=capture,
        parallel=parallel,
        specific_test=specific_test,
        extra_args=extra_args
    )
    
    if dry_run:
        print(f"Would run: {' '.join(cmd)}")
        return 0
    
    print(f"Command: {' '.join(cmd)}")
    print("=" * 80)
    
    # Run tests
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


def check_server_status():
    """Check if the chat proxy server is running."""
    try:
        import httpx
        import asyncio
        
        async def check():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get("http://localhost:8000/api/v1/health", timeout=5)
                    return response.status_code == 200
            except:
                return False
        
        return asyncio.run(check())
    except ImportError:
        print("⚠️ httpx not available for server check")
        return False


def print_test_info():
    """Print information about available tests."""
    categories = get_test_categories()
    
    print("📋 Available Test Categories:")
    print("=" * 50)
    
    for name, info in categories.items():
        speed_indicator = "🚀" if info["fast"] else "🐌"
        print(f"{speed_indicator} {name:15} - {info['description']}")
        if info["markers"]:
            print(f"   Markers: {info['markers']}")
        print()
    
    print("🔧 Test Configuration:")
    print("=" * 30)
    
    # Check environment
    real_services_enabled = os.getenv("ENABLE_REAL_SERVICES", "false").lower() == "true"
    stagehand_key = os.getenv("TEST_STAGEHAND_API_KEY", "not-set")
    
    print(f"Real services enabled: {'✅' if real_services_enabled else '❌'}")
    print(f"Stagehand API key: {'✅' if stagehand_key != 'not-set' else '❌'}")
    
    # Check server status
    server_running = check_server_status()
    print(f"Chat proxy server: {'✅' if server_running else '❌'}")
    
    print()
    print("💡 Tips:")
    print("- Start with 'unit' tests to verify basic functionality")
    print("- Use 'integration' tests to check component interactions")
    print("- Use 'real_services' tests only when you have credentials")
    print("- Set ENABLE_REAL_SERVICES=true for full testing")


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Chat Proxy Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                          # Run unit tests
  python run_tests.py --category integration   # Run integration tests
  python run_tests.py --category real_services # Run real service tests
  python run_tests.py --info                   # Show test information
  python run_tests.py --dry-run                # Show what would be run
        """
    )
    
    parser.add_argument(
        "--category", "-c",
        choices=list(get_test_categories().keys()),
        default="unit",
        help="Test category to run (default: unit)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Verbose output (default: True)"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet output (overrides verbose)"
    )
    
    parser.add_argument(
        "--capture",
        choices=["no", "sys", "fd"],
        default="no",
        help="Capture mode for output (default: no)"
    )
    
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel (requires pytest-xdist)"
    )
    
    parser.add_argument(
        "--test", "-t",
        help="Run specific test function"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without executing"
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show test information and exit"
    )
    
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Extra arguments to pass to pytest"
    )
    
    args = parser.parse_args()
    
    # Show info and exit
    if args.info:
        print_test_info()
        return 0
    
    # Set up environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Adjust verbosity
    verbose = args.verbose and not args.quiet
    
    # Run tests
    return run_tests(
        category=args.category,
        verbose=verbose,
        capture=args.capture,
        parallel=args.parallel,
        specific_test=args.test,
        dry_run=args.dry_run,
        extra_args=args.extra_args
    )


if __name__ == "__main__":
    sys.exit(main())
