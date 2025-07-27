#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF_OCR_simple.py - シンプルなPDF OCR処理スクリプト

最低限の機能：PDFを読み取り、テキストを抽出して出力するだけ
"""

import sys
import os

def extract_text_from_pdf(pdf_path):
    """PDFからテキストを抽出する"""
    
    # ファイルの存在確認
    if not os.path.exists(pdf_path):
        print(f"エラー: ファイルが見つかりません - {pdf_path}")
        return None
    
    # 利用可能なライブラリを試す
    libraries = [
        ("PyMuPDF", "import fitz"),
        ("pdfplumber", "import pdfplumber"),
        ("pypdf", "import pypdf")
    ]
    
    for lib_name, import_statement in libraries:
        try:
            exec(import_statement)
            print(f"✅ {lib_name}を使用します")
            
            if lib_name == "PyMuPDF":
                return extract_with_pymupdf(pdf_path)
            elif lib_name == "pdfplumber":
                return extract_with_pdfplumber(pdf_path)
            elif lib_name == "pypdf":
                return extract_with_pypdf(pdf_path)
                
        except ImportError:
            print(f"❌ {lib_name}が見つかりません")
            continue
    
    print("❌ 利用可能なPDFライブラリがありません")
    print("   インストール: pip install PyMuPDF pdfplumber pypdf")
    return None

def extract_with_pymupdf(pdf_path):
    """PyMuPDFでテキスト抽出"""
    import fitz
    
    doc = fitz.open(pdf_path)
    text = ""
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text += f"\n=== ページ {page_num + 1} ===\n"
        text += page.get_text()
    
    doc.close()
    return text

def extract_with_pdfplumber(pdf_path):
    """pdfplumberでテキスト抽出"""
    import pdfplumber
    
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text += f"\n=== ページ {page_num + 1} ===\n"
            page_text = page.extract_text()
            if page_text:
                text += page_text
    
    return text

def extract_with_pypdf(pdf_path):
    """pypdfでテキスト抽出"""
    import pypdf
    
    text = ""
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        for page_num, page in enumerate(reader.pages):
            text += f"\n=== ページ {page_num + 1} ===\n"
            page_text = page.extract_text()
            if page_text:
                text += page_text
    
    return text

def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用方法: python PDF_OCR_simple.py <PDFファイル>")
        return
    
    pdf_path = sys.argv[1]
    print(f"📄 処理中: {pdf_path}")
    
    # テキスト抽出
    text = extract_text_from_pdf(pdf_path)
    
    if text:
        print("\n📝 抽出されたテキスト:")
        print("=" * 50)
        print(text)
        print("=" * 50)
        print(f"✅ 完了! 文字数: {len(text)}")
    else:
        print("❌ テキストの抽出に失敗しました")

if __name__ == "__main__":
    main() 