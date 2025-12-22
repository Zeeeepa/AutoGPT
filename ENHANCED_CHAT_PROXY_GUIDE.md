# Enhanced Chat Proxy System - Complete Guide

This guide covers the enhanced chat proxy system with YAML configuration, session management, auto-scaling, and unified OpenAI-compatible API.

## 🚀 Quick Start

### 1. Configuration Setup

Create a `providers.yaml` file in your project root:

```yaml
providers:
  - name: "Z.AI"
    url: "https://chat.z.ai"
    username: "your-email@example.com"
    password: "your-password"
    models: ["z.ai", "gpt-3.5-turbo", "gpt-4"]
    is_default: true
    
  - name: "Claude"
    url: "https://claude.ai"
    username: "your-email@example.com"
    password: "your-password"
    models: ["claude-3-sonnet", "claude-3-opus"]
    
  - name: "Qwen"
    url: "https://qwen.ai"
    username: "your-email@example.com"
    password: "your-password"
    models: ["qwen-turbo", "qwen-plus"]
```

### 2. Environment Variables

Set up your environment variables:

```bash
# Required for Stagehand browser automation
STAGEHAND_API_KEY=your-stagehand-api-key

# Optional: FlareProx auto-scaling (for IP rotation)
CLOUDFLARE_API_TOKEN=your-cloudflare-token
CLOUDFLARE_ACCOUNT_ID=your-account-id
CLOUDFLARE_ZONE_ID=your-zone-id

# Optional: Custom paths
YAML_CONFIG_PATH=providers.yaml
SESSION_STORAGE_PATH=data/sessions
```

### 3. Start the Server

```bash
cd autogpt_platform/backend
python -m uvicorn backend.server.rest_api:app --host 0.0.0.0 --port 8000
```

## 📡 API Usage

### OpenAI-Compatible Endpoint

The system provides a unified `/v1/chat/completions` endpoint that routes to different providers based on the model name:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="anything"  # Not used but required by OpenAI client
)

# Routes to Z.AI provider
response = client.chat.completions.create(
    model="z.ai",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Routes to Claude provider
response = client.chat.completions.create(
    model="claude-3-sonnet",
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)

# Routes to default provider (Z.AI in this example)
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a poem"}]
)
```

### Model Routing Logic

The system uses intelligent model routing with the following priority:

1. **YAML Provider Exact Match**: `model="z.ai"` → Z.AI provider
2. **YAML Provider Name Match**: `model="claude"` → Claude provider  
3. **YAML Default Provider**: `model="gpt-4"` → Default provider (Z.AI)
4. **Dynamic Provider Match**: Fallback to dynamic providers
5. **Legacy Provider Match**: Final fallback to legacy system

### Available Models

Get all available models:

```bash
curl http://localhost:8000/v1/models
```

Response includes models from:
- YAML configuration providers
- Dynamic providers (if any)
- Legacy providers (backward compatibility)

## 🔧 System Components

### 1. YAML Configuration System

**Features:**
- Hot-reloading configuration changes
- Secure credential encryption
- Provider validation
- Model mapping
- Default provider selection

**Configuration Options:**
```yaml
providers:
  - name: "Provider Name"           # Display name
    url: "https://provider.com"     # Base URL
    username: "email@example.com"   # Login username/email
    password: "secure-password"     # Login password
    models: ["model1", "model2"]    # Supported model names
    is_default: false               # Set as default provider
    timeout: 30                     # Request timeout (seconds)
    max_retries: 3                  # Maximum retry attempts
