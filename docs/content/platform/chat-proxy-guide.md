# AutoGPT Chat Proxy Guide

The AutoGPT Chat Proxy is a powerful system that provides an OpenAI-compatible API interface for multiple chat services using dynamic browser automation. Instead of hardcoded selectors that break when websites change, it uses AI-powered element detection via Stagehand to interact with web interfaces.

## 🌟 Key Features

- **OpenAI-Compatible API**: Drop-in replacement for OpenAI API clients
- **Multi-Service Support**: Z.AI, Qwen.AI, DeepSeek, K2Think, and Grok
- **AI-Powered Automation**: Dynamic element detection that adapts to UI changes
- **Load Balancing**: Multiple strategies for distributing requests across accounts
- **Session Management**: Persistent browser sessions via Browserbase
- **Health Monitoring**: Automatic account health tracking and failover
- **Streaming Support**: Real-time response streaming

## 🏗️ Architecture

```
OpenAI Client → AutoGPT API → Load Balancer → Account Pool → Stagehand → Browser → Chat Service
```

### Components

1. **OpenAI Proxy Router** (`/api/v1/chat/completions`)
   - Receives OpenAI-compatible requests
   - Maps models to chat services
   - Handles streaming and non-streaming responses

2. **Load Balancer** (`backend/util/load_balancer.py`)
   - Selects healthy accounts using various strategies
   - Tracks usage and health metrics
   - Implements failover logic

3. **Chat Proxy Blocks** (`backend/blocks/chat_proxy/`)
   - Login automation with AI element detection
   - Message sending and response extraction
   - Health checking and session management

4. **Data Models** (`backend/data/chat_proxy_models.py`)
   - Account management and configuration
   - Request/response handling
   - Health and usage tracking

## 🚀 Quick Start

### 1. Setup

Run the setup script from the AutoGPT root directory:

```bash
./scripts/setup-chat-proxy.sh
```

This will:
- Create configuration files
- Install dependencies (Stagehand)
- Set up database models
- Provide next steps

### 2. Configuration

Edit `autogpt_platform/backend/.env.chat_proxy` with your credentials:

```env
# Stagehand/Browserbase Configuration
STAGEHAND_API_KEY=your-stagehand-api-key
BROWSERBASE_PROJECT_ID=your-browserbase-project-id

# Chat Service Accounts
ZAI_EMAIL=your-zai-email
ZAI_PASSWORD=your-zai-password
QWEN_EMAIL=your-qwen-email
QWEN_PASSWORD=your-qwen-password
# ... etc for other services
```

### 3. Start the Server

```bash
cd autogpt_platform/backend
poetry run serve
```

### 4. Test the API

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 📡 API Endpoints

### Chat Completions

**POST** `/api/v1/chat/completions`

OpenAI-compatible chat completions endpoint.

**Request:**
```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-3.5-turbo",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! I'm doing well, thank you for asking."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 15,
    "total_tokens": 27
  }
}
```

### List Models

**GET** `/api/v1/models`

Returns available models and their associated services.

### Health Check

**GET** `/api/v1/health`

Returns system health status and available services.

### Statistics

**GET** `/api/v1/stats`

Returns proxy usage statistics and account health metrics.

## 🎯 Model Mapping

The proxy maps OpenAI model names to chat services:

| Model | Service | Description |
|-------|---------|-------------|
| `gpt-3.5-turbo` | Z.AI | General purpose chat |
| `gpt-4` | Z.AI | Advanced reasoning |
| `gpt-4-turbo` | Z.AI | Fast advanced model |
| `claude-3-sonnet` | Z.AI | Anthropic Claude via Z.AI |
| `qwen-max` | Qwen.AI | Qwen's most capable model |
| `qwen-plus` | Qwen.AI | Balanced performance |
| `deepseek-chat` | DeepSeek | General conversation |
| `deepseek-coder` | DeepSeek | Code-focused model |
| `k2-think` | K2Think | Reasoning-focused |
| `grok-beta` | Grok | Grok's beta model |
| `grok-2` | Grok | Grok's production model |

## ⚖️ Load Balancing

The system supports multiple load balancing strategies:

### Round Robin
Cycles through accounts in order. Simple and fair distribution.

### Least Used
Selects the account with the lowest usage count. Good for even distribution.

### Health Based
Selects accounts based on health scores (error rates, response times). Optimal for reliability.

### Weighted
Uses account weights for selection. Allows prioritizing certain accounts.

## 🔧 Configuration Options

### Service Configuration

Each chat service can be configured with:

```python
ChatServiceConfig(
    service_type=ChatServiceType.ZAI,
    base_url="https://chat.z.ai",
    login_url="https://chat.z.ai/login",
    chat_url="https://chat.z.ai",
    login_instructions={
        "email_field": "Find the email input field...",
        "password_field": "Find the password input field...",
        "login_button": "Find the login button...",
        "success_indicator": "Look for successful login indicators..."
    },
    chat_instructions={
        "message_input": "Find the message input area...",
        "send_button": "Find the send button...",
        "response_area": "Find where responses appear...",
        "loading_indicator": "Look for loading indicators..."
    },
    max_requests_per_hour=100,
    max_requests_per_day=1000,
    load_balancing_strategy=LoadBalancingStrategy.ROUND_ROBIN
)
```

