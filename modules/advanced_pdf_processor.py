#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
高级PDF处理器 - 支持多种OCR技术处理图形格式、签名、加密等PDF并输出Markdown格式文档
支持精确识别表格、公式等复杂内容
"""

import os
import re
import sys
import json
import argparse
import time
import io
from pathlib import Path
from typing import List, Optional, Tuple
import logging
import warnings

# 忽略pynvml弃用警告
warnings.filterwarnings(
    'ignore',
    message='The pynvml package is deprecated. Please install nvidia-ml-py instead.',
)

# 设置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 设置MinerU离线模式环境变量(确保始终使用本地模型)
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['MINERU_MODEL_SOURCE'] = 'local'

# 尝试解决PyTorch模型加载问题
os.environ['TORCH_CUDNN_ENABLED'] = '0'  # 禁用cuDNN可能有助于解决某些问题

# MinerU imports
try:
    from mineru.cli.common import do_parse, read_fn
    from mineru.utils.enum_class import MakeMode

    MINERU_AVAILABLE = True
    # 检查必要的函数和类是否可用
    if do_parse is None or read_fn is None or MakeMode is None:
        raise ImportError('MinerU导入不完整')
except ImportError:
    MINERU_AVAILABLE = False
    do_parse = None
    read_fn = None
    MakeMode = None
    logger.warning('MinerU未安装或导入失败,将使用其他OCR方法')

# 第三方库:用于在解析前将PDF页面旋转内容归一化
try:
    from pypdf import PdfReader, PdfWriter, Transformation

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfReader = None
    PdfWriter = None
    Transformation = None
    logger.warning('pypdf未安装,旋转归一化功能将不可用')

# 可选:PyMuPDF (fitz) 用于PDF处理
try:
    import fitz  # PyMuPDF

    PymuPDF_AVAILABLE = True
except ImportError:
    PymuPDF_AVAILABLE = False
    fitz = None
    logger.warning('PyMuPDF (fitz) 未安装')

# 可选:pdfplumber 用于PDF文本提取
try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None
    logger.warning('pdfplumber 未安装')


# =============================================================================
# PDF旋转处理模块
# =============================================================================


class PDFRotationHandler:
    """PDF旋转处理类"""

    def __init__(self):
        pass

    def normalize_pdf_rotation(self, pdf_bytes: bytes) -> Tuple[bytes, int]:
        """
        归一化PDF旋转(内容级旋转矫正)

        Args:
            pdf_bytes: PDF文件字节

        Returns:
            (矫正后的PDF字节, 旋转角度)
        """
        if not PYPDF_AVAILABLE or PdfReader is None or PdfWriter is None:
            logger.warning('pypdf未安装,跳过旋转归一化')
            return pdf_bytes, 0

        try:
            # 读取PDF
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))

            # 检查第一页是否有旋转
            first_page = pdf_reader.pages[0]
            rotation = first_page.get('/Rotate', 0)

            # 如果没有旋转或旋转角度为0，则无需处理
            if not rotation:
                return pdf_bytes, 0

            logger.info(f'检测到PDF旋转角度: {rotation}度')

            # 创建新的PDF写入器
            pdf_writer = PdfWriter()

            # 处理每一页
            for page in pdf_reader.pages:
                # 获取页面旋转角度
                page_rotation = page.get('/Rotate', 0)
                if page_rotation:
                    # 应用反向旋转
                    page.transfer_rotation_to_content()
                    page.rotate(-page_rotation)  # 反向旋转

                pdf_writer.add_page(page)

            # 将矫正后的PDF写入字节流
            output_stream = io.BytesIO()
            pdf_writer.write(output_stream)
            normalized_pdf_bytes = output_stream.getvalue()

            logger.info('PDF旋转归一化完成')
            return normalized_pdf_bytes, rotation

        except Exception as e:
            logger.error(f'PDF旋转归一化失败: {e}')
            return pdf_bytes, 0

    def rotate_pdf_pages(self, pdf_path: str, angle: int) -> str:
        """
        旋转PDF页面

        Args:
            pdf_path: PDF文件路径
            angle: 旋转角度 (90, 180, 270)

        Returns:
            旋转后的PDF文件路径
        """
        if not PYPDF_AVAILABLE or PdfReader is None or PdfWriter is None:
            raise RuntimeError('pypdf未安装,无法旋转PDF')

        if angle not in [90, 180, 270]:
            raise ValueError('旋转角度必须是90、180或270度')

        try:
            # 打开原始PDF
            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            # 旋转每一页
            for page in reader.pages:
                page.rotate(angle)
                writer.add_page(page)

            # 保存旋转后的PDF
            original_name = Path(pdf_path).stem
            rotated_pdf_path = (
                Path(pdf_path).parent / f'{original_name}_rotated_{angle}.pdf'
            )

            with open(rotated_pdf_path, 'wb') as f:
                writer.write(f)

            logger.info(f'PDF旋转完成: {pdf_path} → {rotated_pdf_path}')
            return str(rotated_pdf_path)

        except Exception as e:
            logger.error(f'PDF旋转失败: {e}')
            raise


# =============================================================================
# MinerU处理模块
# =============================================================================


class MinerUProcessor:
    """MinerU处理器类"""

    def __init__(self, output_dir: Path, temp_dir: Path):
        self.output_dir = output_dir
        self.temp_dir = temp_dir

        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

    def process_with_mineru(
        self,
        pdf_path: str,
        output_format: str = 'markdown',
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = 'ch',
        dpi: int = 300,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> str:
        """
        使用MinerU处理PDF文件

        Args:
            pdf_path: PDF文件路径
            output_format: 输出格式 ('markdown' 或 'json')
            enable_formula: 是否启用公式识别
            enable_table: 是否启用表格识别
            language: 语言 ('ch' 中文, 'en' 英文)
            dpi: 渲染图像用于OCR的分辨率 (默认: 300)
            start_page: 开始页码(从1开始,可选)
            end_page: 结束页码(包含,可选)

        Returns:
            输出文件路径
        """
        if not MINERU_AVAILABLE:
            raise RuntimeError('MinerU未安装,无法使用此方法')

        # 环境变量已在类初始化时设置,确保使用本地模型
        try:
            # 读取PDF文件
            pdf_bytes = read_fn(pdf_path)  # type: ignore

            # 进行内容级旋转归一化
            try:
                rotation_handler = PDFRotationHandler()
                pdf_bytes, rotated_pages = rotation_handler.normalize_pdf_rotation(
                    pdf_bytes
                )

                if rotated_pages > 0:
                    logger.info(
                        f'页面级旋转检测完成:内容矫正 {rotated_pages} 页 → {pdf_path}'
                    )
                else:
                    logger.info(f'页面级旋转检测完成，未发现需要旋转的页面: {pdf_path}')
            except Exception as e:
                logger.warning(f'页面级旋转检测失败,使用原始PDF: {e}')

            file_name = Path(pdf_path).stem
            logger.info(f'处理文件: {pdf_path}, 文件名: {file_name}')

            # 确保文件名是安全的，移除可能导致问题的特殊字符
            file_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', file_name)
            file_name = file_name.strip(' .')
            if not file_name:
                file_name = 'pdf_document'
            logger.info(f'安全处理后的文件名: {file_name}')

            # 根据输出格式设置MakeMode
            if output_format.lower() == 'markdown':
                # 保持使用MM_MD模式，但调整其他参数来提取更多文本内容
                make_mode = MakeMode.MM_MD  # type: ignore
            elif output_format.lower() == 'json':
                make_mode = MakeMode.CONTENT_LIST  # type: ignore
            else:
                raise ValueError("不支持的输出格式,仅支持 'markdown' 或 'json'")

            # 使用Mineru解析PDF,增加更多参数以提高识别效果
            # 使用temp目录进行处理,避免污染output目录
            logger.info(f'开始使用MinerU处理PDF,处理目录: {self.temp_dir}')

            # 在处理前检查temp目录
            if not self.temp_dir.exists():
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f'创建temp目录: {self.temp_dir}')

            # 确保temp目录干净,删除可能存在的旧文件
            self._cleanup_temp_dir_for_file(file_name)

            # 使用MinerU处理PDF，让其自动判断是否需要OCR
            logger.info('使用MinerU处理PDF（自动判断OCR需求）')
            do_parse(  # type: ignore
                output_dir=str(self.temp_dir),
                pdf_file_names=[file_name],
                pdf_bytes_list=[pdf_bytes],
                formula_enable=enable_formula,
                table_enable=enable_table,
                p_lang_list=[language],
                f_make_md_mode=make_mode,
                backend='pipeline',
                ocr=True,  # 启用OCR功能
                parse_method='auto',  # 自动判断处理方式
                f_dump_md=True,
                f_dump_content_list=True,
                ocr_post_process=True,
                txt_keep_one_line=False,
                smart_layout=True,
                table_recognition=True,
                formula_recognition=enable_formula,
                force_ocr=False,  # 不强制OCR，让MinerU自动判断
                table_cell_merge=True,
                table_line_recognition=True,
                rotation_detection=True,
                auto_rotate=True,
                dpi=dpi,  # 设置渲染DPI
                start_page=start_page,  # 传递起始页码
                end_page=end_page,  # 传递结束页码
            )
            logger.info('MinerU处理完成')

            # 添加更详细的调试信息：检查temp目录中生成的文件
            if self.temp_dir.exists():
                generated_files = list(self.temp_dir.iterdir())
                logger.info(f'MinerU处理后temp目录中的文件数量: {len(generated_files)}')
                for f in generated_files:
                    logger.info(f'  文件: {f.name} (大小: {f.stat().st_size} 字节)')
            else:
                logger.warning('MinerU处理后temp目录不存在')

            # 特别检查是否有与file_name相关的文件
            related_files = []
            if self.temp_dir.exists():
                related_files = [
                    f for f in self.temp_dir.iterdir() if file_name in f.name
                ]
                logger.info(
                    f'与文件名 {file_name} 相关的文件数量: {len(related_files)}'
                )
                for f in related_files:
                    logger.info(f'  相关文件: {f.name} (大小: {f.stat().st_size} 字节)')

            # 如果没有找到精确匹配的文件，尝试查找可能的MD文件
            if not related_files:
                logger.info('未找到与文件名直接相关的文件，尝试查找所有MD文件...')
                md_files = list(self.temp_dir.rglob('*.md'))
                if md_files:
                    logger.info(f'找到 {len(md_files)} 个MD文件')
                    # 优先选择文件名最接近的文件
                    best_match = None
                    best_score = 0
                    for md_file in md_files:
                        # 计算文件名相似度
                        name_similarity = self._calculate_filename_similarity(
                            file_name, md_file.stem
                        )
                        if name_similarity > best_score:
                            best_score = name_similarity
                            best_match = md_file

                    if best_match:
                        logger.info(
                            f'选择最佳匹配文件: {best_match.name} (相似度: {best_score})'
                        )
                        # 重命名文件以确保与原始PDF文件名对应
                        target_path = self.temp_dir / f'{file_name}.md'
                        try:
                            best_match.rename(target_path)
                            logger.info(
                                f'已重命名文件: {best_match.name} → {target_path.name}'
                            )
                            related_files = [target_path]
                        except Exception as e:
                            logger.warning(f'重命名文件失败: {e}')
                    else:
                        # 如果没有找到好的匹配，使用第一个文件
                        target_path = self.temp_dir / f'{file_name}.md'
                        try:
                            md_files[0].rename(target_path)
                            logger.info(
                                f'重命名文件: {md_files[0].name} → {target_path.name}'
                            )
                            related_files = [target_path]
                        except Exception as e:
                            logger.warning(f'重命名文件失败: {e}')

            # 初始化keep_ext变量
            keep_ext = '.md'  # 默认值

            # 处理完成后,先移动最终结果到output目录,再清理中间文件
            # 这样可以确保最终输出文件不会被清理过程误删
            try:
                keep_ext = '.md' if make_mode == MakeMode.MM_MD else '.json'  # type: ignore

                # 首先将最终输出文件从temp目录移动到output目录
                logger.info('开始移动最终输出文件')
                logger.info(f'期望的输出文件名: {file_name}{keep_ext}')
                logger.info(f'Temp目录: {self.temp_dir}')
                logger.info(f'Output目录: {self.output_dir}')

                # 调试：列出temp目录中的所有文件
                if self.temp_dir.exists():
                    temp_files = list(self.temp_dir.iterdir())
                    logger.info(f'Temp目录中的文件: {[f.name for f in temp_files]}')
                else:
                    logger.warning('Temp目录不存在')

                move_success = self._move_final_output(file_name, make_mode)

                # 检查移动是否成功
                output_file = self.output_dir / f'{file_name}{keep_ext}'
                if not move_success or not output_file.exists():
                    logger.error(f'文件移动失败,无法找到输出文件: {output_file}')
                    # 尝试在temp目录中直接查找可能的文件
                    if self.temp_dir.exists():
                        # 查找所有可能的文件
                        possible_files = list(self.temp_dir.glob(f'{file_name}*'))
                        logger.info(
                            f'Temp目录中找到的可能文件: {[f.name for f in possible_files]}'
                        )

                        # 如果找到任何文件，尝试移动第一个
                        if possible_files:
                            source_file = possible_files[0]
                            logger.info(f'尝试移动找到的文件: {source_file}')
                            try:
                                import shutil

                                shutil.move(str(source_file), str(output_file))
                                logger.info(
                                    f'成功移动文件: {source_file} → {output_file}'
                                )
                                move_success = True
                            except Exception as move_err:
                                logger.error(f'移动找到的文件时出错: {move_err}')

                    # 如果仍然失败，抛出异常
                    if not move_success or not output_file.exists():
                        raise RuntimeError(
                            f'无法找到处理结果文件: {file_name}{keep_ext}'
                        )

                # 验证关键信息完整性
                # 注释掉硬编码的关键信息验证，因为不同文件的关键信息不同
                # if keep_ext == '.md':
                #     self._verify_and_enhance_key_information(output_file)

                # 改用更通用的关键信息验证方法
                if keep_ext == '.md':
                    self._verify_key_information(output_file)

                # 然后优化Markdown格式(如果需要)
                if output_file.exists() and keep_ext == '.md':
                    logger.info('开始优化Markdown格式')
                    self._optimize_markdown_format(output_file)

                # 最后清理所有中间文件(包括图片、JSON、PDF等)
                # 注意:清理操作应该在移动最终文件之后进行
                logger.info('开始清理中间文件')
                self._cleanup_mineru_intermediate_files(file_name)

                # 返回最终输出文件路径(直接在output_dir根目录下)
                final_output_path = self.output_dir / f'{file_name}{keep_ext}'
                logger.info(f'最终输出文件路径: {final_output_path}')
                return str(final_output_path)

            except Exception as e:
                logger.warning(f'后处理过程中出错: {e}')
                raise

        except Exception as e:
            logger.error(f'使用MinerU处理PDF时出错: {e}')
            raise

    def _cleanup_temp_dir_for_file(self, file_name: str) -> None:
        """
        在处理文件之前清理temp目录中与该文件相关的旧文件

        Args:
            file_name: 文件名(不含扩展名)
        """
        try:
            if self.temp_dir.exists():
                # 删除与该文件名相关的所有文件和目录
                for item in self.temp_dir.rglob('*'):
                    # 检查文件或目录名是否与文件名相关
                    if file_name in item.name:
                        try:
                            if item.is_file():
                                item.unlink()
                                logger.info(f'已删除旧临时文件: {item}')
                            elif item.is_dir():
                                import shutil

                                shutil.rmtree(item, ignore_errors=True)
                                logger.info(f'已删除旧临时目录: {item}')
                        except Exception as e:
                            logger.warning(f'删除旧临时文件/目录失败: {item}, {e}')
        except Exception as e:
            logger.warning(f'清理temp目录时出错: {e}')

    def _verify_key_information(self, md_file_path: Path) -> bool:
        """
        验证关键信息完整性

        Args:
            md_file_path: Markdown文件路径

        Returns:
            是否验证成功
        """
        try:
            if not md_file_path.exists():
                logger.warning(f'文件不存在: {md_file_path}')
                return False

            # 读取文件内容
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查是否包含基本的Markdown结构
            if not content.strip():
                logger.warning(f'文件内容为空: {md_file_path}')
                return False

            # 检查是否包含标题
            if not re.search(r'^#\s+.+', content, re.MULTILINE):
                logger.warning(f'文件缺少标题: {md_file_path}')
                return False

            logger.info(f'关键信息验证通过: {md_file_path}')
            return True

        except Exception as e:
            logger.warning(f'验证关键信息时出错: {e}')
            return False

    def _calculate_filename_similarity(
        self, original_name: str, target_name: str
    ) -> float:
        """
        计算两个文件名的相似度

        Args:
            original_name: 原始文件名
            target_name: 目标文件名

        Returns:
            相似度分数 (0-1)
        """
        # 简单的相似度计算方法
        import difflib

        return difflib.SequenceMatcher(
            None, original_name.lower(), target_name.lower()
        ).ratio()

    def _move_final_output(self, file_name: str, make_mode) -> bool:
        """
        移动最终输出文件到output目录

        Args:
            file_name: 文件名(不含扩展名)
            make_mode: MinerU的MakeMode

        Returns:
            是否移动成功
        """
        try:
            # 确定文件扩展名
            if not MINERU_AVAILABLE:
                raise RuntimeError('MinerU的MakeMode不可用')
            ext = '.md' if make_mode == MakeMode.MM_MD else '.json'  # type: ignore

            # 构建源文件路径(temp目录中)
            source_file = self.temp_dir / f'{file_name}{ext}'

            # 添加详细的调试信息
            logger.info(f'尝试移动文件: {source_file}')
            logger.info(f'源文件是否存在: {source_file.exists()}')
            logger.info(f'源文件完整路径: {source_file.absolute()}')

            # 检查源文件是否存在
            if not source_file.exists():
                logger.warning(f'源文件不存在: {source_file}')
                # 尝试查找可能的文件
                if self.temp_dir.exists():
                    # 查找所有可能的文件，包括不同扩展名的文件
                    possible_files = list(self.temp_dir.iterdir())
                    logger.info(
                        f'temp目录中的所有文件: {[f.name for f in possible_files]}'
                    )

                    # 首先查找精确匹配文件名的文件
                    exact_matches = [
                        f for f in possible_files if f.name.startswith(file_name)
                    ]
                    logger.info(f'精确匹配的文件: {[f.name for f in exact_matches]}')

                    if exact_matches:
                        # 优先选择匹配扩展名的文件
                        matching_ext_files = [
                            f for f in exact_matches if f.suffix == ext
                        ]
                        if matching_ext_files:
                            source_file = matching_ext_files[0]
                            logger.info(f'使用精确匹配的文件作为源文件: {source_file}')
                        else:
                            # 如果没有匹配扩展名的文件，使用第一个精确匹配的文件
                            source_file = exact_matches[0]
                            logger.info(
                                f'使用第一个精确匹配的文件作为源文件: {source_file}'
                            )
                    else:
                        # 如果没有精确匹配，尝试模糊匹配
                        fuzzy_matches = [
                            f for f in possible_files if file_name in f.name
                        ]
                        logger.info(
                            f'模糊匹配的文件: {[f.name for f in fuzzy_matches]}'
                        )

                        if fuzzy_matches:
                            source_file = fuzzy_matches[0]
                            logger.info(f'使用模糊匹配的文件作为源文件: {source_file}')
                        else:
                            logger.warning(
                                f'在temp目录中未找到任何与 {file_name} 相关的文件'
                            )
                            return False

            # 构建目标文件路径(output目录中)
            target_file = self.output_dir / f'{file_name}{ext}'
            logger.info(f'目标文件路径: {target_file}')
            logger.info(f'目标文件完整路径: {target_file.absolute()}')

            # 确保目标目录存在
            self.output_dir.mkdir(exist_ok=True)
            logger.info(f'确保输出目录存在: {self.output_dir}')

            # 移动文件或目录
            import shutil

            # 如果目标文件已存在，先删除
            if target_file.exists():
                if target_file.is_dir():
                    shutil.rmtree(target_file)
                else:
                    target_file.unlink()
                logger.info(f'已删除已存在的目标文件: {target_file}')

            # 检查源是文件还是目录
            if source_file.is_dir():
                logger.info(f'源是目录，查找其中的MD文件: {source_file}')
                # 如果是目录，查找其中的.md文件
                # 根据MinerU的输出结构，MD文件在ocr子目录中
                md_file_path = source_file / 'auto' / f'{file_name}{ext}'
                if not md_file_path.exists():
                    md_file_path = source_file / 'ocr' / f'{file_name}{ext}'

                if md_file_path.exists():
                    logger.info(f'找到MD文件: {md_file_path}')
                    # 读取文件内容并修复编码问题
                    try:
                        # 先尝试以UTF-8编码读取
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # 如果UTF-8失败，尝试以GBK编码读取
                        with open(md_file_path, 'r', encoding='gbk') as f:
                            content = f.read()

                    # 修复可能的编码问题
                    if '\u0000' in content:  # 检查是否有空字符
                        content = content.replace('\u0000', '')

                    # 写入目标文件
                    with open(target_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(
                        f'已复制并修复编码的MD文件: {md_file_path} → {target_file}'
                    )
                else:
                    # 如果特定路径不存在，查找所有.md文件
                    md_files = list(source_file.rglob(f'*{ext}'))
                    if md_files:
                        logger.info(f'找到MD文件: {md_files[0]}')
                        # 读取文件内容并修复编码问题
                        try:
                            # 先尝试以UTF-8编码读取
                            with open(md_files[0], 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            # 如果UTF-8失败，尝试以GBK编码读取
                            with open(md_files[0], 'r', encoding='gbk') as f:
                                content = f.read()

                        # 修复可能的编码问题
                        if '\u0000' in content:  # 检查是否有空字符
                            content = content.replace('\u0000', '')

                        # 写入目标文件
                        with open(target_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                        logger.info(
                            f'已复制并修复编码的MD文件: {md_files[0]} → {target_file}'
                        )
                    else:
                        # 如果没有找到MD文件，移动整个目录
                        logger.warning(f'未找到MD文件，移动整个目录: {source_file}')
                        shutil.move(str(source_file), str(target_file))
                        logger.info(f'已移动目录: {source_file} → {target_file}')
            else:
                # 源是文件，读取内容并修复编码问题
                try:
                    # 先尝试以UTF-8编码读取
                    with open(source_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # 如果UTF-8失败，尝试以GBK编码读取
                    with open(source_file, 'r', encoding='gbk') as f:
                        content = f.read()

                # 修复可能的编码问题
                if '\u0000' in content:  # 检查是否有空字符
                    content = content.replace('\u0000', '')

                # 写入目标文件
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f'已复制并修复编码的文件: {source_file} → {target_file}')

            return True

        except Exception as e:
            logger.error(f'移动最终输出文件时出错: {e}')
            import traceback

            logger.error(f'详细错误信息: {traceback.format_exc()}')
            return False

    def _cleanup_mineru_intermediate_files(self, file_name: str) -> None:
        """
        清理MinerU的中间文件

        Args:
            file_name: 文件名(不含扩展名)
        """
        try:
            # 清理temp目录中的所有中间文件
            if self.temp_dir.exists():
                for item in self.temp_dir.iterdir():
                    try:
                        # 删除与文件名相关的所有文件和目录
                        if file_name in item.name:
                            if item.is_file():
                                item.unlink()
                                logger.info(f'已删除中间文件: {item}')
                            elif item.is_dir():
                                import shutil

                                shutil.rmtree(item, ignore_errors=True)
                                logger.info(f'已删除中间目录: {item}')
                    except Exception as e:
                        logger.warning(f'删除中间文件/目录失败: {item}, {e}')

        except Exception as e:
            logger.warning(f'清理中间文件时出错: {e}')

    def _optimize_markdown_format(self, md_file_path: Path) -> None:
        """
        优化Markdown格式

        Args:
            md_file_path: Markdown文件路径
        """
        try:
            if not md_file_path.exists():
                logger.warning(f'文件不存在: {md_file_path}')
                return

            # 读取原始内容
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 优化内容
            optimized_content = self._enhance_table_display(content)

            # 写回文件
            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(optimized_content)

            logger.info(f'Markdown格式优化完成: {md_file_path}')

        except Exception as e:
            logger.warning(f'优化Markdown格式时出错: {e}')

    def _enhance_table_display(self, content: str) -> str:
        """
        增强表格显示效果（已简化）
        """
        # 直接返回原始内容，不进行额外处理
        return content

    def _is_table_line(self, line: str) -> bool:
        """
        判断是否是表格行（已简化）
        """
        # 简化实现
        return '|' in line and line.count('|') >= 2

    def _is_table_separator(self, line: str) -> bool:
        """
        判断是否是表格分隔行（已简化）
        """
        # 简化实现
        return '|' in line and '---' in line


# =============================================================================
# 其他OCR处理器模块
# =============================================================================


class OtherOCRProcessors:
    """其他OCR处理器类"""

    def __init__(self, output_dir: Path, temp_dir: Path):
        self.output_dir = output_dir
        self.temp_dir = temp_dir

    def process_with_pymupdf(self, pdf_path: str) -> str:
        """
        使用PyMuPDF处理PDF

        Args:
            pdf_path: PDF文件路径

        Returns:
            输出文件路径
        """
        if not PymuPDF_AVAILABLE or fitz is None:
            raise RuntimeError('PyMuPDF (fitz) 未安装')

        logger.info(f'开始使用PyMuPDF处理PDF: {pdf_path}')
        start_time = time.time()

        try:
            # 打开PDF文件
            doc = fitz.open(pdf_path)  # type: ignore

            # 生成输出文件名 - 使用临时名称，主处理器会重命名
            file_name = Path(pdf_path).stem
            output_file = self.output_dir / f'{file_name}_pymupdf_temp.md'

            # 提取文本内容
            with open(output_file, 'w', encoding='utf-8') as f:
                for page_num in range(len(doc)):
                    # 获取页面
                    page = doc[page_num]  # type: ignore

                    # 提取文本
                    text = page.get_text()  # type: ignore

                    # 写入页面标题
                    f.write(f'## 第{page_num + 1}页\n\n')

                    # 写入文本内容
                    if text.strip():
                        f.write(text)
                    else:
                        # 如果没有文本，尝试OCR
                        try:
                            # 对页面进行OCR处理
                            pix = page.get_pixmap(dpi=300)  # type: ignore
                            img_data = pix.tobytes('ppm')
                            temp_img_path = (
                                self.temp_dir / f'temp_page_{page_num + 1}.png'
                            )
                            with open(temp_img_path, 'wb') as img_f:
                                img_f.write(img_data)

                            # 使用PyMuPDF的OCR功能
                            # 注意：这需要安装额外的OCR引擎
                            ocr_text = page.get_text_ocr(dpi=300)  # type: ignore
                            if ocr_text.strip():
                                f.write(ocr_text)
                            else:
                                f.write('> 此页面内容无法识别\n\n')

                            # 清理临时图像文件
                            if temp_img_path.exists():
                                temp_img_path.unlink()

                        except Exception as ocr_e:
                            logger.warning(f'第{page_num + 1}页OCR处理失败: {ocr_e}')
                            f.write('> 此页面内容无法识别\n\n')

                    f.write('\n---\n\n')

            doc.close()  # type: ignore

            elapsed_time = time.time() - start_time
            logger.info(
                f'PyMuPDF处理完成: {pdf_path} → {output_file} (耗时: {elapsed_time:.2f}秒)'
            )
            return str(output_file)

        except Exception as e:
            logger.error(f'使用PyMuPDF处理PDF时出错: {e}')
            raise

    def process_with_pdfplumber(self, pdf_path: str) -> str:
        """
        使用pdfplumber处理PDF

        Args:
            pdf_path: PDF文件路径

        Returns:
            输出文件路径
        """
        if not PDFPLUMBER_AVAILABLE or pdfplumber is None:
            raise RuntimeError('pdfplumber 未安装')

        logger.info(f'开始使用pdfplumber处理PDF: {pdf_path}')
        start_time = time.time()

        try:
            # 生成输出文件名 - 使用临时名称，主处理器会重命名
            file_name = Path(pdf_path).stem
            output_file = self.output_dir / f'{file_name}_pdfplumber_temp.md'

            with open(output_file, 'w', encoding='utf-8') as f:
                with pdfplumber.open(pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        # 写入页面标题
                        f.write(f'## 第{page_num + 1}页\n\n')

                        # 提取文本
                        text = page.extract_text()
                        if text:
                            f.write(text)
                        else:
                            f.write('> 此页面内容无法识别\n\n')

                        # 提取表格
                        tables = page.extract_tables()
                        if tables:
                            for i, table in enumerate(tables):
                                f.write(f'\n### 表格 {i + 1}\n\n')
                                # 转换为Markdown表格
                                for row_num, row in enumerate(table):
                                    # 过滤掉空行
                                    if not any(
                                        cell is not None and str(cell).strip()
                                        for cell in row
                                    ):
                                        continue

                                    # 写入表格行
                                    f.write(
                                        '| '
                                        + ' | '.join(
                                            str(cell) if cell is not None else ''
                                            for cell in row
                                        )
                                        + ' |\n'
                                    )
                                    # 写入表头分隔行
                                    if row_num == 0:
                                        f.write(
                                            '|'
                                            + '|'.join([' --- ' for _ in row])
                                            + '|\n'
                                        )
                                f.write('\n')

            logger.info(f'pdfplumber处理完成: {pdf_path} → {output_file}')
            return str(output_file)

        except Exception as e:
            logger.error(f'使用pdfplumber处理PDF时出错: {e}')
            raise


# =============================================================================
# 主处理器类
# =============================================================================


class AdvancedPDFProcessor:
    """高级PDF处理器类"""

    def __init__(self, output_dir: str = './output', temp_dir: str = './temp'):
        """
        初始化处理器

        Args:
            output_dir: 输出目录
            temp_dir: 临时目录
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

        # 初始化各模块处理器
        self.mineru_processor = MinerUProcessor(self.output_dir, self.temp_dir)
        self.other_ocr_processors = OtherOCRProcessors(self.output_dir, self.temp_dir)

        # 检查依赖
        self._check_dependencies()

    def _check_dependencies(self):
        """检查必要的依赖库"""
        missing_deps = []
        if not MINERU_AVAILABLE:
            missing_deps.append('MinerU')
        if not PYPDF_AVAILABLE:
            missing_deps.append('pypdf')
        if not PymuPDF_AVAILABLE:
            missing_deps.append('PyMuPDF (fitz)')
        if not PDFPLUMBER_AVAILABLE:
            missing_deps.append('pdfplumber')

        if missing_deps:
            logger.warning(f'缺少以下依赖库: {", ".join(missing_deps)}')
            logger.info('某些功能可能不可用')

    def cleanup_temp_directory(self):
        """
        清理临时目录及其所有子目录和文件
        项目完成后调用此方法清空temp目录，但保留temp目录本身
        """
        try:
            if self.temp_dir.exists() and self.temp_dir.is_dir():
                # 删除temp目录下的所有文件和子目录，但保留temp目录本身
                for item in self.temp_dir.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                            logger.info(f'已删除临时文件: {item}')
                        elif item.is_dir():
                            import shutil

                            shutil.rmtree(item)
                            logger.info(f'已删除临时目录: {item}')
                    except Exception as e:
                        logger.warning(f'删除临时文件/目录失败 {item}: {e}')

                logger.info(f'已清空临时目录内容: {self.temp_dir}')
            else:
                logger.info(f'临时目录不存在: {self.temp_dir}')
        except Exception as e:
            logger.error(f'清理临时目录时出错: {e}')

    def _calculate_filename_similarity(
        self, original_name: str, target_name: str
    ) -> float:
        """
        计算两个文件名的相似度

        Args:
            original_name: 原始文件名
            target_name: 目标文件名

        Returns:
            相似度分数 (0-1)
        """
        # 简单的相似度计算方法
        import difflib

        return difflib.SequenceMatcher(
            None, original_name.lower(), target_name.lower()
        ).ratio()

    def _extract_page_range(self, pdf_path: str, start_page: int, end_page: int) -> str:
        """
        提取PDF文件的指定页码范围

        Args:
            pdf_path: PDF文件路径
            start_page: 开始页码（从1开始）
            end_page: 结束页码（包含）

        Returns:
            提取的PDF文件路径
        """
        if PdfWriter is None or PdfReader is None:
            raise RuntimeError('pypdf未安装,无法提取页码范围')

        try:
            # 打开原始PDF
            reader = PdfReader(pdf_path)

            # 验证页码范围
            total_pages = len(reader.pages)
            if start_page < 1:
                start_page = 1
            if end_page > total_pages:
                end_page = total_pages
            if start_page > end_page:
                raise ValueError(f'无效的页码范围: {start_page}-{end_page}')

            logger.info(
                f'PDF总页数: {total_pages}, 提取页码范围: {start_page}-{end_page}'
            )

            # 创建新的PDF写入器
            writer = PdfWriter()

            # 添加指定范围的页面 (转换为0基索引)
            for page_num in range(start_page - 1, end_page):
                try:
                    writer.add_page(reader.pages[page_num])
                except Exception as e:
                    logger.warning(f'添加第{page_num + 1}页时出错: {e}')
                    # 尝试重新读取页面
                    try:
                        writer.add_page(reader.pages[page_num])
                    except Exception as e2:
                        logger.error(f'重新添加第{page_num + 1}页也失败: {e2}')
                        raise

            # 保存提取的PDF
            original_name = Path(pdf_path).stem
            temp_pdf_path = (
                self.temp_dir
                / f'{original_name}_pages_{start_page:04d}_{end_page:04d}.pdf'
            )

            # 确保父目录存在
            temp_pdf_path.parent.mkdir(exist_ok=True)

            # 写入文件
            with open(temp_pdf_path, 'wb') as f:
                writer.write(f)

            logger.info(f'已保存提取的PDF文件: {temp_pdf_path}')

            # 验证提取的文件是否存在且非空
            if not temp_pdf_path.exists():
                raise RuntimeError(f'提取的PDF文件未创建: {temp_pdf_path}')

            if temp_pdf_path.stat().st_size == 0:
                raise RuntimeError(f'提取的PDF文件为空: {temp_pdf_path}')

            return str(temp_pdf_path)

        except Exception as e:
            logger.error(f'提取页码范围时出错: {e}')
            # 提供更详细的错误信息
            import traceback

            logger.error(f'详细错误信息: {traceback.format_exc()}')
            raise

    def _extract_text_from_image_page(self, pdf_path: str, page_number: int) -> str:
        """
        从图像页面提取文本内容
        使用MinerU处理图像型PDF页面

        Args:
            pdf_path: PDF文件路径
            page_number: 页码（从1开始）

        Returns:
            提取的文本内容
        """
        if not MINERU_AVAILABLE:
            return ''

        if not PymuPDF_AVAILABLE or fitz is None:
            return ''

        try:
            # 打开PDF文件
            doc = fitz.open(pdf_path)

            # 验证页码
            if page_number < 1 or page_number > len(doc):
                doc.close()
                return ''

            # 获取页面
            page = doc[page_number - 1]

            # 检查是否有图像
            image_list = page.get_images()
            if not image_list:
                doc.close()
                return ''

            # 提取图像数据
            img_index = image_list[0][0]
            pix = fitz.Pixmap(doc, img_index)

            # 转换图像数据
            if pix.n < 5:
                img_data = pix.tobytes('ppm')
            else:
                pix = fitz.Pixmap(fitz.csRGB, pix)
                img_data = pix.tobytes('ppm')

            # 保存到临时文件
            temp_img_path = self.temp_dir / f'temp_page_{page_number}.png'
            temp_img_path.write_bytes(img_data)

            # 处理图像
            if (
                not MINERU_AVAILABLE
                or read_fn is None
                or do_parse is None
                or MakeMode is None
            ):
                doc.close()
                return ''

            pdf_bytes = read_fn(str(temp_img_path))
            file_name = f'page_{page_number}_image'

            do_parse(
                output_dir=str(self.temp_dir),
                pdf_file_names=[file_name],
                pdf_bytes_list=[pdf_bytes],
                formula_enable=False,
                table_enable=True,
                p_lang_list=['ch'],
                f_make_md_mode=MakeMode.MM_MD,
                backend='pipeline',
                ocr=True,
                parse_method='auto',
                f_dump_md=True,
                f_dump_content_list=True,
                ocr_post_process=True,
                single_page_process=True,
                txt_keep_one_line=False,
                smart_layout=True,
                table_recognition=True,
                formula_recognition=False,
                image_only_pdf=True,
                force_ocr=False,
                table_cell_merge=True,
                table_line_recognition=True,
                rotation_detection=True,
                auto_rotate=True,
                dpi=300,
            )

            # 查找并读取结果
            output_dir = self.temp_dir / file_name
            output_file = output_dir / 'ocr' / f'{file_name}.md'

            # 如果主文件不存在，尝试查找其他可能的MD文件
            if not output_file.exists():
                possible_files = list(self.temp_dir.rglob(f'{file_name}*.md'))
                output_file = possible_files[0] if possible_files else None

            # 读取文本内容
            result_text = ''
            if output_file and output_file.exists():
                result_text = output_file.read_text(encoding='utf-8')

            # 清理资源
            doc.close()
            if temp_img_path.exists():
                temp_img_path.unlink()

            if output_dir.exists():
                import shutil

                shutil.rmtree(output_dir, ignore_errors=True)

            # 清理相关临时文件
            for file in self.temp_dir.glob(f'{file_name}*'):
                if file.is_file():
                    file.unlink(missing_ok=True)

            # 返回提取的文本
            if result_text.strip():
                return result_text

            # 如果没有MD内容，尝试从content_list.json提取
            content_list_files = list(output_dir.rglob('*content_list*.json'))
            if content_list_files:
                try:
                    with open(content_list_files[0], 'r', encoding='utf-8') as f:
                        content_list_data = json.load(f)

                    extracted_text = ''
                    for item in content_list_data:
                        if isinstance(item, dict):
                            if 'text' in item and item['text']:
                                extracted_text += item['text'] + '\n'
                            elif 'type' in item and item['type'] == 'table':
                                if 'html' in item and item['html']:
                                    extracted_text += item['html'] + '\n'
                                elif 'latex' in item and item['latex']:
                                    extracted_text += item['latex'] + '\n'

                    if extracted_text:
                        return extracted_text

                except Exception:
                    pass

            return ''

        except Exception:
            return ''

    def process_pdf(
        self,
        pdf_path: str,
        method: str = 'mineru',
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = 'ch',
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        dpi: int = 300,
    ) -> str:
        """
        处理PDF文件

        Args:
            pdf_path: PDF文件路径
            method: 处理方法 ('mineru', 'pymupdf', 'pdfplumber')
            enable_formula: 是否启用公式识别(仅MinerU)
            enable_table: 是否启用表格识别(仅MinerU)
            language: 语言(仅MinerU)
            start_page: 开始页码(从1开始,可选)
            end_page: 结束页码(包含,可选)
            dpi: 渲染图像用于OCR的分辨率 (默认: 300)

        Returns:
            输出文件路径
        """
        logger.info(f'开始处理PDF: {pdf_path} (方法: {method}, DPI: {dpi})')
        start_time = time.time()

        # 保存原始PDF路径，用于OCR处理
        original_pdf_path = pdf_path

        # 如果指定了页码范围,先提取指定页码范围的PDF
        processed_pdf_path = pdf_path
        temp_extracted_pdf = None
        if start_page is not None and end_page is not None:
            logger.info(f'提取页码范围: {start_page}-{end_page}')
            try:
                temp_extracted_pdf = self._extract_page_range(
                    pdf_path, start_page, end_page
                )
                processed_pdf_path = temp_extracted_pdf
                logger.info(f'已提取页码范围PDF: {processed_pdf_path}')
            except Exception as e:
                logger.error(f'提取页码范围失败: {e}')
                # 继续处理整个PDF文件

        try:
            output_file = ''
            file_name = Path(original_pdf_path).stem

            # 根据是否有页码范围确定基础文件名
            if start_page is not None and end_page is not None:
                base_name = f'{file_name}_pages_{start_page:04d}_{end_page:04d}'
            else:
                base_name = file_name

            if method.lower() == 'mineru':
                try:
                    output_file = self.mineru_processor.process_with_mineru(
                        processed_pdf_path,
                        'markdown',
                        enable_formula,
                        enable_table,
                        language,
                        dpi,
                        start_page,  # 传递start_page参数
                        end_page,  # 传递end_page参数
                    )
                    # 检查MinerU处理结果是否为空，如果为空则尝试OCR
                    if output_file and Path(output_file).exists():
                        file_size = Path(output_file).stat().st_size
                        if file_size == 0:
                            logger.warning(
                                f'MinerU处理结果为空文件: {output_file}，尝试OCR处理'
                            )
                            # 删除空文件
                            Path(output_file).unlink()
                            raise RuntimeError('MinerU处理结果为空')
                except Exception as e:
                    logger.warning(f'MinerU处理失败: {e}')
                    # 如果MinerU处理失败且指定了页面范围，尝试OCR方法
                    if start_page is not None and end_page is not None:
                        # 对于单页或多页处理，都尝试OCR方法
                        logger.info(f'尝试使用OCR处理页面范围: {start_page}-{end_page}')

                        # 创建OCR结果文件，使用统一的命名规则
                        ocr_output_path = self.output_dir / f'{base_name}_ocr.md'

                        # 逐页OCR处理
                        all_ocr_text = ''
                        for page_num in range(start_page, end_page + 1):
                            ocr_text = self._extract_text_from_image_page(
                                original_pdf_path, page_num
                            )
                            if ocr_text and ocr_text.strip():
                                all_ocr_text += f'\n\n{ocr_text}\n'
                            else:
                                all_ocr_text += f'\n\n#### 第{page_num}页\n\n未能从该页面提取到有效内容。\n'

                        if all_ocr_text and all_ocr_text.strip():
                            with open(ocr_output_path, 'w', encoding='utf-8') as f:
                                f.write(all_ocr_text)
                            output_file = str(ocr_output_path)
                            logger.info(f'OCR处理完成: {output_file}')
                        else:
                            # 如果OCR也失败，创建一个占位文件
                            file_name = Path(original_pdf_path).stem
                            placeholder_output_path = (
                                self.output_dir
                                / f'{file_name}_pages_{start_page:04d}_{end_page:04d}_placeholder.md'
                            )
                            with open(
                                placeholder_output_path, 'w', encoding='utf-8'
                            ) as f:
                                f.write('> 注意: 此页面内容无法识别\n\n')
                                f.write('未能从指定页面范围提取到有效内容。\n')
                            output_file = str(placeholder_output_path)
                            logger.info(f'创建占位文件: {output_file}')
                    else:
                        raise e
            elif method.lower() == 'pymupdf':
                # 使用统一的命名规则
                output_filename = f'{base_name}_pymupdf.md'
                output_file = str(self.output_dir / output_filename)
                temp_output = self.other_ocr_processors.process_with_pymupdf(
                    processed_pdf_path
                )
                # 如果处理器返回了不同的路径，将其移动到统一命名的路径
                if temp_output != output_file:
                    import shutil

                    shutil.move(temp_output, output_file)
            elif method.lower() == 'pdfplumber':
                # 使用统一的命名规则
                output_filename = f'{base_name}_pdfplumber.md'
                output_file = str(self.output_dir / output_filename)
                temp_output = self.other_ocr_processors.process_with_pdfplumber(
                    processed_pdf_path
                )
                # 如果处理器返回了不同的路径，将其移动到统一命名的路径
                if temp_output != output_file:
                    import shutil

                    shutil.move(temp_output, output_file)
            else:
                raise ValueError(f'不支持的处理方法: {method}')

            # 记录处理时间
            elapsed_time = time.time() - start_time
            logger.info(
                f'PDF处理完成: {pdf_path} → {output_file} (耗时: {elapsed_time:.2f}秒)'
            )

            # 如果使用了页码范围提取，清理临时文件
            if temp_extracted_pdf and temp_extracted_pdf != pdf_path:
                try:
                    Path(temp_extracted_pdf).unlink()
                    logger.info(f'已清理临时提取文件: {temp_extracted_pdf}')
                except Exception as e:
                    logger.warning(f'清理临时提取文件失败: {e}')

            return output_file

        except Exception as e:
            logger.error(f'处理PDF时出错: {e}')
            # 如果使用了页码范围提取，清理临时文件
            if temp_extracted_pdf and temp_extracted_pdf != pdf_path:
                try:
                    Path(temp_extracted_pdf).unlink()
                    logger.info(f'已清理临时提取文件: {temp_extracted_pdf}')
                except Exception as e:
                    logger.warning(f'清理临时提取文件失败: {e}')
            raise

    def batch_process_pdfs(
        self,
        pdf_paths: List[str],
        method: str = 'mineru',
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = 'ch',
        dpi: int = 300,
    ) -> List[Tuple[str, str]]:
        """
        批量处理PDF文件

        Args:
            pdf_paths: PDF文件路径列表
            method: 处理方法
            enable_formula: 是否启用公式识别(仅MinerU)
            enable_table: 是否启用表格识别(仅MinerU)
            language: 语言(仅MinerU)
            dpi: 渲染图像用于OCR的分辨率 (默认: 300)

        Returns:
            处理结果列表 [(输入文件路径, 输出文件路径)]
        """
        results = []
        for pdf_path in pdf_paths:
            try:
                output_file = self.process_pdf(
                    pdf_path, method, enable_formula, enable_table, language, dpi=dpi
                )
                results.append((pdf_path, output_file))
            except Exception as e:
                logger.error(f'处理PDF失败: {pdf_path}, 错误: {e}')
                results.append((pdf_path, f'ERROR: {e}'))

        return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='高级PDF处理器')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument(
        '--output', '-o', default='./output', help='输出目录 (默认: ./output)'
    )
    parser.add_argument(
        '--method',
        '-m',
        default='mineru',
        choices=['mineru', 'pymupdf', 'pdfplumber'],
        help='处理方法 (默认: mineru)',
    )
    parser.add_argument(
        '--enable-formula', action='store_true', help='启用公式识别(仅MinerU)'
    )
    parser.add_argument(
        '--enable-table', action='store_true', help='启用表格识别(仅MinerU)'
    )
    parser.add_argument(
        '--language', '-l', default='ch', help='语言设置(仅MinerU) (默认: ch)'
    )
    parser.add_argument('--start-page', type=int, help='开始页码(从1开始)')
    parser.add_argument('--end-page', type=int, help='结束页码(包含)')
    parser.add_argument(
        '--dpi', type=int, default=300, help='OCR渲染图像的分辨率 (默认: 300)'
    )

    args = parser.parse_args()

    try:
        # 创建处理器实例
        processor = AdvancedPDFProcessor(args.output, './temp')

        # 处理PDF文件
        output_file = processor.process_pdf(
            args.pdf_path,
            args.method,
            args.enable_formula,
            args.enable_table,
            args.language,
            args.start_page,
            args.end_page,
            args.dpi,
        )

        print(f'处理完成，输出文件: {output_file}')

    except Exception as e:
        logger.error(f'处理失败: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