```

### 2. Session Management

**Features:**
- Persistent authentication sessions
- Encrypted session storage
- Automatic session restoration
- Session validation and cleanup
- Cookie and storage state management

**Benefits:**
- Avoid repeated authentication
- Faster response times
- Reduced provider load
- Automatic session recovery

### 3. FlareProx Auto-Scaling

**Features:**
- Request volume monitoring
- Automatic worker scaling
- Load balancing across workers
- Health monitoring and cleanup
- Configurable scaling thresholds

**Configuration:**
```bash
# Enable auto-scaling with Cloudflare credentials
CLOUDFLARE_API_TOKEN=your-token
CLOUDFLARE_ACCOUNT_ID=your-account-id
CLOUDFLARE_ZONE_ID=your-zone-id  # Optional
```

**Scaling Metrics:**
- Scale up: >100 requests/minute or >5s average response time
- Scale down: <20 requests/minute and idle >10 minutes
- Min workers: 1, Max workers: 50

## 🔍 Monitoring and Management

### Health Check

```bash
curl http://localhost:8000/v1/health
```

### System Statistics

```bash
curl http://localhost:8000/v1/stats
```

### Session Management

List active sessions:
```bash
curl http://localhost:8000/api/sessions
```

### Auto-Scaling Status

```bash
curl http://localhost:8000/api/scaling/status
```

## 🛠️ Advanced Configuration

### Custom Provider Selectors

For providers requiring custom login selectors, extend the YAML configuration:

```yaml
providers:
  - name: "Custom Provider"
    url: "https://custom.ai"
    username: "user@example.com"
    password: "password"
    models: ["custom-model"]
    selectors:
      email: "#email-input"
      password: "#password-input"
      submit: ".login-button"
      chat_input: ".message-input"
      send_button: ".send-btn"
      response: ".response-text"
```

### Session Configuration

Customize session behavior:

```python
# In your environment or config
SESSION_TIMEOUT_HOURS=24          # Session expiry time
SESSION_VALIDATION_INTERVAL=30    # Validation frequency (minutes)
MAX_VALIDATION_FAILURES=3         # Max failures before marking invalid
```

### Auto-Scaling Tuning

Adjust scaling parameters:

```python
# Environment variables for fine-tuning
SCALE_UP_THRESHOLD_RPM=100        # Requests/minute to scale up
SCALE_DOWN_THRESHOLD_RPM=20       # Requests/minute to scale down
SCALE_UP_RESPONSE_TIME=5.0        # Response time threshold (seconds)
SCALE_DOWN_IDLE_MINUTES=10        # Idle time before scale down
MIN_WORKERS=1                     # Minimum workers
MAX_WORKERS=50                    # Maximum workers
```

## 🔐 Security Features

### Credential Encryption

- YAML passwords are encrypted at rest
- Session data is encrypted with Fernet
- Automatic key generation and management
- Secure key storage in `config/` directory

### Session Security

- Encrypted session storage
- Automatic session expiry
- Validation failure tracking
- Secure cookie handling

### Request Security

- Stagehand API key validation
- Request rate limiting (via auto-scaling)
- Error handling and logging
- Input validation and sanitization

## 🚨 Troubleshooting

### Common Issues

1. **Authentication Failures**
   ```bash
   # Check session status
   curl http://localhost:8000/api/sessions
   
   # Clear invalid sessions
   curl -X DELETE http://localhost:8000/api/sessions/invalid
   ```

2. **Provider Not Found**
   ```bash
   # Verify YAML configuration
   curl http://localhost:8000/api/config/providers
   
   # Reload configuration
   curl -X POST http://localhost:8000/api/config/reload
   ```

3. **Scaling Issues**
   ```bash
   # Check scaling status
   curl http://localhost:8000/api/scaling/status
   
   # View scaling metrics
   curl http://localhost:8000/api/scaling/metrics
   ```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m uvicorn backend.server.rest_api:app --log-level debug
```

### Health Checks

Monitor system health:

```bash
# Overall health
curl http://localhost:8000/v1/health

# Component-specific health
curl http://localhost:8000/api/health/yaml-config
curl http://localhost:8000/api/health/sessions
curl http://localhost:8000/api/health/scaling
```

## 📊 Performance Optimization

### Best Practices

1. **Session Management**
   - Keep sessions active with periodic requests
   - Monitor session validation failures
   - Clean up expired sessions regularly

2. **Auto-Scaling**
   - Monitor request patterns
   - Adjust scaling thresholds based on usage
   - Use FlareProx for IP rotation if needed

3. **Provider Configuration**
   - Set appropriate timeouts
   - Configure retry limits
   - Use default providers for common models

4. **Monitoring**
   - Track response times
   - Monitor error rates
   - Watch scaling metrics

### Performance Metrics

