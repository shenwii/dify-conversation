<p align="center">
  <img src="custom_components/dify_conversation/brand/logo.png" alt="Dify Conversation Logo" width="360" />
</p>

<h1 align="center">Dify Conversation for Home Assistant</h1>

<p align="center">
  Connect <strong>Dify</strong> (Chatbot, Agent, and Chatflow apps) to <strong>Home Assistant Assist</strong> with streaming responses, conversation ID mapping, custom template inputs, and continuous voice conversation.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge" alt="HACS Custom" /></a>
  <a href="https://github.com/shenwii/dify-conversation/releases"><img src="https://img.shields.io/github/v/release/shenwii/dify-conversation?style=for-the-badge" alt="GitHub Release" /></a>
  <a href="https://github.com/shenwii/dify-conversation/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shenwii/dify-conversation?style=for-the-badge" alt="License" /></a>
</p>

<p align="center">
  <strong>English</strong> | <a href="README.zh-Hans.md">简体中文</a> | <a href="README.ja.md">日本語</a>
</p>

---

## Overview

**Dify Conversation** integrates Dify's `/v1/chat-messages` API directly into Home Assistant as a native `ConversationEntity`. You can add one or multiple Dify applications (for example, a smart-home control Agent and a knowledge-base Chatflow) and assign them to any Home Assistant Assist voice pipeline.

> [!NOTE]
> Only Dify **Chatbot**, **Agent**, and **Chatflow** applications (`/v1/chat-messages`) are supported. Stateless **Workflow** (`/v1/workflows/run`) and **Text Generator** (`/v1/completion-messages`) applications are not supported.

## Features

- **Streaming (SSE) & Blocking Modes**: Uses Dify Server-Sent Events (`streaming`) by default for lower TTS latency and timeout resilience on long Agent/Chatflow runs, with an option to switch to `blocking`.
- **Automatic `conversation_id` Mapping**: Maps Home Assistant `conversation_id` to Dify `conversation_id` using a bounded LRU + TTL cache, with automatic recovery if Dify returns `404 Conversation Not Exists`.
- **Continuous Conversation**: Trims trailing whitespace/newlines and sets `continue_conversation = True` whenever Dify's response ends with `?` or `？`, allowing supported voice satellites to stay open for follow-up replies without repeating the wake word.
- **Custom `inputs` JSON with Validation & Templates**: Multiline JSON editor in the Home Assistant UI that blocks saving invalid JSON syntax or non-object payloads. Supports dynamic HA context variables (`$user_id`, `$user_name`, `$device_id`, `$area_name`, etc.).
- **Speech-Friendly Output Cleanup (Optional)**: Strips `<think>...</think>` reasoning blocks and Markdown formatting for cleaner Text-to-Speech (TTS) playback.
- **Self-Hosted Ready**: Configurable API Base URL, HTTP timeout, and SSL verification toggle for self-signed certificates.
- **Multilingual UI**: Includes English, Simplified Chinese (`zh-Hans`), and Japanese (`ja`) configuration translations.

## Installation

### Option 1: HACS (Recommended)

Click the button below to add this repository directly to HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=shenwii&repository=dify-conversation&category=integration)

Or add it manually in HACS:

1. Open **HACS** in Home Assistant.
2. Click the top-right menu (`⋮`) -> **Custom repositories**.
3. Enter `https://github.com/shenwii/dify-conversation` and choose **Integration** as the category.
4. Search for **Dify Conversation**, click **Download**, and restart Home Assistant.

### Option 2: Manual Installation

