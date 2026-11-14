<p align="center">
  <img src="custom_components/dify_conversation/brand/logo.png" alt="Dify Conversation Logo" width="360" />
</p>

<h1 align="center">Dify Conversation for Home Assistant</h1>

<p align="center">
  将 <strong>Dify</strong>（聊天助手、Agent 与 Chatflow 应用）接入 <strong>Home Assistant Assist</strong>，支持流式响应、会话 ID 映射、自定义模板变量与连续语音对话。
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge" alt="HACS Custom" /></a>
  <a href="https://github.com/shenwii/dify-conversation/releases"><img src="https://img.shields.io/github/v/release/shenwii/dify-conversation?style=for-the-badge" alt="GitHub Release" /></a>
  <a href="https://github.com/shenwii/dify-conversation/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shenwii/dify-conversation?style=for-the-badge" alt="License" /></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong> | <a href="README.ja.md">日本語</a>
</p>

---

## 简介

**Dify Conversation** 通过 Dify 的 `/v1/chat-messages` 接口将 Dify 对话能力原生接入 Home Assistant 的 `ConversationEntity`。你可以同时添加多个 Dify 应用（例如一个负责智能家居控制、一个负责家庭知识库问答），并在 Assist 语音流水线中自由切换。

> [!NOTE]
> 本插件仅支持 Dify **聊天助手（Chatbot）**、**Agent** 与 **Chatflow** 应用（`/v1/chat-messages`）。不支持无状态的 **Workflow**（`/v1/workflows/run`）与 **文本生成**（`/v1/completion-messages`）应用。

## 核心特性

- **流式（SSE）与阻塞模式**：默认启用 Dify 流式输出（首字延迟低，利于 TTS 快速播报，也可避免长耗时 Agent/Chatflow 触发网关超时），并支持切换为阻塞模式。
- **自动维护 `conversation_id` 映射**：使用带容量上限的 LRU + TTL 缓存自动关联 HA `conversation_id` 与 Dify `conversation_id`；若 Dify 侧会话过期或被删除（404），会自动清理失效映射并重开新会话。
- **连续对话（Continue Conversation）**：对回复执行 `.rstrip()` 去除尾部空白换行后，若最后一个字符为 `?` 或 `？`，则自动向 Home Assistant 返回 `continue_conversation = True`，支持连续对话的语音卫星无需再次唤醒即可继续聆听。
- **自定义 `inputs` JSON 校验与模板变量**：提供多行 JSON 输入框，保存时强制校验 JSON 语法及对象格式（不合法禁止保存），支持注入 HA 用户名、设备、区域等动态模板变量。
- **语音播报文本清理（可选）**：自动剥离推理模型的 `<think>...</think>` 思考过程和 Markdown 符号，让语音播报更自然。
- **自托管友好**：支持自定义 API 基础 URL、请求超时时间与 SSL 证书校验开关。
- **多语言界面**：内置简体中文（`zh-Hans`）、英文（`en`）与日文（`ja`）配置界面翻译。

## 安装方法

### 方式一：通过 HACS 安装（推荐）

点击下方按钮直接将本仓库添加到你的 HACS：

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=shenwii&repository=dify-conversation&category=integration)

或手动在 HACS 中添加：

1. 打开 Home Assistant 中的 **HACS**。
2. 点击右上角菜单（`⋮`）-> **自定义存储库（Custom repositories）**。
3. 填入仓库地址 `https://github.com/shenwii/dify-conversation`，类别选择 **集成（Integration）**。
4. 搜索 **Dify Conversation** 并点击 **下载**，完成后重启 Home Assistant。

### 方式二：手动安装

1. 将 `custom_components/dify_conversation` 目录复制到 Home Assistant 配置目录下的 `<config>/custom_components/` 中。
2. 重启 Home Assistant。

## 配置说明

点击下方按钮快速添加集成，或在 **设置 -> 设备与服务 -> 添加集成** 中搜索 **Dify Conversation**：

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=dify_conversation)

