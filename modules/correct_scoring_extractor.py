#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-05 21:03:02
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-20 19:02:30
# 文件相对于项目的路径   : \AI_ENV2\modules\correct_scoring_extractor.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正确的评分规则提取器
严格按照用户要求实现：直接从PDF中提取表格，不转换为txt或MD
"""

import re
import logging
from typing import List, Dict, Any
import fitz  # PyMuPDF

# 尝试导入TextProcessor
try:
    from .text_processor import TextProcessor
except ImportError:
    try:
        from text_processor import TextProcessor
    except ImportError:
        TextProcessor = None


class CorrectScoringExtractor:
    """正确的评分规则提取器"""

    def __init__(self, pdf_path: str):
        """
        初始化评分规则提取器

        Args:
            pdf_path: PDF文件路径（直接使用原始PDF文件）
        """
        self.pdf_path = pdf_path
        self.logger = logging.getLogger(__name__)
        # 初始化文本处理器
        self.text_processor = TextProcessor() if TextProcessor else None

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        直接从PDF文件中提取评分规则（严格按照用户要求）

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        self.logger.info(f'开始直接从PDF文件提取评分规则: {self.pdf_path}')

        try:
            # 1. 使用PyMuPDF打开PDF文件
            doc = fitz.open(self.pdf_path)

            # 2. 查找包含评分规则相关关键词的页面
            scoring_section_pages = self._find_scoring_section_pages(doc)

            if not scoring_section_pages:
                self.logger.warning('未找到评分规则相关章节')
                doc.close()
                return []

            # 3. 从这些页面中提取表格，并处理跨页表格的拼接
            all_table_data = []
            for page_num in scoring_section_pages:
                page = doc.load_page(page_num)
                tables = fitz.find_tables(page)  # 直接使用PyMuPDF提取表格

                for table in tables:
                    # 提取表格数据
                    table_data = table.extract()
                    if table_data:
                        all_table_data.append(table_data)

            # 4. 拼接跨页表格
            merged_tables = self._merge_cross_page_tables(all_table_data)

            # 5. 解析评分规则
            all_rules = []
            for table_data in merged_tables:
                try:
                    rules = self._parse_scoring_table(table_data)
                    all_rules.extend(rules)
                except Exception as e:
                    self.logger.error(f'解析表格时出错: {e}')
                    import traceback

                    self.logger.error(f'错误详情: {traceback.format_exc()}')

            doc.close()

            # 6. 构建层级结构
            hierarchy_rules = self._build_hierarchy(all_rules)

            # 7. 自我验证：确保所有父项总分是100分，所有子项总分之和也是100分
            self._validate_scoring_rules(hierarchy_rules)

            # 修复：记录提取到的规则信息，便于调试
            self.logger.info(f'提取到 {len(hierarchy_rules)} 条评分规则')
            for i, rule in enumerate(hierarchy_rules):
                self.logger.info(
                    f'规则 {i + 1}: {rule["criteria_name"]}, 分数: {rule["max_score"]}, 是否父项: {rule["is_parent"]}'
                )
                if rule.get('children'):
                    for j, child in enumerate(rule['children']):
                        self.logger.info(
                            f'  子项 {j + 1}: {child["criteria_name"]}, 分数: {child["max_score"]}'
                        )

            # 检查是否提取到了任何有分值的规则
            has_quantitative_rules = any(
                rule.get('max_score', 0) > 0 for rule in hierarchy_rules
            )
            if not has_quantitative_rules:
                self.logger.warning(
                    '警告：未从PDF中提取到任何有效的评分规则（所有规则分数为0）。'
                    '请检查PDF中的评分表格格式是否正确。'
                )

            return hierarchy_rules

        except Exception as e:
            self.logger.error(f'提取评分规则时出错: {e}')
            import traceback

            self.logger.error(f'错误详情: {traceback.format_exc()}')
            return []

    def _merge_cross_page_tables(
        self, table_data_list: List[List[List[str]]]
    ) -> List[List[List[str]]]:
        """
        合并跨页的表格数据

        Args:
            table_data_list: 表格数据列表

        Returns:
            List[List[List[str]]]: 合并后的表格数据列表
        """
        if not table_data_list:
            return []

        merged_tables = []
        current_table = None

        for table_data in table_data_list:
            if not table_data:
                continue

            # 如果当前没有表格，或者新表格的表头与当前表格不同，则开始新表格
            if current_table is None or not self._has_same_header(
                current_table, table_data
            ):
                if current_table is not None:
                    merged_tables.append(current_table)
                current_table = table_data.copy()
            else:
                # 合并表格数据（去掉表头）
                current_table.extend(table_data[1:])

        # 添加最后一个表格
        if current_table is not None:
            merged_tables.append(current_table)

        return merged_tables

    def _has_same_header(
        self, table1: List[List[str]], table2: List[List[str]]
    ) -> bool:
        """
        判断两个表格是否具有相同的表头

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            bool: 是否具有相同的表头
        """
        if not table1 or not table2:
            return False

        if len(table1) == 0 or len(table2) == 0:
            return False

        header1 = table1[0]
        header2 = table2[0]

        if len(header1) != len(header2):
            return False

        # 确保所有表头单元格都是字符串类型
        header1 = [str(cell) if cell is not None else '' for cell in header1]
        header2 = [str(cell) if cell is not None else '' for cell in header2]

        # 特殊处理：如果第二个表格的表头明显是内容而不是表头，则认为是同一个表格
        # 判断标准：表头中包含"分"、"扣完"等评分相关关键词，但不包含"评价项目"、"评分项"等真正的表头关键词
        header2_text = ''.join(header2)
        if (
            '分' in header2_text
            and '扣完' in header2_text
            and '评价项目' not in header2_text
            and '评分项' not in header2_text
        ):
            return True

        # 特殊处理：如果第二个表格的表头是明显的评分内容，则认为是同一个表格
        if (
            '分' in header2_text
            and ('得' in header2_text or '扣' in header2_text)
            and len([h for h in header2 if h and h.strip()]) <= 2
        ):  # 大部分表头单元格为空
            return True

        # 检查是否是正常的表头
        normal_header_keywords = [
            '评价项目',
            '评分项',
            '评分标准',
            '项目',
            '标准',
            '分值',
        ]
        header1_text = ''.join(header1)
        is_header1_normal = any(
            keyword in header1_text for keyword in normal_header_keywords
        )
        is_header2_normal = any(
            keyword in header2_text for keyword in normal_header_keywords
        )

        # 如果两个表头都包含正常表头关键词，则认为是相同的表头
        if is_header1_normal and is_header2_normal:
            return True

        # 如果第一个表头是正常表头，第二个表头不是正常表头，则认为是同一个表格的内容
        if is_header1_normal and not is_header2_normal:
            return True

        return False

    def _find_scoring_section_pages(self, doc) -> List[int]:
        """
        查找包含评分规则相关关键词的页面

        Args:
            doc: PyMuPDF文档对象

        Returns:
            List[int]: 包含评分规则相关关键词的页面编号列表
        """
        scoring_pages = []
        # 扩展关键词列表，包含更多与评分规则相关的关键词
        keywords = [
            '评标办法',
            '评分标准',
            '评审标准',
            'Evaluation Method',
            'Scoring Criteria',
            '价格分',
            '技术部分',
            '商务部分',
            '价格部分',
        ]

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()

            # 查找包含评分规则关键词的页面
            for keyword in keywords:
                if keyword in text:
                    scoring_pages.append(page_num)
                    break  # 避免重复添加同一页面

        return scoring_pages

    def _parse_scoring_table(self, table_data: List[List[str]]) -> List[Dict[str, Any]]:
        """
        解析评分表格数据

        Args:
            table_data: 表格数据

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        if not table_data or len(table_data) < 2:
            return []

        rules = []
        header_index = 0

        # 查找表头行
        for i, row in enumerate(table_data):
            if (
                len(row) >= 2
                and (
                    '评价项目' in (row[0] if row[0] else '')
                    or '评分项' in (row[0] if row[0] else '')
                    or 'Evaluation Item' in (row[0] if row[0] else '')
                    or 'Scoring Item' in (row[0] if row[0] else '')
                )
            ) or (
                len(row) >= 3
                and (
                    '评价项目' in (row[1] if row[1] else '')
                    or '评分项' in (row[1] if row[1] else '')
                    or 'Evaluation Item' in (row[1] if row[1] else '')
                    or 'Scoring Item' in (row[1] if row[1] else '')
                )
            ):
                header_index = i
                break

        # 检查表头是否符合要求
        header = table_data[header_index]
        if len(header) >= 2 and (
            '评价项目' in header[0]
            or '评分项' in header[0]
            or 'Evaluation Item' in header[0]
            or 'Scoring Item' in header[0]
        ):
            # 符合要求的表格格式：三列（父项、子项、描述）
            for i in range(header_index + 1, len(table_data)):
                row = table_data[i]
                # 处理不同长度的行
                first_col = row[0].strip() if len(row) > 0 and row[0] else ''
                second_col = row[1].strip() if len(row) > 1 and row[1] else ''
                third_col = row[2].strip() if len(row) > 2 and row[2] else ''

                # 确保所有列都是字符串类型
                first_col = str(first_col) if first_col is not None else ''
                second_col = str(second_col) if second_col is not None else ''
                third_col = str(third_col) if third_col is not None else ''

                # 立即清理描述内容
                description = self._clean_description(third_col)

                # 解析第一列和第二列
                first_info = (
                    self._parse_item_with_score(first_col) if first_col else None
                )
                second_info = (
                    self._parse_item_with_score(second_col) if second_col else None
                )

                # 处理不同的情况
                if first_info and not self._should_ignore_item(first_info['name']):
                    # 第一列是父项或子项
                    # 修复：正确识别父项，包含"部分"关键词或分数大于10或包含价格关键词的项应被视为父项
                    is_parent = (
                        '部分' in first_info['name']
                        or first_info['score'] > 10
                        or '价格' in first_info['name']
                    )

                    # 特殊处理：如果该行还有子项信息（第二列也有分数），则第一列更可能是父项
                    if second_info and not self._should_ignore_item(
                        second_info['name']
                    ):
                        is_parent = True

                    # 对于价格项，保存第二列作为描述信息
                    price_description = ''
                    if '价格' in first_info['name'] and second_col:
                        price_description = self._clean_description(second_col)
                        # 调试信息
                        # print(f"DEBUG: 价格项描述处理 - 名称: {first_info['name']}, 第二列: {second_col}, 清理后: {price_description}")

                    # 判断是否为否决项（名称前有"*"号）
                    is_veto = first_info['name'].startswith('*')
                    # 清理名称，移除"*"号
                    clean_name = first_info['name'].lstrip('*').strip()

                    # 判断是否为定性规则（无分数）或定量规则（有分数）
                    is_qualitative = first_info['score'] == 0 and not is_parent
                    is_quantitative = first_info['score'] > 0 or is_parent

                    rules.append(
                        {
                            'criteria_name': clean_name,
                            'max_score': first_info['score'],
                            'description': price_description
                            if '价格' in first_info['name']
                            else '',
                            'is_price_criteria': '价格' in first_info['name'],
                            'is_veto': is_veto,
                            'is_parent': is_parent,
                            'is_qualitative': is_qualitative,
                            'is_quantitative': is_quantitative,
                        }
                    )

                    # 如果第一列是父项，且第二列也是有效的子项，则同时添加第二列作为子项
                    if (
                        is_parent
                        and second_info
                        and not self._should_ignore_item(second_info['name'])
                    ):
                        # 使用第三列作为描述
                        child_description = self._clean_description(third_col)

                        # 判断是否为否决项（名称前有"*"号）
                        is_veto = second_info['name'].startswith('*')
                        # 清理名称，移除"*"号
                        clean_name = second_info['name'].lstrip('*').strip()

                        # 判断是否为定性规则（无分数）或定量规则（有分数）
                        is_qualitative = second_info['score'] == 0
                        is_quantitative = second_info['score'] > 0

                        rules.append(
                            {
                                'criteria_name': clean_name,
                                'max_score': second_info['score'],
                                'description': child_description,
                                'is_price_criteria': False,
                                'is_veto': is_veto,
                                'is_parent': False,
                                'is_qualitative': is_qualitative,
                                'is_quantitative': is_quantitative,
                            }
                        )
                elif second_info and not self._should_ignore_item(second_info['name']):
                    # 第二列是子项
                    # 判断是否为否决项（名称前有"*"号）
                    is_veto = second_info['name'].startswith('*')
                    # 清理名称，移除"*"号
                    clean_name = second_info['name'].lstrip('*').strip()

                    # 判断是否为定性规则（无分数）或定量规则（有分数）
                    is_qualitative = second_info['score'] == 0
                    is_quantitative = second_info['score'] > 0

                    rules.append(
                        {
                            'criteria_name': clean_name,
                            'max_score': second_info['score'],
                            'description': description,
                            'is_price_criteria': False,
                            'is_veto': is_veto,
                            'is_parent': False,
                            'is_qualitative': is_qualitative,
                            'is_quantitative': is_quantitative,
                        }
                    )
                elif (
                    not first_col
                    and second_col
                    and not self._should_ignore_item(second_col)
                ):
                    # 第一列为空，第二列是子项（跨页表格的情况）
                    # 尝试从第二列文本中提取分数
                    second_info_alt = self._parse_item_with_score(second_col)
                    if second_info_alt:
                        # 判断是否为否决项（名称前有"*"号）
                        is_veto = second_info_alt['name'].startswith('*')
                        # 清理名称，移除"*"号
                        clean_name = second_info_alt['name'].lstrip('*').strip()

                        # 判断是否为定性规则（无分数）或定量规则（有分数）
                        is_qualitative = second_info_alt['score'] == 0
                        is_quantitative = second_info_alt['score'] > 0

                        rules.append(
                            {
                                'criteria_name': clean_name,
                                'max_score': second_info_alt['score'],
                                'description': description,
                                'is_price_criteria': False,
                                'is_veto': is_veto,
                                'is_parent': False,
                                'is_qualitative': is_qualitative,
                                'is_quantitative': is_quantitative,
                            }
                        )
                    else:
                        # 如果无法解析分数，可能是描述性的子项
                        # 在这种情况下，我们尝试从第三列提取分数信息
                        score_info = self._extract_score_from_description(third_col)
                        if score_info:
                            # 判断是否为否决项（名称前有"*"号）
                            is_veto = (
                                score_info['name'].startswith('*')
                                if 'name' in score_info
                                else False
                            )
                            # 清理名称，移除"*"号
                            clean_name = (
                                score_info['name'].lstrip('*').strip()
                                if 'name' in score_info
                                else self._clean_text(second_col)
                            )

                            # 判断是否为定性规则（无分数）或定量规则（有分数）
                            is_qualitative = (
                                score_info['score'] == 0
                                if 'score' in score_info
                                else True
                            )
                            is_quantitative = (
                                score_info['score'] > 0
                                if 'score' in score_info
                                else False
                            )

                            rules.append(
                                {
                                    'criteria_name': clean_name,
                                    'max_score': score_info['score']
                                    if 'score' in score_info
                                    else 0,
                                    'description': score_info['description']
                                    if 'description' in score_info
                                    else '',
                                    'is_price_criteria': False,
                                    'is_veto': is_veto,
                                    'is_parent': False,
                                    'is_qualitative': is_qualitative,
                                    'is_quantitative': is_quantitative,
                                }
                            )
                elif first_info and not second_col and description:
                    # 第一列是项，第二列为空，但有描述（可能是子项）
                    # 判断是否为否决项（名称前有"*"号）
                    is_veto = first_info['name'].startswith('*')
                    # 清理名称，移除"*"号
                    clean_name = first_info['name'].lstrip('*').strip()

                    # 判断是否为定性规则（无分数）或定量规则（有分数）
                    is_qualitative = first_info['score'] == 0
                    is_quantitative = first_info['score'] > 0

                    rules.append(
                        {
                            'criteria_name': clean_name,
                            'max_score': first_info['score'],
                            'description': description,
                            'is_price_criteria': False,
                            'is_veto': is_veto,
                            'is_parent': False,
                            'is_qualitative': is_qualitative,
                            'is_quantitative': is_quantitative,
                        }
                    )
                # 特殊处理：同一行中既有父项又有子项的情况
                elif (
                    first_info
                    and second_info
                    and not self._should_ignore_item(first_info['name'])
                    and not self._should_ignore_item(second_info['name'])
                ):
                    # 第一列是父项
                    is_parent = (
                        '部分' in first_info['name']
                        or first_info['score'] > 10
                        or '价格' in first_info['name']
                    )

                    # 判断是否为否决项（名称前有"*"号）
                    is_veto_first = first_info['name'].startswith('*')
                    # 清理名称，移除"*"号
                    clean_name_first = first_info['name'].lstrip('*').strip()

                    # 判断是否为定性规则（无分数）或定量规则（有分数）
                    is_qualitative_first = first_info['score'] == 0 and not is_parent
                    is_quantitative_first = first_info['score'] > 0 or is_parent

                    rules.append(
                        {
                            'criteria_name': clean_name_first,
                            'max_score': first_info['score'],
                            'description': ''
                            if not is_parent
                            else (
                                self._clean_description(second_col)
                                if '价格' in first_info['name']
                                else ''
                            ),
                            'is_price_criteria': '价格' in first_info['name'],
                            'is_veto': is_veto_first,
                            'is_parent': is_parent,
                            'is_qualitative': is_qualitative_first,
                            'is_quantitative': is_quantitative_first,
                        }
                    )

                    # 第二列是子项
                    if (
                        not is_parent or '价格' not in first_info['name']
                    ):  # 价格项特殊处理
                        # 判断是否为否决项（名称前有"*"号）
                        is_veto_second = second_info['name'].startswith('*')
                        # 清理名称，移除"*"号
                        clean_name_second = second_info['name'].lstrip('*').strip()

                        # 判断是否为定性规则（无分数）或定量规则（有分数）
                        is_qualitative_second = second_info['score'] == 0
                        is_quantitative_second = second_info['score'] > 0

                        rules.append(
                            {
                                'criteria_name': clean_name_second,
                                'max_score': second_info['score'],
                                'description': description,
                                'is_price_criteria': False,
                                'is_veto': is_veto_second,
                                'is_parent': False,
                                'is_qualitative': is_qualitative_second,
                                'is_quantitative': is_quantitative_second,
                            }
                        )
        else:
            # 不符合标准格式，尝试其他解析方式
            # 但我们仍然需要处理价格项的描述
            for row in table_data:
                if row and len(row) >= 1:
                    # 处理不同长度的行
                    first_col = row[0].strip() if len(row) > 0 and row[0] else ''
                    second_col = row[1].strip() if len(row) > 1 and row[1] else ''
                    third_col = row[2].strip() if len(row) > 2 and row[2] else ''

                    # 确保所有列都是字符串类型
                    first_col = str(first_col) if first_col is not None else ''
                    second_col = str(second_col) if second_col is not None else ''
                    third_col = str(third_col) if third_col is not None else ''

                    # 解析第一列和第二列
                    first_info = (
                        self._parse_item_with_score(first_col) if first_col else None
                    )
                    second_info = (
                        self._parse_item_with_score(second_col) if second_col else None
                    )

                    # 处理不同的情况
                    if first_info and not self._should_ignore_item(first_info['name']):
                        # 第一列是父项或子项
                        # 修复：正确识别父项，包含"部分"关键词或分数大于10或包含价格关键词的项应被视为父项
                        is_parent = (
                            '部分' in first_info['name']
                            or first_info['score'] > 10
                            or '价格' in first_info['name']
                        )

                        # 特殊处理：如果该行还有子项信息（第二列也有分数），则第一列更可能是父项
                        if second_info and not self._should_ignore_item(
                            second_info['name']
                        ):
                            is_parent = True

                        # 对于价格项，保存第二列作为描述信息
                        price_description = ''
                        if '价格' in first_info['name'] and second_col:
                            price_description = self._clean_description(second_col)

                        # 判断是否为否决项（名称前有"*"号）
                        is_veto = first_info['name'].startswith('*')
                        # 清理名称，移除"*"号
                        clean_name = first_info['name'].lstrip('*').strip()

                        # 判断是否为定性规则（无分数）或定量规则（有分数）
                        is_qualitative = first_info['score'] == 0 and not is_parent
                        is_quantitative = first_info['score'] > 0 or is_parent

                        rules.append(
                            {
                                'criteria_name': clean_name,
                                'max_score': first_info['score'],
                                'description': price_description
                                if '价格' in first_info['name']
                                else '',
                                'is_price_criteria': '价格' in first_info['name'],
                                'is_veto': is_veto,
                                'is_parent': is_parent,
                                'is_qualitative': is_qualitative,
                                'is_quantitative': is_quantitative,
                            }
                        )

                        # 如果第一列是父项，且第二列也是有效的子项，则同时添加第二列作为子项
                        if (
                            is_parent
                            and second_info
                            and not self._should_ignore_item(second_info['name'])
                        ):
                            # 使用第三列作为描述
                            child_description = self._clean_description(third_col)

                            # 判断是否为否决项（名称前有"*"号）
                            is_veto = second_info['name'].startswith('*')
                            # 清理名称，移除"*"号
                            clean_name = second_info['name'].lstrip('*').strip()

                            # 判断是否为定性规则（无分数）或定量规则（有分数）
                            is_qualitative = second_info['score'] == 0
                            is_quantitative = second_info['score'] > 0

                            rules.append(
                                {
                                    'criteria_name': clean_name,
                                    'max_score': second_info['score'],
                                    'description': child_description,
                                    'is_price_criteria': False,
                                    'is_veto': is_veto,
                                    'is_parent': False,
                                    'is_qualitative': is_qualitative,
                                    'is_quantitative': is_quantitative,
                                }
                            )
                    elif second_info and not self._should_ignore_item(
                        second_info['name']
                    ):
                        # 第二列是子项
                        # 判断是否为否决项（名称前有"*"号）
                        is_veto = second_info['name'].startswith('*')
                        # 清理名称，移除"*"号
                        clean_name = second_info['name'].lstrip('*').strip()

                        # 判断是否为定性规则（无分数）或定量规则（有分数）
                        is_qualitative = second_info['score'] == 0
                        is_quantitative = second_info['score'] > 0

                        rules.append(
                            {
                                'criteria_name': clean_name,
                                'max_score': second_info['score'],
                                'description': self._clean_description(third_col),
                                'is_price_criteria': False,
                                'is_veto': is_veto,
                                'is_parent': False,
                                'is_qualitative': is_qualitative,
                                'is_quantitative': is_quantitative,
                            }
                        )

        return rules

    def _parse_item_with_score(self, text: str) -> Dict[str, Any]:
        """
        解析包含分值的项目名称

        Args:
            text: 包含分值的文本

        Returns:
            Dict[str, Any]: 解析结果{name: 名称, score: 分值}
        """
        if not text:
            return {}  # 返回空字典而不是None

        # 清理文本
        text = re.sub(r'\s+', ' ', text.strip())

        # 匹配格式如：商务部分(18分) 或 企业证书，认证体系（5 分）
        # 支持范围分数如 (0-2分)、(1-3分) 等，取最大值
        # 支持不完整的括号如（5分 或 (10分
        pattern = r'(.+?)[\(（](\d+(?:-\d+)?)(?:\s*[分\)\)]|\s*$)'
        match = re.search(pattern, text)

        if match:
            name = match.group(1).strip()
            score_text = match.group(2)

            # 如果是范围分数，取最大值
            if '-' in score_text:
                score = float(score_text.split('-')[1])
            else:
                score = float(score_text)

            return {'name': name, 'score': score}

        # 如果没有匹配到括号格式，尝试其他格式
        # 匹配格式如：商务部分 18分
        pattern2 = r'(.+?)\s+(\d+(?:\.\d+)?)\s*分'
        match2 = re.search(pattern2, text)
        if match2:
            name = match2.group(1).strip()
            score = float(match2.group(2))
            return {'name': name, 'score': score}

        # 如果仍然没有匹配到，返回原始文本作为名称，分数为0
        return {'name': text.strip(), 'score': 0}

    def _should_ignore_item(self, item_name: str) -> bool:
        """
        判断是否应该忽略某个评分项

        Args:
            item_name: 评分项名称

        Returns:
            bool: 是否应该忽略
        """
        # 定义应该忽略的项的关键字
        ignore_keywords = ['投标保证金', '保证金', '没收', '废标', '否决', '无效']

        for keyword in ignore_keywords:
            if keyword in item_name:
                return True

        return False

    def _extract_score_from_description(self, description: str) -> Dict[str, Any]:
        """
        从描述中提取分数信息

        Args:
            description: 描述文本

        Returns:
            Dict[str, Any]: 分数信息{score: 分值, description: 描述}
        """
        if not description:
            return {}

        # 尝试从描述中提取分数
        pattern = r'(\d+(?:\.\d+)?)\s*分'
        match = re.search(pattern, description)
        if match:
            score = float(match.group(1))
            # 移除分数部分，得到纯描述
            clean_description = re.sub(pattern, '', description).strip()
            clean_description = re.sub(r'\s+', ' ', clean_description)
            # 从描述中提取名称（假设描述的第一部分是名称）
            name_parts = (
                clean_description.split('，')[0]
                .split('。')[0]
                .split(',')[0]
                .split('.')[0]
            )
            name = name_parts.strip()
            return {'name': name, 'score': score, 'description': clean_description}

        return {}

    def _clean_text(self, text: str) -> str:
        """
        使用textacy清理文本，移除多余的空格和特殊字符

        Args:
            text: 原始文本

        Returns:
            str: 清理后的文本
        """
        if not text:
            return ''

        # 如果textacy可用，使用textacy清洗文本
        if self.text_processor:
            try:
                return self.text_processor.clean_text(text)
            except Exception as e:
                self.logger.warning(f'使用textacy清洗文本时出错: {e}')
                # 回退到基本方法

        # 基本文本清洗方法（textacy不可用时的回退方案）
        # 移除首尾空格
        text = text.strip()

        # 移除多余的空格
        text = re.sub(r'\s+', ' ', text)

        return text

    def _clean_description(self, description: str) -> str:
        """
        使用textacy清理描述文本

        Args:
            description: 原始描述

        Returns:
            str: 清理后的描述
        """
        if not description:
            return ''

        # 如果textacy可用，使用textacy清洗文本
        if self.text_processor:
            try:
                description = self.text_processor.clean_text(description)
            except Exception as e:
                self.logger.warning(f'使用textacy清洗描述文本时出错: {e}')
                # 回退到基本方法

        # 基本清理方法
        # 移除首尾空格
        description = description.strip()

        # 移除多余的空格
        description = re.sub(r'\s+', ' ', description)

        # 移除常见的无用描述
        useless_patterns = [
            r'见.*说明',
            r'详见.*',
            r'参见.*',
            r'见.*表',
            r'如.*所示',
            r'同上',
            r'同前',
        ]

        for pattern in useless_patterns:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE)

        # 移除首尾空格
        description = description.strip()

        return description

    def _build_hierarchy(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        构建评分规则的层级结构

        Args:
            rules: 打平的规则列表，包含父项和子项

        Returns:
            List[Dict[str, Any]]: 层级化的规则列表
        """
        if not rules:
            return []

        result = []
        i = 0

        while i < len(rules):
            rule = rules[i]

            # 检查是否应该被视为父项（即使标记为非父项，但如果它有子项，也应该被视为父项）
            has_children_in_next_rules = False
            # 检查接下来的几条规则是否可能是当前规则的子项
            for j in range(i + 1, min(i + 10, len(rules))):  # 检查接下来的10条规则
                next_rule = rules[j]
                # 如果下一条规则的分数小于当前规则，且当前规则分数大于10，则可能是父子关系
                if (
                    next_rule.get('max_score', 0) < rule.get('max_score', 0)
                    and rule.get('max_score', 0) > 10
                ):
                    has_children_in_next_rules = True
                    break

            # 如果是父项或者应该被视为父项
            if rule.get('is_parent', False) or has_children_in_next_rules:
                # 确保将其标记为父项
                rule['is_parent'] = True

                parent_rule = {
                    'criteria_name': rule['criteria_name'],
                    'max_score': rule['max_score'],
                    'description': rule.get('description', ''),
                    'is_price_criteria': rule['is_price_criteria'],
                    'is_veto': rule['is_veto'],
                    'is_parent': True,  # 确保标记为父项
                    'is_qualitative': rule['is_qualitative'],
                    'is_quantitative': rule['is_quantitative'],
                    'children': [],
                }

                # 特殊处理价格项
                if rule['is_price_criteria']:
                    # 价格项的父项和子项是同一个，子项最高分值应等于父项最高分值
                    parent_rule['price_formula'] = self._extract_price_formula(rule)
                    # 为价格项创建子项，名称和分值都与父项相同
                    child_rule = {
                        'criteria_name': rule['criteria_name'],  # 子项名称与父项相同
                        'max_score': rule['max_score'],  # 子项分值与父项相同
                        'description': rule.get(
                            'description', ''
                        ),  # 子项描述与父项相同
                        'is_price_criteria': True,
                        'is_veto': False,
                        'is_parent': False,  # 子项不应该标记为父项
                        'is_qualitative': False,
                        'is_quantitative': True,
                    }
                    parent_rule['children'].append(child_rule)
                    # 价格项通常没有其他子项，直接添加到结果中
                    result.append(parent_rule)
                    i += 1
                    continue

                # 处理普通父项的子项
                i += 1
                # 收集属于当前父项的子项
                child_scores_sum = 0.0  # 用于校验子项分值之和
                while i < len(rules) and not rules[i].get('is_parent', False):
                    child_rule = rules[i]
                    parent_rule['children'].append(
                        {
                            'criteria_name': child_rule['criteria_name'],
                            'max_score': child_rule['max_score'],
                            'description': child_rule.get('description', ''),
                            'is_price_criteria': child_rule['is_price_criteria'],
                            'is_veto': child_rule['is_veto'],
                            'is_parent': False,  # 子项不应该标记为父项
                            'is_qualitative': child_rule['is_qualitative'],
                            'is_quantitative': child_rule['is_quantitative'],
                        }
                    )
                    # 累加子项分值
                    child_scores_sum += child_rule['max_score']
                    i += 1

                # 校验子项分值之和是否等于父项分值
                parent_score = parent_rule['max_score']
                # 修复：允许更大的误差范围，避免浮点数精度问题
                if abs(child_scores_sum - parent_score) > 0.1:  # 允许0.1的误差
                    self.logger.warning(
                        f"父项 '{parent_rule['criteria_name']}' 的子项分值之和 ({child_scores_sum}) 不等于父项分值 ({parent_score})"
                    )
                    # 修复：当子项分值之和不等于父项分值时，调整父项分值为子项分值之和
                    parent_rule['max_score'] = child_scores_sum

                result.append(parent_rule)
            else:
                # 独立的子项（没有父项的规则）
                rule['is_parent'] = False  # 确保标记为非父项
                result.append(
                    {
                        'criteria_name': rule['criteria_name'],
                        'max_score': rule['max_score'],
                        'description': rule.get('description', ''),
                        'is_price_criteria': rule['is_price_criteria'],
                        'is_veto': rule['is_veto'],
                        'is_parent': False,  # 确保标记为非父项
                        'is_qualitative': rule['is_qualitative'],
                        'is_quantitative': rule['is_quantitative'],
                        'children': [],
                    }
                )
                i += 1

        return result

    def _should_belong_to_next_parent(
        self, current_parent: Dict[str, Any], child: Dict[str, Any]
    ) -> bool:
        """
        判断子项是否应该属于下一个父项

        Args:
            current_parent: 当前父项
            child: 子项

        Returns:
            bool: 是否应该属于下一个父项
        """
        # 这是一个简化的实现，实际应该根据具体的业务逻辑来判断
        # 例如，可以根据子项名称中的关键字来判断
        parent_name = current_parent['criteria_name']
        child_name = child['criteria_name']

        # 如果子项名称中包含父项名称的关键字，则认为属于当前父项
        # 否则，可能属于下一个父项
        # 这里我们使用一个简单的策略：如果子项名称以某些关键字开头，可能属于下一个父项
        next_parent_indicators = ['企业', '标书', '业绩', '供货', '节能', 'PLC']
        for indicator in next_parent_indicators:
            if child_name.startswith(indicator):
                # 检查当前父项是否包含这些关键字
                if indicator not in parent_name:
                    return True

        return False

    def _extract_price_formula(self, price_rule: Dict[str, Any]) -> str:
        """
        提取价格公式

        Args:
            price_rule: 价格规则

        Returns:
            str: 价格公式
        """
        # 默认价格公式
        return '投标报价得分＝(评标基准价/投标报价)×价格权重×100'

    def _validate_scoring_rules(self, rules: List[Dict[str, Any]]) -> None:
        """
        验证评分规则的完整性

        Args:
            rules: 评分规则列表
        """
        if not rules:
            self.logger.warning('没有提取到任何评分规则')
            return

        # 计算所有父项总分
        parent_total_score = 0
        child_total_score = 0

        for rule in rules:
            if rule.get('is_parent', False):
                parent_score = rule.get('max_score', 0)
                parent_total_score += parent_score

                # 计算子项分数之和
                children = rule.get('children', [])
                child_scores_sum = sum(child.get('max_score', 0) for child in children)

                # 验证父项分数是否等于子项分数之和
                if abs(parent_score - child_scores_sum) > 0.1:
                    self.logger.warning(
                        f"父项 '{rule.get('criteria_name', 'N/A')}' 的分数({parent_score})不等于其子项分数之和({child_scores_sum})"
                    )

                # 累加子项分数
                child_total_score += child_scores_sum

        # 验证总分是否为100分
        if abs(parent_total_score - 100) > 0.1:
            self.logger.warning(f'所有父项总分({parent_total_score})不等于100分')
        else:
            self.logger.info('✓ 所有父项总分等于100分')

        if abs(child_total_score - 100) > 0.1:
            self.logger.warning(f'所有子项总分({child_total_score})不等于100分')
        else:
            self.logger.info('✓ 所有子项总分等于100分')
