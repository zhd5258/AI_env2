#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
批量PDF处理器模块
支持批量上传和批量下载PDF文件进行OCR处理
"""

import os
import logging
import time
import requests
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from .minerui_OCR import MinerUOnlineProcessor, download_file_with_progress
from .advanced_pdf_processor import MinerUProcessor

logger = logging.getLogger(__name__)


class BatchPDFProcessor:
    """批量PDF处理器"""

    def __init__(self, output_dir: str = 'output', temp_dir: str = 'temp/mineru'):
        """
        初始化批量PDF处理器

        Args:
            output_dir (str): 输出目录
            temp_dir (str): 临时目录
        """
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 初始化在线和本地处理器
        self.online_processor = MinerUOnlineProcessor(output_dir=str(self.output_dir))
        self.local_processor = MinerUProcessor(
            output_dir=self.output_dir, temp_dir=self.temp_dir
        )

    def process_batch_files(
        self, file_paths: List[str], use_online: bool = True
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        批量处理PDF文件

        Args:
            file_paths (List[str]): PDF文件路径列表
            use_online (bool): 是否优先使用在线OCR处理

        Returns:
            Tuple[List[str], Dict[str, Any]]: (生成的MD文件路径列表, 处理状态信息)
        """
        if not file_paths:
            logger.warning('没有提供文件路径')
            return [], {'status': 'error', 'message': '没有提供文件路径'}

        # 验证文件是否存在
        valid_files = []
        for path in file_paths:
            if os.path.exists(path):
                valid_files.append(path)
            else:
                logger.warning(f'文件不存在，跳过: {path}')

        if not valid_files:
            logger.error('没有有效的文件可供处理')
            return [], {'status': 'error', 'message': '没有有效的文件可供处理'}

        logger.info(f'开始批量处理 {len(valid_files)} 个PDF文件')

        if use_online:
            # 优先使用在线OCR处理
            logger.info('使用在线MinerU批量处理PDF文件')
            md_files, status_info = self._process_with_online_mineru_with_progress(
                valid_files
            )

            if md_files:
                logger.info(f'在线OCR处理完成，生成 {len(md_files)} 个MD文件')
                status_info['status'] = 'success'
                return md_files, status_info
            else:
                # 在线处理失败，回退到本地处理
                logger.warning('在线OCR处理失败，回退到本地MinerU处理')
                local_md_files = self._process_with_local_mineru(valid_files)
                return local_md_files, {
                    'status': 'fallback',
                    'message': '在线处理失败，已回退到本地处理',
                }
        else:
            # 直接使用本地OCR处理
            logger.info('使用本地MinerU批量处理PDF文件')
            local_md_files = self._process_with_local_mineru(valid_files)
            return local_md_files, {'status': 'local', 'message': '使用本地处理完成'}

    def _process_with_online_mineru_with_progress(
        self, file_paths: List[str]
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        使用在线MinerU批量处理PDF文件并提供进度信息

        Args:
            file_paths (List[str]): PDF文件路径列表

        Returns:
            Tuple[List[str], Dict[str, Any]]: (生成的MD文件路径列表, 处理状态信息)
        """
        try:
            # 先上传文件获取batch_id
            batch_id = self._upload_files_for_processing(file_paths)
            if not batch_id:
                return [], {'status': 'error', 'message': '文件上传失败'}

            # 轮询处理状态并返回进度信息
            md_files, status_info = self._poll_processing_status_with_progress(batch_id)
            return md_files, status_info
        except Exception as e:
            logger.error(f'使用在线MinerU处理PDF时出错: {e}')
            return [], {'status': 'error', 'message': f'处理过程中出错: {str(e)}'}

    def _upload_files_for_processing(self, file_paths: List[str]) -> Optional[str]:
        """
        上传文件以进行在线处理

        Args:
            file_paths (List[str]): PDF文件路径列表

        Returns:
            Optional[str]: batch_id 如果上传成功，否则返回None
        """
        try:
            # 构建上传文件元数据
            files_metadata = []
            for i, path in enumerate(file_paths, start=1):
                files_metadata.append(
                    {'name': path, 'is_ocr': True, 'data_id': f'file{i}'}
                )

            # 请求参数
            data = {
                'enable_formula': self.online_processor.enable_formula,
                'language': self.online_processor.language,
                'enable_table': self.online_processor.enable_table,
                'model_version': self.online_processor.model_version,
                'files': files_metadata,
            }

            # 获取上传链接
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.online_processor.token}',
            }
            response = requests.post(
                self.online_processor.upload_url, headers=headers, json=data
            )
            if response.status_code == 200:
                result = response.json()
                logger.info('获取上传URL成功.')
                if result['code'] == 0:
                    batch_id = result['data']['batch_id']
                    upload_urls = result['data']['file_urls']
                    logger.info(f'Batch ID: {batch_id}')

                    # 上传所有文件
                    all_uploaded = True
                    for idx, file_upload_url in enumerate(upload_urls):
                        file_path = file_paths[idx]
                        try:
                            with open(file_path, 'rb') as f:
                                res_upload = requests.put(file_upload_url, data=f)
                            if res_upload.status_code == 200:
                                logger.info(f'✅ {file_path} 上传成功')
                            else:
                                logger.error(
                                    f'❌ {file_path} 上传失败，HTTP {res_upload.status_code}'
                                )
                                all_uploaded = False
                        except Exception as e:
                            logger.error(f'❌ {file_path} 上传异常: {e}')
                            all_uploaded = False

                    # 如果全部上传成功，返回batch_id
                    if all_uploaded:
                        logger.info('所有文件上传成功')
                        return batch_id
                    else:
                        logger.error('❌ 文件上传失败')
                        return None
                else:
                    logger.error(f'❌ 申请上传URL失败，原因: {result["msg"]}')
                    return None
            else:
                logger.error(
                    f'❌ 响应失败. 状态码: {response.status_code}, 结果: {response.text}'
                )
                return None
        except Exception as err:
            logger.error(f'🚨 文件上传过程中发生异常: {err}')
            return None

    def _poll_processing_status_with_progress(
        self, batch_id: str
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        根据Batch ID轮询处理状态并提供进度信息

        Args:
            batch_id (str): 批处理任务ID

        Returns:
            Tuple[List[str], Dict[str, Any]]: (生成的MD文件路径列表, 处理状态信息)
        """
        poll_url = f'{self.online_processor.poll_url_template}/{batch_id}'
        logger.info(f'开始轮询解析状态，Batch ID: {batch_id}...')
        logger.debug(f'请求URL: {poll_url}')

        total_files = 0
        processed_files = 0
        failed_files = 0

        # 设置超时时间（5分钟）
        timeout_seconds = 300
        start_time = time.time()

        while True:
            # 检查是否超时
            if time.time() - start_time > timeout_seconds:
                logger.error(f'❌ 轮询超时（{timeout_seconds}秒），终止任务')
                return [], {
                    'status': 'error',
                    'message': f'轮询超时（{timeout_seconds}秒）',
                }

            try:
                # 重新创建headers以确保token是最新的
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.online_processor.token}',
                }
                logger.debug(f'认证头: Bearer {self.online_processor.token[:20]}...')

                res = requests.get(poll_url, headers=headers)
                logger.debug(f'响应状态码: {res.status_code}')
                if res.status_code == 200:
                    result = res.json()
                    logger.debug(f'API响应: {result}')
                    if result['code'] == 0:
                        # 检查data字段的类型
                        data = result['data']
                        logger.debug(f'data字段类型: {type(data)}')

                        # 获取extract_result
                        if isinstance(data, dict) and 'extract_result' in data:
                            extract_results = data['extract_result']
                            logger.debug(f'extract_result类型: {type(extract_results)}')

                            # 更新文件计数
                            total_files = len(extract_results)
                            processed_files = 0
                            failed_files = 0

                            # 检查所有文件的处理状态
                            all_done = True
                            any_failed = False
                            for extract_result in extract_results:
                                state = extract_result['state']
                                file_name = extract_result['file_name']
                                logger.info(f'文件 {file_name} 的解析状态: {state}')

                                if state == 'done':
                                    processed_files += 1
                                elif state == 'failed':
                                    any_failed = True
                                    failed_files += 1
                                    err_msg = extract_result.get('err_msg', '未知错误')
                                    logger.error(
                                        f'❌ 文件 {file_name} 解析失败: {err_msg}'
                                    )
                                else:
                                    all_done = False

                            # 计算进度
                            progress = (
                                (processed_files + failed_files) / total_files * 100
                                if total_files > 0
                                else 0
                            )
                            status_info = {
                                'status': 'processing',
                                'progress': progress,
                                'processed': processed_files,
                                'failed': failed_files,
                                'total': total_files,
                                'message': f'已处理: {processed_files}/{total_files}, 失败: {failed_files}',
                            }

                            if all_done and not any_failed:
                                logger.info('🎉 所有文件任务完成，开始下载结果文件...')
                                # 下载所有文件的结果
                                md_files = []
                                for i, extract_result in enumerate(extract_results):
                                    full_zip_url = extract_result['full_zip_url']
                                    full_file_path = extract_result['file_name']
                                    # 提取不带路径的文件名
                                    file_name_with_ext = os.path.basename(
                                        full_file_path
                                    )
                                    # 去除扩展名
                                    file_name_without_ext = os.path.splitext(
                                        file_name_with_ext
                                    )[0]
                                    save_path = os.path.join(
                                        self.output_dir, f'{file_name_without_ext}.zip'
                                    )
                                    logger.info(f'正在下载文件: {save_path}')
                                    # 下载文件（这里简化处理，实际应该有进度显示）
                                    download_file_with_progress(full_zip_url, save_path)

                                    # 下载完成后解压zip文件并提取full.md
                                    try:
                                        with zipfile.ZipFile(save_path, 'r') as zip_ref:
                                            # 查找full.md文件
                                            for file_info in zip_ref.infolist():
                                                if file_info.filename.endswith(
                                                    'full.md'
                                                ):
                                                    # 重命名并提取full.md文件
                                                    md_file_name = (
                                                        f'{file_name_without_ext}.md'
                                                    )
                                                    md_save_path = os.path.join(
                                                        self.output_dir, md_file_name
                                                    )

                                                    # 提取文件
                                                    with (
                                                        zip_ref.open(
                                                            file_info
                                                        ) as source,
                                                        open(
                                                            md_save_path, 'wb'
                                                        ) as target,
                                                    ):
                                                        target.write(source.read())

                                                    logger.info(
                                                        f'已提取并重命名文件: {md_file_name}'
                                                    )
                                                    md_files.append(md_save_path)
                                                    break
                                            else:
                                                logger.warning(
                                                    f'在 {save_path} 中未找到full.md文件'
                                                )
                                    except Exception as e:
                                        logger.error(f'解压过程中发生错误: {e}')

                                # 更新最终状态
                                status_info['status'] = 'success'
                                status_info['message'] = (
                                    f'处理完成: {len(md_files)} 个文件'
                                )
                                return md_files, status_info
                            elif any_failed:
                                logger.error('❌ 部分文件解析失败，终止任务')
                                status_info['status'] = 'error'
                                status_info['message'] = (
                                    f'部分文件解析失败: {failed_files}/{total_files}'
                                )
                                return [], status_info
                            else:
                                logger.info(
                                    f'⏳ 任务正在处理中，进度: {progress:.1f}%，60秒后再次检查...'
                                )
                                # 等待60秒后继续轮询
                                time.sleep(60)
                                continue
                        else:
                            logger.error('❌ 无法解析响应数据结构')
                            return [], {
                                'status': 'error',
                                'message': '无法解析响应数据结构',
                            }
                    else:
                        logger.error(f'❌ 查询状态失败: {result["msg"]}')
                        time.sleep(60)
                elif res.status_code == 401:
                    logger.error('❌ 认证失败，请检查token是否有效')
                    logger.debug(f'响应内容: {res.text}')
                    return [], {'status': 'error', 'message': '认证失败'}
                else:
                    logger.error(f'❌ HTTP错误: {res.status_code}')
                    logger.debug(f'响应内容: {res.text}')
                    time.sleep(60)
            except Exception as e:
                logger.error(f'🔁 轮询过程中发生错误: {e}')
                import traceback

                traceback.print_exc()
                time.sleep(60)

    def _process_with_local_mineru(self, file_paths: List[str]) -> List[str]:
        """
        使用本地MinerU批量处理PDF文件

        Args:
            file_paths (List[str]): PDF文件路径列表

        Returns:
            List[str]: 生成的MD文件路径列表
        """
        md_files = []
        for file_path in file_paths:
            try:
                # 为每个文件单独处理
                md_file = self.local_processor.process_with_mineru(
                    file_path,
                    'markdown',
                    True,  # enable_formula
                    True,  # enable_table
                    'ch',  # language
                )
                if md_file and os.path.exists(md_file):
                    md_files.append(md_file)
                    logger.info(f'本地OCR处理成功: {file_path} -> {md_file}')
                else:
                    logger.error(f'本地OCR处理失败: {file_path}')
            except Exception as e:
                logger.error(f'处理文件 {file_path} 时出错: {e}')

        return md_files
