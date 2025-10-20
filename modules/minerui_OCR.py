# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-19 09:27:31
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-19 11:21:03
# 文件相对于项目的路径   : \PDF处理\minerui_OCR.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import requests
from pathlib import Path
import time
import sys
import os
import zipfile
import logging


def download_file_with_progress(url, save_path):
    """
    下载文件并保存到指定位置，带进度显示

    Args:
        url (str): 文件下载地址
        save_path (str): 保存文件的路径和文件名
    """
    try:
        # 确保保存目录存在
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        # 发送GET请求下载文件，stream=True用于大文件下载
        response = requests.get(url, stream=True)

        # 检查响应状态码
        if response.status_code == 200:
            # 获取文件总大小
            total_size = int(response.headers.get('content-length', 0))

            # 分块下载并保存文件
            with open(save_path, 'wb') as file:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f'\r下载进度: {percent:.1f}%', end='')

            print(f'\n文件已成功下载并保存到: {save_path}')
        else:
            print(f'下载失败，状态码: {response.status_code}')
    except Exception as e:
        print(f'下载过程中发生错误: {e}')


class MinerUOnlineProcessor:
    """在线MinerU OCR处理器"""

    def __init__(
        self,
        api_token=None,
        api_url='https://mineru.net/api/v4',
        output_dir='output',
        enable_formula=False,
        enable_table=True,
        language='ch',
        model_version='vlm',
    ):
        """
        初始化在线MinerU处理器

        Args:
            api_token (str): API认证令牌
            api_url (str): API基础URL
            output_dir (str): 输出目录
            enable_formula (bool): 是否启用公式识别
            enable_table (bool): 是否启用表格识别
            language (str): 语言设置
            model_version (str): 模型版本
        """
        self.token = (
            api_token
            or 'eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI2MzIwMDAzMyIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2MDg0MDM2OSwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiMzJjZjlkMWQtMjIzMi00NzAwLWI1YzItOTAwYTU0ZDViNjk1IiwiZW1haWwiOiJ6aGQ1MjU4QDE2My5jb20iLCJleHAiOjE3NjIwNDk5Njl9.sdAaT6nt2oyEIaqGaM-Vuj7rBkJrwOX-YbpXtETopxx8uY86mC49s4MTM4kc7y3jgUuN08pcc6OUBxjNBQe5lg'
        )
        self.upload_url = f'{api_url}/file-urls/batch'
        self.poll_url_template = f'{api_url}/extract-results/batch'
        self.output_dir = output_dir
        self.enable_formula = enable_formula
        self.enable_table = enable_table
        self.language = language
        self.model_version = model_version
        self.logger = logging.getLogger(__name__)

        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def poll_processing_status(self, batch_id):
        """
        根据Batch ID轮询处理状态

        Args:
            batch_id (str): 批处理任务ID
        """
        poll_url = f'{self.poll_url_template}/{batch_id}'
        self.logger.info(f'开始轮询解析状态，Batch ID: {batch_id}...')
        self.logger.debug(f'请求URL: {poll_url}')

        while True:
            try:
                # 重新创建headers以确保token是最新的
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.token}',
                }
                self.logger.debug(f'认证头: Bearer {self.token[:20]}...')

                res = requests.get(poll_url, headers=headers)
                self.logger.debug(f'响应状态码: {res.status_code}')
                if res.status_code == 200:
                    result = res.json()
                    self.logger.debug(f'API响应: {result}')
                    if result['code'] == 0:
                        # 检查data字段的类型
                        data = result['data']
                        self.logger.debug(f'data字段类型: {type(data)}')

                        # 获取extract_result
                        if isinstance(data, dict) and 'extract_result' in data:
                            extract_results = data['extract_result']
                            self.logger.debug(
                                f'extract_result类型: {type(extract_results)}'
                            )

                            # 检查所有文件的处理状态
                            all_done = True
                            any_failed = False
                            for extract_result in extract_results:
                                state = extract_result['state']
                                file_name = extract_result['file_name']
                                self.logger.info(
                                    f'文件 {file_name} 的解析状态: {state}'
                                )

                                if state != 'done':
                                    all_done = False
                                if state == 'failed':
                                    any_failed = True
                                    err_msg = extract_result.get('err_msg', '未知错误')
                                    self.logger.error(
                                        f'❌ 文件 {file_name} 解析失败: {err_msg}'
                                    )

                            if all_done and not any_failed:
                                self.logger.info(
                                    '🎉 所有文件任务完成，开始下载结果文件...'
                                )
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
                                    self.logger.info(f'正在下载文件: {save_path}')
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

                                                    self.logger.info(
                                                        f'已提取并重命名文件: {md_file_name}'
                                                    )
                                                    md_files.append(md_save_path)
                                                    break
                                            else:
                                                self.logger.warning(
                                                    f'在 {save_path} 中未找到full.md文件'
                                                )
                                    except Exception as e:
                                        self.logger.error(f'解压过程中发生错误: {e}')
                                return md_files
                            elif any_failed:
                                self.logger.error('❌ 部分文件解析失败，终止任务')
                                return None
                            else:
                                self.logger.info('⏳ 任务正在处理中，60秒后再次检查...')
                                time.sleep(60)
                        else:
                            self.logger.error('❌ 无法解析响应数据结构')
                            return None
                    else:
                        self.logger.error(f'❌ 查询状态失败: {result["msg"]}')
                        time.sleep(60)
                elif res.status_code == 401:
                    self.logger.error('❌ 认证失败，请检查token是否有效')
                    self.logger.debug(f'响应内容: {res.text}')
                    return None
                else:
                    self.logger.error(f'❌ HTTP错误: {res.status_code}')
                    self.logger.debug(f'响应内容: {res.text}')
                    time.sleep(60)
            except Exception as e:
                self.logger.error(f'🔁 轮询过程中发生错误: {e}')
                import traceback

                traceback.print_exc()
                time.sleep(60)

    def process_files(self, file_paths):
        """
        处理文件列表

        Args:
            file_paths (list): 文件路径列表

        Returns:
            list: 生成的MD文件路径列表
        """
        if not file_paths:
            self.logger.warning('没有提供文件路径')
            return None

        # 验证文件是否存在
        valid_files = []
        for path in file_paths:
            if os.path.exists(path):
                valid_files.append(path)
            else:
                self.logger.warning(f'文件不存在，跳过: {path}')

        if not valid_files:
            self.logger.error('没有有效的文件可供处理')
            return None

        # 构建上传文件元数据
        files_metadata = []
        for i, path in enumerate(valid_files, start=1):
            files_metadata.append({'name': path, 'is_ocr': True, 'data_id': f'file{i}'})

        # 请求参数
        data = {
            'enable_formula': self.enable_formula,
            'language': self.language,
            'enable_table': self.enable_table,
            'model_version': self.model_version,
            'files': files_metadata,
        }

        # Step 1: 获取上传链接
        try:
            # 在上传请求时也使用动态生成的headers
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.token}',
            }
            response = requests.post(self.upload_url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                self.logger.info('获取上传URL成功.')
                if result['code'] == 0:
                    batch_id = result['data']['batch_id']
                    upload_urls = result['data']['file_urls']
                    self.logger.info(f'Batch ID: {batch_id}')
                    self.logger.debug(f'Upload URLs: {upload_urls}')

                    # Step 2: 上传所有文件
                    all_uploaded = True
                    for idx, file_upload_url in enumerate(upload_urls):
                        file_path = valid_files[idx]
                        try:
                            with open(file_path, 'rb') as f:
                                res_upload = requests.put(file_upload_url, data=f)
                            if res_upload.status_code == 200:
                                self.logger.info(f'✅ {file_path} 上传成功')
                            else:
                                self.logger.error(
                                    f'❌ {file_path} 上传失败，HTTP {res_upload.status_code}'
                                )
                                all_uploaded = False
                        except Exception as e:
                            self.logger.error(f'❌ {file_path} 上传异常: {e}')
                            all_uploaded = False

                    # Step 3: 如果全部上传成功，开始轮询解析状态
                    if all_uploaded:
                        self.logger.info('所有文件上传成功，开始轮询解析状态...')
                        return self.poll_processing_status(batch_id)
                    else:
                        self.logger.error('❌ 文件上传失败，终止后续任务')
                        return None
                else:
                    self.logger.error(f'❌ 申请上传URL失败，原因: {result["msg"]}')
                    return None
            else:
                self.logger.error(
                    f'❌ 响应失败. 状态码: {response.status_code}, 结果: {response.text}'
                )
                return None
        except Exception as err:
            self.logger.error(f'🚨 发生异常: {err}')
            return None

    def process_single_file(self, file_path):
        """
        处理单个文件

        Args:
            file_path (str): 文件路径

        Returns:
            str: 生成的MD文件路径
        """
        md_files = self.process_files([file_path])
        if md_files and len(md_files) > 0:
            return md_files[0]
        return None


def main():
    """主函数，用于命令行调用"""
    # 检查是否有命令行参数传入batch_id
    if len(sys.argv) > 1:
        batch_id = sys.argv[1]
        processor = MinerUOnlineProcessor()
        processor.poll_processing_status(batch_id)
        return

    # 处理默认文件列表
    file_paths = [
        r'D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\山东创杰查急装备科技有限公司集装箱项目投标文件.pdf',
        r'D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\昆明苏净工贸有限公司集装箱项目投标文件.pdf',
    ]

    processor = MinerUOnlineProcessor()
    processor.process_files(file_paths)


if __name__ == '__main__':
    main()

# --- 接口文档参考 ---
# 成功响应字段：
# - code: 0 表示成功
# - msg: "ok" 表示成功
# - data.batch_id: 批量任务ID
# - data.extract_result.state: 状态 (done, running, failed 等)
# - data.extract_result.full_zip_url: 结果ZIP下载地址
# - data.extract_result.err_msg: 失败原因（state=failed时有效）