Key metrics to monitor:
- Average response time: <3 seconds
- Session hit rate: >80%
- Scaling efficiency: <2 minute scale-up
- Error rate: <5%

## 🔄 Migration Guide

### From Legacy System

1. **Export Existing Configuration**
   ```bash
   # Backup current settings
   cp .env .env.backup
   ```

2. **Create YAML Configuration**
   ```yaml
   # Convert environment variables to YAML
   providers:
     - name: "Z.AI"
       url: "https://chat.z.ai"
       username: "${ZAI_EMAIL}"
       password: "${ZAI_PASSWORD}"
       models: ["z.ai", "gpt-4"]
       is_default: true
   ```

3. **Test Migration**
   ```bash
   # Test with new system
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "z.ai", "messages": [{"role": "user", "content": "test"}]}'
   ```

4. **Update Client Code**
   ```python
   # No changes needed for OpenAI client usage
   # Model routing is handled automatically
   ```

## 📚 API Reference

### Core Endpoints

- `POST /v1/chat/completions` - OpenAI-compatible chat completions
- `GET /v1/models` - List available models
- `GET /v1/health` - System health check

### Management Endpoints

- `GET /api/config/providers` - List YAML providers
- `POST /api/config/reload` - Reload YAML configuration
- `GET /api/sessions` - List active sessions
- `DELETE /api/sessions/{provider_id}` - Remove session
- `GET /api/scaling/status` - Auto-scaling status
- `GET /api/scaling/metrics` - Scaling metrics

### WebSocket Support

Real-time updates for monitoring:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/metrics');
ws.onmessage = (event) => {
    const metrics = JSON.parse(event.data);
    console.log('Real-time metrics:', metrics);
};
```

## 🎯 Use Cases

### 1. Multi-Provider Chat Application

```python
import openai

client = openai.OpenAI(base_url="http://localhost:8000/v1", api_key="any")

# Route different tasks to different providers
creative_response = client.chat.completions.create(
    model="claude-3-opus",  # Best for creative tasks
    messages=[{"role": "user", "content": "Write a creative story"}]
)

technical_response = client.chat.completions.create(
    model="z.ai",  # Good for technical tasks
    messages=[{"role": "user", "content": "Explain REST APIs"}]
)
```

### 2. Load Balancing Across Providers

```yaml
# Configure multiple providers for the same models
providers:
  - name: "Primary Z.AI"
    url: "https://chat.z.ai"
    username: "user1@example.com"
    password: "pass1"
    models: ["gpt-4"]
    
  - name: "Backup Z.AI"
    url: "https://chat.z.ai"
    username: "user2@example.com"
    password: "pass2"
    models: ["gpt-4"]
```

### 3. Development vs Production

```yaml
# Development configuration
providers:
  - name: "Dev Z.AI"
    url: "https://chat.z.ai"
    username: "dev@example.com"
    password: "dev-password"
    models: ["gpt-4"]
    is_default: true

# Production configuration (separate file)
providers:
  - name: "Prod Z.AI Primary"
    url: "https://chat.z.ai"
    username: "prod1@example.com"
    password: "prod-password-1"
    models: ["gpt-4"]
    is_default: true
    
  - name: "Prod Z.AI Backup"
    url: "https://chat.z.ai"
    username: "prod2@example.com"
    password: "prod-password-2"
    models: ["gpt-4"]
```

## 🤝 Contributing

### Development Setup

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd autogpt_platform/backend
   pip install -r requirements.txt
   ```

2. **Run Tests**
   ```bash
   pytest tests/
   ```

3. **Code Style**
   ```bash
   black backend/
   isort backend/
   flake8 backend/
   ```

### Adding New Features

1. **New Provider Support**
   - Extend YAML schema
   - Add provider-specific selectors
   - Update routing logic

2. **New Scaling Strategies**
   - Implement in `flareprox_autoscaler.py`
   - Add configuration options
   - Update metrics collection

3. **New Session Features**
   - Extend `SessionData` model
   - Update encryption/decryption
   - Add validation logic

This enhanced chat proxy system provides a robust, scalable, and secure foundation for multi-provider AI chat applications with enterprise-grade features like session persistence, auto-scaling, and comprehensive monitoring.
