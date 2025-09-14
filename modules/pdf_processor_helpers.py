"""
PDF处理辅助模块
包含PDF处理相关的辅助函数
"""

import re
import PyPDF2
import pdfplumber
import pikepdf
from PIL import Image
import pytesseract
import logging
from typing import List, Dict, Any
import io


class PDFProcessorHelpers:
    """PDF处理辅助类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _clean_text(self, text: str) -> str:
        """
        清理提取的文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ''

        # 替换各种换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 替换特殊Unicode字符
        text = text.replace('\u2029', '\n').replace('\u2028', '\n').replace('\u00A0', ' ')
        
        # 修正常见的OCR错误
        text = text.replace('．', '.')  # 全角点号替换为半角
        text = text.replace('，', ',')  # 全角逗号替换为半角
        text = text.replace('（', '(')  # 全角左括号替换为半角
        text = text.replace('）', ')')  # 全角右括号替换为半角
        text = text.replace('：', ':')  # 全角冒号替换为半角
        text = text.replace('；', ';')  # 全角分号替换为半角
        
        # 合并多个换行符为单个换行符
        text = re.sub(r'\n+', '\n', text)
        
        # 合并多个空格为单个空格
        text = re.sub(r' +', ' ', text)
        
        # 去除行首行尾空格
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines]
        text = '\n'.join(cleaned_lines)
        
        # 去除首尾空白
        text = text.strip()
        
        return text

    def _extract_text_with_ocr(self, page, page_number: int) -> str:
        """
        使用OCR从页面提取文本
        
        Args:
            page: pdfplumber页面对象
            page_number: 页码
            
        Returns:
            str: OCR提取的文本
        """
        try:
            # 尝试获取页面图像，使用合适的分辨率
            image = page.to_image(resolution=200)
            
            # 调整图像参数以提高OCR质量
            if hasattr(image, 'reset') and callable(image.reset):
                image = image.reset()
            if hasattr(image, 'scale') and callable(image.scale):
                image = image.scale(2.0)  # 放大图像
            if hasattr(image, 'enhance') and callable(image.enhance):
                image = image.enhance()  # 增强对比度
            
            pil_image = image.original
            
            # 使用pytesseract进行OCR，使用更好的配置
            text = pytesseract.image_to_string(
                pil_image, 
                lang='chi_sim+eng',
                config='--psm 3 --oem 3'  # 使用更准确的识别模式
            )
            
            if text.strip():
                self.logger.debug(f'第 {page_number} 页OCR成功，识别出 {len(text)} 个字符')
                return self._clean_text(text)
            else:
                self.logger.debug(f'第 {page_number} 页OCR未提取到文本')
                return ''
        except Exception as e:
            self.logger.error(f'第 {page_number} 页OCR处理出错: {e}')
            return ''

    def _extract_with_pypdf2(self) -> List[str]:
        """
        使用PyPDF2提取文本（作为备选方案）
        
        Returns:
            List[str]: 每页文本列表
        """
        pages_text = []
        self.logger.info('回退到PyPDF2提取文本...')
        
        try:
            with open(self.file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for i, page in enumerate(pdf_reader.pages):
                    try:
                        text = page.extract_text()
                        if text:
                            text = self._clean_text(text)
                            pages_text.append(text)
                            self.logger.debug(f'PyPDF2第 {i + 1} 页提取到 {len(text)} 个字符')
                        else:
                            pages_text.append('')
                            self.logger.warning(f'PyPDF2第 {i + 1} 页无法提取文本')
                            # 记录失败页面
                            self.failed_pages.append({
                                'page_number': i + 1,
                                'reason': 'PyPDF2无法提取文本',
                                'method': 'PyPDF2'
                            })
                    except Exception as e:
                        self.logger.error(f'PyPDF2处理第 {i + 1} 页时出错: {e}')
                        self.failed_pages.append({
                            'page_number': i + 1,
                            'reason': f'PyPDF2处理出错: {str(e)}',
                            'method': 'PyPDF2'
                        })
                        pages_text.append('')
        except Exception as e:
            self.logger.error(f'使用PyPDF2处理PDF时出错: {e}')
            
        return pages_text

    def _post_process_text(self, text: str) -> str:
        """
        对提取的文本进行后处理
        
        Args:
            text: 原始提取的文本
            
        Returns:
            str: 后处理后的文本
        """
        if not text:
            return ''

        # 清理文本
        text = self._clean_text(text)
        
        # 可以添加更多的后处理逻辑
        # 例如：特定字符替换、格式标准化等
        
        return text