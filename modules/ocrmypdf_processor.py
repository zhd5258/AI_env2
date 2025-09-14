#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCRmyPDF处理器模块
用于处理图形格式的PDF文件，提供更好的OCR文本提取能力
"""

import os
import subprocess
import logging
from typing import List, Optional
from PyPDF2 import PdfReader, PdfWriter


class OCRmyPDFProcessor:
    """OCRmyPDF处理器类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def check_ocrmypdf_installed(self) -> Optional[str]:
        """
        检查OCRmyPDF是否已安装
        
        Returns:
            str: OCRmyPDF路径，如果未安装则返回None
        """
        self.logger.info('开始检查OCRmyPDF是否已安装...')

        # 尝试多种方式查找ocrmypdf
        ocrmypdf_paths = [
            '/home/kr/.local/bin/ocrmypdf',  # pipx安装的路径
            'ocrmypdf',  # 直接使用命令名
        ]

        # 通过which命令查找ocrmypdf路径
        try:
            self.logger.debug('尝试使用which命令查找ocrmypdf...')
            which_result = subprocess.run(
                ['which', 'ocrmypdf'], capture_output=True, text=True, timeout=10
            )
            self.logger.debug(
                'which命令执行结果: 返回码={}, 输出={}'.format(
                    which_result.returncode, which_result.stdout.strip()
                )
            )
            if which_result.returncode == 0 and which_result.stdout.strip():
                ocrmypdf_paths.insert(0, which_result.stdout.strip())
                self.logger.info('通过which命令找到ocrmypdf路径: %s', which_result.stdout.strip())
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            self.logger.warning('which命令执行失败: %s', e)

        # 尝试各个路径
        for i, ocrmypdf_path in enumerate(ocrmypdf_paths):
            try:
                self.logger.debug('尝试路径%d: %s', i + 1, ocrmypdf_path)
                result = subprocess.run(
                    [ocrmypdf_path, '--version'],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
                self.logger.info('OCRmyPDF版本: %s', result.stdout.strip())
                self.logger.info('成功找到OCRmyPDF，使用路径: %s', ocrmypdf_path)
                return ocrmypdf_path
            except (
                subprocess.CalledProcessError,
                FileNotFoundError,
                subprocess.TimeoutExpired,
            ) as e:
                self.logger.debug('路径%d失败: %s', i + 1, e)
                continue

        # 如果所有路径都失败了，打印错误信息
        self.logger.error('OCRmyPDF未安装，请先安装:')
        self.logger.error('pip install ocrmypdf')
        self.logger.error('注意：OCRmyPDF还需要安装Tesseract OCR和Ghostscript')
        self.logger.error('已尝试的路径:')
        for path in ocrmypdf_paths:
            self.logger.error('  - %s', path)
        return None

    def ocr_pdf_pages(self, input_pdf: str, output_pdf: str, output_text: str, 
                      start_page: int = 1, end_page: Optional[int] = None) -> bool:
        """
        使用OCRmyPDF处理PDF文件的指定页面范围
        
        Args:
            input_pdf: 输入的PDF文件路径
            output_pdf: 输出的PDF文件路径
            output_text: 输出的文本文件路径
            start_page: 开始页码（从1开始）
            end_page: 结束页码（从1开始），如果为None则处理到最后一页
            
        Returns:
            bool: 处理是否成功
        """
        ocrmypdf_path = self.check_ocrmypdf_installed()
        if not ocrmypdf_path:
            return False

        # 检查输入文件是否存在
        if not os.path.exists(input_pdf):
            self.logger.error('输入文件不存在: %s', input_pdf)
            return False

        # 读取PDF文件
        reader = PdfReader(input_pdf)
        total_pages = len(reader.pages)
        if end_page is None:
            end_page = total_pages

        # 检查页码范围是否有效
        if start_page < 1 or end_page > total_pages or start_page > end_page:
            self.logger.error('无效的页码范围: %d-%d (总页数: %d)', start_page, end_page, total_pages)
            return False

        # 创建输出PDF文件
        writer = PdfWriter()

        # 处理指定页面范围
        for page_num in range(start_page - 1, end_page):
            page = reader.pages[page_num]
            writer.add_page(page)

        # 保存临时PDF文件
        temp_pdf = 'temp.pdf'
        try:
            with open(temp_pdf, 'wb') as f:
                writer.write(f)
        except Exception as e:
            self.logger.error('保存临时PDF文件失败: %s', e)
            return False

        # 构建OCRmyPDF命令
        # 移除了 --clean 和 --remove-background 参数，因为它们依赖于 unpaper 工具
        # 移除了 --skip-text 参数，因为它与 --force-ocr 冲突
        cmd = [
            ocrmypdf_path,  # 使用完整路径
            '--language',
            'chi_sim+eng',  # 指定OCR语言
            '--output-type',
            'pdf',  # 输出PDF格式，避免PDF/A可能的编码问题
            '--force-ocr',  # 强制OCR（即使页面已有文本）
            '--deskew',  # 矫正倾斜的页面
            '--rotate-pages',  # 自动旋转页面
            '--pdf-renderer',
            'hocr',  # 使用hocr渲染器可能有助于解决文本编码问题
            '--sidecar',
            output_text,  # sidecar文本文件路径
            '--tesseract-timeout',
            '120',  # 增加超时时间到120秒，以提高识别质量
            temp_pdf,  # 输入PDF文件（临时文件）
            output_pdf  # 输出PDF文件
        ]

        self.logger.info('执行命令: %s', ' '.join(cmd))
        self.logger.info('正在执行OCR处理，这可能需要几分钟...')

        try:
            # 执行OCRmyPDF命令
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.info('OCR处理完成！')
                if result.stdout:
                    self.logger.debug('标准输出: %s', result.stdout)
                # 清理临时文件
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
                return True
            else:
                self.logger.error('OCR处理失败，返回码: %d', result.returncode)
                if result.stderr:
                    self.logger.error('错误信息: %s', result.stderr)
                # 清理临时文件
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
                return False

        except subprocess.SubprocessError as e:
            self.logger.error('执行OCRmyPDF时出错: %s', e)
            # 清理临时文件
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            return False
        except Exception as e:
            self.logger.error('OCR处理过程中发生错误: %s', e)
            # 清理临时文件
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            return False