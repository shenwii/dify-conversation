<p align="center">
  <img src="custom_components/dify_conversation/brand/logo.png" alt="Dify Conversation Logo" width="360" />
</p>

<h1 align="center">Dify Conversation for Home Assistant</h1>

<p align="center">
  <strong>Dify</strong>（チャットボット / Agent / Chatflow）を <strong>Home Assistant Assist</strong> に連携し、ストリーミング応答・会話 ID マッピング・テンプレート変数・連続音声会話に対応するカスタムインテグレーションです。
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge" alt="HACS Custom" /></a>
  <a href="https://github.com/shenwii/dify-conversation/releases"><img src="https://img.shields.io/github/v/release/shenwii/dify-conversation?style=for-the-badge" alt="GitHub Release" /></a>
  <a href="https://github.com/shenwii/dify-conversation/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shenwii/dify-conversation?style=for-the-badge" alt="License" /></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-Hans.md">简体中文</a> | <strong>日本語</strong>
</p>

---

## 概要

**Dify Conversation** は Dify の `/v1/chat-messages` API を Home Assistant のネイティブ `ConversationEntity` として統合します。複数の Dify アプリ（スマートホーム制御用 Agent とナレッジ Q&A 用 Chatflow など）を登録し、Assist パイプラインごとに割り当てることができます。

> [!NOTE]
> 対応しているのは Dify の **チャットボット（Chatbot）**、**Agent**、**Chatflow**（`/v1/chat-messages`）のみです。ステートレスな **Workflow**（`/v1/workflows/run`）および **テキスト生成**（`/v1/completion-messages`）には対応していません。

## 主な機能

- **ストリーミング（SSE）＆ ブロッキング対応**: デフォルトで SSE ストリーミングを使用し、TTS の応答開始を高速化しつつ長時間処理時のタイムアウトを防止します。ブロッキングモードへの切り替えも可能です。
- **会話 ID マッピングと自動リカバリ**: Home Assistant の `conversation_id` と Dify の `conversation_id` を LRU + TTL キャッシュで対応付けます。Dify 側で会話が削除・期限切れ（404）になった場合も、古いマッピングを自動破棄して新規会話として再試行します。
- **連続会話（Continue Conversation）**: 応答末尾の空白や改行を `rstrip()` で除去したうえで、末尾文字が `?` または `？` の場合に `continue_conversation = True` を返します。対応する音声サテライトではウェイクワードなしで続けて話しかけられます。
- **カスタム `inputs` JSON バリデーション＆テンプレート**: UI の複数行テキストボックスで JSON 構文および JSON オブジェクト形式を保存前に検証し、不正な入力をブロックします。HA のユーザー・デバイス・エリア情報などをテンプレート変数として利用可能です。
- **音声出力向けテキスト整形（任意）**: 推論モデルの `<think>...</think>` ブロックや Markdown 記法を自動除去し、TTS 読み上げを自然にします。
- **セルフホスト対応**: API ベース URL、タイムアウト秒数、SSL 証明書検証のオン／オフを設定可能です。
- **多言語 UI 対応**: 英語・簡体字中国語（`zh-Hans`）・日本語（`ja`）の設定画面翻訳を同梱しています。

## インストール

### 方法 1: HACS を使用（推奨）

下のボタンからこのリポジトリを HACS に直接追加できます：

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=shenwii&repository=dify-conversation&category=integration)

または HACS から手動で追加します：

1. Home Assistant で **HACS** を開きます。
2. 右上メニュー（`⋮`）-> **カスタムリポジトリ（Custom repositories）** を開きます。
3. `https://github.com/shenwii/dify-conversation` を入力し、カテゴリに **インテグレーション（Integration）** を選択します。
4. **Dify Conversation** を検索して **ダウンロード** し、Home Assistant を再起動します。

### 方法 2: 手動インストール

1. `custom_components/dify_conversation` フォルダを Home Assistant の `<config>/custom_components/` にコピーします。
2. Home Assistant を再起動します。

## 設定方法

下のボタンをクリックするか、**設定 -> デバイスとサービス -> インテグレーションを追加** から **Dify Conversation** を追加します：

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=dify_conversation)

