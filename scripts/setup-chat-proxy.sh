#!/bin/bash

# Setup script for AutoGPT Chat Proxy
# This script helps configure the chat proxy system with multiple accounts

set -e

echo "🚀 AutoGPT Chat Proxy Setup"
echo "================================"

# Check if we're in the right directory
if [ ! -f "autogpt_platform/backend/backend/server/routers/openai_proxy.py" ]; then
    echo "❌ Error: Please run this script from the AutoGPT root directory"
    exit 1
fi

# Create environment file if it doesn't exist
ENV_FILE="autogpt_platform/backend/.env.chat_proxy"
DEFAULT_ENV_FILE="autogpt_platform/backend/.env.chat_proxy.default"

if [ ! -f "$ENV_FILE" ]; then
    echo "📝 Creating chat proxy environment file..."
    cp "$DEFAULT_ENV_FILE" "$ENV_FILE"
    echo "✅ Created $ENV_FILE"
    echo "⚠️  Please edit $ENV_FILE with your actual credentials"
else
    echo "✅ Environment file already exists: $ENV_FILE"
fi

# Check if Stagehand is installed
echo "🔍 Checking Stagehand installation..."
cd autogpt_platform/backend

if ! python -c "import stagehand" 2>/dev/null; then
    echo "📦 Installing Stagehand..."
    poetry add stagehand
    echo "✅ Stagehand installed"
else
    echo "✅ Stagehand already installed"
fi

# Install additional dependencies
echo "📦 Installing additional dependencies..."
poetry add pydantic fastapi

# Run database migrations if needed
echo "🗄️  Running database migrations..."
poetry run prisma migrate dev --name "add_chat_proxy_models"

echo ""
echo "🎉 Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Edit $ENV_FILE with your actual credentials:"
echo "   - Add your Stagehand/Browserbase API key"
echo "   - Update chat service account credentials"
echo ""
echo "2. Start the AutoGPT backend:"
echo "   cd autogpt_platform/backend"
echo "   poetry run serve"
echo ""
echo "3. Test the OpenAI-compatible API:"
echo "   curl -X POST http://localhost:8000/api/v1/chat/completions \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{"
echo "       \"model\": \"gpt-3.5-turbo\","
echo "       \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]"
echo "     }'"
echo ""
echo "4. Available endpoints:"
echo "   - POST /api/v1/chat/completions (OpenAI-compatible)"
echo "   - GET  /api/v1/models (List available models)"
echo "   - GET  /api/v1/health (Health check)"
echo "   - GET  /api/v1/stats (Proxy statistics)"
echo ""
echo "5. Supported models:"
echo "   - gpt-3.5-turbo, gpt-4 (routes to Z.AI)"
echo "   - qwen-max, qwen-plus (routes to Qwen.AI)"
echo "   - deepseek-chat (routes to DeepSeek)"
echo "   - k2-think (routes to K2Think)"
echo "   - grok-beta, grok-2 (routes to Grok)"
echo ""
echo "📚 For more information, see the documentation in:"
echo "   docs/content/platform/chat-proxy-guide.md"
