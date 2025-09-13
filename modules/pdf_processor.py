import re
import PyPDF2
import pdfplumber
import pikepdf
from PIL import Image
import pytesseract
import logging
from typing import List
import sys
import os
import json
import hashlib
from .pdf_processor_helpers import PDFProcessorHelpers


class PDFProcessor(PDFProcessorHelpers):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        # 检查标准输出是否可用，如果不可用则使用基本配置
        try:
            logging.basicConfig(level=logging.INFO, 
                              format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                              stream=sys.stdout)
        except (ValueError, AttributeError):
            # 当stdout被重定向或分离时使用基本配置
            try:
                logging.basicConfig(level=logging.INFO,
                                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            except Exception:
                # 最后的备用方案
                pass
        
        self.logger = logging.getLogger(__name__)
        # 添加空处理器以防日志记录失败
        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())
        self.failed_pages = []  # 用于记录处理失败的页面
        
        # 初始化缓存相关属性
        self.cache_dir = "temp_pdf_cache"
        self.cache_enabled = True
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _get_file_hash(self):
        """获取文件的哈希值，用于缓存标识"""
        hash_md5 = hashlib.md5()
        with open(self.file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_cache_path(self):
        """获取缓存文件路径"""
        if not self.cache_enabled:
            return None
            
        file_hash = self._get_file_hash()
        cache_filename = f"{file_hash}.json"
        return os.path.join(self.cache_dir, cache_filename)

    def _load_from_cache(self):
        """从缓存加载文本"""
        if not self.cache_enabled:
            return None
            
        cache_path = self._get_cache_path()
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    self.logger.info(f"从缓存加载PDF文本: {cache_path}")
                    return cached_data.get('pages_text', [])
            except Exception as e:
                self.logger.warning(f"加载缓存失败: {e}")
        return None

    def _save_to_cache(self, pages_text):
        """保存文本到缓存"""
        if not self.cache_enabled:
            return
            
        cache_path = self._get_cache_path()
        if cache_path:
            try:
                cache_data = {
                    'file_path': self.file_path,
                    'file_hash': self._get_file_hash(),
                    'pages_count': len(pages_text),
                    'pages_text': pages_text
                }
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"保存PDF文本到缓存: {cache_path}")
            except Exception as e:
                self.logger.warning(f"保存缓存失败: {e}")

    def extract_text_per_page(self) -> List[str]:
        pages_text = []

        # 首先尝试从缓存加载
        cached_text = self._load_from_cache()
        if cached_text is not None:
            self.logger.info("使用缓存的PDF文本")
            return cached_text

        # 首先尝试使用pdfplumber
        try:
            self.logger.info('使用pdfplumber提取文本...')
            with pdfplumber.open(self.file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        # 获取页面尺寸信息
                        width = page.width() if callable(page.width) else page.width
                        height = page.height() if callable(page.height) else page.height
                        self.logger.debug(
                            f'处理第 {i + 1} 页 (宽: {width}, 高: {height})'
                        )

                        # 提取文本，并进行初步清理
                        text = page.extract_text()
                        if text:
                            # 清理文本
                            text = self._clean_text(text)
                            pages_text.append(text)
                            self.logger.debug(f'第 {i + 1} 页提取到 {len(text)} 个字符')
                        else:
                            # 如果pdfplumber无法提取文本，尝试OCR
                            self.logger.warning(f'第 {i + 1} 页无法提取文本，尝试OCR...')
                            ocr_text = self._extract_text_with_ocr(page, i + 1)
                            if ocr_text:
                                pages_text.append(ocr_text)
                                self.logger.debug(f'第 {i + 1} 页通过OCR提取到 {len(ocr_text)} 个字符')
                            else:
                                pages_text.append('')
                                self.logger.warning(f'第 {i + 1} 页无法提取任何文本')
                    except Exception as e:
                        self.logger.error(f'处理第 {i + 1} 页时出错: {e}')
                        self.failed_pages.append({
                            'page': i + 1,
                            'error': str(e),
                            'method': 'pdfplumber'
                        })
                        pages_text.append('')  # 即使出错也添加空字符串以保持页码一致性

        except Exception as e:
            self.logger.error(f'使用pdfplumber处理PDF时出错: {e}')
            # 回退到PyPDF2
            pages_text = self._extract_with_pypdf2()

        # 保存到缓存
        self._save_to_cache(pages_text)
        
        return pages_text

    def process_pdf_per_page(self) -> List[str]:
        """处理PDF并返回每页的文本列表"""
        pages_text = self.extract_text_per_page()
        
        # 后处理：清理和标准化文本
        processed_pages = []
        for i, text in enumerate(pages_text):
            try:
                # 进一步清理文本
                cleaned_text = self._post_process_text(text)
                processed_pages.append(cleaned_text)
            except Exception as e:
                self.logger.error(f'后处理第 {i + 1} 页文本时出错: {e}')
                processed_pages.append(text)  # 出错时使用原始文本
        
        return processed_pages

    def clear_cache(self):
        """清理当前文件的缓存"""
        if not self.cache_enabled:
            return
            
        cache_path = self._get_cache_path()
        if cache_path and os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                self.logger.info(f"清理缓存文件: {cache_path}")
            except Exception as e:
                self.logger.warning(f"清理缓存文件失败: {e}")
                
    def clear_all_cache(self):
        """清理所有缓存文件"""
        if not self.cache_enabled:
            return
            
        try:
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                self.logger.info(f"清理所有缓存文件: {self.cache_dir}")
            self._ensure_cache_dir()
        except Exception as e:
            self.logger.warning(f"清理所有缓存文件失败: {e}")