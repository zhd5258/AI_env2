import re
import PyPDF2
import pdfplumber
import pikepdf
from PIL import Image
import pytesseract
import logging
from typing import List
import sys


class PDFProcessor:
    def __init__(self, file_path):
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

    def extract_text_per_page(self) -> List[str]:
        pages_text = []

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
                        text = page.extract_text() or ''
                        text = text.strip()

                        # 检查提取的文本质量
                        if text:
                            self.logger.debug(
                                f'第 {i + 1} 页成功提取 {len(text)} 个字符'
                            )
                        else:
                            self.logger.warning(
                                f'{self.file_path}第 {i + 1} 页未提取到文本'
                            )
                            # 记录失败页面
                            self.failed_pages.append(
                                {
                                    'page_number': i + 1,
                                    'reason': '未提取到文本内容',
                                    'width': width,
                                    'height': height,
                                }
                            )

                        pages_text.append(text)
                    except Exception as page_e:
                        self.logger.error(f'处理第 {i + 1} 页时出错: {page_e}')
                        pages_text.append('')
                        # 记录失败页面
                        self.failed_pages.append(
                            {
                                'page_number': i + 1,
                                'reason': f'处理页面时出错: {str(page_e)}',
                                'error_type': 'pdfplumber_error',
                            }
                        )

        except Exception as e:
            self.logger.error(f'pdfplumber提取失败: {e}')
            self.logger.info('尝试使用PyPDF2作为备选方案...')

            # 如果pdfplumber失败，使用PyPDF2
            try:
                with open(self.file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for i, page in enumerate(reader.pages):
                        try:
                            text = page.extract_text() or ''
                            text = text.strip()
                            if text:
                                self.logger.debug(
                                    f'PyPDF2: 第 {i + 1} 页提取了 {len(text)} 个字符'
                                )
                            else:
                                self.logger.warning(
                                    f'PyPDF2: 第 {i + 1} 页未提取到文本'
                                )
                                # 记录失败页面
                                self.failed_pages.append(
                                    {
                                        'page_number': i + 1,
                                        'reason': 'PyPDF2未提取到文本内容',
                                        'method': 'PyPDF2',
                                    }
                                )
                            pages_text.append(text)
                        except Exception as page_e:
                            self.logger.error(
                                f'PyPDF2处理第 {i + 1} 页时出错: {page_e}'
                            )
                            pages_text.append('')
                            # 记录失败页面
                            self.failed_pages.append(
                                {
                                    'page_number': i + 1,
                                    'reason': f'PyPDF2处理页面时出错: {str(page_e)}',
                                    'error_type': 'pypdf2_error',
                                }
                            )
            except Exception as e2:
                self.logger.error(f'PyPDF2提取也失败了: {e2}')
                self.logger.warning('所有文本提取方法都失败了')
                # 记录所有页面为失败
                try:
                    with open(self.file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        for i in range(len(reader.pages)):
                            self.failed_pages.append(
                                {
                                    'page_number': i + 1,
                                    'reason': f'所有提取方法都失败: {str(e2)}',
                                    'error_type': 'all_methods_failed',
                                }
                            )
                except Exception as e3:
                    self.logger.error(f'无法获取PDF页数: {e3}')

        # 简单的后处理和清理
        pages_text = [self._clean_text(text) for text in pages_text]
        return pages_text

    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        if not text:
            return ''

        # 1. 移除多余的空白字符
        text = ' '.join(text.split())

        # 2. 修正常见的OCR错误
        text = text.replace('．', '.')
        text = text.replace('，', ',')
        text = text.replace('（', '(')
        text = text.replace('）', ')')

        # 3. 确保中文之间没有多余的空格
        text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)

        return text

    def ocr_pdf_per_page(self) -> List[str]:
        pages_text = []
        try:
            self.logger.info('开始OCR处理...')
            with pdfplumber.open(self.file_path) as pdf:
                total_pages = len(pdf.pages)
                self.logger.info(f'PDF文件共 {total_pages} 页')

                for i, page in enumerate(pdf.pages):
                    try:
                        # 使用try-except包装日志记录，以防缓冲区分离错误
                        try:
                            self.logger.info(f'正在处理第 {i + 1}/{total_pages} 页')
                        except ValueError:
                            # 忽略日志记录错误，继续执行主要功能
                            pass

                        # 转换为图像
                        image = page.to_image()

                        # 调整图像参数以提高OCR质量
                        # 确保reset()和scale()方法存在并且正确调用
                        if hasattr(image, 'reset') and callable(image.reset):
                            image = image.reset()
                        if hasattr(image, 'scale') and callable(image.scale):
                            image = image.scale(2.0)  # 放大图像
                        if hasattr(image, 'enhance') and callable(image.enhance):
                            image = image.enhance()  # 增强对比度

                        # 进行OCR识别
                        self.logger.debug(f'对第 {i + 1} 页进行OCR识别')
                        text = (
                            pytesseract.image_to_string(
                                image.original if hasattr(image, 'original') else image,
                                lang='chi_sim+eng',
                                config='--psm 3 --oem 3',  # 使用更准确的识别模式
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
                            # 记录失败页面
                            self.failed_pages.append(
                                {
                                    'page_number': i + 1,
                                    'reason': 'OCR未识别出文本内容',
                                    'method': 'OCR',
                                }
                            )

                        pages_text.append(text)

                    except Exception as page_e:
                        self.logger.error(f'处理第 {i + 1} 页时出错: {page_e}')
                        pages_text.append('')
                        # 记录失败页面
                        self.failed_pages.append(
                            {
                                'page_number': i + 1,
                                'reason': f'OCR处理页面时出错: {str(page_e)}',
                                'error_type': 'ocr_error',
                            }
                        )

        except Exception as e:
            self.logger.error(f'OCR处理失败: {e}')
            self.logger.error('OCR过程中发生严重错误')
            # 记录所有页面为OCR失败
            try:
                with pdfplumber.open(self.file_path) as pdf:
                    for i in range(len(pdf.pages)):
                        self.failed_pages.append(
                            {
                                'page_number': i + 1,
                                'reason': f'OCR处理失败: {str(e)}',
                                'error_type': 'ocr_process_failed',
                            }
                        )
            except Exception as e2:
                self.logger.error(f'无法获取PDF页数进行OCR失败记录: {e2}')

        if not any(pages_text):
            self.logger.error('OCR未能识别出任何文本')

        return pages_text

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

    def get_failed_pages_info(self):
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
