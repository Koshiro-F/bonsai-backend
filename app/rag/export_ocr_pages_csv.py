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


# 環境変数の読み込み（スクリプト位置からの相対パスで解決）
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
_ENV_PATH = os.path.join(_BASE_DIR, ".env.local")
load_dotenv(dotenv_path=_ENV_PATH)


class OCRPageExporter:
    """DocumentAIを使ってPDFからページ単位のテキストを抽出してCSV保存する"""

    def __init__(self, imageless: bool = True):
        # DocumentAI設定
        self.project_id = "utopian-saga-466802-m5"
        self.location = "us"
        self.processor_id = "e794632016082b0"
        self.processor_version = "pretrained-ocr-v2.0-2023-06-02"
        self.client = documentai.DocumentProcessorServiceClient()
        # 画像抽出を省略するimagelessモード（ページ上限の緩和を狙う）。
        self.imageless = imageless

    def _get_documentai_document(self, pdf_path: str):
        """DocumentAIでPDFを処理し、documentを返す"""
        name = self.client.processor_version_path(
            self.project_id, self.location, self.processor_id, self.processor_version
        )

        with open(pdf_path, "rb") as pdf_file:
            pdf_content = pdf_file.read()

        # imagelessモード指定（利用可能な場合）。失敗時は通常オプションで再試行。
        request = None
        if self.imageless:
            try:
                request = documentai.ProcessRequest(
                    name=name,
                    raw_document=documentai.RawDocument(content=pdf_content, mime_type="application/pdf"),
                    process_options=documentai.ProcessOptions(
                        # 画像関連抽出を無効化（imageless相当）
                        enable_image_extraction=False,
                        # ネイティブPDFパースを有効化
                        ocr_config=documentai.OcrConfig(
                            enable_native_pdf_parsing=True
                        )
                    )
                )
            except Exception:
                request = None

        if request is None:
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
        """指定ページの内容テキストをまとめて返す。
        カラム推定は行わず、要素は y（上→下）で行グループ化し、
        同一行では x（右→左）に整列。段落はユークリッド距離で結合。
        """
        if page_index >= len(document.pages):
            return ""
        page = document.pages[page_index]

        elements: List[Dict] = []

        # 段落
        if hasattr(page, "paragraphs") and page.paragraphs:
            for para in page.paragraphs:
                text = self._extract_text_from_layout(para.layout, document.text)
                if text.strip():
                    bbox = self._extract_bbox(para.layout)
                    elements.append({
                        "type": "paragraph",
                        "text": text.strip(),
                        "bbox": bbox
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

        if not elements:
            return ""

        # ページサイズの推定（閾値設定のため）
        min_x = min(el["bbox"].get("x1", 0) for el in elements)
        max_x = max(el["bbox"].get("x2", 0) for el in elements)
        min_y = min(el["bbox"].get("y1", 0) for el in elements)
        max_y = max(el["bbox"].get("y2", 0) for el in elements)
        page_width = max(1.0, max_x - min_x)
        page_height = max(1.0, max_y - min_y)
        page_diag = (page_width ** 2 + page_height ** 2) ** 0.5

        # y座標を離散化（許容誤差内の要素は同じ行として扱う）
        def y_center(b):
            return (b.get("y1", 0) + b.get("y2", 0)) / 2.0

        y_tolerance = page_height * 0.1  # ほぼ同じ高さとみなす許容範囲（1%）

        # まずy中心でソート
        elements.sort(key=lambda x: (y_center(x["bbox"]), x["bbox"].get("x1", 0)))

        # グルーピング: 近いy（±y_tolerance）を同じ行グループにまとめる
        row_groups: List[List[Dict]] = []
        current_group: List[Dict] = []
        current_y: Optional[float] = None

        for el in elements:
            yc = y_center(el["bbox"]) if el.get("bbox") else 0
            if current_group and current_y is not None and abs(yc - current_y) <= y_tolerance:
                current_group.append(el)
                # 代表yは初期値を維持（ドリフト防止）
            else:
                if current_group:
                    row_groups.append(current_group)
                current_group = [el]
                current_y = yc
        if current_group:
            row_groups.append(current_group)

        # 各行グループ内をxで降順ソートし、行グループ順にフラット化（上→下、同じ行は右→左）
        for g in row_groups:
            g.sort(key=lambda e: e["bbox"].get("x1", 0), reverse=True)
        elements = [e for g in row_groups for e in g]

        # ユークリッド距離の閾値（ページ対角の割合）
        distance_threshold = page_diag * 0.1  # 10% 程度

        def center(b):
            return ((b.get("x1", 0) + b.get("x2", 0)) / 2.0,
                    (b.get("y1", 0) + b.get("y2", 0)) / 2.0)

        def euclid(b1, b2) -> float:
            x1, y1 = center(b1)
            x2, y2 = center(b2)
            dx, dy = (x2 - x1), (y2 - y1)
            return (dx * dx + dy * dy) ** 0.5

        merged: List[Dict] = []
        current_block: Optional[Dict] = None

        for item in elements:
            if item["type"] == "table":
                # 表は独立ブロックとして配置、段落結合はリセット
                if current_block:
                    merged.append(current_block)
                    current_block = None
                merged.append(item)
                continue

            # paragraph
            if current_block is None:
                current_block = {"type": "paragraph", "text": item["text"], "bbox": item["bbox"]}
                continue

            dist = euclid(current_block["bbox"], item["bbox"]) if current_block else 1e9
            if dist <= distance_threshold:
                # 近い段落は結合（単純結合）
                current_block["text"] = current_block["text"].rstrip() + "\n" + item["text"].lstrip()
                # bboxの統合
                cb = current_block["bbox"]
                ib = item["bbox"]
                cb["x1"] = min(cb.get("x1", 0), ib.get("x1", 0))
                cb["y1"] = min(cb.get("y1", 0), ib.get("y1", 0))
                cb["x2"] = max(cb.get("x2", 0), ib.get("x2", 0))
                cb["y2"] = max(cb.get("y2", 0), ib.get("y2", 0))
            else:
                merged.append(current_block)
                current_block = {"type": "paragraph", "text": item["text"], "bbox": item["bbox"]}

        if current_block:
            merged.append(current_block)

        # 出力整形
        lines: List[str] = []
        for block in merged:
            if block["type"] == "table":
                lines.append("**表形式データ**:")
                lines.append(block["text"])  # そのまま複数行
                lines.append("")
            else:
                lines.append(block["text"])  # 結合済み段落
                lines.append("")

        return "\n".join(lines).strip()

    def process_file(self, pdf_path: str, selected_pages: Optional[Set[int]] = None) -> List[Dict[str, str]]:
        """1つのPDFを処理し、各ページの内容を返す

        selected_pages: 1始まりのページ番号集合（Noneなら全ページ）
        """
        print(f"📖 OCR処理: {os.path.basename(pdf_path)}")
        results: List[Dict[str, str]] = []

        # ページバッチング（imageless時30/非imageless時15）
        def batched(lst: List[int], size: int) -> List[List[int]]:
            return [lst[i:i + size] for i in range(0, len(lst), size)]

        if selected_pages:
            zero_based_all = sorted({p - 1 for p in selected_pages if p >= 1})
        else:
            # 全ページ指定: 元PDFからページ数を取得
            with fitz.open(pdf_path) as doc:
                zero_based_all = list(range(len(doc)))

        if not zero_based_all:
            print(f"  ⚠️ 指定ページが不正のためスキップ: {os.path.basename(pdf_path)}")
            return results

        batch_limit = 30 if self.imageless else 15
        for batch in batched(zero_based_all, batch_limit):
            try:
                document, original_page_numbers = self._process_selected_pages_with_documentai(pdf_path, batch)
            except Exception as e:
                msg = str(e)
                # imagelessが効いていない場合のフォールバック: 15ページに再分割
                if self.imageless and ("PAGE_LIMIT_EXCEEDED" in msg or "non-imageless" in msg or "page limit" in msg.lower()):
                    fallback_limit = 15
                    print(f"  ⚠️ imageless未適用の可能性。{fallback_limit}ページに再分割して再試行します。")
                    for small in batched(batch, fallback_limit):
                        document, original_page_numbers = self._process_selected_pages_with_documentai(pdf_path, small)
                        print(f"  🔁 再試行: {len(small)}ページ")
                        for tmp_idx in range(len(document.pages)):
                            orig_page_num = original_page_numbers[tmp_idx]
                            print(f"    📄 ページ {orig_page_num} を抽出中...")
                            content = self._extract_page_content(document, tmp_idx)
                            results.append({
                                "filename": os.path.basename(pdf_path),
                                "page": str(orig_page_num),
                                "content": content,
                            })
                    continue
                else:
                    raise

            print(f"  🔢 ページバッチ処理: {len(batch)}ページ (上限 {batch_limit})")
            for tmp_idx in range(len(document.pages)):
                orig_page_num = original_page_numbers[tmp_idx]
                print(f"    📄 ページ {orig_page_num} を抽出中...")
                content = self._extract_page_content(document, tmp_idx)
                results.append({
                    "filename": os.path.basename(pdf_path),
                    "page": str(orig_page_num),
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
                        default=_BASE_DIR + "/data/ocr_pages.csv",
                        help="出力CSVファイルのパス")
    parser.add_argument("--spec", action="append", required=True,
                        help="処理対象指定: 'filename.pdf:1,3-5,10' の形式。複数指定可。相対パスは--base-dir基準")
    parser.add_argument("--base-dir", default=_BASE_DIR + "/data/input",
                        help="--specで相対パスを解決する基準ディレクトリ")
    parser.add_argument("--imageless", dest="imageless", action="store_true", default=True,
                        help="imagelessモードを有効化（ページ上限の緩和）。デフォルト: 有効")
    parser.add_argument("--no-imageless", dest="imageless", action="store_false",
                        help="imagelessモードを無効化（画像抽出も含む）")

    args = parser.parse_args()

    exporter = OCRPageExporter(imageless=args.imageless)

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

