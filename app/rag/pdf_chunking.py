from typing import List, Dict
from google.cloud import documentai
from datetime import datetime

# --- test.pyからの関数移植 ---
# analyze_text_orientation, analyze_bounding_box_orientation, get_docai_orientation, get_line_coordinates
# analyze_paragraph_orientation, calculate_paragraph_bounds_from_lines, calculate_paragraph_distance_from_bounds
# should_merge_paragraphs, merge_paragraph_chunks, extract_document_chunks, extract_text_from_layout, get_text_range, create_chunk

# ここにtest.pyの該当関数をそのまま移植する
# ... existing code ... 

def analyze_text_orientation(layout, text: str) -> Dict:
    """
    テキストの向き（縦書き/横書き）を判定する
    """
    # 方法1: Bounding Boxの座標分析（最も信頼性が高い）
    bbox_result = analyze_bounding_box_orientation(layout, text)
    if bbox_result.get("confidence", 0) >= 0.6:
        bbox_result["method"] = "bounding_box"
        return bbox_result
    # 方法2: Document AIのorientationフィールド（フォールバック）
    orientation_result = get_docai_orientation(layout)
    if orientation_result.get("confidence", 0) > 0:
        if bbox_result.get("confidence", 0) > 0.3 and bbox_result.get("is_vertical") != orientation_result.get("is_vertical"):
            bbox_result["method"] = "bounding_box_override"
            bbox_result["note"] = f"Document AI orientation={orientation_result['description']}, but coordinates suggest otherwise"
            return bbox_result
        orientation_result["method"] = "document_ai"
        return orientation_result
    # 方法3: 座標分析（信頼度が低い場合）
    if bbox_result.get("confidence", 0) > 0:
        bbox_result["method"] = "bounding_box_low"
        return bbox_result
    # デフォルト: 横書きと仮定
    return {
        "is_vertical": False,
        "confidence": 0.1,
        "description": "横書き（デフォルト）",
        "method": "default"
    }

