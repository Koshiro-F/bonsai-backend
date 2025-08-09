#!/usr/bin/env python3
"""
DocumentAI を用いて PDF をOCRし、ページごとのテキスト内容をCSVに保存するスクリプト。
OpenAI は使用せず、ページ単位で抽出した「内容」のみを格納します。

出力CSVカラム: filename, page, content
"""

import os
import csv
import tempfile
from typing import List, Dict, Optional, Tuple, Set

from dotenv import load_dotenv
from google.cloud import documentai
import fitz  # PyMuPDF


# 環境変数の読み込み
load_dotenv(dotenv_path="/Users/fujikawaakirashirou/jinshari/bonsai-backend/.env.local")


class OCRPageExporter:
    """DocumentAIを使ってPDFからページ単位のテキストを抽出してCSV保存する"""

    def __init__(self):
        # DocumentAI設定
        self.project_id = "utopian-saga-466802-m5"
        self.location = "us"
        self.processor_id = "e794632016082b0"
        self.processor_version = "pretrained-ocr-v2.0-2023-06-02"
        self.client = documentai.DocumentProcessorServiceClient()

    def _get_documentai_document(self, pdf_path: str):
        """DocumentAIでPDFを処理し、documentを返す"""
        name = self.client.processor_version_path(
            self.project_id, self.location, self.processor_id, self.processor_version
        )

        with open(pdf_path, "rb") as pdf_file:
            pdf_content = pdf_file.read()

        request = documentai.ProcessRequest(
            name=name,
            raw_document=documentai.RawDocument(content=pdf_content, mime_type="application/pdf"),
        )

        result = self.client.process_document(request=request)
        return result.document

    def _process_selected_pages_with_documentai(self, pdf_path: str, zero_based_indices: List[int]):
        """選択ページのみを抽出して一時PDFを作成し、DocumentAIで処理

        Returns: (documentai.Document, List[int] original_page_numbers)
        """
        # 元PDFから対象ページのみ抽出
        src = fitz.open(pdf_path)
        dst = fitz.open()
        for idx in zero_based_indices:
            if 0 <= idx < len(src):
                dst.insert_pdf(src, from_page=idx, to_page=idx)
        # 一時ファイルに保存
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            dst.save(tmp_path)
        finally:
            dst.close()
            src.close()

        # 一時PDFをDocumentAIで処理
        try:
            document = self._get_documentai_document(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        # マッピング（出力のページ順はzero_based_indicesの順）
        original_page_numbers = [i + 1 for i in zero_based_indices]
        return document, original_page_numbers

    def _extract_text_from_layout(self, layout, full_text: str) -> str:
        """レイアウト情報から該当のテキストを抽出"""
        if not layout or not getattr(layout, "text_anchor", None):
            return ""

        text_segments: List[str] = []
        for segment in layout.text_anchor.text_segments:
            start_index = int(segment.start_index) if segment.start_index else 0
            end_index = int(segment.end_index) if segment.end_index else len(full_text)
            text_segments.append(full_text[start_index:end_index])

        return "".join(text_segments)

    def _extract_table_text(self, table, full_text: str) -> str:
        """テーブル構造からテキストを抽出し、パイプ区切りで整形"""
        table_rows: List[str] = []
        for row in table.body_rows:
            row_cells: List[str] = []
            for cell in row.cells:
                cell_text = self._extract_text_from_layout(cell.layout, full_text)
                row_cells.append(cell_text.strip())
            if any(cell for cell in row_cells):
                table_rows.append(" | ".join(row_cells))
        return "\n".join(table_rows) if table_rows else ""

    def _extract_bbox(self, layout) -> Dict[str, float]:
        """Bounding Boxを抽出 (y1, x1でソート用)"""
        if not layout or not getattr(layout, "bounding_poly", None):
            return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
        vertices = layout.bounding_poly.vertices
        if not vertices or len(vertices) < 4:
            return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
        x_coords = [v.x for v in vertices if hasattr(v, "x")]
        y_coords = [v.y for v in vertices if hasattr(v, "y")]
        return {"x1": min(x_coords), "y1": min(y_coords), "x2": max(x_coords), "y2": max(y_coords)}

    def _extract_page_content(self, document, page_index: int) -> str:
        """指定ページの内容テキストをレイアウト順にまとめて返す"""
        if page_index >= len(document.pages):
            return ""
        page = document.pages[page_index]

        elements: List[Dict] = []

        # 段落
        if hasattr(page, "paragraphs") and page.paragraphs:
            for para in page.paragraphs:
                text = self._extract_text_from_layout(para.layout, document.text)
                if text.strip():
                    elements.append({
                        "type": "paragraph",
                        "text": text.strip(),
                        "bbox": self._extract_bbox(para.layout)
                    })

        # 表
        if hasattr(page, "tables") and page.tables:
            for table in page.tables:
                table_text = self._extract_table_text(table, document.text)
                if table_text:
                    bbox = self._extract_bbox(table.layout) if getattr(table, "layout", None) else {}
                    elements.append({
                        "type": "table",
                        "text": table_text,
                        "bbox": bbox
                    })

        # レイアウト順にソート (y1 -> x1)
        elements.sort(key=lambda x: (x["bbox"].get("y1", 0), x["bbox"].get("x1", 0)))

        # テキスト整形
        lines: List[str] = []
        for el in elements:
            if el["type"] == "table":
                lines.append("**表形式データ**:")
                lines.append(el["text"])  # そのまま複数行
                lines.append("")
            else:
                lines.append(el["text"])
                lines.append("")

        return "\n".join(lines).strip()

    def process_file(self, pdf_path: str, selected_pages: Optional[Set[int]] = None) -> List[Dict[str, str]]:
        """1つのPDFを処理し、各ページの内容を返す

        selected_pages: 1始まりのページ番号集合（Noneなら全ページ）
        """
        print(f"📖 OCR処理: {os.path.basename(pdf_path)}")
        results: List[Dict[str, str]] = []

        if selected_pages:
            # 0始まりに変換（元PDFの総ページ数を知らなくてもよい）
            zero_based = sorted({p - 1 for p in selected_pages if p >= 1})
            if not zero_based:
                print(f"  ⚠️ 指定ページが不正のためスキップ: {os.path.basename(pdf_path)}")
                return results
            # 指定ページのみで一時PDFを作成してDocumentAIに渡す（サイズ制限対策）
            document, original_page_numbers = self._process_selected_pages_with_documentai(pdf_path, zero_based)
            total_pages_tmp = len(document.pages)
            print(f"  🔢 指定ページ: {', '.join(str(p) for p in sorted(selected_pages))} → 抽出{total_pages_tmp}ページ")

            for tmp_idx in range(total_pages_tmp):
                orig_page_num = original_page_numbers[tmp_idx]
                print(f"  📄 ページ {orig_page_num} を抽出中...")
                content = self._extract_page_content(document, tmp_idx)
                results.append({
                    "filename": os.path.basename(pdf_path),
                    "page": str(orig_page_num),
                    "content": content,
                })
        else:
            # 全ページ処理（ファイルが大きすぎる場合はユーザーが--specで範囲指定推奨）
            document = self._get_documentai_document(pdf_path)
            total_pages = len(document.pages)
            for idx in range(total_pages):
                page_num = idx + 1
                print(f"  📄 ページ {page_num}/{total_pages} を抽出中...")
                content = self._extract_page_content(document, idx)
                results.append({
                    "filename": os.path.basename(pdf_path),
                    "page": str(page_num),
                    "content": content,
                })
        return results

    def process_directory(self, input_dir: str) -> List[str]:
        """ディレクトリ内のPDF一覧を取得"""
        pdfs: List[str] = []
        for name in sorted(os.listdir(input_dir)):
            if name.lower().endswith(".pdf"):
                pdfs.append(os.path.join(input_dir, name))
        return pdfs


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DocumentAI OCR → ページ別CSVエクスポート")
    parser.add_argument("--output", "-o",
                        default="/Users/fujikawaakirashirou/jinshari/bonsai-backend/data/ocr_pages.csv",
                        help="出力CSVファイルのパス")
    parser.add_argument("--spec", action="append", required=True,
                        help="処理対象指定: 'filename.pdf:1,3-5,10' の形式。複数指定可。相対パスは--base-dir基準")
    parser.add_argument("--base-dir", default="/Users/fujikawaakirashirou/jinshari/bonsai-backend/data/input",
                        help="--specで相対パスを解決する基準ディレクトリ")

    args = parser.parse_args()

    exporter = OCRPageExporter()

    def parse_pages(pages_str: str) -> Set[int]:
        pages: Set[int] = set()
        if not pages_str:
            return pages
        tokens = [t.strip() for t in pages_str.split(',') if t.strip()]
        for tok in tokens:
            if '-' in tok:
                try:
                    a, b = tok.split('-', 1)
                    start = int(a)
                    end = int(b)
                    if start <= end:
                        pages.update(range(start, end + 1))
                    else:
                        pages.update(range(end, start + 1))
                except ValueError:
                    continue
            else:
                try:
                    pages.add(int(tok))
                except ValueError:
                    continue
        return pages

    # 対象とページ指定の解釈
    file_to_pages: List[Tuple[str, Optional[Set[int]]]] = []
    base_dir = args.base_dir

    if args.spec:
        # --spec 優先
        for spec in args.spec:
            if ':' not in spec:
                filename = spec.strip()
                pages_set: Optional[Set[int]] = None
            else:
                filename, pages_str = spec.split(':', 1)
                filename = filename.strip()
                pages_set = parse_pages(pages_str.strip())

            # パス解決
            candidate = filename
            if not os.path.isabs(candidate):
                if os.path.isfile(candidate):
                    pass
                else:
                    candidate = os.path.join(base_dir, filename)

            if not os.path.isfile(candidate):
                print(f"❌ ファイルが見つかりません: {filename} (解決先: {candidate})")
                continue

            file_to_pages.append((candidate, pages_set))
    else:
        # --specはrequiredなのでここには来ないが安全のため
        print("❌ --spec が指定されていません")
        return

    if not file_to_pages:
        print("❌ 処理対象がありません")
        return

    print(f"🧪 対象ファイル数: {len(file_to_pages)}")
    all_rows: List[Dict[str, str]] = []
    for pdf_path, pages in file_to_pages:
        try:
            rows = exporter.process_file(pdf_path, selected_pages=pages)
            all_rows.extend(rows)
        except Exception as e:
            print(f"⚠️  処理失敗: {pdf_path} ({e})")

    # CSV保存
    if all_rows:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "page", "content"], quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in all_rows:
                writer.writerow(row)
        print(f"✅ CSVに保存しました: {args.output} ({len(all_rows)} 行)")
    else:
        print("⚠️ 出力する行がありませんでした")


if __name__ == "__main__":
    main()

