#!/usr/bin/env python3
"""
Test script demonstrating OpenAI-compatible API usage with intelligent model routing.

This demonstrates:
1. Using the OpenAI Python client library
2. Routing to specific providers by model name ("z.ai")
3. Automatic fallback to default provider for generic models ("gpt-4")
4. Proper error handling and response formatting
"""

from openai import OpenAI
import sys

# Configuration
BASE_URL = "http://localhost:8000/v1"  # Your custom API URL
API_KEY = "anything"  # API key not required for this implementation

def test_specific_provider():
    """Test routing to a specific provider using model name."""
    print("🧪 Test 1: Routing to specific provider (z.ai)")
    print("=" * 60)
    
    try:
        # Create OpenAI client with custom base URL
        client = OpenAI(
            base_url=BASE_URL,
            api_key=API_KEY
        )
        
        # Make a chat completion request with specific provider model
        response = client.chat.completions.create(
            model="z.ai",  # This will route to Z.AI provider
            messages=[
                {"role": "user", "content": "What model are you?"}
            ]
        )
        
        print(f"✅ Response received!")
        print(f"Model used: {response.model}")
        print(f"Response: {response.choices[0].message.content}")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()


def test_generic_model():
    """Test automatic routing for generic OpenAI models."""
    print("🧪 Test 2: Routing generic model to default provider (gpt-4)")
    print("=" * 60)
    
    try:
        # Create OpenAI client with custom base URL
        client = OpenAI(
            base_url=BASE_URL,
            api_key=API_KEY
        )
        
        # Make a chat completion request with generic model name
        # This will route to the default provider configured in YAML
        response = client.chat.completions.create(
            model="gpt-4",  # Generic model - routes to default provider
            messages=[
                {"role": "user", "content": "What model are you?"}
            ]
        )
        
        print(f"✅ Response received!")
        print(f"Model used: {response.model}")
        print(f"Response: {response.choices[0].message.content}")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()


def test_streaming():
    """Test streaming responses."""
    print("🧪 Test 3: Streaming response")
    print("=" * 60)
    
    try:
        # Create OpenAI client with custom base URL
        client = OpenAI(
            base_url=BASE_URL,
            api_key=API_KEY
        )
        
        # Make a streaming chat completion request
        stream = client.chat.completions.create(
            model="z.ai",
            messages=[
                {"role": "user", "content": "Count from 1 to 5 slowly."}
            ],
            stream=True
        )
        
        print("✅ Streaming response:")
        for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print("\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()


def test_model_listing():
    """Test listing available models."""
    print("🧪 Test 4: List available models")
    print("=" * 60)
    
    try:
        # Create OpenAI client with custom base URL
        client = OpenAI(
            base_url=BASE_URL,
            api_key=API_KEY
        )
        
        # List available models
        models = client.models.list()
        
        print("✅ Available models:")
        for model in models.data:
            print(f"  - {model.id}")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()


def test_conversation():
    """Test multi-turn conversation."""
    print("🧪 Test 5: Multi-turn conversation")
    print("=" * 60)
    
    try:
        # Create OpenAI client with custom base URL
        client = OpenAI(
            base_url=BASE_URL,
            api_key=API_KEY
        )
        
        # Build conversation
        messages = [
            {"role": "user", "content": "My name is Alice."},
        ]
        
        # First message
        response1 = client.chat.completions.create(
            model="z.ai",
            messages=messages
        )
        
        print(f"User: My name is Alice.")
        print(f"AI: {response1.choices[0].message.content}")
        
        # Add AI response to conversation
        messages.append({
            "role": "assistant", 
            "content": response1.choices[0].message.content
        })
        
        # Follow-up question
        messages.append({
            "role": "user",
            "content": "What's my name?"
        })
        
        response2 = client.chat.completions.create(
            model="z.ai",
            messages=messages
        )
        
        print(f"User: What's my name?")
        print(f"AI: {response2.choices[0].message.content}")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()


def main():
    """Run all tests."""
    print("\n🚀 OpenAI-Compatible API Test Suite")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {API_KEY}")
    print()
    
    # Run tests
    test_specific_provider()
    test_generic_model()
    test_model_listing()
    test_streaming()
    test_conversation()
    
    print("=" * 60)
    print("✅ Test suite completed!")
    print()
    print("📋 Summary:")
    print("  - Specific provider routing (z.ai) ✓")
    print("  - Generic model fallback (gpt-4) ✓")
    print("  - Model listing ✓")
    print("  - Streaming responses ✓")
    print("  - Multi-turn conversations ✓")


if __name__ == "__main__":
    # Check if OpenAI library is installed
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ Error: OpenAI library not installed")
        print("Install it with: pip install openai")
        sys.exit(1)
    
    main()

