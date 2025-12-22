# 🚀 Chat Proxy Usage Guide

This guide shows how to test and use the chat proxy system with the 5 target services.

## 📋 Prerequisites

1. **Stagehand API Key** - Get from [Stagehand](https://stagehand.dev)
2. **Browserbase Project ID** - Get from [Browserbase](https://browserbase.com)
3. **Service Credentials** - The provided login credentials for each service

## 🔧 Setup

1. **Install Dependencies**
```bash
cd autogpt_platform/backend
pip install fastapi uvicorn httpx stagehand
```

2. **Set Environment Variables**
```bash
export STAGEHAND_API_KEY="your-stagehand-api-key"
export BROWSERBASE_PROJECT_ID="your-browserbase-project-id"
```

3. **Configure Service Credentials**
You need to configure your own credentials for each service. Copy the `.env.chat_proxy.default` file to `.env.chat_proxy` and update with your credentials:

- **K2Think.AI**: Set `K2THINK_EMAIL` and `K2THINK_PASSWORD` in your environment
- **Qwen.AI**: Set `QWEN_EMAIL` and `QWEN_PASSWORD` in your environment  
- **DeepSeek**: Set `DEEPSEEK_EMAIL` and `DEEPSEEK_PASSWORD` in your environment
- **Grok**: Set `GROK_EMAIL` and `GROK_PASSWORD` in your environment
- **Z.AI**: Set `ZAI_EMAIL` and `ZAI_PASSWORD` in your environment

**Security Note**: Never commit real credentials to version control. Use environment variables or secure credential management systems.

## 🧪 Testing Process

### Step 1: Test Individual Services
```bash
# Test all 5 services directly
./scripts/test_real_services.py
```

This will:
- Test login to each service
- Send a test message
- Verify we get responses
- Check service health

### Step 2: Start the Server
```bash
# Start the chat proxy server
./scripts/start_chat_proxy_server.py
```

The server will be available at `http://localhost:8000` with endpoints:
- `POST /v1/chat/completions` - OpenAI-compatible chat
- `GET /v1/models` - List available models
- `GET /v1/health` - Health check
- `GET /v1/stats` - Service statistics

### Step 3: Test OpenAI API Compatibility
```bash
# Test all services via OpenAI API (in another terminal)
./scripts/test_openai_api.py
```

This will test each service through the OpenAI-compatible API.

## 🎯 Usage Examples

### Using curl
```bash
# Test K2Think.AI
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "k2think-chat",
    "messages": [{"role": "user", "content": "Hello from K2Think!"}],
    "max_tokens": 50
  }'

# Test Qwen.AI
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-max",
    "messages": [{"role": "user", "content": "Hello from Qwen!"}],
    "max_tokens": 50
  }'

# Test DeepSeek
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello from DeepSeek!"}],
    "max_tokens": 50
  }'

# Test Grok
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-beta",
    "messages": [{"role": "user", "content": "Hello from Grok!"}],
    "max_tokens": 50
  }'

# Test Z.AI (via gpt-3.5-turbo mapping)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello from Z.AI!"}],
    "max_tokens": 50
  }'
```

### Using Python OpenAI Client
```python
import openai

# Configure client to use our proxy
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy-key"  # Not used but required by client
)

# Test each service
services = [
    ("k2think-chat", "K2Think.AI"),
    ("qwen-max", "Qwen.AI"),
    ("deepseek-chat", "DeepSeek"),
    ("grok-beta", "Grok"),
    ("gpt-3.5-turbo", "Z.AI")
]

for model, service_name in services:
    print(f"Testing {service_name}...")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": f"Hello from {service_name}!"}
        ],
        max_tokens=50
    )
    
    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens: {response.usage.total_tokens}")
    print()
```

## 📊 Model Mappings

| OpenAI Model | Service | URL |
|-------------|---------|-----|
| `k2think-chat` | K2Think.AI | https://www.k2think.ai |
| `qwen-max` | Qwen.AI | https://chat.qwen.ai |
| `deepseek-chat` | DeepSeek | https://chat.deepseek.com |
| `grok-beta` | Grok | https://grok.com |
| `gpt-3.5-turbo` | Z.AI | https://chat.z.ai |

## 🔍 Monitoring

### Health Check
```bash
curl http://localhost:8000/v1/health
```

### Service Statistics
```bash
curl http://localhost:8000/v1/stats
```

### Available Models
```bash
curl http://localhost:8000/v1/models
```

## ✅ Success Criteria

The system is working correctly when:

1. **All 5 services login successfully**
2. **All 5 services respond to test messages**
3. **OpenAI API returns proper responses for all models**
4. **Health checks pass for all services**
5. **No errors in server logs**

## 🐛 Troubleshooting

### Common Issues

1. **Login Failures**
   - Check credentials are correct
   - Verify service websites are accessible
   - Check if accounts are locked/suspended

2. **Browser Automation Issues**
   - Verify Stagehand API key is valid
   - Check Browserbase project ID is correct
   - Ensure services haven't changed their UI

3. **Server Errors**
   - Check all dependencies are installed
   - Verify environment variables are set
   - Look at server logs for specific errors

### Debug Mode
Add debug logging to see what's happening:
```bash
export LOG_LEVEL=DEBUG
./scripts/start_chat_proxy_server.py
```

## 🎉 Next Steps

Once all 5 services are confirmed working:
1. ✅ **Proceed with dynamic service discovery implementation**
2. 🔄 **Add automatic pattern detection**
3. 💾 **Implement persistent pattern storage**
4. 🌐 **Create service discovery API endpoints**

The goal is to confirm we can get responses from all 5 services before building the dynamic system!
