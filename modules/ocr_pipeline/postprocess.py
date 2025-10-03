from __future__ import annotations

from typing import List

from .models import OCRLine, TextBlock, BBox


def group_lines_into_blocks(
    lines: List[OCRLine], y_gap_threshold: int = 12
) -> List[TextBlock]:
    if not lines:
        return []
    blocks: List[TextBlock] = []
    current_block: List[OCRLine] = []

    def merge_bbox(lines: List[OCRLine]) -> BBox:
        x1 = min(l.bbox.x1 for l in lines)
        y1 = min(l.bbox.y1 for l in lines)
        x2 = max(l.bbox.x2 for l in lines)
        y2 = max(l.bbox.y2 for l in lines)
        return BBox(x1=x1, y1=y1, x2=x2, y2=y2)

    prev_bottom = None
    for line in lines:
        if prev_bottom is None:
            current_block = [line]
            prev_bottom = line.bbox.y2
            continue
        if line.bbox.y1 - prev_bottom <= y_gap_threshold:
            current_block.append(line)
        else:
            blocks.append(
                TextBlock(bbox=merge_bbox(current_block), lines=current_block)
            )
            current_block = [line]
        prev_bottom = line.bbox.y2

    if current_block:
        blocks.append(TextBlock(bbox=merge_bbox(current_block), lines=current_block))

    return blocks