1. Copy `custom_components/dify_conversation` into your Home Assistant `<config>/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

Click the button below or go to **Settings -> Devices & Services -> Add Integration** and search for **Dify Conversation**:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=dify_conversation)

| Field | Default | Description |
|---|---|---|
| **Name (optional)** | Dify app name | Friendly integration name in Home Assistant. Leave blank to fetch the app name from Dify automatically. |
| **API Base URL** | `https://api.dify.ai/v1` | Dify API base URL (e.g. `https://your-dify.example.com/v1` for self-hosted deployments). |
| **API Key** | — | Application API key from your Dify app's **API Access** page. |
| **Verify SSL certificate** | `true` | Disable when connecting to a self-hosted Dify server with a self-signed certificate. |
| **Request timeout** | `60` | Request timeout in seconds (`5`–`600`). |
| **Response mode** | `streaming` | `streaming` (SSE, recommended) or `blocking`. |
| **Clean `<think>` tags and Markdown** | `false` | Strips `<think>...</think>` reasoning blocks and Markdown symbols before speech output. |
| **Custom Dify inputs (JSON)** | `{}` | JSON object passed to Dify `inputs`. Invalid JSON syntax or non-object values cannot be saved. |

After adding the integration, open **Settings -> Voice assistants** and select **Dify Conversation** as the conversation agent for your Assist pipeline.

## Custom `inputs` & Template Variables

Example JSON configuration:

```json
{
  "user_id": "$user_id",
  "user_name": "$user_name",
  "device_id": "$device_id",
  "area": "$area_name"
}
```

Both `$var` and `${var}` placeholders are supported. JSON is parsed first and template substitution runs safely on string values, so quotes or newlines inside user messages or device names never break JSON formatting.

### Template Variables Reference

| Variable | Description | Notes |
|---|---|---|
| `$user_id` | Home Assistant login username | Read from `homeassistant` auth credentials (**not** the internal UUID). Empty string `""` when unavailable (e.g. voice satellites). |
| `$user_name` | Home Assistant user display name | `user.name`. Empty string `""` when unavailable. |
| `$ha_user_uuid` | Home Assistant internal user UUID | `context.user_id`. Empty string `""` when unavailable. |
| `$device_id` | Triggering device ID | `ConversationInput.device_id`, or `""`. |
| `$device_name` | Triggering device name | User-defined name or device name from Device Registry, or `""`. |
| `$area_id` | Area ID of the triggering device | From Device Registry, or `""`. |
| `$area_name` | Area name of the triggering device | From Area Registry (e.g. `"Living Room"`), or `""`. |
| `$satellite_id` | Assist satellite entity ID | `ConversationInput.satellite_id`, or `""`. |
| `$language` | Conversation language code | e.g. `en`, `zh-CN`, `ja`. |
| `$conversation_id` | Home Assistant `conversation_id` | Current HA `ChatLog` session ID. |
| `$query` | User input text | Current user utterance. |

> [!IMPORTANT]
> - **`query` Override**: Dify's top-level `query` field is always set to the user's input. If you also define `"query"` inside **Custom Dify inputs (JSON)**, its value is forcibly overwritten with the user's input.
> - **Dify `inputs` Caching**: Per Dify's `/v1/chat-messages` specification, `inputs` are captured on the first turn of a `conversation_id` and reused by Dify for subsequent turns in that session.
> - **Dify `user` Parameter**: Dify requires a top-level `user` identifier on every request. It is populated automatically using the first non-empty value from: `$user_id` -> `$ha_user_uuid` -> `$device_id` -> `$satellite_id` -> `"homeassistant"`.

## Continuous Conversation Setup

The integration runs `.rstrip()` on Dify's final reply and sets `continue_conversation = True` when the last character is `?` or `？`.

Add an instruction like this to your Dify system prompt:

```text
If you need to ask the user a follow-up question or request confirmation, end your response with a question mark (? or ？). If no follow-up reply is expected, do not end with a question mark.
```

## Troubleshooting

- **Voice satellite does not keep listening**: Make sure your Assist pipeline uses a voice satellite that supports `continue_conversation` and that Dify's reply ends with `?` or `？`.
- **Self-hosted Dify fails to connect**: Verify your URL includes the `/v1` suffix (e.g. `https://dify.example.com/v1`), and disable **Verify SSL certificate** if using a self-signed certificate.
- **TTS reads `<think>` or `*` characters aloud**: Enable **Clean `<think>` tags and Markdown** in the integration options.
- **Dify `Conversation Not Exists` error**: The integration automatically clears stale session mappings and retries once as a fresh Dify conversation.
