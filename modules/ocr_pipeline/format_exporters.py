from __future__ import annotations

import os
from typing import List, Optional
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import DocumentResult, PageResult, Table, TableCell, TextBlock, OCRLine


class DocumentFormatAnalyzer:
    """Analyze document to determine best output format"""
    
    @staticmethod
    def analyze_document(doc: DocumentResult) -> str:
        """Analyze document structure to recommend format"""
        total_tables = sum(len(page.tables) for page in doc.pages)
        total_text_blocks = sum(len(page.text_blocks) for page in doc.pages)
        total_lines = sum(len(page.lines) for page in doc.pages)
        
        # Calculate table density
        table_density = total_tables / max(1, len(doc.pages))
        
        # Calculate average table size
        avg_table_size = 0
        if total_tables > 0:
            all_cells = []
            for page in doc.pages:
                for table in page.tables:
                    all_cells.extend(table.cells)
            avg_table_size = len(all_cells) / total_tables if all_cells else 0
        
        # Decision logic
        if total_tables == 0:
            return "word"  # Pure text document
        elif table_density > 2 or avg_table_size > 20:
            return "excel"  # Table-heavy document
        elif total_tables > 0 and total_text_blocks > total_tables * 3:
            return "word"  # Mixed document with more text
        else:
            return "excel"  # Default to excel for table documents


