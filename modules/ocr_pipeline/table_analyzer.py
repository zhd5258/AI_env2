from __future__ import annotations

import math
from typing import List, Tuple, Dict, Set
import numpy as np

from .models import OCRLine, Table, TableCell, BBox


class TableAnalyzer:
    """Analyze OCR lines to detect and structure tables"""
    
    def __init__(self, 
                 min_cell_width: int = 20,
                 min_cell_height: int = 15,
                 max_cell_gap: int = 50,
                 min_table_rows: int = 2,
                 min_table_cols: int = 2):
        self.min_cell_width = min_cell_width
        self.min_cell_height = min_cell_height
        self.max_cell_gap = max_cell_gap
        self.min_table_rows = min_table_rows
        self.min_table_cols = min_table_cols
    
    def detect_tables(self, lines: List[OCRLine]) -> List[Table]:
        """Detect tables from OCR lines"""
        if not lines:
            return []
        
        # Group lines by potential table regions
        table_regions = self._group_lines_into_table_regions(lines)
        
        tables = []
        for region_lines in table_regions:
            table = self._analyze_table_structure(region_lines)
            if table and table.rows >= self.min_table_rows and table.cols >= self.min_table_cols:
                tables.append(table)
        
        return tables
    
    def _group_lines_into_table_regions(self, lines: List[OCRLine]) -> List[List[OCRLine]]:
        """Group lines that might form tables based on alignment patterns"""
        if len(lines) < 2:
            return []
        
        # Sort lines by vertical position
        sorted_lines = sorted(lines, key=lambda l: l.bbox.y1)
        
        regions = []
        current_region = [sorted_lines[0]]
        
        for i in range(1, len(sorted_lines)):
            line = sorted_lines[i]
            prev_line = sorted_lines[i-1]
            
            # Check if line belongs to current region
            if self._should_group_with_region(line, current_region):
                current_region.append(line)
            else:
                # Start new region if current one has enough lines
                if len(current_region) >= self.min_table_rows:
                    regions.append(current_region)
                current_region = [line]
        
        # Add last region
        if len(current_region) >= self.min_table_rows:
            regions.append(current_region)
        
        return regions
    
    def _should_group_with_region(self, line: OCRLine, region: List[OCRLine]) -> bool:
        """Check if a line should be grouped with existing region"""
        if not region:
            return True
        
        # Check vertical proximity
        avg_y_gap = sum(line.bbox.y1 - prev.bbox.y2 for prev in region[-3:]) / min(3, len(region))
        if avg_y_gap > self.max_cell_gap:
            return False
        
        # Check horizontal alignment patterns
        region_x_centers = [(l.bbox.x1 + l.bbox.x2) / 2 for l in region]
        line_x_center = (line.bbox.x1 + line.bbox.x2) / 2
        
        # Check if line aligns with existing columns
        aligned = any(abs(line_x_center - xc) < self.max_cell_gap for xc in region_x_centers)
        
        return aligned
    
    def _analyze_table_structure(self, lines: List[OCRLine]) -> Table:
        """Analyze table structure from grouped lines"""
        if not lines:
            return None
        
        # Detect columns by clustering x-positions
        columns = self._detect_columns(lines)
        if len(columns) < self.min_table_cols:
            return None
        
        # Detect rows by clustering y-positions
        rows = self._detect_rows(lines)
        if len(rows) < self.min_table_rows:
            return None
        
        # Create grid and assign cells
        cells = self._assign_cells_to_grid(lines, rows, columns)
        
        # Calculate table bounding box
        table_bbox = self._calculate_table_bbox(cells)
        
        return Table(
            cells=cells,
            rows=len(rows),
            cols=len(columns),
            table_bbox=table_bbox,
            structure=f"{len(rows)}x{len(columns)}"
        )
    
    def _detect_columns(self, lines: List[OCRLine]) -> List[float]:
        """Detect column positions by clustering x-coordinates"""
        x_positions = []
        for line in lines:
            x_positions.extend([line.bbox.x1, line.bbox.x2])
        
        if not x_positions:
            return []
        
        # Simple clustering: group nearby x-positions
        x_positions.sort()
        columns = []
        current_col = x_positions[0]
        
        for x in x_positions[1:]:
            if x - current_col > self.max_cell_gap:
                columns.append(current_col)
                current_col = x
            else:
                current_col = (current_col + x) / 2
        
        columns.append(current_col)
        return columns
    
    def _detect_rows(self, lines: List[OCRLine]) -> List[float]:
        """Detect row positions by clustering y-coordinates"""
        y_positions = []
        for line in lines:
            y_positions.extend([line.bbox.y1, line.bbox.y2])
        
        if not y_positions:
            return []
        
        y_positions.sort()
        rows = []
        current_row = y_positions[0]
        
        for y in y_positions[1:]:
            if y - current_row > self.max_cell_gap:
                rows.append(current_row)
                current_row = y
            else:
                current_row = (current_row + y) / 2
        
        rows.append(current_row)
        return rows
    
    def _assign_cells_to_grid(self, lines: List[OCRLine], rows: List[float], columns: List[float]) -> List[TableCell]:
        """Assign OCR lines to grid cells"""
        cells = []
        
        for line in lines:
            # Find which row and column this line belongs to
            row_idx = self._find_closest_index(line.bbox.y1, rows)
            col_idx = self._find_closest_index(line.bbox.x1, columns)
            
            # Check if cell already exists
            existing_cell = None
            for cell in cells:
                if cell.row == row_idx and cell.col == col_idx:
                    existing_cell = cell
                    break
            
            if existing_cell:
                # Merge text
                existing_cell.text += " " + line.text
                # Expand bounding box
                existing_cell.bbox = BBox(
                    x1=min(existing_cell.bbox.x1, line.bbox.x1),
                    y1=min(existing_cell.bbox.y1, line.bbox.y1),
                    x2=max(existing_cell.bbox.x2, line.bbox.x2),
                    y2=max(existing_cell.bbox.y2, line.bbox.y2)
                )
            else:
                # Create new cell
                cell = TableCell(
                    text=line.text,
                    bbox=line.bbox,
                    row=row_idx,
                    col=col_idx,
                    confidence=line.score
                )
                cells.append(cell)
        
        return cells
    
    def _find_closest_index(self, value: float, positions: List[float]) -> int:
        """Find index of closest position"""
        if not positions:
            return 0
        
        distances = [abs(value - pos) for pos in positions]
        return distances.index(min(distances))
    
    def _calculate_table_bbox(self, cells: List[TableCell]) -> BBox:
        """Calculate overall table bounding box"""
        if not cells:
            return None
        
        x1 = min(cell.bbox.x1 for cell in cells)
        y1 = min(cell.bbox.y1 for cell in cells)
        x2 = max(cell.bbox.x2 for cell in cells)
        y2 = max(cell.bbox.y2 for cell in cells)
        
        return BBox(x1=x1, y1=y1, x2=x2, y2=y2)
    
    def export_table_to_csv(self, table: Table) -> str:
        """Export table to CSV format"""
        if not table.cells:
            return ""
        
        # Create grid
        grid = [["" for _ in range(table.cols)] for _ in range(table.rows)]
        
        for cell in table.cells:
            if 0 <= cell.row < table.rows and 0 <= cell.col < table.cols:
                grid[cell.row][cell.col] = cell.text
        
        # Convert to CSV
        csv_lines = []
        for row in grid:
            csv_lines.append(",".join(f'"{cell}"' for cell in row))
        
        return "\n".join(csv_lines)
