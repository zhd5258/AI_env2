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
from .ocrmypdf_processor import OCRmyPDFProcessor


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

    def ocr_pdf_per_page(self) -> List[str]:
        pages_text = []
        try:
            self.logger.info('开始OCR处理...')
            with pdfplumber.open(self.file_path) as pdf:
                total_pages = len(pdf.pages)
                self.logger.info(f'PDF文件共 {total_pages} 页')

                for i, page in enumerate(pdf.pages):
                    try:
                        self.logger.info(f'正在处理第 {i + 1}/{total_pages} 页')

                        # 转换为图像
                        image = page.to_image(resolution=200)  # 设置合适的分辨率

                        # 调整图像参数以提高OCR质量
                        # 确保reset()和scale()方法存在并且正确调用
                        if hasattr(image, 'reset') and callable(image.reset):
                            image = image.reset()
                        if hasattr(image, 'scale') and callable(image.scale):
                            image = image.scale(2.0)  # 放大图像
                        if hasattr(image, 'enhance') and callable(image.enhance):
                            image = image.enhance()  # 增强对比度

                        # 进行OCR识别，使用更准确的配置
                        self.logger.debug(f'对第 {i + 1} 页进行OCR识别')
                        text = (
                            pytesseract.image_to_string(
                                image.original,
                                lang='chi_sim+eng',
                                config='--psm 3 --oem 3'  # 使用更准确的识别模式
                            )
                            or ''
                        )

                        # 清理OCR结果
                        text = self._clean_text(text)

                        if text.strip():
                            self.logger.debug(
                                f'第 {i + 1} 页OCR成功，识别出 {len(text)} 个字符'
                            )
                        else:
                            self.logger.warning(f'第 {i + 1} 页OCR未识别出文本')

                        pages_text.append(text)

                    except Exception as page_e:
                        self.logger.error(f'处理第 {i + 1} 页时出错: {page_e}')
                        pages_text.append('')
                        # 记录失败页面
                        self.failed_pages.append({
                            'page_number': i + 1,
                            'reason': f'OCR处理失败: {str(page_e)}',
                            'error_type': 'ocr_page_failed',
                        })

        except Exception as e:
            self.logger.error(f'OCR处理失败: {e}')
            self.logger.error('OCR过程中发生严重错误')
            # 记录所有页面为OCR失败
            try:
                with pdfplumber.open(self.file_path) as pdf:
                    for i in range(len(pdf.pages)):
                        self.failed_pages.append({
                            'page_number': i + 1,
                            'reason': f'OCR处理失败: {str(e)}',
                            'error_type': 'ocr_process_failed',
                        })
            except Exception as e2:
                self.logger.error(f'无法获取PDF页数进行OCR失败记录: {e2}')

        if not any(pages_text):
            self.logger.error('OCR未能识别出任何文本')

        return pages_text

    def enhanced_ocr_processing(self) -> List[str]:
        """
        使用OCRmyPDF进行增强的OCR处理，适用于图形格式的PDF文件
        """
        self.logger.info('使用OCRmyPDF进行增强OCR处理...')
        
        # 创建OCRmyPDF处理器实例
        ocr_processor = OCRmyPDFProcessor()
        
        # 生成输出文件路径
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        output_pdf = f'{base_name}_ocr_processed.pdf'
        output_text = f'{base_name}_ocr_text.txt'
        
        try:
            # 使用OCRmyPDF处理整个PDF
            success = ocr_processor.ocr_pdf_pages(
                input_pdf=self.file_path,
                output_pdf=output_pdf,
                output_text=output_text
            )
            
            if success and os.path.exists(output_text):
                # 读取OCRmyPDF生成的文本文件
                with open(output_text, 'r', encoding='utf-8') as f:
                    ocr_text = f.read()
                
                # 尝试将文本按页分割（如果可能）
                # 这里我们简单地将整个文本作为一页返回
                # 在实际应用中，可能需要更复杂的逻辑来分割页面
                pages_text = [ocr_text]
                
                self.logger.info('OCRmyPDF处理成功，提取到文本长度: %d', len(ocr_text))
                
                # 清理临时文件
                for temp_file in [output_pdf, output_text]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                            self.logger.debug('清理临时文件: %s', temp_file)
                        except Exception as e:
                            self.logger.warning('清理临时文件失败: %s - %s', temp_file, e)
                
                return pages_text
            else:
                self.logger.error('OCRmyPDF处理失败')
                return []
                
        except Exception as e:
            self.logger.error('使用OCRmyPDF处理时出错: %s', e)
            return []

    def process_pdf_per_page(self) -> List[str]:
        self.logger.info(f'开始处理PDF文件: {self.file_path}')
        # 重置失败页面记录
        self.failed_pages = []

        # 首先尝试直接提取文本
        self.logger.info('尝试直接提取PDF文本...')
        pages_text = self.extract_text_per_page()

        # 检查提取的文本质量
        total_text = ''.join(pages_text).strip()
        if len(total_text) < 100:
            self.logger.warning(
                f'提取的文本内容很少（长度：{len(total_text)}），可能是扫描件PDF'
            )
            self.logger.info('尝试使用OCR识别...')
            ocr_pages = self.ocr_pdf_per_page()

            # 如果OCR结果比原始提取结果更好，则使用OCR结果
            if len(''.join(ocr_pages).strip()) > len(total_text):
                self.logger.info('使用OCR识别结果（内容更丰富）')
                pages_text = ocr_pages
            else:
                self.logger.warning('OCR结果质量不佳，保留原始提取文本')
                
                # 如果PyTesseract OCR效果也不好，尝试使用OCRmyPDF
                if len(''.join(ocr_pages).strip()) < 100:
                    self.logger.info('PyTesseract OCR效果不佳，尝试使用OCRmyPDF...')
                    enhanced_ocr_pages = self.enhanced_ocr_processing()
                    if len(''.join(enhanced_ocr_pages).strip()) > len(total_text):
                        self.logger.info('使用OCRmyPDF识别结果（内容更丰富）')
                        pages_text = enhanced_ocr_pages
                    else:
                        self.logger.warning('OCRmyPDF结果质量也不佳，保留原始提取文本')

        # 验证每页的文本质量
        for i, page_text in enumerate(pages_text):
            if not page_text.strip():
                self.logger.warning(f'{self.file_path}第 {i + 1} 页未提取到文本内容')
                # 检查是否已经记录了这个页面的失败信息
                page_already_recorded = any(
                    fail_info['page_number'] == i + 1 for fail_info in self.failed_pages
                )
                if not page_already_recorded:
                    self.failed_pages.append(
                        {
                            'page_number': i + 1,
                            'reason': '处理完成后仍未提取到文本内容',
                            'method': 'post_processing',
                        }
                    )
            else:
                self.logger.debug(
                    f'第 {i + 1} 页提取到 {len(page_text.strip())} 个字符'
                )

        self.logger.info(f'PDF处理完成，共处理 {len(pages_text)} 页')
        return pages_text

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

    def get_failed_pages_info(self) -> List[dict]:
        """获取处理失败的页面信息"""
        return self.failed_pages

    def process_pdf(self) -> str:
        """
        Processes the PDF and returns the entire text content as a single string.
        This method is kept for backward compatibility.
        For memory-efficient processing, use process_pdf_per_page().
        """
        pages_text = self.process_pdf_per_page()
        return '\n'.join(pages_text)

    def handle_encrypted_pdf(self, password=None):
        try:
            with pikepdf.open(self.file_path, password=password) as pdf:
                # Save a decrypted version temporarily
                temp_pdf_path = self.file_path + '_decrypted.pdf'
                pdf.save(temp_pdf_path)
                # Process the decrypted PDF
                processor = PDFProcessor(temp_pdf_path)
                return processor.process_pdf()
        except Exception as e:
            self.logger.error(f'Error handling encrypted PDF: {e}')
            # 记录加密PDF处理失败
            self.failed_pages.append(
                {
                    'page_number': 0,  # 0表示整个文档
                    'reason': f'加密PDF处理失败: {str(e)}',
                    'error_type': 'encrypted_pdf_error',
                }
            )
            return ''