#!/usr/bin/env python
# -*- coding:utf-8 -*-
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
        import json

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
        except json.JSONDecodeError as e:
            self.logger.error(f'JSON解析错误: {e}')
            self.logger.error(f'响应内容: {response}')
            # 尝试更强大的修复方法
            return self._fix_broken_json(response)
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

    def _fix_broken_json(self, response: str) -> Dict[str, Any]:
        """
        尝试修复损坏的JSON响应

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 修复后的结果
        """
        try:
            import re
            import json

            # 更强大的JSON修复方法
            # 1. 移除所有控制字符
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response)

            # 2. 特殊处理：修复未闭合的字符串
            # 查找最后一个未闭合的字符串（以引号开始但没有结束的）
            # 从末尾开始查找，找到最后一个引号
            last_quote_pos = cleaned.rfind('"')
            if last_quote_pos != -1:
                # 检查这个引号后面是否有闭合的大括号
                after_quote = cleaned[last_quote_pos + 1 :].strip()
                if not after_quote.endswith('}') and not '}' in after_quote:
                    # 如果没有闭合的大括号，尝试添加
                    # 先添加缺失的引号（如果需要）
                    if cleaned.count('"') % 2 != 0:
                        cleaned = cleaned.rstrip() + '"'
                    # 然后添加缺失的大括号
                    cleaned = cleaned.rstrip() + '}'

            # 3. 尝试提取JSON对象
            # 查找第一个{和最后一个}的位置
            first_brace = cleaned.find('{')
            last_brace = cleaned.rfind('}')

            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_part = cleaned[first_brace : last_brace + 1]

                # 4. 修复常见的JSON问题
                # 修复未闭合的字符串 - 在行末添加缺失的引号和逗号
                lines = json_part.split('\n')
                fixed_lines = []
                for i, line in enumerate(lines):
                    # 如果一行以冒号结尾但没有闭合引号，尝试修复
                    if line.strip().endswith(':') and line.count('"') % 2 == 1:
                        # 查找该行中最后一个引号的位置
                        last_quote = line.rfind('"')
                        if last_quote != -1:
                            # 在最后一个引号后添加闭合引号
                            line = line[: last_quote + 1] + '"' + line[last_quote + 1 :]
                    # 如果一行有奇数个引号，尝试在行末添加引号
                    elif line.count('"') % 2 == 1 and not line.strip().endswith('\\'):
                        line = line.rstrip() + '"'
                    # 如果是最后一行且看起来像是未完成的对象，尝试闭合
                    elif (
                        i == len(lines) - 1
                        and line.strip()
                        and not line.strip().endswith('}')
                    ):
                        # 检查是否需要添加闭合括号
                        if '{' in line and not '}' in line:
                            line = line.rstrip() + '"}'
                    fixed_lines.append(line)

                json_part = '\n'.join(fixed_lines)

                # 5. 修复多余的逗号
                json_part = re.sub(r',(\s*[}\]])', r'\1', json_part)

                # 6. 确保对象正确闭合
                open_braces = json_part.count('{')
                close_braces = json_part.count('}')
                if open_braces > close_braces:
                    # 添加缺失的闭合大括号
                    json_part = json_part.rstrip() + '}' * (open_braces - close_braces)

                open_brackets = json_part.count('[')
                close_brackets = json_part.count(']')
                if open_brackets > close_brackets:
                    # 添加缺失的闭合方括号
                    json_part = json_part.rstrip() + ']' * (
                        open_brackets - close_brackets
                    )

                # 7. 特殊处理：确保所有字符串都正确闭合
                # 查找所有未闭合的字符串
                quote_count = json_part.count('"')
                if quote_count % 2 != 0:
                    # 查找最后一个引号
                    last_quote = json_part.rfind('"')
                    # 如果最后一个引号不在末尾，尝试在末尾添加引号
                    if last_quote < len(json_part) - 1:
                        json_part = json_part.rstrip() + '"'

                # 8. 尝试解析
                try:
                    result = json.loads(json_part)
                    self.logger.info('JSON修复成功')
                    return result
                except json.JSONDecodeError as e:
                    self.logger.error(f'修复后仍然无法解析JSON: {e}')
                    # 如果还是解析失败，尝试更激进的修复
                    # 移除所有可能造成问题的字符
                    json_part = re.sub(
                        r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', json_part
                    )
                    # 确保字符串正确闭合
                    json_part = re.sub(r'([^\\])"$', r'\1\"', json_part)
                    # 确保对象闭合
                    if not json_part.endswith('}'):
                        json_part = json_part.rstrip() + '}'
                    return json.loads(json_part)
            else:
                self.logger.error('无法从响应中提取有效的JSON对象')
                # 尝试直接修复原始响应
                return self._aggressive_json_fix(response)
        except Exception as e:
            self.logger.error(f'修复损坏的JSON时出错: {e}')
            return {}

    def _aggressive_json_fix(self, response: str) -> Dict[str, Any]:
        """
        激进的JSON修复方法

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 修复后的结果
        """
        try:
            import re
            import json

            # 1. 移除所有控制字符
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response)

            # 2. 移除代码块标记
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]

            # 3. 查找JSON对象的开始和结束
            first_brace = cleaned.find('{')
            if first_brace == -1:
                self.logger.error('响应中未找到JSON对象开始标记')
                return {}

            # 从第一个{开始处理
            json_content = cleaned[first_brace:]

            # 4. 确保字符串正确闭合
            quote_positions = [i for i, char in enumerate(json_content) if char == '"']
            if len(quote_positions) % 2 != 0:
                # 添加缺失的引号
                json_content = json_content.rstrip() + '"'

            # 5. 确保对象正确闭合
            open_braces = json_content.count('{')
            close_braces = json_content.count('}')
            if open_braces > close_braces:
                json_content = json_content.rstrip() + '}' * (
                    open_braces - close_braces
                )

            open_brackets = json_content.count('[')
            close_brackets = json_content.count(']')
            if open_brackets > close_brackets:
                json_content = json_content.rstrip() + ']' * (
                    open_brackets - close_brackets
                )

            # 6. 移除可能导致问题的尾部内容
            # 查找最后一个有效的JSON结束位置
            last_valid_end = max(json_content.rfind('}'), json_content.rfind(']'))
            if last_valid_end != -1:
                json_content = json_content[: last_valid_end + 1]

            # 7. 尝试解析
            return json.loads(json_content)
        except Exception as e:
            self.logger.error(f'激进JSON修复失败: {e}')
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
