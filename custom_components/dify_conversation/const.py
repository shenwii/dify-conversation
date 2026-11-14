"""Constants for the Dify Conversation integration."""

from __future__ import annotations

DOMAIN = "dify_conversation"

CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_TIMEOUT = "timeout"
CONF_RESPONSE_MODE = "response_mode"
CONF_CUSTOM_INPUTS = "custom_inputs"
CONF_CLEAN_RESPONSE = "clean_response"
CONF_APP_MODE = "app_mode"

RESPONSE_MODE_STREAMING = "streaming"
RESPONSE_MODE_BLOCKING = "blocking"

DEFAULT_NAME = "Dify Conversation"
DEFAULT_BASE_URL = "https://api.dify.ai/v1"
DEFAULT_VERIFY_SSL = True
DEFAULT_TIMEOUT = 60
DEFAULT_RESPONSE_MODE = RESPONSE_MODE_STREAMING
DEFAULT_CUSTOM_INPUTS = "{}"
DEFAULT_CLEAN_RESPONSE = False

CONVERSATION_CACHE_MAX_SIZE = 1000
CONVERSATION_CACHE_TTL_SECONDS = 86400

SUPPORTED_APP_MODES = frozenset({"chat", "agent-chat", "advanced-chat"})
UNSUPPORTED_APP_MODES = frozenset({"workflow", "completion"})
