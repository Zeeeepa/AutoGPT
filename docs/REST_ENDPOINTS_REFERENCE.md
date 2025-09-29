# 📡 **REST API Endpoints Reference**

Complete reference for all REST endpoints in the Dynamic Provider Management System.

## 🎯 **Text Processing Endpoints (OpenAI Compatible)**

### **Primary Chat Completions Endpoint**
```bash
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "z.ai",  # Dynamic routing: z.ai → Z.AI provider
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "max_tokens": 150,
  "temperature": 0.7,
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "z.ai",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

### **Model Routing Examples**
```bash
# Exact match routing
POST /v1/chat/completions {"model": "z.ai"}     # → Z.AI provider
POST /v1/chat/completions {"model": "k2"}       # → K2Think provider
POST /v1/chat/completions {"model": "qwen"}     # → Qwen provider

# Default fallback routing (unknown models)
POST /v1/chat/completions {"model": "gpt-4.1"}  # → Default provider
POST /v1/chat/completions {"model": "unknown"}  # → Default provider

# Provider name matching
POST /v1/chat/completions {"model": "custom-chat"} # → Custom Chat provider
```

### **System Information Endpoints**
```bash
# Get available models
GET /v1/models

# Health check
GET /v1/health

# System statistics
GET /v1/stats
```

## 🔧 **Dynamic Provider Management Endpoints**

### **Provider CRUD Operations**

#### **Add New Provider**
```bash
POST /api/dynamic-providers/providers
Content-Type: application/json

{
  "name": "Custom Chat",
  "base_url": "https://customchat.com",
  "auth_method": "email_password",
  "email": "user@example.com",
  "password": "password123",
  "auto_authenticate": true,
  "is_default": false,
  "supported_models": ["custom-chat", "custom-gpt"],
  "description": "Custom chat provider",
  "tags": ["custom", "chat"]
}
```

#### **List All Providers**
```bash
# List all providers
GET /api/dynamic-providers/providers

# Filter by status
GET /api/dynamic-providers/providers?status=active

# Filter enabled only
GET /api/dynamic-providers/providers?enabled_only=true
```

#### **Get Specific Provider**
```bash
GET /api/dynamic-providers/providers/{provider_id}
```

#### **Update Provider**
```bash
PUT /api/dynamic-providers/providers/{provider_id}
Content-Type: application/json

{
  "name": "Updated Provider Name",
  "email": "newemail@example.com",
  "is_enabled": true,
  "supported_models": ["updated-model-1", "updated-model-2"]
}
```

#### **Delete Provider**
```bash
DELETE /api/dynamic-providers/providers/{provider_id}
```

### **Provider Operations**

#### **Authenticate Provider**
```bash
POST /api/dynamic-providers/providers/{provider_id}/authenticate
```

#### **Test Provider**
```bash
POST /api/dynamic-providers/providers/{provider_id}/test
Content-Type: application/json

{
  "test_message": "Hello, this is a test message.",
  "timeout_seconds": 30
}
```

#### **Enable/Disable Provider**
```bash
# Enable provider
POST /api/dynamic-providers/providers/{provider_id}/enable

