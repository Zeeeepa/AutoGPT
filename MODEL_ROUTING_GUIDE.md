# OpenAI-Compatible API Model Routing Guide

## Overview

The Enhanced Chat Proxy System provides an OpenAI-compatible API with intelligent model routing. This allows you to use the standard OpenAI Python client library while automatically routing requests to different providers based on the model name.

## Quick Start

```python
from openai import OpenAI

# Override the default base URL
client = OpenAI(
    base_url="https://your-custom-api-url.com/v1",
    api_key="anything"  # API key is not required
)

# Make a chat completion request
response = client.chat.completions.create(
    model="z.ai",  # Model name determines routing
    messages=[{"role": "user", "content": "what model are you"}]
)

print(response.choices[0].message.content)
```

## Model Routing Logic

The system uses a multi-tier routing strategy to determine which provider should handle each request:

### 1. **YAML Provider Configuration** (Highest Priority)

Providers can be configured in a YAML file (`providers.yaml`):

```yaml
providers:
  - name: "Z.AI"
    url: "https://chat.z.ai"
    username: "your-email@example.com"
    password: "your-password"
    models: ["z.ai", "gpt-3.5-turbo", "gpt-4"]
    is_default: true
    timeout: 30
    max_retries: 3
    selectors:
      email: "#email"
      password: "#password"
      submit: ".login-btn"
      chat_input: ".message-input"
      send_button: ".send-btn"
      response: ".response-text"
```

**Routing Rules:**
- If the requested model matches any model in a provider's `models` list, route to that provider
- If multiple providers support the model, use the first match
- If a provider is marked `is_default: true`, it will be used for unmatched models

### 2. **Dynamic Provider Manager** (Medium Priority)

Providers can be added at runtime through the API:

```python
import requests

# Add a provider dynamically
response = requests.post(
    "https://your-api-url.com/api/providers",
    json={
        "name": "Custom Provider",
        "base_url": "https://custom-ai.example.com",
        "supported_models": ["custom-model", "gpt-4"],
        "is_default": False,
        # ... authentication and selector configuration
    }
)
```

**Routing Rules:**
- Exact model name match in `supported_models`
- Provider name match (e.g., model "custom-provider" routes to "Custom Provider")
- Partial match in supported models
- Default provider if configured

### 3. **Legacy Model Mapping** (Lowest Priority - Backward Compatibility)

Hardcoded mappings for common models:

```python
LEGACY_MODEL_SERVICE_MAPPING = {
    "gpt-3.5-turbo": ChatServiceType.ZAI,
    "gpt-4": ChatServiceType.ZAI,
    "gpt-4-turbo": ChatServiceType.ZAI,
    "claude-3-sonnet": ChatServiceType.ZAI,
    "qwen-max": ChatServiceType.QWEN,
    "deepseek-chat": ChatServiceType.DEEPSEEK,
    "grok-2": ChatServiceType.GROK,
}
```

**Routing Rules:**
- Direct mapping from model name to service type
- Defaults to Z.AI for unknown models

## Routing Examples

### Example 1: Specific Provider Model

```python
# Route to Z.AI provider
response = client.chat.completions.create(
    model="z.ai",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Routing Path:**
1. Check YAML config for provider with "z.ai" in models list → **Found: Z.AI Provider**
2. Route request to Z.AI

### Example 2: Generic OpenAI Model

```python
# Route to default provider
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Routing Path:**
1. Check YAML config for provider with "gpt-4" in models list → **Found: Z.AI Provider (has gpt-4 in models)**
2. Route request to Z.AI
3. If not found in YAML, check dynamic providers
4. If not found, use legacy mapping → Z.AI

### Example 3: Custom Provider

