from __future__ import annotations

from typing import List, Tuple, Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    # x1,y1,x2,y2 in image pixel coordinates
    x1: int
    y1: int
    x2: int
    y2: int


class OCRWord(BaseModel):
    text: str
    score: float = Field(ge=0.0, le=1.0)
    bbox: BBox


class OCRLine(BaseModel):
    text: str
    score: float
    bbox: BBox
    words: List[OCRWord] = Field(default_factory=list)


class TextBlock(BaseModel):
    bbox: BBox
    lines: List[OCRLine]


class TableCell(BaseModel):
    text: str
    bbox: BBox
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    confidence: float = 1.0


class Table(BaseModel):
    cells: List[TableCell] = Field(default_factory=list)
    structure: Optional[str] = None
    rows: int = 0
    cols: int = 0
    table_bbox: Optional[BBox] = None


class PageResult(BaseModel):
    page_index: int
    width: int
    height: int
    text_blocks: List[TextBlock] = Field(default_factory=list)
    lines: List[OCRLine] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)


class DocumentResult(BaseModel):
    source_pdf: str
    dpi: int
    pages: List[PageResult]