# Disable provider
POST /api/dynamic-providers/providers/{provider_id}/disable
```

### **System Configuration**

#### **Get System Configuration**
```bash
GET /api/dynamic-providers/system/config
```

**Response:**
```json
{
  "default_provider_id": "provider-123",
  "fallback_provider_id": "provider-456",
  "total_providers": 5,
  "active_providers": 4,
  "total_model_mappings": 15,
  "auto_authenticate": true,
  "health_check_interval": 300,
  "enable_fuzzy_matching": true
}
```

#### **Set Default Provider**
```bash
PUT /api/dynamic-providers/system/default-provider/{provider_id}
```

### **Model Mapping Management**

#### **Get Model Mappings**
```bash
GET /api/dynamic-providers/models/mappings
```

**Response:**
```json
{
  "mappings": [
    {
      "model_name": "z.ai",
      "provider_id": "provider-123",
      "provider_name": "Z.AI Provider",
      "priority": 1,
      "is_exact_match": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### **Add Model Mapping**
```bash
POST /api/dynamic-providers/models/mappings
Content-Type: application/json

{
  "model_name": "custom-gpt",
  "provider_id": "provider-123",
  "priority": 1,
  "is_exact_match": true
}
```

#### **Remove Model Mapping**
```bash
DELETE /api/dynamic-providers/models/mappings?model_name=custom-gpt&provider_id=provider-123
```

## 🔄 **Legacy Provider Management Endpoints**

### **Provider Status Management**
```bash
# Get all providers
GET /api/providers

# Enable service type
POST /api/providers/{service_type}/enable

# Disable service type  
POST /api/providers/{service_type}/disable
```

### **Instance Management**
```bash
# Get all instances
GET /api/instances

# Start instance
POST /api/instances/{instance_id}/start

# Stop instance
POST /api/instances/{instance_id}/stop

# Get instance health
GET /api/instances/{instance_id}/health
```

### **Scaling Management**
```bash
# Get scaling status
GET /api/scaling/status

# Get scaling rules
GET /api/scaling/rules

# Update scaling rules
POST /api/scaling/rules

# Get overall status
GET /api/status
```

## 📊 **Analytics and Monitoring Endpoints**

### **Analytics**
```bash
# Log raw metric
POST /api/analytics/log_raw_metric

# Log raw analytics
POST /api/analytics/log_raw_analytics
```

### **Integration Endpoints**
```bash
# Get credentials
GET /api/integrations/credentials

# Get provider credentials
GET /api/integrations/{provider}/credentials

# Create credentials
POST /api/integrations/{provider}/credentials

# Delete credentials
DELETE /api/integrations/{provider}/credentials/{cred_id}

# Webhook ingress
POST /api/integrations/{provider}/webhooks/{webhook_id}/ingress
```

## 🎯 **Usage Examples**

### **Complete Workflow Example**

#### **1. Add a New Provider**
```bash
curl -X POST http://localhost:8000/api/dynamic-providers/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ChatGPT Web",
    "base_url": "https://chat.openai.com",
    "auth_method": "email_password",
    "email": "your-email@example.com",
    "password": "your-password",
    "supported_models": ["chatgpt", "gpt-web", "openai-web"],
    "auto_authenticate": true
  }'
```

#### **2. Test the Provider**
```bash
curl -X POST http://localhost:8000/api/dynamic-providers/providers/{provider_id}/test \
  -H "Content-Type: application/json" \
  -d '{
    "test_message": "Hello, this is a test",
    "timeout_seconds": 30
  }'
```

#### **3. Set as Default Provider**
```bash
curl -X PUT http://localhost:8000/api/dynamic-providers/system/default-provider/{provider_id}
```

#### **4. Use the Provider via Chat Completions**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chatgpt",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }'
```

### **Load Testing Example**
```bash
# Run multiple concurrent requests to test load balancing
for i in {1..100}; do
  curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"z.ai\", \"messages\": [{\"role\": \"user\", \"content\": \"Test $i\"}]}" &
done
wait
```

## 🔍 **Response Headers**

The system includes helpful response headers for debugging and monitoring:

```
X-Provider-ID: provider-123          # Which provider handled the request
X-Provider-Name: Z.AI Provider       # Provider display name
X-Model-Routing: exact_match         # How the model was routed
X-Response-Time: 1.234               # Response time in seconds
X-Load-Balancer: round_robin         # Load balancing strategy used
X-Circuit-Breaker: closed            # Circuit breaker status
```

## 🚨 **Error Responses**

### **Common Error Codes**
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (authentication required)
- `404` - Not Found (provider/resource not found)
- `429` - Too Many Requests (rate limiting)
- `503` - Service Unavailable (provider down/circuit breaker open)

### **Error Response Format**
```json
{
  "error": {
    "code": "provider_not_found",
    "message": "Provider with ID 'provider-123' not found",
    "details": {
      "provider_id": "provider-123",
      "available_providers": ["provider-456", "provider-789"]
    }
  }
}
```

## 🔐 **Authentication**

Most endpoints require authentication. Include the authorization header:

```bash
Authorization: Bearer your-api-key
```

Or use API key in query parameter:
```bash
?api_key=your-api-key
```

---

**This reference covers all available REST endpoints for the Dynamic Provider Management System. The system provides both OpenAI-compatible chat completions and comprehensive provider management capabilities.**