def analyze_bounding_box_orientation(layout, text: str) -> Dict:
    """
    Bounding Boxの座標からテキスト方向を判定
    """
    if not layout or not hasattr(layout, 'bounding_poly') or not layout.bounding_poly:
        return {"confidence": 0.0}
    vertices = layout.bounding_poly.vertices
    if not vertices or len(vertices) < 4:
        return {"confidence": 0.0}
    x_coords = [v.x for v in vertices if hasattr(v, 'x')]
    y_coords = [v.y for v in vertices if hasattr(v, 'y')]
    if len(x_coords) < 4 or len(y_coords) < 4:
        return {"confidence": 0.0}
    width = max(x_coords) - min(x_coords)
    height = max(y_coords) - min(y_coords)
    if width <= 0 or height <= 0:
        return {"confidence": 0.0}
    aspect_ratio = width / height
    text_length = len(text.strip())
    if aspect_ratio < 0.15:
        return {
            "is_vertical": True,
            "confidence": 0.95,
            "description": "縦書き（非常に縦長）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }
    elif aspect_ratio < 0.4:
        return {
            "is_vertical": True,
            "confidence": 0.8,
            "description": "縦書き（縦長）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }
    elif aspect_ratio < 0.8:
        return {
            "is_vertical": True,
            "confidence": 0.6,
            "description": "縦書き（やや縦長）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }
    elif aspect_ratio > 4.0:
        return {
            "is_vertical": False,
            "confidence": 0.9,
            "description": "横書き（非常に横長）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }
    elif aspect_ratio > 2.0:
        return {
            "is_vertical": False,
            "confidence": 0.7,
            "description": "横書き（横長）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }
    elif aspect_ratio > 1.2:
        return {
            "is_vertical": False,
            "confidence": 0.5,
            "description": "横書き（やや横長）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }
    else:
        confidence = 0.4 if text_length > 50 else 0.2
        return {
            "is_vertical": False,
            "confidence": confidence,
            "description": f"横書き（正方形、{'長文' if text_length > 50 else '短文'}）",
            "aspect_ratio": round(aspect_ratio, 3),
            "width": width,
            "height": height
        }

def get_docai_orientation(layout) -> Dict:
    """
    Document AIのorientationフィールドから判定
    """
    if not layout or not hasattr(layout, 'orientation'):
        return {"confidence": 0.0}
    orientation_mapping = {
        documentai.Document.Page.Layout.Orientation.PAGE_UP: {"is_vertical": False, "description": "横書き"},
        documentai.Document.Page.Layout.Orientation.PAGE_RIGHT: {"is_vertical": True, "description": "縦書き（右→左）"},
        documentai.Document.Page.Layout.Orientation.PAGE_DOWN: {"is_vertical": False, "description": "逆横書き"},
        documentai.Document.Page.Layout.Orientation.PAGE_LEFT: {"is_vertical": True, "description": "縦書き（左→右）"}
    }
    if layout.orientation in orientation_mapping:
        mapping = orientation_mapping[layout.orientation]
        return {
            "is_vertical": mapping["is_vertical"],
            "confidence": 0.9,
            "description": mapping["description"]
        }
    return {"confidence": 0.0}

def get_line_coordinates(layout) -> Dict:
    """
    行の座標情報を取得する
    """
    if not layout or not hasattr(layout, 'bounding_poly') or not layout.bounding_poly:
        return None
    vertices = layout.bounding_poly.vertices
    if not vertices or len(vertices) < 4:
        return None
    x_coords = [v.x for v in vertices if hasattr(v, 'x')]
    y_coords = [v.y for v in vertices if hasattr(v, 'y')]
    if len(x_coords) < 4 or len(y_coords) < 4:
        return None
    return {
        "min_x": min(x_coords),
        "max_x": max(x_coords),
        "min_y": min(y_coords),
        "max_y": max(y_coords),
        "width": max(x_coords) - min(x_coords),
        "height": max(y_coords) - min(y_coords)
    }

def analyze_paragraph_orientation(lines_data: List[Dict]) -> Dict:
    """
    段落内の複数行から総合的にテキスト方向を判定する
    """
    if not lines_data:
        return {
            "is_vertical": False,
            "confidence": 0.1,
            "description": "横書き（デフォルト）",
            "method": "default"
        }
    orientations = []
    high_confidence_results = []
    all_coordinates = []
    for line_data in lines_data:
        orientation = line_data["orientation"]
        coordinates = line_data["coordinates"]
        orientations.append(orientation)
        if coordinates:
            all_coordinates.append(coordinates)
        if orientation["confidence"] >= 0.7:
            high_confidence_results.append(orientation)
    if len(high_confidence_results) >= 2:
        vertical_count = sum(1 for r in high_confidence_results if r["is_vertical"])
        horizontal_count = len(high_confidence_results) - vertical_count
        if vertical_count > horizontal_count:
            return {
                "is_vertical": True,
                "confidence": 0.9,
                "description": f"縦書き（段落内高信頼度多数決 {vertical_count}/{len(high_confidence_results)}）",
                "method": "paragraph_high_confidence_majority",
                "contributing_lines": len(high_confidence_results)
            }
        elif horizontal_count > vertical_count:
            return {
                "is_vertical": False,
                "confidence": 0.9,
                "description": f"横書き（段落内高信頼度多数決 {horizontal_count}/{len(high_confidence_results)}）",
                "method": "paragraph_high_confidence_majority",
                "contributing_lines": len(high_confidence_results)
            }
    vertical_score = 0
    horizontal_score = 0
    for orientation in orientations:
        weight = orientation["confidence"]
        if orientation["is_vertical"]:
            vertical_score += weight
        else:
            horizontal_score += weight
    total_score = vertical_score + horizontal_score
    if total_score > 0:
        if vertical_score > horizontal_score:
            confidence = min(0.8, vertical_score / total_score)
            return {
                "is_vertical": True,
                "confidence": confidence,
                "description": f"縦書き（段落内重み付け多数決 {vertical_score:.2f}/{total_score:.2f}）",
                "method": "paragraph_weighted_majority",
                "contributing_lines": len(orientations)
            }
        else:
            confidence = min(0.8, horizontal_score / total_score)
            return {
                "is_vertical": False,
                "confidence": confidence,
                "description": f"横書き（段落内重み付け多数決 {horizontal_score:.2f}/{total_score:.2f}）",
                "method": "paragraph_weighted_majority",
                "contributing_lines": len(orientations)
            }
    if all_coordinates:
        min_x = min(coord["min_x"] for coord in all_coordinates)
        max_x = max(coord["max_x"] for coord in all_coordinates)
        min_y = min(coord["min_y"] for coord in all_coordinates)
        max_y = max(coord["max_y"] for coord in all_coordinates)
        paragraph_width = max_x - min_x
        paragraph_height = max_y - min_y
        if paragraph_width > 0 and paragraph_height > 0:
            aspect_ratio = paragraph_width / paragraph_height
            if aspect_ratio < 0.5:
                return {
                    "is_vertical": True,
                    "confidence": 0.6,
                    "description": f"縦書き（段落全体が縦長 {aspect_ratio:.2f}）",
                    "method": "paragraph_overall_bbox",
                    "aspect_ratio": round(aspect_ratio, 3),
                    "contributing_lines": len(all_coordinates)
                }
            elif aspect_ratio > 2.0:
                return {
                    "is_vertical": False,
                    "confidence": 0.6,
                    "description": f"横書き（段落全体が横長 {aspect_ratio:.2f}）",
                    "method": "paragraph_overall_bbox",
                    "aspect_ratio": round(aspect_ratio, 3),
                    "contributing_lines": len(all_coordinates)
                }
    best_orientation = max(orientations, key=lambda x: x["confidence"])
    best_orientation["method"] = "paragraph_best_line"
    best_orientation["description"] += "（段落内最高信頼度）"
    return best_orientation

def calculate_paragraph_bounds_from_lines(lines_data: List[Dict]) -> Dict:
    """
    段落内の行情報から段落全体の境界を計算する
    """
    if not lines_data:
        return None
    valid_coordinates = []
    for line_data in lines_data:
        if line_data["coordinates"]:
            valid_coordinates.append(line_data["coordinates"])
    if not valid_coordinates:
        return None
    min_x = min(coord["min_x"] for coord in valid_coordinates)
    max_x = max(coord["max_x"] for coord in valid_coordinates)
    min_y = min(coord["min_y"] for coord in valid_coordinates)
    max_y = max(coord["max_y"] for coord in valid_coordinates)
    return {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "width": max_x - min_x,
        "height": max_y - min_y
    }

def calculate_paragraph_distance_from_bounds(bounds1: Dict, bounds2: Dict) -> float:
    """
    段落の境界情報から最短距離を計算する（横・縦両方向を考慮）
    """
    if not bounds1 or not bounds2:
        return float('inf')
    x1_min, x1_max = bounds1["min_x"], bounds1["max_x"]
    y1_min, y1_max = bounds1["min_y"], bounds1["max_y"]
    x2_min, x2_max = bounds2["min_x"], bounds2["max_x"]
    y2_min, y2_max = bounds2["min_y"], bounds2["max_y"]
    if x1_max < x2_min:
        x_distance = x2_min - x1_max
    elif x2_max < x1_min:
        x_distance = x1_min - x2_max
    else:
        x_distance = 0
    if y1_max < y2_min:
        y_distance = y2_min - y1_max
    elif y2_max < y1_min:
        y_distance = y1_min - y2_max
    else:
        y_distance = 0
    if x_distance == 0 and y_distance == 0:
        return 0.0
    elif x_distance == 0:
        return y_distance
    elif y_distance == 0:
        return x_distance
    else:
        return (x_distance ** 2 + y_distance ** 2) ** 0.5

def should_merge_paragraphs(para1, para2, max_distance=100, max_chars_per_chunk=1500) -> bool:
    """
    2つの段落を結合すべきかどうかを判定する
    """
    combined_length = len(para1["text"]) + len(para2["text"])
    if combined_length > max_chars_per_chunk:
        return False
    if para1["page_number"] != para2["page_number"]:
        return False
    if para1["orientation"]["is_vertical"] != para2["orientation"]["is_vertical"]:
        return False
    if para1["bounds"] and para2["bounds"]:
        bounds1, bounds2 = para1["bounds"], para2["bounds"]
        distance = calculate_paragraph_distance_from_bounds(bounds1, bounds2)
        if distance > max_distance:
            return False
    else:
        if len(para1["text"].strip()) < 100 and len(para2["text"].strip()) < 100:
            return True
    return True

def merge_paragraph_chunks(chunks: List[Dict], max_distance=20, max_chars_per_chunk=1500) -> List[Dict]:
    """
    段落チャンクを適切に結合する
    """
    if not chunks:
        return chunks
    merged_chunks = []
    i = 0
    while i < len(chunks):
        current_chunk = chunks[i].copy()
        current_chunk["metadata"] = current_chunk["metadata"].copy()
        merged_paragraphs = [current_chunk]
        j = i + 1
        while j < len(chunks):
            next_chunk = chunks[j]
            current_para_data = {
                "text": merged_paragraphs[-1]["text"],
                "orientation": merged_paragraphs[-1]["metadata"]["orientation_details"],
                "bounds": merged_paragraphs[-1].get("_bounds"),
                "page_number": merged_paragraphs[-1]["metadata"]["page_number"]
            }
            next_para_data = {
                "text": next_chunk["text"],
                "orientation": next_chunk["metadata"]["orientation_details"],
                "bounds": next_chunk.get("_bounds"),
                "page_number": next_chunk["metadata"]["page_number"]
            }
            if should_merge_paragraphs(
                current_para_data, 
                next_para_data, 
                max_distance,
                max_chars_per_chunk
            ):
                merged_paragraphs.append(next_chunk)
                j += 1
            else:
                break
        if len(merged_paragraphs) > 1:
            merged_text = "\n".join([p["text"] for p in merged_paragraphs])
            current_chunk["text"] = merged_text
            current_chunk["metadata"]["chunk_type"] = "merged_paragraph"
            current_chunk["metadata"]["original_chunk_count"] = len(merged_paragraphs)
            current_chunk["metadata"]["chunk_length"] = len(merged_text)
            current_chunk["metadata"]["merged_chunk_count"] = len(merged_paragraphs)
            current_chunk["metadata"]["merged_from_ids"] = [p["chunk_id"] for p in merged_paragraphs]
            confidences = [p["metadata"]["orientation_confidence"] for p in merged_paragraphs]
            current_chunk["metadata"]["orientation_confidence"] = sum(confidences) / len(confidences)
            current_chunk["metadata"]["merge_details"] = {
                "merged_texts": [p["text"][:50] + "..." if len(p["text"]) > 50 else p["text"] for p in merged_paragraphs],
                "original_orientations": [p["metadata"]["text_orientation"] for p in merged_paragraphs],
                "merge_criteria": "distance_and_orientation"
            }
        merged_chunks.append(current_chunk)
        i += len(merged_paragraphs)
    for idx, chunk in enumerate(merged_chunks):
        chunk["chunk_id"] = idx
        chunk["metadata"]["final_chunk_id"] = idx
    return merged_chunks

def extract_document_chunks(document: documentai.Document, base_metadata: Dict) -> List[Dict]:
    """
    Document AIの段落構造に基づいてチャンクを抽出する（境界情報付き）
    """
    chunks = []
    chunk_id = 0
    method_stats = {}
    for page_idx, page in enumerate(document.pages):
        if hasattr(page, 'paragraphs') and page.paragraphs:
            for para_idx, paragraph in enumerate(page.paragraphs):
                paragraph_text = extract_text_from_layout(paragraph.layout, document.text)
                if paragraph_text.strip():
                    lines_in_paragraph = []
                    para_start, para_end = get_text_range(paragraph.layout)
                    if hasattr(page, 'lines') and page.lines:
                        for line in page.lines:
                            line_start, line_end = get_text_range(line.layout)
                            if (line_start is not None and line_end is not None and 
                                para_start is not None and para_end is not None and
                                line_start >= para_start and line_end <= para_end):
                                line_text = extract_text_from_layout(line.layout, document.text)
                                if line_text.strip():
                                    line_orientation = analyze_text_orientation(line.layout, line_text)
                                    line_coordinates = get_line_coordinates(line.layout)
                                    lines_in_paragraph.append({
                                        "text": line_text,
                                        "orientation": line_orientation,
                                        "coordinates": line_coordinates
                                    })
                    if lines_in_paragraph:
                        paragraph_orientation = analyze_paragraph_orientation(lines_in_paragraph)
                        paragraph_bounds = calculate_paragraph_bounds_from_lines(lines_in_paragraph)
                    else:
                        paragraph_orientation = analyze_text_orientation(paragraph.layout, paragraph_text)
                        paragraph_bounds = None
                    method = paragraph_orientation["method"]
                    if method not in method_stats:
                        method_stats[method] = 0
                    method_stats[method] += 1
                    chunk = create_chunk(
                        chunk_id=chunk_id,
                        text=paragraph_text.strip(),
                        chunk_type="paragraph",
                        base_metadata=base_metadata,
                        page_number=page_idx + 1,
                        element_index=para_idx,
                        orientation_analysis=paragraph_orientation,
                        paragraph_layout=paragraph.layout,
                        paragraph_bounds=paragraph_bounds
                    )
                    chunks.append(chunk)
                    chunk_id += 1
        elif hasattr(page, 'lines') and page.lines:
            for line_idx, line in enumerate(page.lines):
                line_text = extract_text_from_layout(line.layout, document.text)
                if line_text.strip():
                    orientation_analysis = analyze_text_orientation(line.layout, line_text)
                    line_coordinates = get_line_coordinates(line.layout)
                    method = orientation_analysis["method"]
                    if method not in method_stats:
                        method_stats[method] = 0
                    method_stats[method] += 1
                    chunk = create_chunk(
                        chunk_id=chunk_id,
                        text=line_text.strip(),
                        chunk_type="line",
                        base_metadata=base_metadata,
                        page_number=page_idx + 1,
                        element_index=line_idx,
                        orientation_analysis=orientation_analysis,
                        paragraph_layout=line.layout,
                        paragraph_bounds={"min_x": line_coordinates["min_x"], "max_x": line_coordinates["max_x"], 
                                        "min_y": line_coordinates["min_y"], "max_y": line_coordinates["max_y"], 
                                        "width": line_coordinates["width"], "height": line_coordinates["height"]} if line_coordinates else None
                    )
                    chunks.append(chunk)
                    chunk_id += 1
    base_metadata["orientation_method_stats"] = method_stats
    return chunks

def extract_text_from_layout(layout, full_text: str) -> str:
    """
    レイアウト情報からテキストを抽出する
    """
    if not layout or not layout.text_anchor:
        return ""
    text_segments = []
    for segment in layout.text_anchor.text_segments:
        start_index = int(segment.start_index) if segment.start_index else 0
        end_index = int(segment.end_index) if segment.end_index else len(full_text)
        text_segments.append(full_text[start_index:end_index])
    return "".join(text_segments)

def get_text_range(layout):
    """
    レイアウトのテキスト範囲（開始・終了インデックス）を取得する
    """
    if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
        return None, None
    segments = layout.text_anchor.text_segments
    start_index = int(segments[0].start_index) if segments[0].start_index else 0
    end_index = int(segments[-1].end_index) if segments[-1].end_index else None
    return start_index, end_index

def create_chunk(chunk_id: int, text: str, chunk_type: str, base_metadata: Dict, 
                page_number: int, element_index: int, orientation_analysis: Dict,
                paragraph_layout=None, paragraph_bounds=None) -> Dict:
    """
    チャンクオブジェクトを作成する（境界情報付き）
    """
    chunk = {
        "chunk_id": chunk_id,
        "text": text,
        "metadata": {
            **base_metadata,
            "chunk_type": chunk_type,
            "page_number": page_number,
            "element_index": element_index,
            "chunk_length": len(text),
            "text_orientation": "縦書き" if orientation_analysis["is_vertical"] else "横書き",
            "is_vertical_text": orientation_analysis["is_vertical"],
            "orientation_confidence": orientation_analysis["confidence"],
            "orientation_method": orientation_analysis["method"],
            "orientation_details": orientation_analysis,
            "created_at": datetime.now().isoformat()
        }
    }
    if paragraph_layout:
        chunk["_layout"] = paragraph_layout
    if paragraph_bounds:
        chunk["_bounds"] = paragraph_bounds
        chunk["metadata"]["has_bounds"] = True
    else:
        chunk["metadata"]["has_bounds"] = False
    return chunk 