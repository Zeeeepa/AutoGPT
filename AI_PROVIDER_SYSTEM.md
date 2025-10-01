# AI-Powered Dynamic Chat Provider System

This document describes the new AI-powered dynamic chat provider system that allows users to add chat providers with minimal configuration using AI-powered element detection and browser automation.

## Overview

The AI Provider System enables users to add any chat service provider with just three pieces of information:
- **Domain**: The domain of the chat service (e.g., "chat.mistral.ai")
- **Username**: Email or username for authentication
- **Password**: Password for authentication

The system automatically:
1. **Discovers** the interface using AI-powered element detection
2. **Authenticates** using browser automation
3. **Tests** chat functionality end-to-end
4. **Makes available** through a unified API

## Key Features

### 🤖 AI-Powered Element Detection
- Uses Stagehand AI to detect login forms, chat inputs, and response areas
- Adapts to UI changes automatically
- No hardcoded selectors required
- Fallback heuristic detection when AI is unavailable

### 🔐 Automatic Authentication
- AI-powered login automation
- Session persistence and management
- Authentication verification
- Automatic re-authentication when needed

### 💬 Universal Chat Interface
- Unified API for all providers
- Automatic response extraction
- Error handling and retry logic
- Real-time chat functionality

### 📊 Comprehensive Testing
- Domain accessibility testing
- Element detection validation
- Authentication testing
- End-to-end chat functionality testing

### 🔄 Adaptive UI Handling
- Automatically adapts to interface changes
- Re-detects elements when selectors fail
- Learns from successful interactions
- Maintains compatibility over time

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Provider Engine                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Element Detector│  │  Authenticator  │  │ Chat Provider│ │
│  │   (Stagehand)   │  │   (AI-powered)  │  │ (AI-powered) │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │    Validator    │  │ Config Manager  │  │Event Handler │ │
│  │  (Comprehensive)│  │  (Persistent)   │  │ (Lifecycle)  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Simple Provider API                      │
│  POST /api/providers/add     - Add provider                │
│  GET  /api/providers/list    - List providers              │
│  POST /api/providers/chat    - Chat with any provider      │
│  GET  /api/providers/health  - System health               │
└─────────────────────────────────────────────────────────────┘
```

### Interface Definitions

The system is built around clean interfaces defined in `provider_interfaces.py`:

- **AIElementDetector**: AI-powered element detection
- **ProviderAuthenticator**: Authentication automation
- **ChatProvider**: Chat interaction handling
- **ProviderValidator**: Comprehensive testing
- **ProviderManager**: Provider lifecycle management

## Usage

### Adding a Provider

```bash
curl -X POST "http://localhost:8000/api/providers/add" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "chat.mistral.ai",
    "username": "your-email@example.com",
    "password": "your-password"
  }'
```

Response:
```json
{
  "success": true,
  "provider_id": "mistral_ai_12345",
  "domain": "chat.mistral.ai",
  "status": "active",
  "message": "Successfully added provider for chat.mistral.ai",
  "discovery_results": {
    "login_elements": {
      "login_email": {
        "selector": "input[type=\"email\"]",
        "confidence": 0.9,
        "method": "stagehand_ai"
      }
    },
    "success": true
  },
  "endpoints": {
    "chat": "/api/providers/mistral_ai_12345/chat",
    "status": "/api/providers/mistral_ai_12345/status",
    "test": "/api/providers/mistral_ai_12345/test"
  }
}
```

### Chatting with a Provider

```bash
curl -X POST "http://localhost:8000/api/providers/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how are you today?"
  }'
```

Response:
```json
{
  "success": true,
  "content": "Hello! I'm doing well, thank you for asking. How can I help you today?",
  "provider_id": "mistral_ai_12345",
  "response_time": 2.3
}
```

### Listing Providers

```bash
curl "http://localhost:8000/api/providers/list"
```

Response:
```json
[
  {
    "provider_id": "mistral_ai_12345",
    "domain": "chat.mistral.ai",
    "display_name": "Mistral AI",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "tags": []
  }
]
```

## Configuration

### Environment Variables

```bash
# Stagehand API Key (for AI-powered element detection)
STAGEHAND_API_KEY=your_stagehand_api_key

