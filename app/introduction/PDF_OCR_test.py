#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF_OCR_test.py - プログラミング初心者向けPDF OCR処理スクリプト

このスクリプトは、PDFファイルからテキストを抽出する簡単なOCR処理を行います。
初心者でも理解しやすいように、エラーハンドリングとコメントを充実させています。

使用方法:
    python PDF_OCR_test.py <PDFファイルのパス>

例:
    python PDF_OCR_test.py sample.pdf
"""

import os
import sys
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

# 環境変数の読み込み
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path="/home/fujikawa/jinshari/flask-bonsai/.env.local")
    print("✅ 環境変数を読み込みました")
except ImportError:
    print("⚠️  dotenvライブラリが見つかりません（オプション）")
except Exception as e:
    print(f"⚠️  環境変数の読み込みでエラーが発生しました: {e}")

@dataclass
class OCRResult:
    """OCR処理結果を格納するデータクラス"""
    success: bool
    text: str
    processing_time: float
    pages_processed: int
    error_message: str = ""
    additional_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}

class SimplePDFOCR:
    """初心者向けの簡単なPDF OCR処理クラス"""
    
    def __init__(self, pdf_path: str):
        """
        PDF OCR処理クラスの初期化
        
        Args:
            pdf_path: 処理対象のPDFファイルのパス
        """
        self.pdf_path = pdf_path
        self.available_libraries = self._check_available_libraries()
        
    def _check_available_libraries(self) -> Dict[str, bool]:
        """
        利用可能なライブラリをチェック
        
        Returns:
            利用可能なライブラリの辞書
        """
        libraries = {}
        
        # PyMuPDF (推奨 - 高速で安定)
        try:
            import fitz
            libraries['pymupdf'] = True
            print("✅ PyMuPDF ライブラリが利用可能です")
        except ImportError:
            libraries['pymupdf'] = False
            print("❌ PyMuPDF ライブラリが見つかりません")
            print("   インストール方法: pip install PyMuPDF")
        
        # pdfplumber (表抽出に強い)
        try:
            import pdfplumber
            libraries['pdfplumber'] = True
            print("✅ pdfplumber ライブラリが利用可能です")
        except ImportError:
            libraries['pdfplumber'] = False
            print("❌ pdfplumber ライブラリが見つかりません")
            print("   インストール方法: pip install pdfplumber")
        
        # unstructured (OCR機能付き)
        try:
            from unstructured.partition.pdf import partition_pdf
            libraries['unstructured'] = True
            print("✅ unstructured ライブラリが利用可能です")
        except ImportError:
            libraries['unstructured'] = False
            print("❌ unstructured ライブラリが見つかりません")
            print("   インストール方法: pip install unstructured")
        
        return libraries
    
    def validate_pdf_file(self) -> bool:
        """
        PDFファイルの存在と形式を検証
        
        Returns:
            ファイルが有効な場合はTrue
        """
        try:
            # ファイルの存在確認
            if not os.path.exists(self.pdf_path):
                print(f"❌ ファイルが見つかりません: {self.pdf_path}")
                return False
            
            # ファイルサイズの確認
            file_size = os.path.getsize(self.pdf_path)
            if file_size == 0:
                print("❌ ファイルが空です")
                return False
            
            print(f"✅ ファイルサイズ: {file_size:,} バイト")
            
            # PDFファイルの拡張子確認
            if not self.pdf_path.lower().endswith('.pdf'):
                print("⚠️  ファイルの拡張子が.pdfではありません")
                print("   処理を続行しますが、PDFファイルであることを確認してください")
            
            return True
            
        except Exception as e:
            print(f"❌ ファイル検証中にエラーが発生しました: {e}")
            return False
    
    def extract_text_with_pymupdf(self) -> OCRResult:
        """
        PyMuPDFを使用してテキストを抽出（推奨方法）
        
        Returns:
            OCRResult: 処理結果
        """
        print("\n🔍 PyMuPDFでテキスト抽出を開始...")
        start_time = time.time()
        
        try:
            import fitz  # PyMuPDF
            
            # PDFファイルを開く
            doc = fitz.open(self.pdf_path)
            print(f"✅ PDFファイルを開きました（ページ数: {len(doc)}）")
            
            all_text = []
            pages_processed = 0
            
            # 各ページからテキストを抽出
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    text = page.get_text()
                    
                    if text.strip():  # 空でないテキストのみ追加
                        all_text.append(f"=== ページ {page_num + 1} ===\n{text}")
                    
                    pages_processed += 1
                    print(f"   ページ {page_num + 1} を処理しました")
                    
                except Exception as e:
                    print(f"⚠️  ページ {page_num + 1} の処理でエラー: {e}")
                    continue
            
            # ファイルを閉じる
            doc.close()
            
            processing_time = time.time() - start_time
            extracted_text = "\n\n".join(all_text)
            
            print(f"✅ PyMuPDF処理完了: {pages_processed}ページ, {len(extracted_text)}文字")
            
            return OCRResult(
                success=True,
                text=extracted_text,
                processing_time=processing_time,
                pages_processed=pages_processed,
                additional_info={"method": "pymupdf", "text_blocks": len(all_text)}
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"PyMuPDF処理中にエラーが発生しました: {e}"
            print(f"❌ {error_msg}")
            
            return OCRResult(
                success=False,
                text="",
                processing_time=processing_time,
                pages_processed=0,
                error_message=error_msg
            )
    
    def extract_text_with_pdfplumber(self) -> OCRResult:
        """
        pdfplumberを使用してテキストを抽出（表に強い）
        
        Returns:
            OCRResult: 処理結果
        """
        print("\n🔍 pdfplumberでテキスト抽出を開始...")
        start_time = time.time()
        
        try:
            import pdfplumber
            
            all_text = []
            pages_processed = 0
            
            # PDFファイルを開く
            with pdfplumber.open(self.pdf_path) as pdf:
                print(f"✅ PDFファイルを開きました（ページ数: {len(pdf.pages)}）")
                
                # 各ページからテキストを抽出
                for page_num, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text()
                        
                        if text and text.strip():
                            all_text.append(f"=== ページ {page_num + 1} ===\n{text}")
                        
                        pages_processed += 1
                        print(f"   ページ {page_num + 1} を処理しました")
                        
                    except Exception as e:
                        print(f"⚠️  ページ {page_num + 1} の処理でエラー: {e}")
                        continue
            
            processing_time = time.time() - start_time
            extracted_text = "\n\n".join(all_text)
            
            print(f"✅ pdfplumber処理完了: {pages_processed}ページ, {len(extracted_text)}文字")
            
            return OCRResult(
                success=True,
                text=extracted_text,
                processing_time=processing_time,
                pages_processed=pages_processed,
                additional_info={"method": "pdfplumber", "text_blocks": len(all_text)}
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"pdfplumber処理中にエラーが発生しました: {e}"
            print(f"❌ {error_msg}")
            
            return OCRResult(
                success=False,
                text="",
                processing_time=processing_time,
                pages_processed=0,
                error_message=error_msg
            )
    
    def extract_text_with_unstructured(self) -> OCRResult:
        """
        unstructuredを使用してOCR処理（画像内のテキストも抽出）
        
        Returns:
            OCRResult: 処理結果
        """
        print("\n🔍 unstructuredでOCR処理を開始...")
        start_time = time.time()
        
        try:
            from unstructured.partition.pdf import partition_pdf
            
            print("⚠️  OCR処理は時間がかかる場合があります...")
            
            # OCR処理でPDFを解析
            elements = partition_pdf(
                filename=self.pdf_path,
                languages=["jpn", "eng"],  # 日本語と英語をサポート
                strategy="ocr_only",  # OCRのみを使用
            )
            
            processing_time = time.time() - start_time
            
            # 要素からテキストを抽出
            all_text = []
            pages_processed = 0
            
            for element in elements:
                try:
                    element_dict = element.to_dict()
                    text_content = element_dict.get("text", "")
                    
                    if text_content.strip():
                        all_text.append(text_content)
                    
                    # ページ情報を取得
                    metadata = element_dict.get("metadata", {})
                    page_num = metadata.get("page_number", 1)
                    pages_processed = max(pages_processed, page_num)
                    
                except Exception as e:
                    print(f"⚠️  要素の処理でエラー: {e}")
                    continue
            
            extracted_text = "\n\n".join(all_text)
            
            print(f"✅ unstructured処理完了: {pages_processed}ページ, {len(extracted_text)}文字")
            
            return OCRResult(
                success=True,
                text=extracted_text,
                processing_time=processing_time,
                pages_processed=pages_processed,
                additional_info={"method": "unstructured", "elements": len(elements)}
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"unstructured処理中にエラーが発生しました: {e}"
            print(f"❌ {error_msg}")
            
            return OCRResult(
                success=False,
                text="",
                processing_time=processing_time,
                pages_processed=0,
                error_message=error_msg
            )
    
    def run_ocr(self, method: str = "auto") -> OCRResult:
        """
        OCR処理を実行
        
        Args:
            method: 使用する方法 ("auto", "pymupdf", "pdfplumber", "unstructured")
        
        Returns:
            OCRResult: 処理結果
        """
        print(f"📄 PDFファイル: {os.path.basename(self.pdf_path)}")
        print("=" * 60)
        
        # ファイルの検証
        if not self.validate_pdf_file():
            return OCRResult(
                success=False,
                text="",
                processing_time=0,
                pages_processed=0,
                error_message="ファイルの検証に失敗しました"
            )
        
        # 利用可能なライブラリの確認
        if not any(self.available_libraries.values()):
            error_msg = "利用可能なPDF処理ライブラリがありません"
            print(f"❌ {error_msg}")
            print("   以下のコマンドでライブラリをインストールしてください:")
            print("   pip install PyMuPDF pdfplumber unstructured")
            return OCRResult(
                success=False,
                text="",
                processing_time=0,
                pages_processed=0,
                error_message=error_msg
            )
        
        # 方法の選択
        if method == "auto":
            # 自動選択（推奨順）
            if self.available_libraries.get('pymupdf'):
                return self.extract_text_with_pymupdf()
            elif self.available_libraries.get('pdfplumber'):
                return self.extract_text_with_pdfplumber()
            elif self.available_libraries.get('unstructured'):
                return self.extract_text_with_unstructured()
        elif method == "pymupdf" and self.available_libraries.get('pymupdf'):
            return self.extract_text_with_pymupdf()
        elif method == "pdfplumber" and self.available_libraries.get('pdfplumber'):
            return self.extract_text_with_pdfplumber()
        elif method == "unstructured" and self.available_libraries.get('unstructured'):
            return self.extract_text_with_unstructured()
        else:
            error_msg = f"指定された方法 '{method}' は利用できません"
            print(f"❌ {error_msg}")
            return OCRResult(
                success=False,
                text="",
                processing_time=0,
                pages_processed=0,
                error_message=error_msg
            )
    
    def display_result(self, result: OCRResult):
        """
        処理結果を表示
        
        Args:
            result: OCRResultオブジェクト
        """
        print("\n" + "=" * 60)
        print("📊 OCR処理結果")
        print("=" * 60)
        
        if result.success:
            print(f"✅ 処理成功!")
            print(f"⏱️  処理時間: {result.processing_time:.2f}秒")
            print(f"📄 処理ページ数: {result.pages_processed}")
            print(f"📝 抽出文字数: {len(result.text):,}")
            
            if result.additional_info:
                method = result.additional_info.get("method", "unknown")
                print(f"🔧 使用ライブラリ: {method}")
            
            # テキストのプレビュー
            if result.text.strip():
                preview = result.text[:500]  # 最初の500文字を表示
                print(f"\n📖 抽出テキスト（プレビュー）:")
                print("-" * 40)
                print(preview)
                if len(result.text) > 500:
                    print("...")
                print("-" * 40)
            else:
                print("\n⚠️  抽出されたテキストがありません")
                
        else:
            print(f"❌ 処理失敗")
            print(f"⏱️  処理時間: {result.processing_time:.2f}秒")
            print(f"💬 エラーメッセージ: {result.error_message}")
    
    def save_result(self, result: OCRResult, output_path: Optional[str] = None):
        """
        処理結果をファイルに保存
        
        Args:
            result: OCRResultオブジェクト
            output_path: 保存先ファイルパス（指定しない場合は自動生成）
        """
        if not result.success:
            print("❌ 処理が失敗したため、ファイルを保存できません")
            return
        
        if output_path is None:
            # 自動的にファイル名を生成
            base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
            output_path = f"{base_name}_extracted_text.txt"
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"PDF OCR処理結果\n")
                f.write(f"元ファイル: {self.pdf_path}\n")
                f.write(f"処理時間: {result.processing_time:.2f}秒\n")
                f.write(f"処理ページ数: {result.pages_processed}\n")
                f.write(f"抽出文字数: {len(result.text):,}\n")
                f.write(f"使用ライブラリ: {result.additional_info.get('method', 'unknown')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(result.text)
            
            print(f"💾 結果を保存しました: {output_path}")
            
        except Exception as e:
            print(f"❌ ファイル保存中にエラーが発生しました: {e}")


def main():
    """メイン実行関数"""
    print("🚀 PDF OCR処理スクリプト（初心者向け）")
    print("=" * 60)
    
    # コマンドライン引数の処理
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python PDF_OCR_test.py <PDFファイルのパス> [方法] [出力ファイル]")
        print("\n例:")
        print("  python PDF_OCR_test.py sample.pdf")
        print("  python PDF_OCR_test.py sample.pdf pymupdf")
        print("  python PDF_OCR_test.py sample.pdf auto output.txt")
        print("\n利用可能な方法:")
        print("  auto        - 自動選択（推奨）")
        print("  pymupdf     - PyMuPDF（高速）")
        print("  pdfplumber  - pdfplumber（表に強い）")
        print("  unstructured - unstructured（OCR機能付き）")
        return
    
    # 引数の取得
    pdf_path = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else "auto"
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        # OCR処理の実行
        ocr = SimplePDFOCR(pdf_path)
        result = ocr.run_ocr(method)
        
        # 結果の表示
        ocr.display_result(result)
        
        # 結果の保存
        if result.success:
            ocr.save_result(result, output_path)
        
        # 終了メッセージ
        if result.success:
            print("\n🎉 OCR処理が完了しました!")
        else:
            print("\n💡 ヒント:")
            print("   - 別の方法を試してみてください")
            print("   - 必要なライブラリがインストールされているか確認してください")
            print("   - PDFファイルが破損していないか確認してください")
            
    except KeyboardInterrupt:
        print("\n⚠️  処理が中断されました")
    except Exception as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        print("   詳細なエラー情報:")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
