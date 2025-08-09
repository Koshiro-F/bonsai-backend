# bonsai-backend

## 概要
盆栽管理アプリのバックエンドです。Flaskサーバーを立てます。

## セットアップ
- Docker導入します。少々お待ちを
- Python: 3.10.12, pip: 22.0.2
    - 一応```pip install -r requirements.txt```で依存ライブラリをインストールできます
    - が、足りない可能性が大いにあります

### instanceのインポート
[Googleドライブ](https://drive.google.com/drive/folders/1H3vB7fSie3MDJ-JJliAOFDR5kdyhy7fx)から```instance.zip```をダウンロードして解凍し、中身のフォルダをディレクトリ直下に配置してください

中身は2025.7.26時点でのDB（SQLite）と生画像データです

## ディレクトリについて
基本的にソースコードはappの中を見ればよいです（options, test_scriptsは無視していいです）

## サーバーの起動
以下のコマンドで走ります。6000番ポートで実行されるはずです
```
python run.py
```
---
## RAGの実行まで(実験中)
1. ディレクトリ直下にdataフォルダを作成します
2. data/input/を作成し、中に処理したいPDFを入れます
3. 以下のコマンドで```create_vectorstore.py```を実行します。ここまでがデータベースの準備です
    ```
    python app/rag/create_vectorstore.py
    ```
    1. 現状、Google Cloudのアカウントを作成しログインする必要のあるサービスを使っています

    2. 下で作成することになっている```.env.local```の中に、”GOOGLE_APPLICATION_CREDENTIALS"として認証JSONのパスを指定してください

4. ディレクトリ直下に```.env.local```を作成し、その中に"OPENAI_API_KEY"を入れます
    1. これもOpenAIに課金する必要があります。共有の方法を考えます
5. 以下のコマンドで```run_rag.py```を実行します
    ```
    python app/rag/run_rag.py
    ```