# Optional: Cloudflare credentials for scaling (Phase 2)
CLOUDFLARE_API_TOKEN=your_cloudflare_token
CLOUDFLARE_ACCOUNT_ID=your_account_id
```

### AI Provider Engine Configuration

```python
config = AIProviderEngineConfig(
    stagehand_api_key=None,  # Loaded from environment
    ai_detection_timeout=30,
    ai_confidence_threshold=0.7,
    browser_timeout=60,
    browser_headless=True,
    max_concurrent_sessions=10,
    session_timeout=300,
    auto_scale_enabled=True,
    enable_monitoring=True,
    metrics_collection_interval=60,
    health_check_interval=300
)
```

## Implementation Details

### AI Element Detection

The system uses Stagehand's AI capabilities to detect UI elements:

```python
# Example: Detecting login elements
login_elements = await element_detector.detect_elements(
    "https://chat.mistral.ai/login",
    [ElementType.LOGIN_EMAIL, ElementType.LOGIN_PASSWORD, ElementType.LOGIN_SUBMIT],
    context={"domain": "chat.mistral.ai", "purpose": "login"}
)
```

The AI creates natural language prompts like:
> "Find the email or username input field on chat.mistral.ai. This is typically labeled 'Email', 'Username', 'Login', or similar. Look for input fields that accept email addresses or usernames for authentication."

### Authentication Flow

1. **Element Detection**: Find login form elements
2. **Credential Input**: Fill username and password fields
3. **Form Submission**: Click login button or press Enter
4. **Verification**: Check for successful authentication
5. **Session Storage**: Save cookies and session data

### Chat Interaction

1. **Interface Detection**: Find chat input and send button
2. **Message Sending**: Type message and submit
3. **Response Waiting**: Wait for AI response to appear
4. **Content Extraction**: Extract response text using AI
5. **Response Formatting**: Return structured response

### Validation and Testing

The system performs comprehensive testing:

1. **Domain Accessibility**: Verify the domain is reachable
2. **Element Detection**: Test AI element detection
3. **Authentication**: Verify login functionality
4. **Chat Functionality**: Test end-to-end chat flow

## Error Handling

### Common Error Scenarios

1. **Domain Not Accessible**: Network or DNS issues
2. **Element Detection Failed**: UI changes or complex interfaces
3. **Authentication Failed**: Invalid credentials or CAPTCHA
4. **Chat Interface Not Ready**: Authentication required or interface changes

### Adaptive Recovery

- **UI Changes**: Re-detect elements using AI
- **Authentication Issues**: Retry with fresh session
- **Network Errors**: Exponential backoff retry
- **Rate Limiting**: Respect service limits

## Monitoring and Health Checks

### Health Check Endpoints

```bash
# System health
GET /api/providers/health

# Provider-specific health
GET /api/providers/{provider_id}/test
```

### Metrics Collection

- Provider success rates
- Response times
- Error frequencies
- Element detection confidence
- Authentication success rates

## Future Enhancements (Phase 2)

### Cloudflare Scaling Integration

The system includes FlareProx integration for unlimited scaling:

```python
# FlareProx usage example
python3 flareprox.py config  # Setup Cloudflare credentials
python3 flareprox.py create --count 5  # Create 5 proxy endpoints
python3 flareprox.py test  # Test all endpoints
```

### Advanced Features

- **Load Balancing**: Distribute requests across multiple instances
- **IP Rotation**: Use different IP addresses for each request
- **Rate Limit Bypass**: Automatic scaling when limits are hit
- **Geographic Distribution**: Route through different regions

## Security Considerations

### Credential Storage

- Passwords are stored securely (should be encrypted in production)
- Session data is isolated per provider
- Authentication tokens are managed automatically

### Network Security

- All requests go through secure HTTPS
- Browser automation uses secure contexts
- Session isolation prevents cross-contamination

### Privacy

- No user data is logged or stored unnecessarily
- Chat content is not persisted
- Provider credentials are only used for authentication

## Troubleshooting

### Common Issues

1. **"No Stagehand API key provided"**
   - Set `STAGEHAND_API_KEY` environment variable
   - System will fall back to heuristic detection

2. **"Element detection failed"**
   - Check if the website is accessible
   - Verify the domain is correct
   - Try again as UI might have been loading

3. **"Authentication failed"**
   - Verify credentials are correct
   - Check if CAPTCHA is required
   - Ensure the login URL is accessible

4. **"Chat interface not ready"**
   - Authentication might be required first
   - Check if the chat URL is correct
   - Verify the provider supports the interface

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("backend.core").setLevel(logging.DEBUG)
logging.getLogger("backend.util.stagehand_integration").setLevel(logging.DEBUG)
```

## Contributing

### Adding New Features

1. **Extend Interfaces**: Add new methods to interface definitions
2. **Implement Components**: Create concrete implementations
3. **Add Tests**: Comprehensive testing for new functionality
4. **Update Documentation**: Keep documentation current

### Testing

```bash
# Run provider validation tests
python -m pytest tests/test_provider_validator.py

# Test AI element detection
python -m pytest tests/test_stagehand_integration.py

# Test end-to-end provider addition
python -m pytest tests/test_ai_provider_engine.py
```

## License

This AI Provider System is part of the AutoGPT project and follows the same licensing terms.

---

**Note**: This system represents a significant advancement in making AI chat services accessible through a unified interface. The AI-powered approach eliminates the need for manual configuration and makes the system adaptive to changes in provider interfaces.