class WordExporter:
    """Export document to Word format"""
    
    def __init__(self):
        self.doc = Document()
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup document styles"""
        # Title style
        title_style = self.doc.styles['Title']
        title_style.font.size = Pt(16)
        title_style.font.bold = True
        
        # Heading style
        heading_style = self.doc.styles['Heading 1']
        heading_style.font.size = Pt(14)
        heading_style.font.bold = True
    
    def export_document(self, doc_result: DocumentResult, output_path: str) -> None:
        """Export document to Word format"""
        # Add title
        title = self.doc.add_heading(f"OCR结果 - {Path(doc_result.source_pdf).name}", 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add document info
        info_para = self.doc.add_paragraph()
        info_para.add_run(f"源文件: {doc_result.source_pdf}\n")
        info_para.add_run(f"DPI: {doc_result.dpi}\n")
        info_para.add_run(f"页数: {len(doc_result.pages)}\n")
        
        # Process each page
        for page in doc_result.pages:
            self._add_page_content(page)
        
        # Save document
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.doc.save(output_path)
    
    def _add_page_content(self, page: PageResult) -> None:
        """Add page content to document"""
        # Page header
        page_header = self.doc.add_heading(f"第 {page.page_index + 1} 页", level=1)
        
        # Add tables first
        if page.tables:
            self.doc.add_heading("表格", level=2)
            for i, table in enumerate(page.tables):
                self._add_table_to_doc(table, f"表格 {i + 1}")
        
        # Add text blocks
        if page.text_blocks:
            self.doc.add_heading("文本内容", level=2)
            for block in page.text_blocks:
                self._add_text_block_to_doc(block)
        
        # Add page break (except for last page)
        if page.page_index < len(self.doc.paragraphs) - 1:
            self.doc.add_page_break()
    
    def _add_table_to_doc(self, table: Table, title: str) -> None:
        """Add table to Word document"""
        if not table.cells:
            return
        
        # Add table title
        self.doc.add_paragraph(title)
        
        # Create table
        doc_table = self.doc.add_table(rows=table.rows, cols=table.cols)
        doc_table.style = 'Table Grid'
        doc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Fill table cells
        for cell in table.cells:
            if 0 <= cell.row < table.rows and 0 <= cell.col < table.cols:
                doc_cell = doc_table.cell(cell.row, cell.col)
                doc_cell.text = cell.text
                
                # Set cell properties
                for paragraph in doc_cell.paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Auto-fit columns
        for column in doc_table.columns:
            for cell in column.cells:
                cell.width = Inches(1.5)
    
    def _add_text_block_to_doc(self, block: TextBlock) -> None:
        """Add text block to Word document"""
        # Combine all lines in the block
        text = " ".join(line.text for line in block.lines)
        
        # Add paragraph
        para = self.doc.add_paragraph(text)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


class ExcelExporter:
    """Export document to Excel format"""
    
    def __init__(self):
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "OCR结果"
        self._setup_styles()
        self.current_row = 1
    
    def _setup_styles(self):
        """Setup Excel styles"""
        self.title_font = Font(bold=True, size=14)
        self.header_font = Font(bold=True, size=12)
        self.normal_font = Font(size=11)
        self.center_alignment = Alignment(horizontal='center', vertical='center')
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    def export_document(self, doc_result: DocumentResult, output_path: str) -> None:
        """Export document to Excel format"""
        # Add document info
        self._add_document_info(doc_result)
        
        # Process each page
        for page in doc_result.pages:
            self._add_page_content(page)
        
        # Auto-fit columns
        self._auto_fit_columns()
        
        # Save workbook
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.wb.save(output_path)
    
    def _add_document_info(self, doc_result: DocumentResult) -> None:
        """Add document information"""
        self.ws['A1'] = f"OCR结果 - {Path(doc_result.source_pdf).name}"
        self.ws['A1'].font = self.title_font
        self.ws['A1'].alignment = self.center_alignment
        
        self.ws['A3'] = "源文件:"
        self.ws['B3'] = doc_result.source_pdf
        self.ws['A4'] = "DPI:"
        self.ws['B4'] = doc_result.dpi
        self.ws['A5'] = "页数:"
        self.ws['B5'] = len(doc_result.pages)
        
        self.current_row = 7
    
    def _add_page_content(self, page: PageResult) -> None:
        """Add page content to Excel"""
        # Page header
        self.ws[f'A{self.current_row}'] = f"第 {page.page_index + 1} 页"
        self.ws[f'A{self.current_row}'].font = self.header_font
        self.current_row += 2
        
        # Add tables
        if page.tables:
            for i, table in enumerate(page.tables):
                self._add_table_to_excel(table, f"表格 {i + 1}")
                self.current_row += 2
        
        # Add text blocks
        if page.text_blocks:
            self._add_text_blocks_to_excel(page.text_blocks)
            self.current_row += 2
    
    def _add_table_to_excel(self, table: Table, title: str) -> None:
        """Add table to Excel"""
        if not table.cells:
            return
        
        # Add table title
        self.ws[f'A{self.current_row}'] = title
        self.ws[f'A{self.current_row}'].font = self.header_font
        self.current_row += 1
        
        # Create table grid
        grid = [["" for _ in range(table.cols)] for _ in range(table.rows)]
        for cell in table.cells:
            if 0 <= cell.row < table.rows and 0 <= cell.col < table.cols:
                grid[cell.row][cell.col] = cell.text
        
        # Add table data
        start_row = self.current_row
        for row_idx, row_data in enumerate(grid):
            for col_idx, cell_data in enumerate(row_data):
                cell_ref = f"{get_column_letter(col_idx + 1)}{self.current_row}"
                self.ws[cell_ref] = cell_data
                self.ws[cell_ref].font = self.normal_font
                self.ws[cell_ref].alignment = self.center_alignment
                self.ws[cell_ref].border = self.border
            self.current_row += 1
        
        # Add table border
        for row in range(start_row, self.current_row):
            for col in range(table.cols):
                cell_ref = f"{get_column_letter(col + 1)}{row}"
                self.ws[cell_ref].border = self.border
    
    def _add_text_blocks_to_excel(self, blocks: List[TextBlock]) -> None:
        """Add text blocks to Excel"""
        self.ws[f'A{self.current_row}'] = "文本内容"
        self.ws[f'A{self.current_row}'].font = self.header_font
        self.current_row += 1
        
        for block in blocks:
            text = " ".join(line.text for line in block.lines)
            self.ws[f'A{self.current_row}'] = text
            self.ws[f'A{self.current_row}'].font = self.normal_font
            self.current_row += 1
    
    def _auto_fit_columns(self):
        """Auto-fit column widths"""
        for column in self.ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            self.ws.column_dimensions[column_letter].width = adjusted_width


class FormatExporter:
    """Main exporter class that handles different output formats"""
    
    def __init__(self):
        self.analyzer = DocumentFormatAnalyzer()
        self.word_exporter = WordExporter()
        self.excel_exporter = ExcelExporter()
    
    def export_document(self, doc_result: DocumentResult, output_dir: str, 
                       format_choice: str = "auto") -> None:
        """Export document in specified format"""
        if format_choice == "auto":
            format_choice = self.analyzer.analyze_document(doc_result)
        
        if format_choice == "json":
            # JSON is already handled by the main script
            return
        elif format_choice == "word":
            output_path = os.path.join(output_dir, "document.docx")
            self.word_exporter.export_document(doc_result, output_path)
            print(f"[OK] Word文档已保存: {output_path}")
        elif format_choice == "excel":
            output_path = os.path.join(output_dir, "document.xlsx")
            self.excel_exporter.export_document(doc_result, output_path)
            print(f"[OK] Excel文档已保存: {output_path}")
        else:
            raise ValueError(f"不支持的格式: {format_choice}")
    
    def get_recommended_format(self, doc_result: DocumentResult) -> str:
        """Get recommended format for the document"""
        return self.analyzer.analyze_document(doc_result)
