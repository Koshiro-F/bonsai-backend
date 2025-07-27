#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF_OCR_minimal.py - 最小限のPDFテキスト抽出

pypdfのみを使用した最もシンプルなバージョン
"""

import sys
import pypdf

# コマンドライン引数チェック
if len(sys.argv) < 2:
    print("使用方法: python PDF_OCR_minimal.py <PDFファイル>")
    sys.exit(1)

pdf_path = sys.argv[1]

try:
    # PDFファイルを開く
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        
        # 全ページからテキストを抽出
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                print(f"\n=== ページ {page_num + 1} ===")
                print(text)
        print("テキスト抽出が完了しました")

except FileNotFoundError:
    print(f"エラー: ファイルが見つかりません - {pdf_path}")
except Exception as e:
    print(f"エラー: {e}") 