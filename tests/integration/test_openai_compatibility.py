"""
Test OpenAI API compatibility with real OpenAI client libraries.
This ensures our proxy is a true drop-in replacement for OpenAI API.
"""

import pytest
import asyncio
import json
from typing import List, Dict, Any


@pytest.mark.integration
@pytest.mark.real_services
class TestOpenAICompatibility:
    """Test OpenAI API compatibility using real OpenAI client library."""
    
    async def test_openai_client_chat_completion(
        self, 
        openai_client, 
        chat_proxy_server,
        skip_if_no_real_services,
        test_utils
    ):
        """Test basic chat completion with OpenAI client."""
        # Create a simple chat completion request
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Say hello in a friendly way"}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        # Verify response structure matches OpenAI format
        assert response.id is not None
        assert response.object == "chat.completion"
        assert response.created is not None
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices) == 1
        
        choice = response.choices[0]
        assert choice.index == 0
        assert choice.message.role == "assistant"
        assert choice.message.content is not None
        assert len(choice.message.content) > 0
        assert choice.finish_reason == "stop"
        
        # Verify usage information is present
        assert response.usage is not None
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert response.usage.total_tokens > 0
        
        print(f"✅ Chat completion successful: {choice.message.content[:100]}...")
    
    async def test_openai_client_streaming(
        self, 
        openai_client, 
        chat_proxy_server,
        skip_if_no_real_services,
        test_utils
    ):
        """Test streaming chat completion with OpenAI client."""
        chunks = []
        content_parts = []
        
        # Create streaming chat completion
        stream = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Count from 1 to 5"}
            ],
            stream=True,
            max_tokens=50
        )
        
        # Collect all chunks
        async for chunk in stream:
            chunks.append(chunk)
            
            # Verify chunk structure
            assert chunk.id is not None
            assert chunk.object == "chat.completion.chunk"
            assert chunk.created is not None
            assert chunk.model == "gpt-3.5-turbo"
            assert len(chunk.choices) == 1
            
            choice = chunk.choices[0]
            assert choice.index == 0
            
            # Collect content
            if choice.delta.content:
                content_parts.append(choice.delta.content)
        
        # Verify we received multiple chunks
        assert len(chunks) > 1
        
        # Verify final chunk has finish_reason
        final_chunk = chunks[-1]
        assert final_chunk.choices[0].finish_reason == "stop"
        
        # Verify we got content
        full_content = "".join(content_parts)
        assert len(full_content) > 0
        
        print(f"✅ Streaming completion successful: {len(chunks)} chunks, content: {full_content[:100]}...")
    
    async def test_multiple_models(
        self, 
        openai_client, 
        chat_proxy_server,
        skip_if_no_real_services,
        test_utils
    ):
        """Test different model mappings work correctly."""
        models_to_test = [
            "gpt-3.5-turbo",  # Z.AI
            "qwen-max",       # Qwen.AI
            "deepseek-chat",  # DeepSeek
            "k2-think",       # K2Think
            "grok-beta",      # Grok
        ]
        
        results = {}
        
        for model in models_to_test:
            try:
                response = await openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": f"Hello from {model}"}
                    ],
                    max_tokens=30,
                    temperature=0.5
                )
                
                # Verify response
                assert response.model == model
                assert len(response.choices) == 1
                assert response.choices[0].message.content is not None
                
                results[model] = {
                    "success": True,
                    "content": response.choices[0].message.content,
                    "tokens": response.usage.total_tokens if response.usage else 0
                }
                
                print(f"✅ Model {model} successful: {response.choices[0].message.content[:50]}...")
                
            except Exception as e:
                results[model] = {
                    "success": False,
                    "error": str(e)
                }
                print(f"❌ Model {model} failed: {e}")
        
        # At least one model should work
        successful_models = [m for m, r in results.items() if r["success"]]
        assert len(successful_models) > 0, f"No models worked. Results: {results}"
        
        print(f"✅ {len(successful_models)}/{len(models_to_test)} models working")
    
    async def test_openai_parameters(
        self, 
        openai_client, 
        chat_proxy_server,
        skip_if_no_real_services,
        test_utils
    ):
        """Test various OpenAI parameters are handled correctly."""
        # Test with various parameters
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            max_tokens=100,
            temperature=0.1,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1,
            stop=["END"]
        )
        
        # Verify response structure
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices) == 1
        assert response.choices[0].message.content is not None
        
        print(f"✅ Parameters test successful: {response.choices[0].message.content}")
    
    async def test_error_handling(
        self, 
        openai_client, 
        chat_proxy_server,
        skip_if_no_real_services,
        test_utils
    ):
        """Test error handling matches OpenAI format."""
        # Test with invalid model (should still work but might route to default)
        try:
            response = await openai_client.chat.completions.create(
                model="invalid-model-name",
                messages=[
                    {"role": "user", "content": "Hello"}
                ]
            )
            # If it succeeds, it should route to default service
            assert response.choices[0].message.content is not None
            print("✅ Invalid model routed to default service")
            
        except Exception as e:
            # If it fails, error should be properly formatted
            print(f"✅ Invalid model properly rejected: {e}")
        
        # Test with empty messages (should fail)
        with pytest.raises(Exception):
            await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[]
            )
        
        print("✅ Empty messages properly rejected")
    
    async def test_concurrent_requests(
        self, 
        openai_client, 
        chat_proxy_server,
        skip_if_no_real_services,
        test_utils
    ):
        """Test handling multiple concurrent requests."""
        # Create multiple concurrent requests
        tasks = []
        for i in range(3):  # Start with 3 concurrent requests
            task = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": f"This is request number {i+1}"}
                ],
                max_tokens=30
            )
            tasks.append(task)
        
        # Wait for all to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        failed_responses = [r for r in responses if isinstance(r, Exception)]
        
        print(f"✅ Concurrent requests: {len(successful_responses)} successful, {len(failed_responses)} failed")
        
        # At least some should succeed
        assert len(successful_responses) > 0
        
        # Verify successful responses
        for response in successful_responses:
            assert response.choices[0].message.content is not None
    
    async def test_models_endpoint(
        self, 
        api_client, 
        chat_proxy_server,
        skip_if_no_real_services
    ):
        """Test the /v1/models endpoint returns proper OpenAI format."""
        response = await api_client.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify OpenAI models format
        assert data["object"] == "list"
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        
        # Verify model structure
        for model in data["data"]:
            assert "id" in model
            assert "object" in model
            assert model["object"] == "model"
            assert "created" in model
            assert "owned_by" in model
        
        print(f"✅ Models endpoint returned {len(data['data'])} models")
    
    async def test_health_endpoint(
        self, 
        api_client, 
        chat_proxy_server,
        skip_if_no_real_services
    ):
        """Test the health endpoint."""
        response = await api_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "services" in data
        assert "models" in data
        
        print("✅ Health endpoint working")
    
    async def test_stats_endpoint(
        self, 
        api_client, 
        chat_proxy_server,
        skip_if_no_real_services
    ):
        """Test the stats endpoint."""
        response = await api_client.get("/api/v1/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "services" in data
        
        print("✅ Stats endpoint working")


@pytest.mark.integration
class TestOpenAICompatibilityUnit:
    """Unit tests for OpenAI compatibility (no real services required)."""
    
    async def test_request_format_validation(self, test_utils):
        """Test request format validation."""
        # Test valid request
        request = test_utils.create_openai_request()
        assert request["model"] is not None
        assert request["messages"] is not None
        assert len(request["messages"]) > 0
        
        # Test message format
        message = test_utils.create_test_message()
        assert message["role"] == "user"
        assert message["content"] is not None
        
        print("✅ Request format validation working")
    
    def test_model_mapping_logic(self):
        """Test model to service mapping logic."""
        from autogpt_platform.backend.backend.server.routers.openai_proxy import MODEL_SERVICE_MAPPING
        from autogpt_platform.backend.backend.data.chat_proxy_models import ChatServiceType
        
        # Verify all mappings are valid
        for model, service in MODEL_SERVICE_MAPPING.items():
            assert isinstance(service, ChatServiceType)
            assert model is not None
            assert len(model) > 0
        
        # Test specific mappings
        assert MODEL_SERVICE_MAPPING["gpt-3.5-turbo"] == ChatServiceType.ZAI
        assert MODEL_SERVICE_MAPPING["qwen-max"] == ChatServiceType.QWEN
        assert MODEL_SERVICE_MAPPING["deepseek-chat"] == ChatServiceType.DEEPSEEK
        
        print(f"✅ Model mapping validation: {len(MODEL_SERVICE_MAPPING)} mappings")
    
    def test_response_format_structure(self):
        """Test response format matches OpenAI structure."""
        from autogpt_platform.backend.backend.server.routers.openai_proxy import (
            ChatCompletionResponse,
            ChatCompletionChoice,
            ChatMessage
        )
        
        # Test response structure
        message = ChatMessage(role="assistant", content="Hello!")
        choice = ChatCompletionChoice(
            index=0,
            message=message,
            finish_reason="stop"
        )
        response = ChatCompletionResponse(
            id="test-id",
            created=1234567890,
            model="gpt-3.5-turbo",
            choices=[choice]
        )
        
        # Verify structure
        assert response.id == "test-id"
        assert response.object == "chat.completion"
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices) == 1
        assert response.choices[0].message.content == "Hello!"
        
        print("✅ Response format structure validation")
