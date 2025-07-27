# PDF OCR処理プログラム

PDFファイルからテキストを抽出する3つのプログラム+αを提供しています。

## 📁 ファイル一覧

### 0. `hello.py` - 動作確認用

### 1. `PDF_OCR_test.py` - 包括的（完全版）
- **特徴**: 詳細なエラーハンドリング、複数ライブラリ対応、結果保存機能
- **対象**: プログラミング初心者、本格的な処理が必要な場合
- **コード行数**: 約520行

### 2. `PDF_OCR_simple.py` - シンプル版
- **特徴**: 基本的な機能、複数ライブラリの自動選択
- **対象**: 基本的な処理が必要な場合
- **コード行数**: 約80行

### 3. `PDF_OCR_minimal.py` - 最小限版
- **特徴**: 最もシンプル、pypdfのみ使用
- **対象**: 最小限の機能で十分な場合
- **コード行数**: 約30行

## 🚀 使用方法
（パス指定に気を付けてください。以下のコマンドはカレントディレクトリがapp/introductionである想定です）

### 最小限版（推奨）
```bash
python PDF_OCR_minimal.py sample.pdf
```

### シンプル版
```bash
python PDF_OCR_simple.py sample.pdf
```

### 包括版
```bash
python PDF_OCR_test.py sample.pdf
python PDF_OCR_test.py sample.pdf pymupdf
python PDF_OCR_test.py sample.pdf auto output.txt
```

## 📦 必要なライブラリ

### 最小限版
```bash
pip install pypdf
```

### シンプル版
```bash
pip install pypdf PyMuPDF pdfplumber
```

### 包括版
```bash
pip install pypdf PyMuPDF pdfplumber unstructured
```

## 📊 比較表

| 機能 | 最小限版 | シンプル版 | 包括版 |
|------|----------|------------|--------------|
| ライブラリ | pypdfのみ | 3種類 | 3種類 |
| エラーハンドリング | 最低限 | 基本 | 詳細 |
| 結果保存 | × | × | ○ |
| 統計情報 | × | × | ○ |
| 使用方法 | 簡単 | 簡単 | 詳細 |

## 💡 選び方

- **初めて使う**: 最小限版から始める
- **基本的な処理**: シンプル版
- **本格的な処理**: 包括版

## 🔧 トラブルシューティング

### よくあるエラー

1. **ライブラリが見つからない**
   ```bash
   pip install pypdf
   ```

2. **ファイルが見つからない**
   - ファイルパスを確認
   - ファイルが存在するか確認

3. **テキストが抽出されない**
   - PDFが画像ベースの場合、OCR機能が必要
   - 初心者向け版の`unstructured`を試す 