| 配置项 | 默认值 | 说明 |
|---|---|---|
| **名称（可选）** | Dify 应用名 | 在 Home Assistant 中的显示名称；留空将自动读取 Dify 应用名称。 |
| **API 基础 URL** | `https://api.dify.ai/v1` | Dify API 基础地址（自托管部署如 `https://your-dify.example.com/v1`）。 |
| **API Key** | — | Dify 应用「访问 API」页面生成的密钥。 |
| **验证 SSL 证书** | `true` | 自托管使用自签名证书时可关闭。 |
| **请求超时时间** | `60` | 单次请求超时秒数（`5`–`600`）。 |
| **响应模式** | `streaming` | `streaming`（SSE 流式，推荐）或 `blocking`（阻塞等待）。 |
| **清理 `<think>` 标签与 Markdown** | `false` | 开启后会在语音输出前自动去除思考标签与 Markdown 符号。 |
| **自定义 Dify inputs（JSON）** | `{}` | 传递给 Dify `inputs` 的 JSON 对象；语法错误或非 JSON 对象将无法保存。 |

添加完成后，前往 **设置 -> 语音助手（Assist）**，将需要使用的语音流水线对话代理切换为 **Dify Conversation** 即可。

## 自定义 `inputs` 与模板变量

配置示例：

```json
{
  "user_id": "$user_id",
  "user_name": "$user_name",
  "device_id": "$device_id",
  "area": "$area_name"
}
```

同时支持 `$var` 与 `${var}` 写法。插件会先解析 JSON 再对字符串值做安全的模板替换，因此用户提问或设备名称中的引号、换行等特殊字符不会破坏 JSON 结构。

### 支持的模板变量列表

| 变量名 | 含义 | 说明 |
|---|---|---|
| `$user_id` | Home Assistant 登录用户名 | 来自 `homeassistant` 认证凭据的登录用户名（**不是 UUID**）。语音卫星或无用户上下文时为 `""`。 |
| `$user_name` | Home Assistant 用户显示名 | 对应 `user.name`。无用户上下文时为 `""`。 |
| `$ha_user_uuid` | Home Assistant 内部用户 UUID | 对应 `context.user_id`。无用户上下文时为 `""`。 |
| `$device_id` | 触发设备 ID | 来自 `ConversationInput.device_id`，无则 `""`。 |
| `$device_name` | 触发设备名称 | 从 Device Registry 读取（优先用户自定义名称），无则 `""`。 |
| `$area_id` | 触发设备所在区域 ID | 从 Device Registry 读取，无则 `""`。 |
| `$area_name` | 触发设备所在区域名称 | 从 Area Registry 读取（如 `"客厅"`），无则 `""`。 |
| `$satellite_id` | 语音卫星实体 ID | 来自 `ConversationInput.satellite_id`，无则 `""`。 |
| `$language` | 当前会话语言代码 | 如 `zh-CN`、`en`、`ja`。 |
| `$conversation_id` | Home Assistant 会话 ID | 当前 HA `ChatLog` 的会话 ID。 |
| `$query` | 用户输入文本 | 当前用户的提问内容。 |

> [!IMPORTANT]
> - **`query` 强制覆盖**：Dify 请求体顶层的 `query` 固定为用户输入；若你在自定义 `inputs` JSON 中也写入了 `"query"` 字段，插件会强制将其覆盖为当前用户输入。
> - **Dify `inputs` 首轮缓存机制**：按 Dify `/v1/chat-messages` 协议规范，`inputs` 在新会话第一轮传入后由 Dify 服务端缓存，同一 `conversation_id` 的后续轮次沿用首轮状态。
> - **Dify 顶层 `user` 字段**：API 要求每次请求携带 `user` 标识，插件会按 `$user_id` -> `$ha_user_uuid` -> `$device_id` -> `$satellite_id` -> `"homeassistant"` 顺序自动取首个非空值。

## 连续对话设置建议

插件会在对 Dify 回复执行 `.rstrip()` 去除尾部空白换行后，检查末尾字符是否为 `?` 或 `？`，匹配时自动设置 `continue_conversation = True`。

建议在 Dify 系统提示词（System Prompt）中加入以下规则：

```text
当你需要向用户追问、反问或请求确认时，请确保回复的最后一个字符是问号（？或 ?）。如果不需要用户继续回答，请不要以问号结尾。
```

## 常见问题（FAQ）

- **语音卫星没有继续开麦**：请确认你的语音卫星设备支持 `continue_conversation`，且 Dify 返回的回复末尾为 `?` 或 `？`。
- **自托管 Dify 无法连接**：请确认 URL 末尾包含 `/v1`（如 `https://dify.example.com/v1`）；若使用内网自签名证书，请关闭 **验证 SSL 证书**。
- **TTS 读出了 `<think>` 或 `*` 符号**：请在集成「选项」中开启 **清理 `<think>` 标签与 Markdown**。
- **出现会话不存在（404）**：插件会自动清除旧会话映射并以新会话自动重试一次，无需人工干预。
