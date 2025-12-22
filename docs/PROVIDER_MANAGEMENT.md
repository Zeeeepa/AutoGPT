# 🎛️ Provider Management System

A comprehensive webchat-to-API proxy system with intelligent scaling, browser instance management, and real-time monitoring.

## 🌟 Overview

The Provider Management System transforms webchat interfaces into OpenAI-compatible API endpoints through browser automation. It features smart scaling, load balancing, and a modern React dashboard for real-time monitoring and control.

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI API Proxy                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Smart Scaling Engine                   │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │          Browser Instance Manager          │    │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐      │    │    │
│  │  │  │Instance1│ │Instance2│ │Instance3│      │    │    │
│  │  │  │(Always) │ │(On-Demand)│(On-Demand)│    │    │    │
│  │  │  └─────────┘ └─────────┘ └─────────┘      │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 🧠 Smart Scaling Logic

- **Instance 1**: Always running with 5 providers
- **Instance 2**: Starts when all 5 providers in Instance 1 are busy
- **Instance 3**: Starts when all 10 providers (Instances 1+2) are busy
- **Auto-shutdown**: Instances 2 and 3 shut down after 30 minutes of inactivity

### 🖥️ Browser Instances

Each instance has a unique fingerprint to avoid detection:

| Instance | Platform | Viewport | Timezone | User Agent |
|----------|----------|----------|----------|------------|
| 1 | Windows | 1920x1080 | America/New_York | Chrome/Windows |
| 2 | macOS | 1440x900 | America/Los_Angeles | Chrome/macOS |
| 3 | Linux | 1366x768 | Europe/London | Chrome/Linux |

## 🚀 Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt
npm install  # For frontend

# Set environment variables
export STAGEHAND_API_KEY="your-stagehand-key"
export BROWSERBASE_PROJECT_ID="your-browserbase-project"
```

### 2. Start the Server

```bash
# Start the backend
uvicorn backend.server.main:app --host 0.0.0.0 --port 8000

# Start the frontend (in another terminal)
npm run dev
```

### 3. Access the Dashboard

- **API Endpoint**: `http://localhost:8000/api/v1/chat/completions`
- **Management Dashboard**: `http://localhost:3000/provider-management`
- **API Documentation**: `http://localhost:8000/docs`

## 📡 API Endpoints

### OpenAI-Compatible Chat API

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "k2think-chat",
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### Provider Management API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/provider-management/providers` | GET | List all providers |
| `/api/provider-management/providers/{service}/enable` | POST | Enable a provider |
| `/api/provider-management/providers/{service}/disable` | POST | Disable a provider |
| `/api/provider-management/instances` | GET | List browser instances |
| `/api/provider-management/instances/{id}/start` | POST | Start an instance |
| `/api/provider-management/instances/{id}/stop` | POST | Stop an instance |
| `/api/provider-management/scaling/status` | GET | Get scaling status |
| `/api/provider-management/ws` | WebSocket | Real-time updates |

## 🎯 Supported Services

| Service | Model Name | Status |
|---------|------------|--------|
| K2Think | `k2think-chat` | ✅ Active |
| Qwen | `qwen-chat` | ✅ Active |
| DeepSeek | `deepseek-coder` | ✅ Active |
| Grok | `grok-beta`, `grok-2` | ✅ Active |
| Z.AI | `zai-chat` | ✅ Active |

## 🖥️ Dashboard Features

### Provider Management
- **Real-time Status**: Live provider availability and health
- **Toggle Control**: Enable/disable providers individually
- **Request Metrics**: Track requests, errors, and response times
- **Instance Assignment**: See which browser instance handles each provider

### Browser Instance Control
- **Start/Stop**: Control instances 2 and 3 (Instance 1 always runs)
- **Health Monitoring**: Real-time health checks and uptime tracking
- **Fingerprint Details**: View browser fingerprint configurations
- **Session Management**: Monitor active provider sessions

### Smart Scaling Visualization
- **Capacity Utilization**: Visual progress bars for system load
- **Scaling Events**: Track when instances start/stop
- **Configuration**: View and modify scaling rules
- **Real-time Metrics**: Live updates via WebSocket

## 🧪 Testing

### Run the Test Suite

```bash
# Make sure the server is running
python scripts/test_provider_management.py
```

### Test Coverage

- ✅ System health and status
- ✅ Provider enable/disable operations
- ✅ Browser instance management
- ✅ Scaling engine functionality
- ✅ WebSocket real-time updates
- ✅ OpenAI API compatibility

### Expected Output

```
🚀 Starting Provider Management System Tests
============================================================
✅ PASS System Status: System healthy: True
✅ PASS List Providers: Found 5 providers
✅ PASS List Instances: Found 3 instances
✅ PASS Instance 1 Health: Healthy: True
✅ PASS Scaling Status: Active instances: 1, Active providers: 5
✅ PASS Scaling Rules: All scaling rules configured correctly
✅ PASS Provider Enable/Disable: Successfully toggled k2think
✅ PASS Instance Start/Stop: Successfully controlled Instance 2
✅ PASS WebSocket Connection: Real-time connection working
✅ PASS OpenAI API Integration: Chat completion successful
============================================================
📊 Test Results Summary
✅ Passed: 10/10
🎉 All tests passed! Provider Management System is working correctly.
```

