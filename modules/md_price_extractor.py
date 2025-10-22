#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
从MD文件中提取价格模块
专门负责从投标文件生成的MD文件中提取投标总价
"""

import logging
import re
import os
from typing import Any
from pathlib import Path

# 尝试导入TextProcessor
try:
    from .text_processor import TextProcessor
except ImportError:
    try:
        from text_processor import TextProcessor
    except ImportError:
        TextProcessor = None


class MDPriceExtractor:
    """MD文件价格提取器"""

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)
        # 初始化文本处理器
        self.text_processor = TextProcessor() if TextProcessor else None

        # 投标一览表关键词（按优先级排序）
        self.bid_summary_keywords = [
            '投标一览表',
            '开标一览表',
            '价格一览表',
            '投标报价一览表',
            '报价一览表',
            '投标文件一览表',
            '投标价格汇总表',
            '投标汇总表',
            '投标总价',  # 增加这个关键词
            '货物名称.*投标总价',  # 增加这种模式
        ]

        # 价格字段关键词
        self.price_field_keywords = [
            '投标总价',
            '投标报价',
            '总报价',
            '总价',
            '报价金额',
            '合同金额',
            '项目总价',
        ]

        # 表格中的价格识别模式
        self.table_price_patterns = [
            # 明确的价格字段模式
            r'(?:投标总价|投标报价|总报价|总价|报价金额)[:：\s]*([￥¥]?\s*[\d,]+\.?\d*)\s*(?:元|万元)?',
            # 小写/大写标识模式
            r'(?:小写|小写金额)[:：\s]*([￥¥]?\s*[\d,]+\.?\d*)\s*(?:元|万元)?',
            r'(?:大写|大写金额)[:：\s]*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            # 货币符号模式
            r'[￥¥]\s*([\d,]+\.?\d*)',
            # 数字+元的模式（在表格环境中）
            r'([\d,]+\.?\d*)\s*(?:元|万元)',
        ]

        # 排除的干扰词
        self.exclude_keywords = [
            '保证金',
            '投标保证金',
            '履约保证金',
            '质量保证金',
            '保函',
            '保证金金额',
            '投标保函',
            '履约保函',
            '押金',
            '投标押金',
            '投标担保',
            '银行保函',
            '注册资本',
            '年营业额',
            '净资产',
        ]

    def extract_price_from_md_file(self, md_file_path: str) -> float | None:
        """
        从MD文件中提取投标总价

        Args:
            md_file_path: MD文件路径

        Returns:
            提取到的价格，如果未找到则返回None
        """
        try:
            if not os.path.exists(md_file_path):
                self.logger.warning(f'MD文件不存在: {md_file_path}')
                return None

            # 读取MD文件内容
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取价格
            price = self._extract_price_from_content(content)
            if price is not None:
                self.logger.info(f'从MD文件 {md_file_path} 中提取到价格: {price}')
                return price
            else:
                self.logger.warning(f'未能从MD文件 {md_file_path} 中提取到价格')
                return None

        except Exception as e:
            self.logger.error(f'从MD文件提取价格时出错: {e}')
            return None

    def _extract_price_from_content(self, content: str) -> float | None:
        """
        从内容中提取价格

        Args:
            content: 文本内容

        Returns:
            提取到的价格，如果未找到则返回None
        """
        # 1. 定位包含投标一览表的区域
        target_sections = self._locate_bid_summary_sections(content)
        self.logger.info(f'定位到 {len(target_sections)} 个投标一览表区域')

        # 2. 优先从投标一览表区域提取价格
        if target_sections:
            for i, section in enumerate(target_sections):
                self.logger.info(f'正在处理第 {i + 1} 个投标一览表区域')
                price = self._extract_price_from_section(section)
                if price is not None and price > 1000:  # 过滤过小的价格
                    self.logger.info(
                        f'从第 {i + 1} 个投标一览表区域提取到价格: {price}'
                    )
                    return price

        # 3. 如果投标一览表区域未找到，从全文提取
        self.logger.info('从全文提取价格')
        price = self._extract_price_from_full_content(content)
        if price is not None and price > 1000:  # 过滤过小的价格
            self.logger.info(f'从全文提取到价格: {price}')
            return price

        self.logger.info('未能从任何区域提取到有效价格')
        return None

    def _locate_bid_summary_sections(self, content: str) -> list[str]:
        """
        定位包含投标一览表的区域

        Args:
            content: 文本内容

        Returns:
            包含投标一览表的文本区域列表
        """
        sections = []

        # 查找包含投标一览表关键词的行
        lines = content.split('\n')
        for i, line in enumerate(lines):
            for keyword in self.bid_summary_keywords:
                # 使用更精确的匹配，避免匹配到业绩合同等无关内容
                if keyword in line and '业绩' not in line and '合同' not in line:
                    self.logger.info(f'在第 {i + 1} 行找到关键词: {keyword}')
                    # 找到关键词后，提取包含该关键词的段落
                    # 向前向后各扩展一定行数，但限制在合理范围内
                    start_idx = max(0, i - 15)  # 减少向前扩展的行数
                    end_idx = min(len(lines), i + 30)  # 减少向后扩展的行数
                    section = '\n'.join(lines[start_idx:end_idx])
                    sections.append(section)
                    self.logger.info(
                        f'提取了从第 {start_idx + 1} 行到第 {end_idx} 行的段落'
                    )
                    break  # 找到一个关键词就足够了

        return sections

    def _extract_price_from_section(self, section: str) -> float | None:
        """
        从特定区域提取价格，优先从投标一览表中提取，并进行小写和大写金额的交叉对比验证

        Args:
            section: 文本区域

        Returns:
            提取到的价格，如果未找到则返回None
        """
        # 1. 首先尝试处理特殊格式的价格
        special_price = self._extract_special_format_price(section)
        if special_price is not None:
            return special_price

        # 2. 查找明确的价格字段（小写金额）
        small_number_price = None
        large_number_price = None
        small_confidence = 0.0
        large_confidence = 0.0

        # 首先查找投标一览表中的特殊格式价格（小写和大写在同一单元格中）
        # 支持多种格式，包括用户提到的"小写）203 万元  （大写）贰佰零叁万元"
        bid_table_patterns = [
            r'（小写）[￥¥]?\s*([\d,]+\.?\d*)元（大写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            r'小写[）\)]\s*([\d,]+\.?\d*)\s*(?:万元|元)\s*[(（]大写[)）]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元万元整]+)',
            r'（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*元\s*（含[\d%]+税）\s*（大写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)',
        ]

        for pattern in bid_table_patterns:
            bid_table_match = re.search(pattern, section)
            if bid_table_match:
                small_price_str = bid_table_match.group(1)
                chinese_num = bid_table_match.group(2)

                small_number_price = self._str_to_float(small_price_str)
                large_number_price = self._chinese_to_number(chinese_num)

                self.logger.info(
                    f'从投标一览表中提取到小写价格: {small_number_price} (原始字符串: {small_price_str})'
                )
                self.logger.info(
                    f'从投标一览表中提取到大写价格: {large_number_price} (原始字符串: {chinese_num})'
                )

                # 设置高置信度
                small_confidence = 95.0
                large_confidence = 95.0
                break  # 找到一个匹配就足够了

        # 如果没有找到特殊格式，使用原有方法
        if small_number_price is None and large_number_price is None:
            for keyword in self.price_field_keywords:
                # 避免在包含排除关键词的行中查找价格
                lines = section.split('\n')
                for line in lines:
                    if any(exclude in line for exclude in self.exclude_keywords):
                        continue

                    pattern = rf'{keyword}[:：\s]*\(?(?:小写)?\)?[:：\s]*([￥¥]?\s*[\d,]+\.?\d*)'
                    match = re.search(pattern, line)
                    if match:
                        price_str = match.group(1)
                        small_number_price = self._str_to_float(price_str)
                        self.logger.info(
                            f'从投标一览表的投标总价列提取到阿拉伯数字价格: {small_number_price} (原始字符串: {price_str})'
                        )
                        if small_number_price is not None:
                            # 检查是否包含排除关键词
                            line_start = section.rfind('\n', 0, match.start()) + 1
                            line_end = section.find('\n', match.end())
                            if line_end == -1:
                                line_end = len(section)
                            line_text = section[line_start:line_end]
                            if not any(
                                exclude in line_text
                                for exclude in self.exclude_keywords
                            ):
                                # 基础置信度
                                small_confidence = 70.0
                                # 如果有千位分隔符，则增加置信度
                                if ',' in price_str:
                                    small_confidence += 15.0
                                # 如果在表格环境中，增加置信度
                                if '|' in line_text or '│' in line_text:
                                    small_confidence += 15.0
                                break

            # 2. 查找大写中文金额
            chinese_pattern = r'(?:大写|大写金额)[:：\s]*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
            chinese_match = re.search(chinese_pattern, section)
            if chinese_match:
                chinese_num = chinese_match.group(1)
                large_number_price = self._chinese_to_number(chinese_num)
                self.logger.info(
                    f'从投标一览表的投标总价列提取到汉字大写价格: {large_number_price} (原始字符串: {chinese_num})'
                )
                if large_number_price is not None:
                    # 基础置信度
                    large_confidence = 60.0
                    # 根据中文数字的完整性评估置信度
                    # 包含"亿"、"萬"、"万"等单位，置信度更高
                    if any(unit in chinese_num for unit in ['亿', '萬', '万']):
                        large_confidence += 20.0
                    elif '千' in chinese_num:
                        large_confidence += 10.0
                    # 包含"元整"，说明是完整金额
                    if '元整' in chinese_num:
                        large_confidence += 10.0
                    # 字符长度较长，可能是完整的
                    if len(chinese_num) >= 8:
                        large_confidence += 5.0

        # 3. 进行小写和大写金额的交叉对比与置信度评估
        if small_number_price is not None and large_number_price is not None:
            self.logger.debug(
                f'找到两个价格: 小写金额={small_number_price}(置信度{small_confidence}), 大写金额={large_number_price}(置信度{large_confidence})'
            )
            # 如果两者相差很小，则认为是正确的，直接返回小写金额
            if abs(small_number_price - large_number_price) < 1000:  # 允许一定误差
                self.logger.debug('两个价格差异很小，返回小写金额')
                return small_number_price
            else:
                # 如果数值差异较大，说明OCR可能出错，比较置信度
                self.logger.debug('两个价格差异较大，比较置信度')
                if small_confidence > large_confidence:
                    self.logger.debug(
                        f'小写金额置信度更高，返回小写金额: {small_number_price}'
                    )
                    return small_number_price
                else:
                    self.logger.debug(
                        f'大写金额置信度更高，返回大写金额: {large_number_price}'
                    )
                    return large_number_price

        # 4. 如果只有一种格式存在，则根据其置信度决定是否返回
        if small_number_price is not None:
            self.logger.info(
                f'只找到小写金额: {small_number_price}(置信度{small_confidence})'
            )
            if small_confidence >= 85.0:  # 高置信度才返回
                self.logger.info(f'小写金额置信度足够高，返回: {small_number_price}')
                return small_number_price
            else:
                self.logger.info('小写金额置信度不足，不返回')

        if large_number_price is not None:
            self.logger.info(
                f'只找到大写金额: {large_number_price}(置信度{large_confidence})'
            )
            if large_confidence >= 85.0:  # 高置信度才返回
                self.logger.info(f'大写金额置信度足够高，返回: {large_number_price}')
                return large_number_price
            else:
                self.logger.info('大写金额置信度不足，不返回')

        self.logger.info('未能找到高置信度的价格')

        # 5. 查找表格中的价格
        # 首先尝试解析结构化表格
        table_data = self._parse_markdown_table(section)
        if table_data:
            self.logger.info(f'成功解析结构化表格，包含 {len(table_data)} 行数据')
            table_price = self._extract_price_from_structured_table(table_data)
            if table_price is not None:
                self.logger.info(f'从结构化表格中提取到价格: {table_price}')
                return table_price
            else:
                self.logger.info('未能从结构化表格中提取到价格')

        # 如果结构化表格提取失败，尝试原有表格提取方法
        price = self._extract_price_from_table(section)
        if price is not None:
            return price

        # 6. 查找货币符号模式
        currency_patterns = [r'[￥¥]\s*([\d,]+\.?\d*)', r'([\d,]+\.?\d*)\s*(?:元|万元)']
        for pattern in currency_patterns:
            matches = re.findall(pattern, section)
            for match in matches:
                price_str = match if isinstance(match, str) else match[0]
                price = self._str_to_float(price_str)
                if price is not None and price > 1000:
                    return price

        return None

    def _extract_price_from_table(self, section: str) -> float | None:
        """
        从表格中提取价格，分别提取阿拉伯数字和汉字大写金额并进行置信度评估

        Args:
            section: 文本区域

        Returns:
            提取到的价格，如果未找到则返回None
        """
        # 查找表格行（以管道符分隔的行）
        table_lines = [
            line
            for line in section.split('\n')
            if '|' in line and len(line.strip()) > 10
        ]

        # 如果没有找到标准的Markdown表格，尝试查找简单的表格格式
        if not table_lines:
            lines = section.split('\n')
            for i, line in enumerate(lines):
                if '|' in line and len(line.strip()) > 10:
                    # 查找连续的表格行
                    table_block = []
                    j = i
                    while j < len(lines) and '|' in lines[j]:
                        table_block.append(lines[j])
                        j += 1

                    # 如果找到足够的表格行
                    if len(table_block) >= 2:
                        table_lines = table_block
                        break

        # 查找包含价格关键词的表头
        header_line = None
        found_keyword = None
        for line in table_lines:
            for keyword in self.price_field_keywords:
                # 避免在包含排除关键词的行中查找价格关键词
                if keyword in line and not any(
                    exclude in line for exclude in self.exclude_keywords
                ):
                    found_keyword = keyword
                    break
            if found_keyword:
                self.logger.info(f'在表格中找到价格关键词: {found_keyword}')
                header_line = line
                break

        if header_line:
            # 找到表头后，查找对应的数据行
            header_index = table_lines.index(header_line)
            if header_index + 1 < len(table_lines):
                data_line = table_lines[header_index + 1]
                self.logger.info(f'表格数据行: {data_line}')

                # 初始化阿拉伯数字和汉字大写金额及其置信度
                small_number_price = None
                large_number_price = None
                small_confidence = 0.0
                large_confidence = 0.0

                # 在数据行中查找价格
                cells = data_line.split('|')
                for cell in cells:
                    cell_content = cell.strip()

                    # 新增支持用户提到的格式：小写）203 万元  （大写）贰佰零叁万元
                    mixed_pattern = r'小写[）\)]\s*([\d,]+\.?\d*)\s*(?:万元|元)\s*[(（]大写[)）]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元万元整]+)'
                    mixed_match = re.search(mixed_pattern, cell_content)
                    if mixed_match:
                        small_price_str = mixed_match.group(1)
                        chinese_num = mixed_match.group(2)

                        small_number_price = self._str_to_float(small_price_str)
                        large_number_price = self._chinese_to_number(chinese_num)

                        if (
                            small_number_price is not None
                            and large_number_price is not None
                        ):
                            self.logger.info(
                                f'从表格中提取到混合格式价格: 小写={small_number_price}, 大写={large_number_price}'
                            )
                            small_confidence = 98.0  # 最高置信度
                            large_confidence = 98.0  # 最高置信度
                            # 直接返回，因为这是最高置信度的格式
                            return small_number_price

                    # 查找阿拉伯数字价格
                    small_pattern = r'[￥¥]?\s*([\d,]+\.?\d*)'
                    small_match = re.search(small_pattern, cell_content)
                    if small_match:
                        price_str = small_match.group(1)
                        small_number_price = self._str_to_float(price_str)
                        self.logger.info(
                            f'从表格中提取到阿拉伯数字价格: {small_number_price} (原始字符串: {price_str})'
                        )
                        if small_number_price is not None:
                            # 计算置信度
                            small_confidence = 70.0
                            # 如果有千位分隔符，则增加置信度
                            if ',' in price_str:
                                small_confidence += 15.0
                            # 如果在表格环境中，增加置信度
                            if '|' in cell_content or '│' in cell_content:
                                small_confidence += 15.0

                    # 查找汉字大写价格
                    large_pattern = r'([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
                    large_match = re.search(large_pattern, cell_content)
                    if large_match:
                        chinese_num = large_match.group(1)
                        large_number_price = self._chinese_to_number(chinese_num)
                        self.logger.info(
                            f'从表格中提取到汉字大写价格: {large_number_price} (原始字符串: {chinese_num})'
                        )
                        if large_number_price is not None:
                            # 计算置信度
                            large_confidence = 60.0
                            # 根据中文数字的完整性评估置信度
                            # 包含"亿"、"万"等单位，置信度更高
                            if any(unit in chinese_num for unit in ['亿', '萬', '万']):
                                large_confidence += 20.0
                            elif '千' in chinese_num:
                                large_confidence += 10.0
                            # 包含"元整"，说明是完整金额
                            if '元整' in chinese_num:
                                large_confidence += 10.0
                            # 字符长度较长，可能是完整的
                            if len(chinese_num) >= 8:
                                large_confidence += 5.0

                # 进行小写和大写金额的交叉对比与置信度评估
                if small_number_price is not None and large_number_price is not None:
                    self.logger.info(
                        f'找到两个价格: 阿拉伯数字={small_number_price}(置信度{small_confidence}), 汉字大写={large_number_price}(置信度{large_confidence})'
                    )
                    # 如果两者相差很小，则认为是正确的，直接返回小写金额
                    if abs(small_number_price - large_number_price) < 1:
                        self.logger.info('两个价格差异很小，返回阿拉伯数字价格')
                        return small_number_price
                    else:
                        # 如果数值差异较大，说明OCR可能出错，比较置信度
                        self.logger.debug('两个价格差异较大，比较置信度')
                        if small_confidence > large_confidence:
                            self.logger.info(
                                f'阿拉伯数字置信度更高，返回阿拉伯数字价格: {small_number_price}'
                            )
                            return small_number_price
                        else:
                            self.logger.info(
                                f'汉字大写置信度更高，返回汉字大写价格: {large_number_price}'
                            )
                            return large_number_price

                # 如果只有一种格式存在，则根据其置信度决定是否返回
                if small_number_price is not None:
                    self.logger.info(
                        f'只找到阿拉伯数字价格: {small_number_price}(置信度{small_confidence})'
                    )
                    if small_confidence >= 85.0:  # 高置信度才返回
                        self.logger.info(
                            f'阿拉伯数字价格置信度足够高，返回: {small_number_price}'
                        )
                        return small_number_price
                    else:
                        self.logger.info('阿拉伯数字价格置信度不足，不返回')

                if large_number_price is not None:
                    self.logger.info(
                        f'只找到汉字大写价格: {large_number_price}(置信度{large_confidence})'
                    )
                    if large_confidence >= 85.0:  # 高置信度才返回
                        self.logger.info(
                            f'汉字大写价格置信度足够高，返回: {large_number_price}'
                        )
                        return large_number_price
                    else:
                        self.logger.info('汉字大写价格置信度不足，不返回')

                # 如果没有高置信度的价格，尝试其他模式
                for pattern in [
                    r'[￥¥]?\s*([\d,]+\.?\d*)',
                    r'([\d,]+\.?\d*)\s*(?:元|万元)',
                ]:
                    match = re.search(pattern, data_line)
                    if match:
                        price_str = match.group(1)
                        price = self._str_to_float(price_str)
                        self.logger.info(
                            f'从表格中提取到价格: {price} (原始字符串: {price_str})'
                        )
                        if price is not None:
                            return price

        return None

    def _parse_markdown_table(self, section: str) -> list[dict[str, str]]:
        """
        解析Markdown表格或HTML表格，返回结构化的表格数据

        Args:
            section: 包含表格的文本区域

        Returns:
            list[dict[str, str]]: 结构化的表格数据，每个元素是一行数据的字典
        """
        # 首先尝试解析HTML表格
        html_table_data = self._parse_html_table(section)
        if html_table_data:
            return html_table_data

        # 如果不是HTML表格，则尝试解析Markdown表格
        lines = section.split('\n')
        table_data = []

        # 查找表格行
        table_lines = [line for line in lines if '|' in line and line.strip()]

        if len(table_lines) >= 2:
            # 提取表头
            header_line = table_lines[0]
            headers = [
                h.strip() for h in header_line.split('|')[1:-1]
            ]  # 去掉首尾的空列

            # 解析数据行
            for data_line in table_lines[2:]:  # 跳过表头和分隔行
                cells = [c.strip() for c in data_line.split('|')[1:-1]]
                if len(cells) == len(headers):
                    row_dict = dict(zip(headers, cells))
                    table_data.append(row_dict)

        return table_data

    def _parse_html_table(self, section: str) -> list[dict[str, str]]:
        """
        解析HTML表格，返回结构化的表格数据

        Args:
            section: 包含HTML表格的文本区域

        Returns:
            list[dict[str, str]]: 结构化的表格数据，每个元素是一行数据的字典
        """
        # 检查是否包含HTML表格标签
        if '<table' not in section:
            return []

        table_data = []

        # 提取所有<tr>标签
        tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', section, re.DOTALL)

        if len(tr_matches) < 1:
            return []

        # 如果只有一行，可能是表头行或者数据行
        if len(tr_matches) == 1:
            # 尝试从单行中提取数据
            single_tr = tr_matches[0]
            td_matches = re.findall(r'<td[^>]*>(.*?)</td>', single_tr, re.DOTALL)
            if td_matches:
                # 创建虚拟表头
                headers = [f'列{i + 1}' for i in range(len(td_matches))]
                cells = [self._clean_html_text(td) for td in td_matches]
                row_dict = dict(zip(headers, cells))
                table_data.append(row_dict)
            return table_data

        # 提取表头（第一行）
        header_tr = tr_matches[0]
        th_matches = re.findall(r'<td[^>]*>(.*?)</td>', header_tr, re.DOTALL)
        headers = [self._clean_html_text(th) for th in th_matches]

        # 如果表头为空，创建默认表头
        if not headers or all(not h for h in headers):
            # 使用第二行作为表头（如果有）
            if len(tr_matches) >= 2:
                second_tr = tr_matches[1]
                th_matches = re.findall(r'<td[^>]*>(.*?)</td>', second_tr, re.DOTALL)
                headers = [self._clean_html_text(th) for th in th_matches]
                # 数据行从第三行开始
                data_start_index = 2
            else:
                # 创建默认表头
                max_cols = 0
                for tr in tr_matches:
                    td_matches = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
                    max_cols = max(max_cols, len(td_matches))
                headers = [f'列{i + 1}' for i in range(max_cols)]
                data_start_index = 1
        else:
            # 正常情况，数据行从第二行开始
            data_start_index = 1

        # 提取数据行
        for tr in tr_matches[data_start_index:]:
            td_matches = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
            if td_matches:
                # 确保列数匹配，不足的用空字符串填充
                while len(td_matches) < len(headers):
                    td_matches.append('')
                # 超出的列被忽略
                if len(td_matches) > len(headers):
                    td_matches = td_matches[: len(headers)]

                cells = [self._clean_html_text(td) for td in td_matches]
                row_dict = dict(zip(headers, cells))
                table_data.append(row_dict)

        return table_data

    def _clean_html_text(self, html_text: str) -> str:
        """
        使用textacy清理HTML文本，移除HTML标签

        Args:
            html_text: 包含HTML标签的文本

        Returns:
            清理后的纯文本
        """
        # 如果textacy可用，使用textacy清洗文本
        if self.text_processor:
            try:
                # 先移除HTML标签
                clean_text = re.sub(r'<[^>]+>', '', html_text)
                # 使用textacy进一步清洗
                return self.text_processor.clean_text(clean_text)
            except Exception as e:
                self.logger.warning(f'使用textacy清洗HTML文本时出错: {e}')
                # 回退到基本方法

        # 基本清理方法（textacy不可用时的回退方案）
        # 移除HTML标签
        clean_text = re.sub(r'<[^>]+>', '', html_text)

        # 解码常见的HTML实体
        html_entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
        }

        for entity, replacement in html_entities.items():
            clean_text = clean_text.replace(entity, replacement)

        # 去除多余的空白字符
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text

    def _extract_price_from_structured_table(
        self, table_data: list[dict[str, str]]
    ) -> float | None:
        """
        从结构化的表格数据中提取价格

        Args:
            table_data: 结构化的表格数据

        Returns:
            提取到的价格，如果未找到则返回None
        """
        if not table_data:
            return None

        # 初始化小写和大写价格变量
        small_number_price = None
        large_number_price = None
        small_confidence = 0.0
        large_confidence = 0.0

        # 遍历每一行数据
        for row_idx, row in enumerate(table_data):
            # 查找包含价格关键词的列
            for key, value in row.items():
                # 检查列名是否包含价格关键词
                if any(keyword in key for keyword in self.price_field_keywords):
                    # 在该列的值中查找价格
                    # 首先查找小写价格（带标识）
                    small_pattern = r'（小写）[￥¥]?\s*([\d,]+\.?\d*)'
                    small_match = re.search(small_pattern, value)
                    if small_match:
                        price_str = small_match.group(1)
                        small_number_price = self._str_to_float(price_str)
                        if small_number_price is not None:
                            self.logger.debug(
                                f'从结构化表格中提取到小写价格: {small_number_price} (原始字符串: {price_str})'
                            )
                            small_confidence = 95.0  # 高置信度

                    # 查找汉字大写价格（带标识）
                    large_pattern = r'（大写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
                    large_match = re.search(large_pattern, value)
                    if large_match:
                        chinese_num = large_match.group(1)
                        large_number_price = self._chinese_to_number(chinese_num)
                        if large_number_price is not None:
                            self.logger.debug(
                                f'从结构化表格中提取到汉字大写价格: {large_number_price} (原始字符串: {chinese_num})'
                            )
                            large_confidence = 95.0  # 高置信度

                    # 新增支持用户提到的格式：小写）203 万元  （大写）贰佰零叁万元
                    mixed_pattern = r'小写[）\)]\s*([\d,]+\.?\d*)\s*(?:万元|元)\s*[(（]大写[)）]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元万元整]+)'
                    mixed_match = re.search(mixed_pattern, value)
                    if mixed_match:
                        small_price_str = mixed_match.group(1)
                        chinese_num = mixed_match.group(2)

                        small_number_price = self._str_to_float(small_price_str)
                        large_number_price = self._chinese_to_number(chinese_num)

                        if (
                            small_number_price is not None
                            and large_number_price is not None
                        ):
                            self.logger.debug(
                                f'从结构化表格中提取到混合格式价格: 小写={small_number_price}, 大写={large_number_price}'
                            )
                            small_confidence = 98.0  # 最高置信度
                            large_confidence = 98.0  # 最高置信度

                    # 如果同时找到了小写和大写价格
                    if (
                        small_number_price is not None
                        and large_number_price is not None
                    ):
                        self.logger.debug(
                            f'找到两个价格: 小写金额={small_number_price}(置信度{small_confidence}), 大写金额={large_number_price}(置信度{large_confidence})'
                        )
                        # 如果两者相差很小，则认为是正确的，直接返回小写金额
                        if (
                            abs(small_number_price - large_number_price) < 1000
                        ):  # 允许一定误差
                            self.logger.debug('两个价格差异很小，返回小写金额')
                            return small_number_price
                        else:
                            # 如果数值差异较大，说明OCR可能出错，比较置信度
                            self.logger.debug('两个价格差异较大，比较置信度')
                            if small_confidence > large_confidence:
                                self.logger.debug(
                                    f'小写金额置信度更高，返回小写金额: {small_number_price}'
                                )
                                return small_number_price
                            else:
                                self.logger.debug(
                                    f'大写金额置信度更高，返回大写金额: {large_number_price}'
                                )
                                return large_number_price

                    # 如果只找到小写价格
                    if small_number_price is not None and large_number_price is None:
                        # 查找普通格式的汉字大写价格
                        large_pattern = r'([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
                        large_match = re.search(large_pattern, value)
                        if large_match:
                            chinese_num = large_match.group(1)
                            large_number_price = self._chinese_to_number(chinese_num)
                            if large_number_price is not None:
                                self.logger.debug(
                                    f'从结构化表格中提取到汉字大写价格: {large_number_price} (原始字符串: {chinese_num})'
                                )
                                large_confidence = 80.0  # 中等置信度

                                # 进行交叉验证
                                if abs(small_number_price - large_number_price) < 1000:
                                    self.logger.debug('两个价格差异很小，返回小写金额')
                                    return small_number_price
                                else:
                                    self.logger.debug('两个价格差异较大，比较置信度')
                                    # 小写价格有明确标识，置信度更高
                                    return small_number_price

                    # 如果只找到大写价格
                    if large_number_price is not None and small_number_price is None:
                        # 查找普通格式的小写价格
                        small_pattern = r'[￥¥]?\s*([\d,]+\.?\d*)'
                        small_match = re.search(small_pattern, value)
                        if small_match:
                            price_str = small_match.group(1)
                            small_number_price = self._str_to_float(price_str)
                            if (
                                small_number_price is not None
                                and small_number_price > 1000
                            ):
                                self.logger.debug(
                                    f'从结构化表格中提取到小写价格: {small_number_price} (原始字符串: {price_str})'
                                )
                                small_confidence = 80.0  # 中等置信度

                                # 进行交叉验证
                                if abs(small_number_price - large_number_price) < 1000:
                                    self.logger.debug('两个价格差异很小，返回小写金额')
                                    return small_number_price
                                else:
                                    self.logger.debug('两个价格差异较大，比较置信度')
                                    # 大写价格有明确标识，置信度更高
                                    return large_number_price

                # 检查单元格值是否包含价格关键词（有些表格可能在单元格值中包含关键词而不是列名）
                if any(keyword in value for keyword in self.price_field_keywords):
                    # 在该单元格的值中查找价格
                    # 首先查找小写价格（带标识）
                    small_pattern = r'（小写）[￥¥]?\s*([\d,]+\.?\d*)'
                    small_match = re.search(small_pattern, value)
                    if small_match:
                        price_str = small_match.group(1)
                        small_number_price = self._str_to_float(price_str)
                        if small_number_price is not None:
                            self.logger.debug(
                                f'从结构化表格中提取到小写价格: {small_number_price} (原始字符串: {price_str})'
                            )
                            small_confidence = 95.0  # 高置信度

                    # 查找汉字大写价格（带标识）
                    large_pattern = r'（大写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
                    large_match = re.search(large_pattern, value)
                    if large_match:
                        chinese_num = large_match.group(1)
                        large_number_price = self._chinese_to_number(chinese_num)
                        if large_number_price is not None:
                            self.logger.debug(
                                f'从结构化表格中提取到汉字大写价格: {large_number_price} (原始字符串: {chinese_num})'
                            )
                            large_confidence = 95.0  # 高置信度

                    # 新增支持用户提到的格式：小写）203 万元  （大写）贰佰零叁万元
                    mixed_pattern = r'小写[）\)]\s*([\d,]+\.?\d*)\s*(?:万元|元)\s*[(（]大写[)）]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元万元整]+)'
                    mixed_match = re.search(mixed_pattern, value)
                    if mixed_match:
                        small_price_str = mixed_match.group(1)
                        chinese_num = mixed_match.group(2)

                        small_number_price = self._str_to_float(small_price_str)
                        large_number_price = self._chinese_to_number(chinese_num)

                        if (
                            small_number_price is not None
                            and large_number_price is not None
                        ):
                            self.logger.debug(
                                f'从结构化表格中提取到混合格式价格: 小写={small_number_price}, 大写={large_number_price}'
                            )
                            small_confidence = 98.0  # 最高置信度
                            large_confidence = 98.0  # 最高置信度

                    # 如果同时找到了小写和大写价格
                    if (
                        small_number_price is not None
                        and large_number_price is not None
                    ):
                        self.logger.debug(
                            f'找到两个价格: 小写金额={small_number_price}(置信度{small_confidence}), 大写金额={large_number_price}(置信度{large_confidence})'
                        )
                        # 如果两者相差很小，则认为是正确的，直接返回小写金额
                        if (
                            abs(small_number_price - large_number_price) < 1000
                        ):  # 允许一定误差
                            self.logger.debug('两个价格差异很小，返回小写金额')
                            return small_number_price
                        else:
                            # 如果数值差异较大，说明OCR可能出错，比较置信度
                            self.logger.debug('两个价格差异较大，比较置信度')
                            if small_confidence > large_confidence:
                                self.logger.debug(
                                    f'小写金额置信度更高，返回小写金额: {small_number_price}'
                                )
                                return small_number_price
                            else:
                                self.logger.debug(
                                    f'大写金额置信度更高，返回大写金额: {large_number_price}'
                                )
                                return large_number_price

                # 特殊处理：单元格值中同时包含小写和大写价格的情况
                if '（小写）' in value and '（大写）' in value:
                    # 提取小写价格
                    small_pattern = r'（小写）[￥¥]?\s*([\d,]+\.?\d*)'
                    small_match = re.search(small_pattern, value)
                    if small_match:
                        price_str = small_match.group(1)
                        small_number_price = self._str_to_float(price_str)
                        if small_number_price is not None:
                            self.logger.debug(
                                f'从结构化表格中提取到小写价格: {small_number_price} (原始字符串: {price_str})'
                            )
                            small_confidence = 95.0  # 高置信度

                    # 提取大写价格
                    large_pattern = r'（大写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
                    large_match = re.search(large_pattern, value)
                    if large_match:
                        chinese_num = large_match.group(1)
                        large_number_price = self._chinese_to_number(chinese_num)
                        if large_number_price is not None:
                            self.logger.debug(
                                f'从结构化表格中提取到汉字大写价格: {large_number_price} (原始字符串: {chinese_num})'
                            )
                            large_confidence = 95.0  # 高置信度

                    # 如果同时找到了小写和大写价格
                    if (
                        small_number_price is not None
                        and large_number_price is not None
                    ):
                        self.logger.debug(
                            f'找到两个价格: 小写金额={small_number_price}(置信度{small_confidence}), 大写金额={large_number_price}(置信度{large_confidence})'
                        )
                        # 如果两者相差很小，则认为是正确的，直接返回小写金额
                        if (
                            abs(small_number_price - large_number_price) < 1000
                        ):  # 允许一定误差
                            self.logger.debug('两个价格差异很小，返回小写金额')
                            return small_number_price
                        else:
                            # 如果数值差异较大，说明OCR可能出错，比较置信度
                            self.logger.debug('两个价格差异较大，比较置信度')
                            if small_confidence > large_confidence:
                                self.logger.debug(
                                    f'小写金额置信度更高，返回小写金额: {small_number_price}'
                                )
                                return small_number_price
                            else:
                                self.logger.debug(
                                    f'大写金额置信度更高，返回大写金额: {large_number_price}'
                                )
                                return large_number_price

        # 如果在循环中没有返回价格，检查是否有单个高置信度价格
        if small_number_price is not None and small_confidence >= 90.0:
            self.logger.debug(
                f'只找到小写金额: {small_number_price}(置信度{small_confidence})'
            )
            return small_number_price

        if large_number_price is not None and large_confidence >= 90.0:
            self.logger.debug(
                f'只找到大写金额: {large_number_price}(置信度{large_confidence})'
            )
            return large_number_price

        # 如果没有高置信度的价格，返回None
        self.logger.info('未能从结构化表格中提取到高置信度的价格')
        return None

    def _extract_price_from_full_content(self, content: str) -> float | None:
        """
        从全文中提取价格

        Args:
            content: 文本内容

        Returns:
            提取到的价格，如果未找到则返回None
        """
        # 使用所有价格模式在全文中查找
        for pattern in self.table_price_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                price_str = match if isinstance(match, str) else match[0]
                price = self._str_to_float(price_str)
                if price is not None and price > 1000:
                    self.logger.info(f'从全文中找到价格: {price} (通过模式: {pattern})')
                    return price

        self.logger.info('从全文中未能找到有效价格')
        return None

    def _str_to_float(self, s: str) -> float | None:
        """
        将字符串转换为浮点数，处理逗号分隔符

        Args:
            s: 字符串

        Returns:
            转换后的浮点数，如果转换失败则返回None
        """
        if not s:
            return None
        try:
            # 移除逗号、空格和货币符号
            cleaned = re.sub(r'[￥¥,\s]', '', s)
            result = float(cleaned)
            return result
        except ValueError:
            return None

    def _chinese_to_number(self, chinese_num: str) -> float | None:
        """
        将中文大写数字转换为阿拉伯数字

        Args:
            chinese_num: 中文大写数字字符串

        Returns:
            转换后的浮点数，如果转换失败则返回None
        """
        if not chinese_num:
            return None

        # 定义中文数字映射
        char_to_digit = {
            '零': 0,
            '一': 1,
            '二': 2,
            '三': 3,
            '四': 4,
            '五': 5,
            '六': 6,
            '七': 7,
            '八': 8,
            '九': 9,
        }

        # 单位映射
        unit_map = {'十': 10, '百': 100, '千': 1000, '万': 10000, '亿': 100000000}

        # 预处理：替换全角字符和可能的变体
        chinese_num = (
            chinese_num.replace('壹', '一')
            .replace('贰', '二')
            .replace('叁', '三')
            .replace('肆', '四')
            .replace('伍', '五')
            .replace('陆', '六')
            .replace('柒', '七')
            .replace('捌', '八')
            .replace('玖', '九')
            .replace('拾', '十')
            .replace('佰', '百')
            .replace('仟', '千')
            .replace('萬', '万')
            .replace('億', '亿')
            .replace('圓', '元')
            .replace('整', '')
        )

        # 去除非数字和单位字符
        cleaned = ''.join(c for c in chinese_num if c in char_to_digit or c in unit_map)

        if not cleaned:
            return None

        # 特殊处理：壹佰捌拾壹万元整 -> 1810000
        if '万' in cleaned:
            # 处理包含"万"的格式
            # 分解为万位部分和万以下部分
            parts = cleaned.split('万')
            if len(parts) >= 1:
                # 万位部分
                wan_part = parts[0]
                # 万以下部分
                below_wan_part = parts[1] if len(parts) > 1 else ''

                # 计算万位部分的值
                wan_value = self._convert_chinese_segment(
                    wan_part, char_to_digit, unit_map
                )

                # 计算万以下部分的值
                below_wan_value = (
                    self._convert_chinese_segment(
                        below_wan_part, char_to_digit, unit_map
                    )
                    if below_wan_part
                    else 0
                )

                result = wan_value * 10000 + below_wan_value
                return float(result)

        # 标准处理
        result = self._convert_chinese_segment(cleaned, char_to_digit, unit_map)
        return float(result)

    def _convert_chinese_segment(
        self, segment: str, char_to_digit: dict[str, int], unit_map: dict[str, int]
    ) -> int:
        """
        转换中文数字片段
        """
        if not segment:
            return 0

        result = 0
        temp = 0
        i = 0

        while i < len(segment):
            char = segment[i]

            if char in char_to_digit:
                digit = char_to_digit[char]
                # 查看下一个字符是否是单位
                if i + 1 < len(segment) and segment[i + 1] in unit_map:
                    unit = unit_map[segment[i + 1]]
                    temp += digit * unit
                    i += 2  # 跳过数字和单位
                else:
                    # 如果是最后一个字符或者是后面没有单位的数字
                    if i == len(segment) - 1 or (
                        i + 1 < len(segment) and segment[i + 1] not in unit_map
                    ):
                        temp += digit
                    i += 1
            elif char in unit_map:
                unit = unit_map[char]
                if unit == 10000 or unit == 100000000:  # 万或亿
                    result += (temp or 1) * unit
                    temp = 0
                else:
                    # 如果temp为0，说明是单独的单位（如"十万"中的"十"）
                    if temp == 0:
                        temp = unit
                    else:
                        temp *= unit
                i += 1
            else:
                i += 1

        result += temp
        return result

    def _extract_price_from_text(self, text: str, pattern: str) -> float | None:
        """
        从文本中提取价格

        Args:
            text: 文本内容
            pattern: 价格匹配模式

        Returns:
            提取到的价格，如果未找到则返回None
        """
        match = re.search(pattern, text)
        if match:
            price_str = match.group(1)
            return self._str_to_float(price_str)
        return None

    def _extract_chinese_price_from_text(self, text: str, pattern: str) -> float | None:
        """
        从文本中提取中文大写价格

        Args:
            text: 文本内容
            pattern: 中文大写价格匹配模式

        Returns:
            提取到的价格，如果未找到则返回None
        """
        match = re.search(pattern, text)
        if match:
            chinese_num = match.group(1)
            return self._chinese_to_number(chinese_num)
        return None

    def _extract_special_format_price(self, section: str) -> float | None:
        """
        专门处理用户提到的特殊格式价格：
        "（小写）¥1663634.00 元（含13%税） （大写）人发币壹佰陆陆万叁仟陆佰叁拾肆 元整"

        Args:
            section: 文本区域

        Returns:
            提取到的价格，如果未找到则返回None
        """
        # 查找特殊格式的价格
        special_patterns = [
            # 江苏鑫桥文件中的格式（放在最前面）
            r'（小写）[￥¥]?([\d,]+\.?\d*)元（写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)元整。含[\d%]*增值税',
            # 博达科技文件中的确切格式
            r'（小写）[￥¥]([\d,]+\.?\d*)\s*元（含[\d%]+税）\s*（大写）(.+?)\s*元整',
            # 博达科技文件中的另一种格式
            r'（小写）[￥¥]([\d,]+\.?\d*)\s*元（含[\d%]+税）\s*（大写）(.+)',
            # 江苏鑫桥文件中的格式
            r'（小写）[￥¥]?([\d,]+\.?\d*)元（写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)。含[\d%]+增值税。',
            # 广东创智文件中的格式（部分匹配）
            r'（小写）[￥¥]?([\d,]+\.?\d*)元（写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)',
            # 湖北三江博力智能装备有限公司的格式
            r'\(小写\)([\d,]+\.?\d+)\(大写\)([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            # 盐城大德涂装环保设备有限公司的格式
            r'\(小写\)([\d,]+\.?\d+)\(大写\)(人民币)?([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)(圆整)?',
            # 昆明苏净工贸有限公司的格式（表格格式）
            r'\(小写\)</td><td>([￥¥]?\s*[\d,]+\.?\d*)</td><td>\(大写\)</td><td>([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)',
            # 昆明苏净工贸有限公司的另一种格式
            r'\(小写\)\s*([￥¥]?\s*[\d,]+\.?\d*)\s*元?\s*\(大写\)\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)',
            # 昆明苏净工贸有限公司的表格格式（分离的小写和大写）
            r'<td>\(小写\)</td><td>([￥¥]?\s*[\d,]+\.?\d*)</td>(?:<td>\(大写\)</td><td>([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整\s]+)</td>)?',
            # 更通用的格式
            r'小写[）\)]\s*[￥¥]?\s*([\d,]+\.?\d*)\s*(?:万元|元)\s*[(（]大写[)）]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元万元整\s]+)',
        ]

        for pattern in special_patterns:
            match = re.search(pattern, section)
            if match:
                small_price_str = match.group(1)
                chinese_num = match.group(2) if len(match.groups()) >= 2 else None

                # 处理不同的捕获组情况
                if len(match.groups()) >= 3 and match.group(3):
                    # 如果有第3个捕获组，可能是大写金额
                    if any(
                        c in match.group(3)
                        for c in '壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿'
                    ):
                        chinese_num = match.group(3)
                    # 如果第2个捕获组不是大写金额，使用第3个
                    elif not any(
                        c in match.group(2)
                        for c in '壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿'
                    ):
                        chinese_num = match.group(3)

                small_number_price = self._str_to_float(small_price_str)
                # 对于使用(.+)捕获的大写金额，需要清理文本
                if chinese_num and '(.+)' in pattern:
                    chinese_num = re.sub(r'[\s元整圆]+$', '', chinese_num).strip()

                large_number_price = (
                    self._chinese_to_number(chinese_num) if chinese_num else None
                )

                self.logger.info(
                    f'从特殊格式中提取到小写价格: {small_number_price} (原始字符串: {small_price_str})'
                )
                self.logger.info(
                    f'从特殊格式中提取到大写价格: {large_number_price} (原始字符串: {chinese_num})'
                )

                # 如果两个价格都提取成功且相差不大，则返回小写价格
                if small_number_price is not None and large_number_price is not None:
                    if (
                        abs(small_number_price - large_number_price) < 10000
                    ):  # 允许一定误差
                        self.logger.info(
                            f'特殊格式价格验证通过，返回小写价格: {small_number_price}'
                        )
                        return small_number_price
                # 如果只有小写价格提取成功，且在合理范围内，也返回小写价格
                elif small_number_price is not None and small_number_price > 1000:
                    self.logger.info(
                        f'特殊格式只有小写价格提取成功，返回小写价格: {small_number_price}'
                    )
                    return small_number_price
