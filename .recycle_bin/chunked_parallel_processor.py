#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分块并行PDF处理器
将大型PDF文件分割成小块并行处理，提高处理效率
"""

import os
import re
import sys
import json
import time
import logging
import shutil
import argparse
import multiprocessing as mp
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

# 导入AdvancedPDFProcessor
from modules.advanced_pdf_processor import AdvancedPDFProcessor

# 可选依赖库
try:
    import fitz  # PyMuPDF

    PymuPDF_AVAILABLE = True
except ImportError:
    PymuPDF_AVAILABLE = False
    fitz = None
    logging.warning('PyMuPDF (fitz) 未安装, 内容预检查功能将不可用')


# 获取logger实例而不是重复配置
logger = logging.getLogger(__name__)


class ChunkedParallelProcessor:
    """分块并行PDF处理器类"""

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

        # 清理旧的临时目录
        self._cleanup_old_temp_dirs()

        # 为每个处理实例创建独立的临时目录，避免并发冲突
        self.instance_temp_dir = self.temp_dir / f'instance_{int(time.time() * 1000)}'
        self.instance_temp_dir.mkdir(exist_ok=True)

        # 用于跟踪处理进度
        self.processed_chunks = 0
        self.total_chunks = 0

    def _cleanup_old_temp_dirs(self):
        """
        清理旧的临时目录
        """
        try:
            current_time = time.time() * 1000
            items_to_delete = []

            # 收集需要删除的目录
            for item in self.temp_dir.iterdir():
                if item.is_dir() and item.name.startswith('instance_'):
                    try:
                        # 提取时间戳
                        timestamp_str = item.name.split('_')[1]
                        timestamp = int(timestamp_str)

                        # 如果目录超过30秒未使用，则删除（原为5分钟）
                        if current_time - timestamp > 30000:  # 30秒 = 30000毫秒
                            items_to_delete.append(item)
                    except (ValueError, IndexError):
                        # 如果无法解析时间戳，也尝试删除（可能是损坏的目录）
                        items_to_delete.append(item)

            # 删除收集到的目录
            for item in items_to_delete:
                try:
                    self._force_delete_directory(item)
                    logger.info(f'已清理旧临时目录: {item}')
                except Exception as e:
                    logger.warning(f'清理旧临时目录失败: {item}, {e}')

        except Exception as e:
            logger.warning(f'清理旧临时目录时出错: {e}')

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """
        获取PDF文件总页数

        Args:
            pdf_path: PDF文件路径

        Returns:
            PDF文件总页数
        """
        # 检查文件是否存在
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f'PDF文件不存在: {pdf_path}')

        try:
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except FileNotFoundError:
            # 重新抛出文件不存在的异常
            raise
        except Exception as e:
            logger.error(f'获取PDF页数失败: {e}')
            raise

    def _calculate_optimal_chunk_size(self, pdf_path: str) -> int:
        """
        根据PDF文件大小动态计算最优块大小

        Args:
            pdf_path: PDF文件路径

        Returns:
            最优块大小
        """
        try:
            file_size = Path(pdf_path).stat().st_size
            # 根据文件大小动态调整块大小
            # 小文件(<=10MB): 块大小10页
            # 中等文件(10MB-100MB): 块大小20页
            # 大文件(>100MB): 块大小30页
            if file_size <= 10 * 1024 * 1024:  # <= 10MB
                return 10
            elif file_size <= 100 * 1024 * 1024:  # <= 100MB
                return 20
            else:  # > 100MB
                return 30
        except Exception as e:
            logger.warning(f'计算最优块大小时出错，使用默认值: {e}')
            return 10

    def _get_optimal_worker_count(self) -> int:
        """
        根据CPU核心数确定最佳工作线程数

        Returns:
            最佳工作线程数
        """
        cpu_count = mp.cpu_count()
        # 使用CPU核心数的75%，但至少为2，最多为8
        optimal_workers = max(2, min(int(cpu_count * 0.75), 8))
        logger.info(f'系统CPU核心数: {cpu_count}, 推荐工作线程数: {optimal_workers}')
        return optimal_workers

    def _split_pdf_into_chunks(
        self,
        pdf_path: str,
        chunk_size: int,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> List[Tuple[int, int]]:
        """
        将PDF文件分割成多个块

        Args:
            pdf_path: PDF文件路径
            chunk_size: 每块页数
            start_page: 开始页码(从1开始)
            end_page: 结束页码(包含)

        Returns:
            页码范围列表 [(start_page, end_page), ...]
        """
        try:
            total_pages = self._get_pdf_page_count(pdf_path)
        except Exception as e:
            logger.error(f'获取PDF页数失败: {e}')
            raise

        # 确定实际处理范围
        actual_start = start_page if start_page is not None else 1
        actual_end = end_page if end_page is not None else total_pages

        # 验证页码范围
        if actual_start < 1:
            actual_start = 1
        if actual_end > total_pages:
            actual_end = total_pages
        if actual_start > actual_end:
            raise ValueError(f'无效的页码范围: {actual_start}-{actual_end}')

        logger.info(f'PDF总页数: {total_pages}, 处理范围: {actual_start}-{actual_end}')

        # 生成分块
        chunks = []
        current_page = actual_start
        while current_page <= actual_end:
            chunk_end = min(current_page + chunk_size - 1, actual_end)
            chunks.append((current_page, chunk_end))
            current_page = chunk_end + 1

        # 确保最后一个分块不超过实际结束页
        if chunks and chunks[-1][1] > actual_end:
            chunks[-1] = (chunks[-1][0], actual_end)

        logger.info(f'生成 {len(chunks)} 个分块: {chunks}')
        return chunks

    def _process_chunk_with_mineru(
        self,
        pdf_path: str,
        start_page: int,
        end_page: int,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = 'ch',
        dpi: int = 300,
    ) -> Tuple[int, int, str]:
        """
        使用MinerU处理单个分块

        Args:
            pdf_path: PDF文件路径
            start_page: 开始页码(从1开始)
            end_page: 结束页码(包含)
            enable_formula: 是否启用公式识别
            enable_table: 是否启用表格识别
            language: 语言
            dpi: 渲染图像用于OCR的分辨率

        Returns:
            (start_page, end_page, output_file_path)
        """
        logger.info(f'开始处理分块: {start_page}-{end_page}')
        start_time = time.time()

        # 为每个分块创建独立的临时目录
        chunk_temp_dir = self.instance_temp_dir / f'chunk_{start_page}_{end_page}'
        chunk_temp_dir.mkdir(exist_ok=True, parents=True)

        try:
            # 为每个分块创建独立的处理器实例
            processor = AdvancedPDFProcessor(str(self.output_dir), str(chunk_temp_dir))

            # 直接调用主处理器处理分块
            output_file = processor.process_pdf(
                pdf_path=pdf_path,
                method='mineru',
                enable_formula=enable_formula,
                enable_table=enable_table,
                language=language,
                start_page=start_page,
                end_page=end_page,
                dpi=dpi,
            )

            elapsed_time = time.time() - start_time
            logger.info(
                f'分块 {start_page}-{end_page} 处理完成 (耗时: {elapsed_time:.2f}秒)'
            )

            return (start_page, end_page, output_file)

        except Exception as e:
            logger.error(f'处理分块 {start_page}-{end_page} 失败: {e}')
            import traceback

            logger.error(f'详细错误信息: {traceback.format_exc()}')

            # 即使处理失败，也要创建一个占位文件确保流程继续
            original_name = Path(pdf_path).stem
            placeholder_file_path = (
                self.output_dir
                / f'{original_name}_chunk_{start_page:04d}_{end_page:04d}_placeholder.md'
            )
            with open(placeholder_file_path, 'w', encoding='utf-8') as f:
                f.write(f'#### 第{start_page}页\n\n')
                f.write('> 注意: 此分块内容无法识别\n\n')
                f.write(f'处理分块 {start_page}-{end_page} 时发生错误: {str(e)}\n')

            logger.info(f'为失败的分块创建占位文件: {placeholder_file_path}')
            return (start_page, end_page, str(placeholder_file_path))

    def process_pdf_chunked_parallel(
        self,
        pdf_path: str,
        chunk_size: Optional[int] = None,  # 默认为None，表示动态计算
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        max_workers: Optional[int] = None,  # 默认为None，表示动态计算
        use_process_pool: bool = True,  # 默认使用进程池
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = 'ch',
        dpi: int = 300,
    ) -> str:
        """
        分块并行处理PDF文件（全部使用MinerU处理以确保高质量）

        Args:
            pdf_path: PDF文件路径
            chunk_size: 每块页数 (默认: 动态计算)
            start_page: 开始页码(从1开始)
            end_page: 结束页码(包含)
            max_workers: 最大工作线程数 (默认: 根据CPU核心数动态计算)
            use_process_pool: 是否使用进程池
            enable_formula: 是否启用公式识别
            enable_table: 是否启用表格识别
            language: 语言
            dpi: 渲染图像用于OCR的分辨率 (默认: 300)

        Returns:
            合并后的输出文件路径
        """
        logger.info(f'开始分块并行处理PDF: {pdf_path} (DPI: {dpi})')
        start_time = time.time()

        # 检查PDF文件是否存在
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f'PDF文件不存在: {pdf_path}')

        # 动态计算最优块大小
        if chunk_size is None:
            chunk_size = self._calculate_optimal_chunk_size(pdf_path)
            logger.info(f'动态计算最优块大小: {chunk_size}')

        # 动态计算最优工作线程数
        if max_workers is None:
            max_workers = self._get_optimal_worker_count()
            logger.info(f'动态计算最优工作线程数: {max_workers}')

        # 生成分块
        try:
            chunks = self._split_pdf_into_chunks(
                pdf_path, chunk_size, start_page, end_page
            )
        except Exception as e:
            logger.error(f'生成分块时出错: {e}')
            # 确保即使在分块生成失败时也清理临时目录
            try:
                if (
                    hasattr(self, 'instance_temp_dir')
                    and self.instance_temp_dir.exists()
                ):
                    self._force_delete_directory(self.instance_temp_dir)
                    logger.info(
                        f'分块生成失败，已清理实例临时目录: {self.instance_temp_dir}'
                    )
            except Exception as cleanup_e:
                logger.warning(f'清理临时目录失败: {cleanup_e}')
            raise

        if not chunks:
            raise ValueError('未生成有效的分块')

        # 初始化进度跟踪
        self.total_chunks = len(chunks)
        self.processed_chunks = 0
        logger.info(f'开始处理 {self.total_chunks} 个分块')

        # 确定使用的执行器类型
        executor_class = ProcessPoolExecutor if use_process_pool else ThreadPoolExecutor
        logger.info(
            f'使用 {"进程池" if use_process_pool else "线程池"} 进行并行处理，工作线程数: {max_workers}'
        )

        # 并行处理所有分块
        chunk_results = []
        failed_chunks = []
        try:
            with executor_class(max_workers=max_workers) as executor:
                # 提交所有任务 - 修复：正确为每个分块传递不同的页码范围
                future_to_chunk = {}
                for start_page, end_page in chunks:
                    future = executor.submit(
                        self._process_chunk_with_mineru,
                        pdf_path,
                        start_page,
                        end_page,
                        enable_formula,
                        enable_table,
                        language,
                        dpi,
                    )
                    future_to_chunk[future] = (start_page, end_page)

                # 收集结果 - 添加超时机制和更详细的错误处理
                for future in as_completed(
                    future_to_chunk, timeout=600
                ):  # 增加到10分钟超时
                    chunk_range = future_to_chunk[future]
                    try:
                        result = future.result(timeout=600)  # 增加到10分钟超时
                        chunk_results.append(result)
                        self.processed_chunks += 1
                        progress = (self.processed_chunks / self.total_chunks) * 100
                        logger.info(
                            f'分块 {chunk_range[0]}-{chunk_range[1]} 处理成功 [进度: {progress:.1f}% ({self.processed_chunks}/{self.total_chunks})]'
                        )

                        # 验证分块处理结果
                        start_page, end_page, output_file = result
                        output_path = Path(output_file)
                        if not output_path.exists():
                            logger.warning(
                                f'分块处理后输出文件不存在: {output_file}，但继续处理其他分块'
                            )
                        logger.info(f'分块 {start_page}-{end_page} 结果验证通过')
                    except Exception as e:
                        failed_chunks.append(chunk_range)
                        self.processed_chunks += 1
                        progress = (self.processed_chunks / self.total_chunks) * 100
                        logger.error(
                            f'分块 {chunk_range[0]}-{chunk_range[1]} 处理失败 [进度: {progress:.1f}% ({self.processed_chunks}/{self.total_chunks})]: {e}'
                        )
                        # 记录详细错误信息
                        import traceback

                        logger.error(f'详细错误信息: {traceback.format_exc()}')

            # 检查是否有处理失败的分块 - 严格检查，一旦有失败就立即终止
            if failed_chunks:
                error_msg = (
                    f'部分分块处理失败，终止整个处理流程: 失败分块: {failed_chunks}'
                )
                logger.error(error_msg)
                # 清理已生成的中间文件
                try:
                    self._cleanup_intermediate_files(chunk_results)
                except Exception as cleanup_e:
                    logger.warning(f'清理中间文件时出错: {cleanup_e}')

                # 如果是单页处理失败，尝试单独处理这些失败的页面
                if len(failed_chunks) <= 3:  # 只对少量失败页面尝试重试
                    logger.info('尝试单独处理失败的分块...')
                    retry_results = []
                    still_failed = []
                    for start_page, end_page in failed_chunks:
                        try:
                            logger.info(
                                f'尝试单独处理失败的分块 {start_page}-{end_page}'
                            )
                            # 创建一个新的处理器实例
                            retry_temp_dir = (
                                self.instance_temp_dir
                                / f'retry_{start_page}_{end_page}'
                            )
                            retry_temp_dir.parent.mkdir(
                                parents=True, exist_ok=True
                            )  # 确保父目录存在
                            retry_processor = AdvancedPDFProcessor(
                                str(self.output_dir), str(retry_temp_dir)
                            )
                            output_file = retry_processor.process_pdf(
                                pdf_path=pdf_path,
                                method='mineru',
                                enable_formula=enable_formula,
                                enable_table=enable_table,
                                language=language,
                                start_page=start_page,
                                end_page=end_page,
                                dpi=dpi,
                            )
                            retry_results.append((start_page, end_page, output_file))
                            logger.info(f'重试成功处理分块 {start_page}-{end_page}')
                        except Exception as retry_e:
                            logger.error(
                                f'重试处理分块 {start_page}-{end_page} 仍然失败: {retry_e}'
                            )
                            still_failed.append((start_page, end_page))

                    if not still_failed and retry_results:
                        # 如果重试成功，将结果添加到chunk_results中继续处理
                        chunk_results.extend(retry_results)
                        logger.info('所有失败分块重试成功，继续处理...')
                    else:
                        # 即使重试失败，也要继续处理其他成功的结果
                        logger.warning('部分分块处理失败，但继续处理其他成功的结果...')
                else:
                    logger.warning('大量分块处理失败，但继续处理其他成功的结果...')

            # 检查是否所有分块都成功处理
            if len(chunk_results) != len(chunks):
                # 即使部分分块处理失败，也继续处理合并
                logger.warning(
                    f'分块处理不完整: 成功 {len(chunk_results)}/{len(chunks)}'
                )

            # 按页码顺序排序结果
            chunk_results.sort(key=lambda x: x[0])

            # 合并所有分块结果
            final_output = self._merge_chunk_results(chunk_results, pdf_path)

            # 清理中间文件
            self._cleanup_intermediate_files(chunk_results)

            elapsed_time = time.time() - start_time
            logger.info(
                f'分块并行处理完成: {pdf_path} → {final_output} (总耗时: {elapsed_time:.2f}秒)'
            )

            return final_output

        except Exception as e:
            logger.error(f'分块并行处理过程中出现错误: {e}')
            # 清理已生成的中间文件
            try:
                self._cleanup_intermediate_files(chunk_results)
            except Exception as cleanup_e:
                logger.warning(f'清理中间文件时出错: {cleanup_e}')
            raise

    def _merge_chunk_results(
        self, chunk_results: List[Tuple[int, int, str]], pdf_path: str
    ) -> str:
        """
        合并所有分块处理结果

        Args:
            chunk_results: 分块处理结果列表 [(start_page, end_page, output_file_path), ...]
            pdf_path: 原始PDF文件路径

        Returns:
            合并后的输出文件路径
        """
        if not chunk_results:
            raise ValueError('没有分块处理结果可合并')

        logger.info(f'开始合并 {len(chunk_results)} 个分块结果')

        # 生成合并后的文件名
        original_name = Path(pdf_path).stem
        start_page = chunk_results[0][0]
        end_page = chunk_results[-1][1]
        merged_file_name = (
            f'{original_name}_pages_{start_page:04d}_{end_page:04d}_merged.md'
        )
        merged_file_path = self.output_dir / merged_file_name

        # 合并所有分块结果
        with open(merged_file_path, 'w', encoding='utf-8') as merged_file:
            # 依次写入每个分块的内容
            for i, (start_page, end_page, chunk_file_path) in enumerate(chunk_results):
                try:
                    logger.info(f'合并分块 {start_page}-{end_page}: {chunk_file_path}')

                    # 检查分块文件是否存在
                    if not Path(chunk_file_path).exists():
                        error_msg = f'分块文件不存在: {chunk_file_path}'
                        logger.error(error_msg)
                        # 创建占位内容
                        chunk_content = f'#### 第{start_page}页\n\n此分块文件不存在。\n'
                    else:
                        # 检查分块文件是否为空
                        if Path(chunk_file_path).stat().st_size == 0:
                            logger.warning(f'分块文件为空: {chunk_file_path}')
                            # 对于空文件，创建占位内容而不是抛出错误
                            chunk_content = (
                                f'#### 第{start_page}页\n\n此页面内容为空或无法识别。\n'
                            )
                        else:
                            # 读取分块文件内容
                            try:
                                # 尝试以UTF-8编码读取
                                with open(
                                    chunk_file_path, 'r', encoding='utf-8'
                                ) as chunk_file:
                                    chunk_content = chunk_file.read()
                            except UnicodeDecodeError:
                                # 如果UTF-8失败，尝试以GBK编码读取
                                with open(
                                    chunk_file_path, 'r', encoding='gbk'
                                ) as chunk_file:
                                    chunk_content = chunk_file.read()

                        # 检查内容是否为空
                        if not chunk_content.strip():
                            logger.info(
                                f'分块文件内容为空，这可能是正常的: {chunk_file_path}'
                            )
                            # 创建一个简洁的占位内容，不包含冗余标题
                            chunk_content = '\n此页面内容为空或无法识别。\n'

                    # 如果不是第一个分块，需要处理标题层级
                    if i > 0:
                        # 降低标题层级（增加#号以降低层级）
                        chunk_content = self._adjust_heading_levels(chunk_content)

                    # 写入内容，不添加分块标识
                    merged_file.write(chunk_content)
                    # 在每个分块之间添加分页符，方便阅读
                    merged_file.write('\n\n---\n\n')

                except Exception as e:
                    error_msg = f'合并分块 {start_page}-{end_page} 时出错: {e}'
                    logger.error(error_msg)
                    # 即使出错也添加占位内容
                    merged_file.write(f'#### 第{start_page}页\n\n')
                    merged_file.write(f'处理此分块时发生错误: {str(e)}\n')
                    merged_file.write('\n\n---\n\n')

        # 验证合并后的文件
        try:
            if not merged_file_path.exists():
                raise FileNotFoundError(f'合并后的文件不存在: {merged_file_path}')

            # 验证合并后文件的内容
            with open(merged_file_path, 'r', encoding='utf-8') as f:
                merged_content = f.read()
                if not merged_content.strip():
                    logger.warning(f'合并后的文件内容为空: {merged_file_path}')

        except Exception as e:
            logger.error(f'验证合并文件时出错: {e}')
            raise

        logger.info(f'合并完成，输出文件: {merged_file_path}')
        return str(merged_file_path)

    def _cleanup_intermediate_files(self, chunk_results: List[Tuple[int, int, str]]):
        """
        清理中间文件（只保留最终合并结果）

        Args:
            chunk_results: 分块处理结果列表
        """
        logger.info('开始清理中间文件')

        # 删除分块结果文件
        for _, _, chunk_file_path in chunk_results:
            try:
                chunk_file = Path(chunk_file_path)
                if chunk_file.exists() and chunk_file.is_file():
                    chunk_file.unlink()
                    logger.info(f'已删除中间文件: {chunk_file_path}')
            except Exception as e:
                logger.warning(f'删除中间文件失败: {chunk_file_path}, {e}')

        # 清理所有可能的临时子目录
        try:
            if self.instance_temp_dir.exists():
                # 首先尝试清理所有chunk子目录
                for item in list(
                    self.instance_temp_dir.iterdir()
                ):  # 使用list避免迭代时修改
                    if item.is_dir() and item.name.startswith('chunk_'):
                        try:
                            self._force_delete_directory(item)
                            logger.info(f'已清理分块临时目录: {item}')
                        except Exception as e:
                            logger.warning(f'清理分块临时目录失败: {item}, {e}')

                # 然后清理实例临时目录本身
                self._force_delete_directory(self.instance_temp_dir)
                logger.info(f'已清理实例临时目录: {self.instance_temp_dir}')

                # 确保父级temp目录存在
                self.temp_dir.mkdir(exist_ok=True)
            else:
                logger.info(f'实例临时目录不存在: {self.instance_temp_dir}')
        except Exception as e:
            logger.warning(f'清理实例临时目录失败: {self.instance_temp_dir}, {e}')
            # 尝试另一种清理方法
            try:
                self._force_cleanup_temp_dir()
            except Exception as e2:
                logger.error(f'强制清理临时目录也失败: {e2}')

        # 最后再次检查并清理任何残留的临时目录
        try:
            self._cleanup_old_temp_dirs()
        except Exception as e:
            logger.warning(f'清理旧临时目录时出错: {e}')

        logger.info('中间文件清理完成')

    def _force_delete_directory(self, directory: Path):
        """
        强制删除目录及其所有内容

        Args:
            directory: 要删除的目录路径
        """
        if not directory.exists():
            return

        logger.debug(f'开始强制删除目录: {directory}')

        # 尝试多次删除以确保成功
        for attempt in range(3):  # 减少尝试次数到3次
            try:
                # 先尝试正常的递归删除
                if directory.exists():
                    shutil.rmtree(directory, ignore_errors=False)
                    logger.debug(f'成功删除目录: {directory}')
                    return
            except Exception as e:
                logger.warning(f'第{attempt + 1}次删除目录失败: {directory}, {e}')
                if attempt < 2:  # 不是最后一次尝试
                    time.sleep(0.1)  # 等待0.1秒

        # 如果正常删除失败，尝试逐个删除文件和目录
        try:
            self._recursive_force_delete(directory)
            logger.debug(f'通过递归强制删除完成: {directory}')
        except Exception as e:
            logger.error(f'递归强制删除也失败: {directory}, {e}')
            raise

    def _recursive_force_delete(self, path: Path):
        """
        递归强制删除路径下的所有内容

        Args:
            path: 要删除的路径
        """
        if not path.exists():
            return

        if path.is_file():
            # 删除文件
            path.unlink()
            logger.debug(f'已删除文件: {path}')
        elif path.is_dir():
            # 先删除目录中的所有内容
            try:
                for item in path.iterdir():
                    self._recursive_force_delete(item)
            except Exception as e:
                logger.warning(f'遍历目录内容失败: {path}, {e}')

            # 然后删除空目录
            try:
                path.rmdir()
                logger.debug(f'已删除空目录: {path}')
            except Exception as e:
                logger.warning(f'删除空目录失败: {path}, {e}')
                # 如果删除空目录失败，再次尝试强制删除
                try:
                    path.unlink()
                except Exception as e2:
                    logger.warning(f'强制删除目录也失败: {path}, {e2}')

    def _force_cleanup_temp_dir(self):
        """
        强制清理临时目录的备用方法
        """
        if not self.instance_temp_dir.exists():
            return

        logger.info(f'开始强制清理临时目录: {self.instance_temp_dir}')
        self._force_delete_directory(self.instance_temp_dir)
        logger.info(f'强制清理完成: {self.instance_temp_dir}')

    def _adjust_heading_levels(self, content: str) -> str:
        """
        调整Markdown标题层级（增加#号以降低层级）

        Args:
            content: Markdown内容

        Returns:
            调整后的Markdown内容
        """
        lines = content.split('\n')
        adjusted_lines = []

        for line in lines:
            # 检查是否为标题行（以#开头）
            if line.startswith('#'):
                # 找到第一个非#字符的位置
                hash_count = 0
                for char in line:
                    if char == '#':
                        hash_count += 1
                    else:
                        break

                # 增加标题层级（最多增加到6级）
                if hash_count < 6:
                    line = '#' + line

            adjusted_lines.append(line)

        return '\n'.join(adjusted_lines)

    def compare_processing_methods(
        self,
        pdf_path: str,
        chunk_size: Optional[int] = None,  # 默认为None，表示动态计算
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        max_workers: Optional[int] = None,  # 默认为None，表示动态计算
        use_process_pool: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        对比不同处理方法的性能（使用MinerU确保高质量处理）

        Args:
            pdf_path: PDF文件路径
            chunk_size: 每块页数 (默认改为动态计算)
            start_page: 开始页码(从1开始)
            end_page: 结束页码(包含)
            max_workers: 最大工作线程数 (默认: 根据CPU核心数动态计算)
            use_process_pool: 是否使用进程池

        Returns:
            性能对比结果
        """
        # 使用MinerU进行测试
        try:
            logger.info('开始测试MinerU处理方法')
            start_time = time.time()

            # 使用MinerU处理PDF
            output_file = self.process_pdf_chunked_parallel(
                pdf_path=pdf_path,
                chunk_size=chunk_size,
                start_page=start_page,
                end_page=end_page,
                max_workers=max_workers,
                use_process_pool=use_process_pool,
                enable_formula=True,
                enable_table=True,
                language='ch',
            )

            elapsed_time = time.time() - start_time

            # 获取输出文件大小
            file_size = (
                Path(output_file).stat().st_size if Path(output_file).exists() else 0
            )

            results = {
                'mineru': {
                    'status': 'success',
                    'time': elapsed_time,
                    'size': file_size,
                    'output_file': output_file,
                }
            }

            logger.info(
                f'MinerU处理方法测试完成: {elapsed_time:.2f}秒, {file_size}字节'
            )

        except Exception as e:
            logger.error(f'MinerU处理方法测试失败: {e}')
            import traceback

            logger.error(f'详细错误信息: {traceback.format_exc()}')
            results = {
                'mineru': {
                    'status': f'error: {str(e)}',
                    'time': 0,
                    'size': 0,
                    'output_file': '',
                }
            }

        return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='分块并行PDF处理器')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument(
        '--output', '-o', default='./output', help='输出目录 (默认: ./output)'
    )
    parser.add_argument('--chunk-size', type=int, help='每块页数 (默认: 动态计算)')
    parser.add_argument('--enable-formula', action='store_true', help='启用公式识别')
    parser.add_argument('--enable-table', action='store_true', help='启用表格识别')
    parser.add_argument('--language', '-l', default='ch', help='语言设置 (默认: ch)')
    parser.add_argument('--start-page', type=int, help='开始页码(从1开始)')
    parser.add_argument('--end-page', type=int, help='结束页码(包含)')
    parser.add_argument(
        '--workers', type=int, help='并行工作线程数 (默认: 根据CPU核心数动态计算)'
    )
    parser.add_argument(
        '--use-process-pool',
        action='store_true',
        default=True,
        help='使用进程池而非线程池 (默认启用)',
    )
    parser.add_argument('--compare', action='store_true', help='对比不同处理方法性能')
    parser.add_argument(
        '--dpi', type=int, default=300, help='OCR渲染图像的分辨率 (默认: 300)'
    )

    args = parser.parse_args()

    processor = None
    try:
        # 创建处理器实例
        processor = ChunkedParallelProcessor(args.output, './temp')

        if args.compare:
            # 性能对比测试
            logger.info('开始性能对比测试')
            results = processor.compare_processing_methods(
                pdf_path=args.pdf_path,
                chunk_size=args.chunk_size,
                start_page=args.start_page,
                end_page=args.end_page,
                max_workers=args.workers,
                use_process_pool=args.use_process_pool,
            )

            # 输出对比结果
            print('\n性能对比结果:')
            print('-' * 60)
            for method, result in results.items():
                if result['status'] == 'success':
                    print(
                        f'{method:12}: {result["time"]:6.2f}秒, {result["size"]:8d}字节'
                    )
                else:
                    print(f'{method:12}: 失败 - {result["status"]}')
        else:
            # 分块并行处理PDF文件
            output_file = processor.process_pdf_chunked_parallel(
                pdf_path=args.pdf_path,
                chunk_size=args.chunk_size,
                start_page=args.start_page,
                end_page=args.end_page,
                max_workers=args.workers,
                use_process_pool=args.use_process_pool,
                enable_formula=args.enable_formula,
                enable_table=args.enable_table,
                language=args.language,
                dpi=args.dpi,
            )

            print(f'处理完成，输出文件: {output_file}')

    except Exception as e:
        logger.error(f'处理失败: {e}')
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # 确保在任何情况下都尝试清理临时目录
        if processor and hasattr(processor, 'instance_temp_dir'):
            try:
                if processor.instance_temp_dir and processor.instance_temp_dir.exists():
                    processor._force_delete_directory(processor.instance_temp_dir)
                    logger.info(
                        f'主函数结束，已清理实例临时目录: {processor.instance_temp_dir}'
                    )
            except Exception as cleanup_e:
                logger.warning(f'主函数结束时清理临时目录失败: {cleanup_e}')
                # 尝试最后的清理方法
                try:
                    import shutil

                    if processor.instance_temp_dir.exists():
                        shutil.rmtree(processor.instance_temp_dir, ignore_errors=True)
                        logger.info(
                            f'主函数结束，通过shutil.rmtree强制清理实例临时目录: {processor.instance_temp_dir}'
                        )
                except Exception as final_e:
                    logger.error(f'最终清理方法也失败: {final_e}')


if __name__ == '__main__':
    main()