## 🔧 Configuration

### Environment Variables

```bash
# Required
STAGEHAND_API_KEY=your-stagehand-api-key
BROWSERBASE_PROJECT_ID=your-browserbase-project-id

# Optional
PROVIDER_IDLE_TIMEOUT_MINUTES=30
PROVIDER_MAX_INSTANCES=3
PROVIDER_SCALING_COOLDOWN_SECONDS=60
```

### Scaling Rules

```python
# Default configuration
SCALING_CONFIG = {
    "idle_timeout_minutes": 30,
    "max_instances": 3,
    "providers_per_instance": 5,
    "scaling_cooldown_seconds": 60,
    "auto_scale_enabled": True
}
```

### Provider Accounts

Configure provider accounts in `openai_proxy.py`:

```python
DEFAULT_ACCOUNTS = {
    ChatServiceType.K2THINK: [
        ChatAccount(
            id="k2think_1",
            service_type=ChatServiceType.K2THINK,
            email="your-email@example.com",
            password="your-password",
            browserbase_session_id="k2think_session_1"
        )
    ],
    # ... more providers
}
```

## 🚨 Troubleshooting

### Common Issues

1. **Stagehand API Key Missing**
   ```
   Error: No Stagehand API key provided
   Solution: Set STAGEHAND_API_KEY environment variable
   ```

2. **Browser Instance Not Starting**
   ```
   Error: Failed to start browser instance
   Solution: Check Browserbase project ID and API limits
   ```

3. **Provider Login Failed**
   ```
   Error: Authentication failed for provider
   Solution: Verify account credentials and check for CAPTCHA
   ```

4. **WebSocket Connection Failed**
   ```
   Error: WebSocket connection refused
   Solution: Ensure server is running and firewall allows connections
   ```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Monitor system health:

```bash
# Check system status
curl http://localhost:8000/api/provider-management/status

# Check specific instance health
curl http://localhost:8000/api/provider-management/instances/1/health
```

## 🔒 Security Considerations

### Account Security
- Use dedicated accounts for automation
- Enable 2FA where possible
- Rotate passwords regularly
- Monitor for unusual activity

### API Security
- Implement rate limiting
- Use HTTPS in production
- Validate all inputs
- Monitor for abuse

### Browser Security
- Unique fingerprints per instance
- Regular session cleanup
- Proxy rotation (optional)
- User-agent rotation

## 📈 Performance Optimization

### Scaling Optimization
- Adjust `idle_timeout_minutes` based on usage patterns
- Tune `scaling_cooldown_seconds` to prevent thrashing
- Monitor provider response times

### Browser Optimization
- Use persistent sessions when possible
- Implement connection pooling
- Cache authentication tokens
- Optimize viewport sizes

### API Optimization
- Implement request caching
- Use connection pooling
- Optimize JSON serialization
- Monitor memory usage

## 🛠️ Development

### Adding New Providers

1. **Add Service Type**
   ```python
   class ChatServiceType(str, Enum):
       NEW_SERVICE = "new_service"
   ```

2. **Add Model Mapping**
   ```python
   MODEL_SERVICE_MAPPING = {
       "new-service-model": ChatServiceType.NEW_SERVICE,
   }
   ```

3. **Add Account Configuration**
   ```python
   DEFAULT_ACCOUNTS = {
       ChatServiceType.NEW_SERVICE: [
           ChatAccount(...)
       ]
   }
   ```

4. **Update Frontend**
   ```typescript
   // Add to expected services in test
   const expected_services = ["k2think", "qwen", "deepseek", "grok", "zai", "new_service"];
   ```

### Extending the Dashboard

1. **Add New Components**
   ```typescript
   // Create new component
   export const NewFeature: React.FC = () => {
       // Component implementation
   };
   ```

2. **Add API Endpoints**
   ```python
   @router.get("/new-feature")
   async def get_new_feature():
       return {"data": "new feature data"}
   ```

3. **Update WebSocket Messages**
   ```python
   # Add new message type
   await websocket.send_json({
       "type": "new_feature_update",
       "data": new_feature_data
   })
   ```

## 📊 Monitoring and Metrics

### Key Metrics
- **Request Rate**: Requests per second across all providers
- **Response Time**: Average response time per provider
- **Error Rate**: Percentage of failed requests
- **Instance Utilization**: Active providers per instance
- **Scaling Events**: Frequency of instance start/stop events

### Monitoring Tools
- **Built-in Dashboard**: Real-time metrics and status
- **WebSocket Updates**: Live monitoring data
- **Health Check Endpoints**: Automated monitoring integration
- **Log Analysis**: Structured logging for debugging

### Alerting
- Set up alerts for high error rates
- Monitor instance health status
- Track scaling event frequency
- Alert on authentication failures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Code Style
- Follow PEP 8 for Python code
- Use TypeScript for frontend code
- Add type hints and documentation
- Write comprehensive tests

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

## 🙏 Acknowledgments

- **Stagehand**: Browser automation framework
- **Browserbase**: Cloud browser infrastructure
- **FastAPI**: Modern Python web framework
- **React**: Frontend user interface library
- **WebSocket**: Real-time communication protocol

---

**Ready to transform webchat interfaces into powerful API endpoints!** 🚀