```python
# Add custom provider (one-time setup)
requests.post("https://your-api-url.com/api/providers", json={
    "name": "My AI",
    "base_url": "https://my-ai.example.com",
    "supported_models": ["my-model", "custom-gpt"],
    "is_default": False,
})

# Use custom provider
response = client.chat.completions.create(
    model="my-model",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Routing Path:**
1. Check YAML config → Not found
2. Check dynamic providers for "my-model" → **Found: My AI Provider**
3. Route request to My AI

### Example 4: Fallback to Default

```python
# Unknown model falls back to default provider
response = client.chat.completions.create(
    model="unknown-model-xyz",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Routing Path:**
1. Check YAML config for exact match → Not found
2. Check dynamic providers → Not found
3. Use default provider from YAML config (if is_default: true) → **Found: Z.AI Provider**
4. Route request to Z.AI

## Configuration Best Practices

### 1. **Set a Default Provider**

Always configure at least one provider with `is_default: true`:

```yaml
providers:
  - name: "Z.AI"
    # ... other config
    is_default: true  # This provider handles unmatched models
```

### 2. **Use Descriptive Model Names**

Configure model names that match your use case:

```yaml
providers:
  - name: "Z.AI"
    models: 
      - "z.ai"              # Provider-specific name
      - "gpt-3.5-turbo"     # OpenAI compatibility
      - "gpt-4"             # OpenAI compatibility
      - "fast-model"        # Custom alias
      - "smart-model"       # Custom alias
```

### 3. **Organize by Capability**

Group models by capability:

```yaml
providers:
  - name: "Fast Provider"
    models: ["fast", "quick", "gpt-3.5-turbo"]
    is_default: false
  
  - name: "Smart Provider"
    models: ["smart", "intelligent", "gpt-4", "claude-3"]
    is_default: true
```

## API Endpoints

### Chat Completions

```http
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "z.ai",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

### List Models

```http
GET /v1/models
```

Returns all available models from configured providers.

### Add Provider (Runtime)

```http
POST /api/providers
Content-Type: application/json

{
  "name": "Custom Provider",
  "base_url": "https://custom.example.com",
  "supported_models": ["custom-1", "custom-2"],
  "is_default": false
}
```

## Advanced Features

### 1. **Streaming Responses**

```python
stream = client.chat.completions.create(
    model="z.ai",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### 2. **Multi-turn Conversations**

```python
messages = [
    {"role": "user", "content": "My name is Alice."}
]

# First message
response = client.chat.completions.create(model="z.ai", messages=messages)
messages.append({"role": "assistant", "content": response.choices[0].message.content})

# Follow-up
messages.append({"role": "user", "content": "What's my name?"})
response = client.chat.completions.create(model="z.ai", messages=messages)
```

### 3. **Temperature and Sampling**

```python
response = client.chat.completions.create(
    model="z.ai",
    messages=[{"role": "user", "content": "Be creative!"}],
    temperature=0.9,  # Higher = more creative
    top_p=0.95,
    max_tokens=500
)
```

## Error Handling

```python
from openai import OpenAI
from openai import OpenAIError

try:
    client = OpenAI(base_url="https://your-api-url.com/v1", api_key="anything")
    response = client.chat.completions.create(
        model="z.ai",
        messages=[{"role": "user", "content": "Hello!"}]
    )
except OpenAIError as e:
    print(f"API Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Monitoring and Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("openai")
logger.setLevel(logging.DEBUG)
```

### Check Model Routing

The system logs which provider is being used:

```
INFO - Routing model 'z.ai' to YAML provider 'Z.AI'
INFO - Routing model 'gpt-4' to default YAML provider 'Z.AI'
INFO - No provider found for model 'unknown', using legacy routing
```

## Testing

Use the provided test script:

```bash
python test_openai_client.py
```

This will test:
- Specific provider routing
- Generic model fallback
- Model listing
- Streaming responses
- Multi-turn conversations

## Summary

The Enhanced Chat Proxy System provides:

✅ **Drop-in OpenAI Compatibility** - Use standard OpenAI client library
✅ **Intelligent Routing** - Automatic provider selection based on model name
✅ **Default Fallback** - Graceful handling of unknown models
✅ **Runtime Configuration** - Add providers without restarting
✅ **High Performance** - Optimized for low latency and high throughput
✅ **Production Ready** - Comprehensive error handling and monitoring

For more information, see the API documentation at `/api/docs` when the server is running.

