from __future__ import annotations

import os
from typing import List

import cv2
import orjson
import pandas as pd

from .models import DocumentResult, PageResult, OCRLine, Table


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_document_json(doc: DocumentResult, out_path: str) -> None:
    ensure_dir(os.path.dirname(out_path))
    with open(out_path, 'wb') as f:
        f.write(orjson.dumps(doc.model_dump(), option=orjson.OPT_INDENT_2))


def save_page_image(page_bgr, out_path: str) -> None:
    ensure_dir(os.path.dirname(out_path))
    cv2.imwrite(out_path, page_bgr)


def save_page_lines_csv(lines: List[OCRLine], out_path: str) -> None:
    ensure_dir(os.path.dirname(out_path))
    rows = []
    for ln in lines:
        rows.append(
            {
                'text': ln.text,
                'score': ln.score,
                'x1': ln.bbox.x1,
                'y1': ln.bbox.y1,
                'x2': ln.bbox.x2,
                'y2': ln.bbox.y2,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)


def save_table_csv(table: Table, out_path: str) -> None:
    """Save table as CSV file"""
    ensure_dir(os.path.dirname(out_path))
    rows = []
    for cell in table.cells:
        rows.append({
            'text': cell.text,
            'row': cell.row,
            'col': cell.col,
            'rowspan': cell.rowspan,
            'colspan': cell.colspan,
            'confidence': cell.confidence,
            'x1': cell.bbox.x1,
            'y1': cell.bbox.y1,
            'x2': cell.bbox.x2,
            'y2': cell.bbox.y2,
        })
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)


def save_table_structured_csv(table: Table, out_path: str) -> None:
    """Save table as structured CSV (grid format)"""
    ensure_dir(os.path.dirname(out_path))
    
    # Create grid
    grid = [["" for _ in range(table.cols)] for _ in range(table.rows)]
    
    for cell in table.cells:
        if 0 <= cell.row < table.rows and 0 <= cell.col < table.cols:
            grid[cell.row][cell.col] = cell.text
    
    # Save as CSV
    df = pd.DataFrame(grid)
    df.to_csv(out_path, index=False, header=False)
