# Dify Conversation for Home Assistant

[English](README.md) | 简体中文 | [日本語](README.ja.md)

一个用于将 **Dify**（支持 **聊天助手 / Agent / Chatflow** 应用的 `/v1/chat-messages` 接口）接入 Home Assistant Assist 的自定义会话集成。

## 核心功能

- **支持流式（SSE）与阻塞模式**：默认采用 Dify 流式输出（首字响应快、有利于 TTS 语音合成，并可避免长耗时 Agent/Chatflow 触发网关超时），也可在配置中切换为阻塞模式。
- **会话 ID 映射与容错恢复**：自动维护 Home Assistant `conversation_id` 与 Dify `conversation_id` 的映射关系（基于带容量上限的 LRU + TTL 缓存）。若 Dify 侧会话过期或被删除（404），插件会自动清除失效映射并重开新会话。
- **连续对话支持**：自动去除回复末尾空白换行后，若最后一个字符为 `?` 或 `？`，则向 Home Assistant 发起连续对话（`continue_conversation = True`），语音卫星无需再次唤醒即可继续聆听用户回答。
- **自定义 Dify `inputs`（JSON + 模板变量）**：提供多行 JSON 配置框并在保存时校验 JSON 语法及对象格式（语法错误或非 JSON 对象禁止保存），支持注入 HA 用户、设备、区域等模板变量。
- **语音播报清理（可选）**：支持在输出前自动剥离推理模型的 `<think>...</think>` 思考过程和 Markdown 符号，让语音播报更自然。
- **自托管友好**：支持自定义 API 基础 URL、请求超时时间与 SSL 证书校验开关。
- **多语言界面**：内置简体中文（`zh-Hans`）、英文（`en`）和日文（`ja`）配置界面翻译。

> [!NOTE]
> 本插件仅对接 Dify 的 `/v1/chat-messages` 接口（聊天助手、Agent、Chatflow）。不支持无状态的 **Workflow**（`/v1/workflows/run`）与 **文本生成**（`/v1/completion-messages`）应用。

## 安装方法

### 方式一：通过 HACS 安装（推荐）

1. 打开 Home Assistant 中的 **HACS**。
2. 点击右上角菜单 -> **自定义存储库（Custom repositories）**。
3. 添加本仓库地址，类别选择 **集成（Integration）**。
4. 搜索 **Dify Conversation** 并下载。
5. 重启 Home Assistant。

### 方式二：手动安装

1. 将 `custom_components/dify_conversation` 目录复制到 Home Assistant 配置目录下的 `<config>/custom_components/` 中。
2. 重启 Home Assistant。

## 配置说明

1. 进入 **设置 -> 设备与服务 -> 添加集成**。
2. 搜索并选择 **Dify Conversation**。
3. 填写配置项：
   - **名称（可选）**：集成名称，留空将自动使用 Dify 应用名称。
   - **API 基础 URL**：Dify API 地址（默认 `https://api.dify.ai/v1`；自托管环境请填写如 `https://your-dify.example.com/v1`）。
   - **API Key**：对应 Dify 应用的 API 密钥。
   - **验证 SSL 证书**：自托管使用自签名证书时可关闭。
   - **请求超时时间**：单次请求超时秒数（5–600 秒，默认 `60`）。
   - **响应模式**：`streaming`（流式 SSE，推荐）或 `blocking`（阻塞等待）。
   - **清理 `<think>` 标签与 Markdown**：开启后会在输出前去除思考标签和 Markdown 语法，改善语音播报效果。
   - **自定义 Dify inputs（JSON）**：传递给 Dify `inputs` 的 JSON 对象。保存时会校验 JSON 语法与对象结构，不合法将无法保存。

4. 进入 **设置 -> 语音助手（Assist）**，将对应语音流水线的对话代理切换为你添加的 **Dify Conversation** 实体。

## 自定义 `inputs` 与模板变量说明

配置示例：

```json
{
  "user_id": "$user_id",
  "user_name": "$user_name",
  "device_id": "$device_id",
  "area": "$area_name"
}
```

支持 `$var` 与 `${var}` 两种写法。插件会先解析 JSON 再对字符串值进行安全的模板替换，因此用户输入或设备名称中包含双引号、换行符等特殊字符也不会破坏 JSON 结构。

### 支持的模板变量列表

| 变量名 | 含义 | 说明 |
|---|---|---|
| `$user_id` | Home Assistant 登录用户名 | 从 `homeassistant` 认证凭据中读取的登录用户名（**不是 UUID**）。语音卫星或无用户上下文时为空字符串 `""`。 |
| `$user_name` | Home Assistant 用户显示名 | 对应 `user.name`。无用户上下文时为空字符串 `""`。 |
| `$ha_user_uuid` | Home Assistant 内部用户 UUID | 对应 `context.user_id`。无用户上下文时为空字符串 `""`。 |
| `$device_id` | 触发对话的设备 ID | 来自 `ConversationInput.device_id`，无则 `""`。 |
| `$device_name` | 触发对话的设备名称 | 从 Device Registry 读取（优先用户自定义名称），无则 `""`。 |
| `$area_id` | 触发设备所在区域 ID | 从 Device Registry 读取，无则 `""`。 |
| `$area_name` | 触发设备所在区域名称 | 从 Area Registry 读取（如 `"客厅"`），无则 `""`。 |
| `$satellite_id` | 语音卫星实体 ID | 来自 `ConversationInput.satellite_id`，无则 `""`。 |
| `$language` | 当前会话语言代码 | 如 `zh-CN`、`en`、`ja`。 |
| `$conversation_id` | Home Assistant 会话 ID | 当前 HA `ChatLog` 的会话 ID。 |
| `$query` | 用户输入文本 | 当前用户的提问内容。 |

### 关于 `query` 与 `inputs` 的重要说明

- **`query` 强制覆盖**：Dify 请求体顶层的 `query` 固定为用户输入内容；即使你在自定义 `inputs` JSON 中配置了 `"query"` 字段，插件也会将其强行覆盖为当前用户输入。
- **Dify 的 `inputs` 首轮缓存机制**：根据 Dify `/v1/chat-messages` 接口规范，同一 `conversation_id` 在首轮会话确定 `inputs` 后，后续轮次由 Dify 沿用首轮状态。
- **Dify 顶层 `user` 字段**：Dify 协议要求每次请求必须携带 `user` 标识，插件会按以下优先级自动填充非空值：`$user_id` -> `$ha_user_uuid` -> `$device_id` -> `$satellite_id` -> `"homeassistant"`。

## 连续对话设置建议

插件会在回复文本执行 `rstrip()` 去除尾部空白换行后，检查末尾是否为 `?` 或 `？`。若匹配，则设置 `continue_conversation = True`，支持连续对话的语音卫星会在播报完回复后自动开麦等待下一句。

建议在 Dify 系统提示词（System Prompt）中加入类似约束：

```text
当你需要向用户追问、反问或请求确认时，请确保回复的最后一个字符是问号（？或 ?）。如果不需要用户继续回答，请不要以问号结尾。
```
