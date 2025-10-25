"""
投标分析器辅助模块
包含一些通用的辅助函数和类
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
import datetime

# 导入数据库模型
from models.database import BidDocument


class BidAnalyzerHelpers:
    """投标分析器辅助类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _fix_and_parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        修复并解析AI返回的JSON响应，使用GB18030编码
        """
        try:
            # 首先尝试清理响应，移除可能的代码块标记
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # 移除控制字符
            cleaned_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_response)

            # 使用正则表达式查找被大括号包围的JSON块
            # re.DOTALL 使得 '.' 可以匹配包括换行在内的任意字符
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 如果没有找到JSON块，直接使用清理后的响应
                json_str = cleaned_response

            # 尝试修复JSON格式问题
            # 1. 确保字符串以闭合的大括号结尾
            if not json_str.rstrip().endswith('}'):
                # 查找最后一个闭合的大括号的位置
                last_brace_pos = json_str.rfind('}')
                if last_brace_pos != -1:
                    # 在最后一个闭合大括号后添加缺失的闭合大括号
                    json_str = json_str[: last_brace_pos + 1] + '}'

            # 2. 确保所有引号都是成对出现的
            quote_count = json_str.count('"')
            if quote_count % 2 != 0:
                # 如果引号数量是奇数，尝试在末尾添加一个引号
                json_str = json_str.rstrip() + '"'

            # 3. 修复缺少逗号的问题 - 在 }" 和 " 之间添加逗号（如果它们在同一行）
            json_str = re.sub(r'(\}"\s*)\n\s*"', r'\1,\n"', json_str)

            # 4. 修复多余的逗号问题 - 移除对象或数组末尾的逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 5. 移除控制字符
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            # 尝试解析修复后的JSON，使用GB18030编码
            try:
                # 先尝试直接解析
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试使用GB18030编码
                try:
                    decoded_json = json_str.encode('utf-8').decode('gb18030')
                    data = json.loads(decoded_json)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # 如果GB18030解码也失败，使用原始字符串
                    data = json.loads(json_str)

            return data
        except Exception:
            # 如果修复失败，尝试使用更简单的修复方法
            try:
                # 尝试提取所有的键值对
                pattern = r'"([^"]+)"\s*:\s*([0-9.]+)'
                matches = re.findall(pattern, response)

                result = {}
                for match in matches:
                    key, score = match
                    result[key] = float(score)

                if result:
                    return result
            except Exception:
                pass

            # 如果所有方法都失败，返回空字典
            return {}

    def _save_failed_pages_info(self, db, bid_document_id, bid_processor):
        """保存PDF处理失败页面信息到数据库"""
        if db and bid_document_id:
            try:
                failed_pages_info = bid_processor.get_failed_pages_info()
                if failed_pages_info:
                    bid_doc = (
                        db.query(BidDocument)
                        .filter(BidDocument.id == bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        # 使用GB18030编码保存JSON数据
                        try:
                            json_str = json.dumps(failed_pages_info, ensure_ascii=False)
                            # 确保可以被GB18030编码
                            json_str.encode('gb18030')
                            bid_doc.failed_pages_info = json_str
                        except UnicodeEncodeError:
                            # 如果无法编码为GB18030，使用Unicode转义
                            json_str = json.dumps(failed_pages_info, ensure_ascii=False)
                            bid_doc.failed_pages_info = json_str.encode(
                                'unicode_escape'
                            ).decode('utf-8')

                        db.commit()
                        logging.info(
                            f'已记录 {len(failed_pages_info)} 个PDF处理失败页面到数据库'
                        )
            except Exception as e:
                logging.error(f'保存PDF处理失败页面信息到数据库时出错: {e}')

    def _save_extracted_price(self, best_price):
        """将提取的价格保存到数据库"""
        # 移除价格保存逻辑，价格提取和保存将在统一流程中处理
        pass
