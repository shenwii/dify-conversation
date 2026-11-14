# Dify Conversation for Home Assistant

[English](README.md) | [简体中文](README.zh-Hans.md) | 日本語

**Dify**（**チャットボット / Agent / Chatflow** の `/v1/chat-messages` API）を Home Assistant Assist に連携するためのカスタム Conversation インテグレーションです。

## 主な機能

- **ストリーミング（SSE）＆ ブロッキング対応**: デフォルトで Dify の SSE ストリーミングを使用します（TTS の応答速度向上および長時間処理時のタイムアウト回避）。設定からブロッキングモードへの切り替えも可能です。
- **会話 ID マッピングと自動リカバリ**: Home Assistant の `conversation_id` と Dify の `conversation_id` の対応関係を LRU + TTL キャッシュで管理します。Dify 側で会話が削除・期限切れ（404）になった場合は、古いマッピングを破棄して新規会話として自動再試行します。
- **連続会話（Continue Conversation）**: 応答テキスト末尾の空白や改行を除去（`rstrip`）したうえで、末尾が `?` または `？` の場合に `continue_conversation = True` を返します。対応する音声サテライトではウェイクワードなしで続けて発話できます。
- **カスタム `inputs` JSON ＆ テンプレート変数**: 複数行テキスト入力欄と保存時の厳密な JSON 構文チェック（不正な JSON やオブジェクト以外は保存不可）を搭載。HA のユーザー情報やデバイス情報などをテンプレート変数として渡せます。
- **音声出力向けテキスト整形（任意）**: 推論モデルの `<think>...</think>` ブロックや Markdown 記法を除去し、TTS 読み上げを自然にします。
- **セルフホスト対応**: API ベース URL、タイムアウト秒数、SSL 証明書検証のオン／オフを設定可能です。
- **多言語 UI 対応**: 英語・簡体字中国語・日本語の設定画面翻訳を同梱しています。

> [!NOTE]
> 本インテグレーションは Dify の `/v1/chat-messages`（チャットボット、Agent、Chatflow）専用です。ステートレスな **Workflow**（`/v1/workflows/run`）および **テキスト生成**（`/v1/completion-messages`）アプリには対応していません。

## インストール

### 方法 1: HACS を使用（推奨）

1. Home Assistant で **HACS** を開きます。
2. 右上メニュー -> **カスタムリポジトリ（Custom repositories）** を選択します。
3. このリポジトリ URL を追加し、カテゴリに **インテグレーション（Integration）** を指定します。
4. **Dify Conversation** を検索してダウンロードします。
5. Home Assistant を再起動します。

### 方法 2: 手動インストール

1. `custom_components/dify_conversation` フォルダを Home Assistant の `<config>/custom_components/` にコピーします。
2. Home Assistant を再起動します。

## 設定手順

1. **設定 -> デバイスとサービス -> インテグレーションを追加** を開きます。
2. **Dify Conversation** を検索して選択します。
3. 各項目を入力します：
   - **名前（任意）**: Home Assistant 上の表示名。空欄にすると Dify アプリ名が自動設定されます。
   - **API ベース URL**: Dify API のベース URL（デフォルト: `https://api.dify.ai/v1`。セルフホスト環境の場合は `https://your-dify.example.com/v1` などを指定）。
   - **API キー**: Dify アプリの API キー。
   - **SSL 証明書を検証する**: 自己署名証明書を使うローカル／セルフホスト環境ではオフにできます。
   - **リクエストタイムアウト**: タイムアウト秒数（5〜600 秒、デフォルト `60`）。
   - **応答モード**: `streaming`（SSE ストリーミング・推奨）または `blocking`。
   - **音声出力向けに `<think>` タグと Markdown を除去する**: TTS 読み上げ向けに思考タグや Markdown を自動除去します。
   - **カスタム Dify inputs（JSON）**: Dify の `inputs` フィールドに渡す JSON オブジェクト。構文エラーまたは JSON オブジェクト以外の場合は保存できません。

4. **設定 -> 音声アシスタント（Assist）** で、使用するパイプラインの会話エージェントに **Dify Conversation** を割り当てます。

## カスタム `inputs` とテンプレート変数

設定例：

```json
{
  "user_id": "$user_id",
  "user_name": "$user_name",
  "device_id": "$device_id",
  "area": "$area_name"
}
```

`$var` および `${var}` の両方の記法に対応しています。まず JSON としてパースした後に文字列値へテンプレート置換を行うため、ユーザー発話やデバイス名に引用符や改行が含まれていても JSON 構文が壊れません。

### 利用可能なテンプレート変数一覧

| 変数名 | 内容 | 補足 |
|---|---|---|
| `$user_id` | Home Assistant ログインユーザー名 | `homeassistant` 認証プロバイダのユーザー名（**UUID ではありません**）。音声サテライト等から起動され取得できない場合は空文字 `""` になります。 |
| `$user_name` | Home Assistant ユーザー表示名 | `user.name`。取得できない場合は `""`。 |
| `$ha_user_uuid` | Home Assistant 内部ユーザー UUID | `context.user_id`。取得できない場合は `""`。 |
| `$device_id` | 実行元デバイス ID | `ConversationInput.device_id`。無い場合は `""`。 |
| `$device_name` | 実行元デバイス名 | Device Registry の名前（ユーザー設定名優先）。 |
| `$area_id` | デバイス所属エリア ID | Device Registry 経由で取得、無い場合は `""`。 |
| `$area_name` | デバイス所属エリア名 | Area Registry 経由で取得（例: `"リビング"`）、無い場合は `""`。 |
| `$satellite_id` | 音声サテライトエンティティ ID | `ConversationInput.satellite_id`。無い場合は `""`。 |
| `$language` | 会話の言語コード | 例: `ja`、`en`、`zh-CN`。 |
| `$conversation_id` | Home Assistant 会話 ID | 現在の HA `ChatLog` のセッション ID。 |
| `$query` | ユーザー入力テキスト | 今回のユーザー発話内容。 |

### `query` と `inputs` に関する重要な注意点

- **`query` の強制上書き**: リクエストボディ最上位の `query` には常にユーザー入力が設定されます。また、カスタム `inputs` JSON 内に `"query"` キーが含まれていた場合も、現在のユーザー入力で強制的に上書きされます。
- **Dify 側の `inputs` キャッシュ仕様**: Dify の `/v1/chat-messages` API では、初回メッセージ送信時の `inputs` が会話セッションに保存され、同一 `conversation_id` の 2 ターン目以降は初回値が維持されます。
- **Dify の `user` パラメータ**: API 仕様上必須のトップレベル `user` フィールドには、`$user_id` -> `$ha_user_uuid` -> `$device_id` -> `$satellite_id` -> `"homeassistant"` の優先順で最初に見つかった非空の値が自動設定されます。

## 連続会話のプロンプト設定

応答末尾の空白・改行を除去した後の最終文字が `?` または `？` である場合に `continue_conversation = True` が有効になります。

Dify のシステムプロンプトに以下のような指示を追加することを推奨します：

```text
ユーザーに追加の質問や確認を行いたい場合は、必ず返答の最後を疑問符（？ または ?）で終えてください。返答を待つ必要がない場合は、疑問符で終えないでください。
```
