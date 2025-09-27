"""
Configuration for Chat Proxy providers.
"""

from backend.sdk.provider import ProviderBuilder

# Chat Proxy provider for managing multiple chat service accounts
chat_proxy = (
    ProviderBuilder("chat_proxy")
    .with_description("Multi-service chat proxy with load balancing")
    .with_api_key("CHAT_PROXY_API_KEY", "Chat Proxy API Key")
    .build()
)