| 設定項目 | デフォルト値 | 説明 |
|---|---|---|
| **名前（任意）** | Dify アプリ名 | Home Assistant 上の表示名。空欄にすると Dify からアプリ名を自動取得します。 |
| **API ベース URL** | `https://api.dify.ai/v1` | Dify API のベース URL（セルフホスト時は `https://your-dify.example.com/v1` など）。 |
| **API キー** | — | Dify アプリの「API アクセス」画面で発行した API キー。 |
| **SSL 証明書を検証する** | `true` | 自己署名証明書を使用するセルフホスト環境ではオフにします。 |
| **リクエストタイムアウト** | `60` | タイムアウト秒数（`5`〜`600`）。 |
| **応答モード** | `streaming` | `streaming`（SSE・推奨）または `blocking`。 |
| **音声出力向けに `<think>` タグと Markdown を除去** | `false` | 音声出力前に思考タグや Markdown 記法を取り除きます。 |
| **カスタム Dify inputs（JSON）** | `{}` | Dify の `inputs` に渡す JSON オブジェクト。構文エラーまたはオブジェクト以外は保存できません。 |

追加後、**設定 -> 音声アシスタント（Assist）** から使用するパイプラインの会話エージェントに **Dify Conversation** を設定してください。

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

`$var` と `${var}` の両方が利用可能です。JSON をパースした後に文字列値に対して安全なテンプレート置換を行うため、発話内容やデバイス名に引用符や改行が含まれても JSON 構文は壊れません。

### テンプレート変数一覧

| 変数名 | 内容 | 補足 |
|---|---|---|
| `$user_id` | Home Assistant ログインユーザー名 | `homeassistant` 認証プロバイダから取得するログイン ID（**UUID ではありません**）。音声サテライト等で取得できない場合は `""`。 |
| `$user_name` | Home Assistant ユーザー表示名 | `user.name`。取得できない場合は `""`。 |
| `$ha_user_uuid` | Home Assistant 内部ユーザー UUID | `context.user_id`。取得できない場合は `""`。 |
| `$device_id` | 実行元デバイス ID | `ConversationInput.device_id`。無い場合は `""`。 |
| `$device_name` | 実行元デバイス名 | Device Registry の名前（ユーザー設定名優先）、無い場合は `""`。 |
| `$area_id` | デバイス所属エリア ID | Device Registry 経由で取得、無い場合は `""`。 |
| `$area_name` | デバイス所属エリア名 | Area Registry 経由で取得（例: `"リビング"`）、無い場合は `""`。 |
| `$satellite_id` | 音声サテライトエンティティ ID | `ConversationInput.satellite_id`。無い場合は `""`。 |
| `$language` | 会話の言語コード | 例: `ja`、`en`、`zh-CN`。 |
| `$conversation_id` | Home Assistant 会話 ID | 現在の HA `ChatLog` のセッション ID。 |
| `$query` | ユーザー入力テキスト | 今回のユーザー発話内容。 |

> [!IMPORTANT]
> - **`query` の強制上書き**: リクエストボディ最上位の `query` には常にユーザー入力が設定されます。また、カスタム `inputs` JSON 内に `"query"` キーが含まれていた場合も、現在のユーザー入力で強制的に上書きされます。
> - **Dify 側の `inputs` キャッシュ仕様**: Dify の `/v1/chat-messages` では初回メッセージ時の `inputs` が会話セッションに保存され、同一 `conversation_id` の 2 ターン目以降は初回値が維持されます。
> - **Dify の `user` パラメータ**: API 仕様上必須のトップレベル `user` フィールドには、`$user_id` -> `$ha_user_uuid` -> `$device_id` -> `$satellite_id` -> `"homeassistant"` の順で最初の非空値が自動設定されます。

## 連続会話のプロンプト設定

応答末尾の空白・改行を `rstrip()` で除去した後の最終文字が `?` または `？` の場合に `continue_conversation = True` が有効になります。

Dify のシステムプロンプトに以下のような指示を設定してください：

```text
ユーザーに追加の質問や確認を行いたい場合は、必ず返答の最後を疑問符（？ または ?）で終えてください。返答を待つ必要がない場合は、疑問符で終えないでください。
```

## トラブルシューティング

- **音声サテライトが連続待受にならない**: サテライト側が `continue_conversation` に対応しているか、また Dify の返答末尾が `?` または `？` になっているかご確認ください。
- **セルフホスト Dify に接続できない**: URL の末尾に `/v1` が含まれているか確認し、自己署名証明書の場合は **SSL 証明書を検証する** をオフにしてください。
- **TTS が `<think>` や `*` を読み上げてしまう**: インテグレーションのオプションで **音声出力向けに `<think>` タグと Markdown を除去** を有効にしてください。
- **`Conversation Not Exists`（404）が発生する**: 古いセッションマッピングを自動削除し、新規会話として 1 回自動リトライします。
