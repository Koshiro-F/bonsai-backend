# 真柏データRAGシステム

shinpaku_data.csvを基にした専用のRAG（Retrieval-Augmented Generation）システムです。真柏や盆栽に関する質問に対して、専門的な知識データベースを参照しながら回答を生成します。

## 📁 ファイル構成

```
app/rag/shinpaku/
├── create_vectorstore_shinpaku.py  # ベクトルストア作成スクリプト
├── run_rag_shinpaku.py            # RAG実行スクリプト
├── rag_api_service.py             # Web API用サービスクラス
├── test_api.py                    # API動作テストスクリプト
└── README.md                      # このファイル

app/routes/
└── rag_shinpaku.py                # Flask Blueprint（API エンドポイント）
```

## 🚀 使用方法

### 1. ベクトルストアの作成

最初に、CSVファイルからベクトルストアを作成する必要があります。

```bash
cd /Users/fujikawaakirashirou/jinshari/bonsai-backend/app/rag/shinpaku
python create_vectorstore_shinpaku.py
```

### 2. RAGチャットボットの実行

ベクトルストア作成後、チャットボットを起動できます。

```bash
# 基本実行
python run_rag_shinpaku.py

# 参照ドキュメントの内容も表示する場合
python run_rag_shinpaku.py --show-content
```

## 🔧 環境設定

### 必要な環境変数

`bonsai-backend/.env.local`ファイルに以下の環境変数を設定してください：

```
OPENAI_API_KEY=your_openai_api_key_here
```

**注意**: 環境変数ファイルはスクリプトの位置から相対パスで自動検出されるため、カレントディレクトリに依存しません。

### 必要なPythonパッケージ

```
langchain
langchain-community
langchain-openai
chromadb
pandas
python-dotenv
```

## 📊 データ構造

### 入力データ（shinpaku_data.csv）

| カラム名 | 説明 | 例 |
|---------|------|-----|
| 文献名 | 参考文献の名前 | "盆栽入門マニュアルⅡ.pdf" |
| ページ | ページ番号 | "3" |
| 章 | 章の名前 | "〜こんなところが見どころです~" |
| 節 | 節の名前 | "盆栽・部位の呼び名" |
| 区分 | コンテンツの種類 | "本文", "キャプション" |
| 樹種 | 対象樹種 | "真柏", "黒松" など |
| 内容 | 実際のテキスト内容 | 専門知識の記述 |

### 保存されるベクトルストア

- **場所**: `bonsai-backend/data/vectorstore_shinpaku` (相対パス)
- **形式**: ChromaDB
- **エンベディング**: OpenAI text-embedding-ada-002

## 💬 チャットボット機能

### 基本機能

- **ハイブリッド検索**: ベクトル検索とBM25キーワード検索の組み合わせ
- **会話履歴管理**: 文脈を考慮した対話
- **専門プロンプト**: 真柏・盆栽専用に調整されたシステムメッセージ
- **参照表示**: 回答の根拠となったドキュメント情報の表示

### チャットコマンド

- `quit`, `exit`, `q`: チャット終了
- `clear`: 会話履歴のクリア

### 質問例

```
真柏の水やりはどうすればいいですか？
根張りとは何ですか？
立ち上がりについて教えてください
真柏の剪定時期はいつですか？
```

## 🔍 検索機能の特徴

### 1. セマンティック検索
- OpenAI Embeddingsを使用した意味理解ベースの検索
- 類似した概念や関連する情報を自動的に発見

### 2. キーワード検索（BM25）
- 日本語文字n-gram（3-5文字）による高精度キーワード検索
- 専門用語の完全一致検索に優れる

### 3. メタデータフィルタリング
- 文献名、章節、樹種での絞り込み可能
- 特定の文献やトピックに焦点を当てた検索

## 📈 統計情報表示

チャットボット起動時に以下の統計情報が表示されます：

- 総ドキュメント数
- ユニークな文献数
- ユニークな樹種数
- 主要な樹種一覧

## 🛠️ カスタマイズ

### チャンクサイズの調整

`create_vectorstore_shinpaku.py`の以下の部分を変更：

```python
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,     # チャンクサイズ
    chunk_overlap=128   # オーバーラップサイズ
)
```

### 検索結果数の調整

`run_rag_shinpaku.py`の以下の定数を変更：

```python
TOP_K = 3      # 最終的な検索結果数
BM25_K = 2     # BM25キーワード検索の取得数
VECTOR_K = 2   # ベクトル検索の取得数
```

**検索パラメータの調整:**
- **TOP_K**: 最終的にLLMに渡すドキュメント数
- **BM25_K**: キーワード検索で取得する件数
- **VECTOR_K**: セマンティック検索で取得する件数
- 重複除去後、TOP_K件に制限されます

### システムメッセージの調整

`run_rag_shinpaku.py`の`system_message`を編集して、回答の方針を変更可能。

## 🚨 注意事項

1. **初回実行時**: 必ず`create_vectorstore_shinpaku.py`を最初に実行してください
2. **API制限**: OpenAI APIの使用制限にご注意ください
3. **データ更新**: CSVファイルを更新した場合は、ベクトルストアの再作成が必要です
4. **メモリ使用量**: 大きなCSVファイルの場合、バッチサイズを調整してください

## 📝 ログファイル

- **処理済みファイル記録**: `bonsai-backend/data/processed_shinpaku_files.txt`

## 🌐 Web API機能

### API エンドポイント

真柏RAGシステムをWeb APIとして利用できます。

#### **基本エンドポイント**

```bash
# ヘルスチェック
GET /api/rag/health

# サービス状態確認
GET /api/rag/status

# データベース統計情報
GET /api/rag/stats

# チャット（メイン機能）
POST /api/rag/chat
{
    "question": "真柏の水やりについて教えてください",
    "session_id": "optional_session_id",
    "user_info": {...},        # 将来対応
    "species_filter": "真柏",   # 将来対応
    "search_options": {...}    # 将来対応
}

# セッションリセット
POST /api/rag/reset
{
    "session_id": "session_id"
}
```

#### **レスポンス形式**

```json
{
    "success": true,
    "data": {
        "response": "AI回答テキスト",
        "references": [
            {
                "literature": "盆栽入門マニュアルⅡ.pdf",
                "page": "3",
                "chapter": "〜こんなところが見どころです~",
                "section": "盆栽・部位の呼び名",
                "category": "本文",
                "species": "真柏"
            }
        ],
        "session_id": "session_abc123",
        "processing_time": 2.5,
        "token_info": {...}
    }
}
```

### API テスト

```bash
# Flask サーバー起動
cd /Users/fujikawaakirashirou/jinshari/bonsai-backend
python run.py

# API テスト実行
cd app/rag/shinpaku
python test_api.py
```

### curl 例

```bash
# ヘルスチェック
curl -X GET http://localhost:5000/api/rag/health

# チャット
curl -X POST http://localhost:5000/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "真柏の特徴について教えてください"}'

# セッション付きチャット
curl -X POST http://localhost:5000/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "水やりの方法も教えてください", 
    "session_id": "my_session_123"
  }'
```

## 🔄 更新・メンテナンス

### データの更新手順

1. 新しいCSVファイルを配置
2. 古いベクトルストアを削除（必要に応じて）
3. `create_vectorstore_shinpaku.py`を再実行
4. チャットボットで動作確認

### トラブルシューティング

- **"vectorstore not found"エラー**: ベクトルストアが作成されていません。`create_vectorstore_shinpaku.py`を実行してください
- **API エラー**: `.env.local`ファイルのOPENAI_API_KEYを確認してください
- **メモリエラー**: バッチサイズを小さくしてください