### Account Management

Accounts are stored with health monitoring:

```python
ChatAccount(
    service_type=ChatServiceType.ZAI,
    email="user@example.com",
    password=SecretStr("password"),
    browserbase_session_id="session_123",
    status=AccountStatus.ACTIVE,
    weight=1.0,
    priority=0
)
```

## 🔍 AI-Powered Element Detection

Unlike traditional automation that uses hardcoded CSS selectors, this system uses AI to find elements:

### Traditional Approach (Brittle)
```python
# Breaks when website changes
email_field = page.find_element("input[name='email']")
```

### AI-Powered Approach (Adaptive)
```python
# Adapts to UI changes automatically
await page.act("Find the email input field and type 'user@example.com'")
```

### Instructions Format

The system uses natural language instructions that the AI interprets:

```python
login_instructions = {
    "email_field": "Find the email or username input field, usually labeled 'Email' or 'Username'",
    "password_field": "Find the password input field, usually labeled 'Password'",
    "login_button": "Find the login or sign in button to submit the form",
    "success_indicator": "Look for successful login indicators like chat interface or user profile"
}
```

## 📊 Monitoring and Health

### Health Metrics

The system tracks:
- **Success Rate**: Percentage of successful requests
- **Response Time**: Average response time per account
- **Error Count**: Consecutive errors before marking unhealthy
- **Usage Count**: Total requests per account
- **Last Success**: Timestamp of last successful request

### Health States

- **ACTIVE**: Account is healthy and available
- **INACTIVE**: Account is temporarily disabled
- **RATE_LIMITED**: Account hit rate limits
- **ERROR**: Account has too many consecutive errors
- **MAINTENANCE**: Account is under maintenance

### Automatic Recovery

The system automatically:
- Retries failed requests with different accounts
- Marks accounts as healthy after successful requests
- Rotates accounts to prevent overuse
- Logs in accounts when sessions expire

## 🛠️ Development

### Adding New Services

1. **Add Service Type**
```python
class ChatServiceType(str, Enum):
    NEW_SERVICE = "newservice.com"
```

2. **Create Service Configuration**
```python
DEFAULT_SERVICE_CONFIGS[ChatServiceType.NEW_SERVICE] = ChatServiceConfig(
    service_type=ChatServiceType.NEW_SERVICE,
    base_url="https://newservice.com",
    login_url="https://newservice.com/login",
    chat_url="https://newservice.com/chat",
    login_instructions={...},
    chat_instructions={...}
)
```

3. **Add Model Mapping**
```python
MODEL_SERVICE_MAPPING["new-model"] = ChatServiceType.NEW_SERVICE
```

4. **Add Account Configuration**
```python
DEFAULT_ACCOUNTS[ChatServiceType.NEW_SERVICE] = [
    ChatAccount(...)
]
```

### Testing

Test individual components:

```python
# Test login
login_block = ChatProxyLoginBlock()
result = await login_block.run(login_input)

# Test message sending
send_block = ChatProxySendMessageBlock()
result = await send_block.run(send_input)

# Test health check
health_block = ChatProxyHealthCheckBlock()
result = await health_block.run(health_input)
```

## 🔒 Security Considerations

### Credential Management
- Store passwords as `SecretStr` to prevent logging
- Use environment variables for sensitive configuration
- Rotate credentials regularly

### Session Security
- Use Browserbase for isolated browser sessions
- Implement session timeouts
- Monitor for suspicious activity

### Rate Limiting
- Respect service rate limits
- Implement backoff strategies
- Monitor usage patterns

## 🚨 Troubleshooting

### Common Issues

**Login Failures**
- Check credentials are correct
- Verify service URLs are accessible
- Check if AI instructions need updating

**Element Detection Failures**
- Update AI instructions for UI changes
- Check if service requires different interaction patterns
- Verify Stagehand model is working

**Rate Limiting**
- Add more accounts for the service
- Implement longer delays between requests
- Check service-specific rate limits

**Session Expiration**
- Verify Browserbase configuration
- Check session timeout settings
- Monitor session health

### Debugging

Enable debug logging:

```env
CHAT_PROXY_LOG_LEVEL=DEBUG
ENABLE_REQUEST_LOGGING=true
```

Check health endpoints:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/stats
```

## 📈 Performance Optimization

### Scaling Strategies

1. **Horizontal Scaling**
   - Add more accounts per service
   - Distribute across multiple Browserbase projects
   - Use multiple AutoGPT instances

2. **Vertical Scaling**
   - Increase concurrent session limits
   - Optimize response timeouts
   - Use faster AI models for element detection

3. **Caching**
   - Cache successful login sessions
   - Store element detection results
   - Cache service configurations

### Best Practices

- Monitor account health regularly
- Rotate accounts to prevent overuse
- Use appropriate timeouts for different services
- Implement circuit breakers for failing services
- Log performance metrics for optimization

## 🤝 Contributing

To contribute to the Chat Proxy system:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit a pull request

### Code Style

- Follow existing patterns in the codebase
- Use type hints for all functions
- Add docstrings for public methods
- Include error handling and logging

## 📄 License

This project is licensed under the same terms as AutoGPT.

---

For more information or support, please refer to the AutoGPT documentation or open an issue on GitHub.
