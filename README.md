# Dify Conversation for Home Assistant

English | [简体中文](README.zh-Hans.md) | [日本語](README.ja.md)

A custom Home Assistant Conversation integration that connects **Dify** (**Chatbot**, **Agent**, and **Chatflow** applications via `/v1/chat-messages`) to Home Assistant Assist.

## Features

- **Streaming (SSE) & Blocking Modes**: Supports Dify Server-Sent Events streaming by default (low latency for TTS and avoids proxy timeouts on long Agent/Chatflow runs), with an option to switch to blocking mode.
- **Conversation ID Mapping**: Automatically maps Home Assistant `conversation_id` to Dify `conversation_id` with bounded LRU + TTL caching and automatic stale-session recovery (retries cleanly if Dify returns 404 Conversation Not Exists).
- **Continuous Conversation**: Strips trailing whitespace and automatically triggers Home Assistant's `continue_conversation` when Dify's response ends with `?` or `？`, keeping voice satellites listening for follow-up replies without re-waking.
- **Custom Dify `inputs` JSON + Templates**: Multiline JSON editor in the UI with strict JSON syntax and object-type validation before saving. Supports dynamic Home Assistant template variables (`$user_id`, `$user_name`, `$device_id`, etc.).
- **Speech-Friendly Cleanup (Optional)**: Strips `<think>...</think>` reasoning blocks and Markdown formatting for cleaner Text-to-Speech (TTS) playback.
- **Self-Hosted Friendly**: Configurable API Base URL, request timeout, and SSL certificate verification toggle.
- **Localized UI**: Built-in English, Simplified Chinese (`zh-Hans`), and Japanese (`ja`) configuration flows.

> [!NOTE]
> This integration targets Dify's `/v1/chat-messages` endpoint (Chatbot, Agent, and Chatflow apps). Stateless Dify **Workflow** (`/v1/workflows/run`) and **Text Generator** (`/v1/completion-messages`) apps are not supported.

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Click the menu icon (top right) -> **Custom repositories**.
3. Add this repository URL and select **Integration** as the category.
4. Search for **Dify Conversation** and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/dify_conversation` folder into your Home Assistant `<config>/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **Dify Conversation**.
3. Fill in the configuration fields:
   - **Name (optional)**: Friendly name in Home Assistant. Leave blank to use the Dify app name automatically.
   - **API Base URL**: Your Dify API base URL (default: `https://api.dify.ai/v1`; for self-hosted Dify, e.g. `https://your-dify.example.com/v1`).
   - **API Key**: Your Dify application API key.
   - **Verify SSL certificate**: Disable if your self-hosted Dify instance uses a self-signed certificate.
   - **Request timeout**: HTTP timeout in seconds (5–600, default `60`).
   - **Response mode**: `streaming` (recommended) or `blocking`.
   - **Clean `<think>` tags and Markdown for speech**: Optional toggle to remove reasoning tags and Markdown syntax before speech output.
   - **Custom Dify inputs (JSON)**: A JSON object passed to Dify's `inputs` field. Invalid JSON syntax or non-object JSON values are rejected and cannot be saved.

4. Go to **Settings -> Voice assistants** and select your **Dify Conversation** entity as the conversation agent for your Assist pipeline.

## Custom `inputs` & Template Variables

Example configuration:

```json
{
  "user_id": "$user_id",
  "user_name": "$user_name",
  "device_id": "$device_id",
  "area": "$area_name"
}
```

Both `$var` and `${var}` syntax are supported. JSON is parsed first and template substitution is applied safely to string values, so special characters in user text or device names will not break JSON formatting.

### Supported Template Variables

| Variable | Description | Notes |
|---|---|---|
| `$user_id` | Home Assistant login username | Extracted from `homeassistant` auth credentials (not the UUID). Empty string `""` if unavailable (e.g. voice satellite or non-password login). |
| `$user_name` | Home Assistant user display name | `user.name`. Empty string `""` if unavailable. |
| `$ha_user_uuid` | Home Assistant internal user UUID | `context.user_id`. Empty string `""` if unavailable. |
| `$device_id` | Triggering Home Assistant device ID | From `ConversationInput.device_id`. Empty string `""` if unavailable. |
| `$device_name` | Triggering device name | User-customized name or device name from Device Registry. |
| `$area_id` | Area ID of the triggering device | From Device Registry, or `""`. |
| `$area_name` | Area name of the triggering device | From Area Registry (e.g. `"Living Room"`), or `""`. |
| `$satellite_id` | Assist satellite entity ID | From `ConversationInput.satellite_id`, or `""`. |
| `$language` | Conversation language code | e.g. `en`, `zh-CN`, `ja`. |
| `$conversation_id` | Home Assistant `conversation_id` | Current HA `ChatLog` session ID. |
| `$query` | User's input text | Current user utterance. |

### Important Notes on `query` and `inputs`

- **`query` Override**: Dify's top-level `query` payload field is always populated with the user's input text. If you also include a `"query"` key inside your **Custom Dify inputs (JSON)**, its value will be forcibly overwritten with the user's input text.
- **Dify `inputs` Caching**: In Dify's `/v1/chat-messages` API, `inputs` are recorded when a new Dify `conversation_id` starts and cached for subsequent turns in the same conversation.
- **Dify `user` Parameter**: Dify requires a top-level `user` identifier on every request. The integration automatically populates it using the first non-empty value from: `$user_id` -> `$ha_user_uuid` -> `$device_id` -> `$satellite_id` -> `"homeassistant"`.

## Continuous Conversation Setup

This integration checks whether Dify's response ends with `?` or `？` (after trimming trailing whitespace/newlines). If it does, Home Assistant sets `continue_conversation = True`, allowing supported voice satellites to keep listening for your reply without saying the wake word again.

Recommended snippet to add to your Dify system prompt:

```text
If you need to ask the user a follow-up question or request confirmation, make sure your response ends with a question mark (? or ？). If no reply is needed, do not end with a question mark.
```
