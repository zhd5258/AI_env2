import re
import logging
from typing import List, Dict, Any


class TableAnalyzerMixin:
    """表格分析混入类，提供表格形式评分规则提取功能"""

    def _extract_table_scoring_rules(self, text: str) -> List[Dict[str, Any]]:
        """专门提取表格格式的评分规则"""
        # 使用新的基于表格结构的方法
        table_rules = self._extract_table_scoring_rules_structured(text)

        # 如果新方法没有提取到规则，回退到旧方法
        if not table_rules:
            self.logger.warning('基于结构的表格提取失败，回退到旧方法')
            return self._extract_table_scoring_rules_old(text)

        return table_rules

    def _extract_table_scoring_rules_old(self, text: str) -> List[Dict[str, Any]]:
        """旧的表格评分规则提取方法（保留作为备选）"""
        table_rules = []

        # 查找包含评分标准的表格区域
        # 匹配类似"评价项目...分)"的模式
        table_patterns = [
            # 匹配格式如"xxx (5分)"的规则，限制分数范围避免错误识别
            r'([^\n]*?[\u4e00-\u9fa5]+[^\n]*)\s*\((\d{1,2}(?:\.\d)?)\s*分\)',
            # 匹配格式如"xxx 5分"的规则，限制分数范围避免错误识别
            r'([^\n]*?[\u4e00-\u9fa5]+[^\n]*)\s+(\d{1,2}(?:\.\d)?)\s*分',
            # 匹配范围评分如"xxx (0-5分)"的规则
            r'([^\n]*?[\u4e00-\u9fa5]+[^\n]*)\s*\(0-(\d{1,2}(?:\.\d)?)\s*分\)',
        ]

        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            # 检查是否包含评分相关关键词
            if any(
                keyword in line for keyword in ['分)', '分', '评分', '评价', '技术参数']
            ):
                # 尝试每种模式匹配
                for pattern in table_patterns:
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    for match in matches:
                        criteria_name = match[0].strip()
                        score_str = match[1]

                        # 清理评分项名称
                        criteria_name = self._clean_criteria_name(criteria_name)

                        # 过滤掉太短或太长的名称
                        if not (2 < len(criteria_name) < 100):
                            continue

                        # 检查是否包含价格相关关键词
                        is_price_criteria = (
                            '价格' in criteria_name
                            or '报价' in criteria_name
                            or '单价' in criteria_name
                            or '金额' in criteria_name
                            or '基准价' in criteria_name
                        )

                        # 验证分数是否有效
                        try:
                            score = float(score_str)
                            # 导入验证函数
                            from .utils import is_valid_score

                            if not is_valid_score(score):
                                continue  # 跳过无效分数
                        except ValueError:
                            continue  # 跳过无法转换为浮点数的分数

                        table_rules.append(
                            {
                                'numbering': (str(len(table_rules) + 1),),
                                'criteria_name': criteria_name,
                                'max_score': score,
                                'weight': 1.0,
                                'description': criteria_name,
                                'category': '评标办法',
                                'is_price_criteria': is_price_criteria,
                            }
                        )

            i += 1

        # 特殊处理价格分
        price_pattern = r'价格分[^\n]*?(\d{1,2}(?:\.\d)?)\s*分'
        price_matches = re.findall(price_pattern, text)
        for match in price_matches:
            score = float(match)
            # 验证分数是否有效且合理（价格分通常较高）
            from .utils import is_valid_score

            if score > 10 and is_valid_score(score):
                price_rule = {
                    'numbering': ('99',),
                    'criteria_name': '价格分',
                    'max_score': score,
                    'weight': 1.0,
                    'description': '价格分计算',
                    'category': '评标办法',
                    'is_price_criteria': True,
                }

                # 检查是否已存在价格分规则
                existing_price_rule = None
                for rule in table_rules:
                    if rule.get('is_price_criteria'):
                        existing_price_rule = rule
                        break

                if existing_price_rule:
                    # 更新现有价格规则
                    existing_price_rule.update(price_rule)
                else:
                    # 添加新的价格规则
                    table_rules.append(price_rule)

        # 特殊处理范围评分（如0-5分）
        range_pattern = (
            r'([^\n]*?[\u4e00-\u9fa5]+[^\n]*)\s*\(0-(\d{1,2}(?:\.\d)?)\s*分\)'
        )
        range_matches = re.findall(range_pattern, text)
        for match in range_matches:
            criteria_name = match[0].strip()
            max_score = match[1]

            # 清理评分项名称
            criteria_name = self._clean_criteria_name(criteria_name)

            # 过滤掉太短或太长的名称
            if not (2 < len(criteria_name) < 100):
                continue

            # 验证分数是否有效
            try:
                score = float(max_score)
                from .utils import is_valid_score

                if not is_valid_score(score):
                    continue  # 跳过无效分数
            except ValueError:
                continue  # 跳过无法转换为浮点数的分数

            # 检查是否已存在相同名称的规则
            existing_rule = None
            for rule in table_rules:
                if self._is_similar_criteria(rule['criteria_name'], criteria_name):
                    existing_rule = rule
                    break

            if not existing_rule:
                table_rules.append(
                    {
                        'numbering': (str(len(table_rules) + 1),),
                        'criteria_name': criteria_name,
                        'max_score': score,
                        'weight': 1.0,
                        'description': criteria_name,
                        'category': '评标办法',
                        'is_price_criteria': False,
                    }
                )

        # 移除重复规则
        table_rules = self._remove_duplicate_rules(table_rules)

        return table_rules

    def _extract_table_scoring_rules_structured(
        self, text: str
    ) -> List[Dict[str, Any]]:
        """基于表格结构提取评分规则"""
        table_rules = []

        # 按行分割文本
        lines = text.split('\n')

        # 查找包含评分标准的表格区域
        in_scoring_table = False
        table_lines = []

        for line in lines:
            # 检查是否进入评分表格区域
            if (
                any(keyword in line for keyword in ['评价项目', '评分项目', '评审项目'])
                and '分' in line
            ):
                in_scoring_table = True
                table_lines = [line]
                continue

            # 检查是否离开评分表格区域
            if in_scoring_table and any(
                keyword in line
                for keyword in ['合计', '总分', '价格分', '合计:', '总计:', '总得分']
            ):
                table_lines.append(line)
                # 处理价格分特殊行
                price_rules = self._process_price_line(line)
                if price_rules:
                    table_rules.extend(price_rules)
                break

            # 收集表格行
            if in_scoring_table:
                table_lines.append(line)

        # 处理表格行
        if len(table_lines) > 1:
            # 尝试识别表格结构
            processed_lines = self._process_structured_table_lines(table_lines)
            table_rules.extend(processed_lines)

        return table_rules

    def _process_structured_table_lines(self, lines: List[str]) -> List[Dict[str, Any]]:
        """处理结构化表格行，提取评分规则"""
        rules = []

        # 合并可能被换行符分割的单元格内容
        merged_lines = self._merge_broken_cells(lines)

        current_major_item = None
        current_major_score = 0

        for line in merged_lines:
            # 跳过表头行
            if any(keyword in line for keyword in ['评价项目', '评分项目', '评审项目']):
                continue

            # 处理三列表格结构：大项(分数) 细分项(分数) 评分标准
            # 模式：可能存在大项在前几列，细分项在后几列
            three_column_pattern = r'([^\(]+)\((\d{1,2}(?:\.\d)?)分\)\s+([^\(]+)\((\d{1,2}(?:\.\d)?)分\)\s+(.+)'
            three_match = re.search(three_column_pattern, line)

            if three_match:
                # 第一列：评分大项
                major_item = three_match.group(1).strip()
                major_score = float(three_match.group(2))

                # 验证分数是否有效
                from .utils import is_valid_score

                if not is_valid_score(major_score):
                    continue  # 跳过无效分数

                # 第二列：评分细分项
                minor_item = three_match.group(3).strip()
                minor_score = float(three_match.group(4))

                # 验证分数是否有效
                if not is_valid_score(minor_score):
                    continue  # 跳过无效分数

                # 第三列：评分标准
                criteria = three_match.group(5).strip()

                # 更新当前大项
                current_major_item = major_item
                current_major_score = major_score

                # 添加细分项规则
                rules.append(
                    {
                        'numbering': (str(len(rules) + 1),),
                        'criteria_name': minor_item,
                        'max_score': minor_score,
                        'weight': 1.0,
                        'description': criteria,
                        'category': '评标办法',
                        'is_price_criteria': False,
                    }
                )
                continue

            # 处理两列表格结构：项目(分数) 评分标准
            two_column_pattern = r'([^\(]+)\((\d{1,2}(?:\.\d)?)分\)\s+(.+)'
            two_match = re.search(two_column_pattern, line)

            if two_match:
                item = two_match.group(1).strip()
                score = float(two_match.group(2))

                # 验证分数是否有效
                from .utils import is_valid_score

                if not is_valid_score(score):
                    continue  # 跳过无效分数

                criteria = two_match.group(3).strip()

                # 特殊处理价格相关项
                is_price = '价格' in item or '报价' in item

                rules.append(
                    {
                        'numbering': (str(len(rules) + 1),),
                        'criteria_name': item,
                        'max_score': score,
                        'weight': 1.0,
                        'description': criteria,
                        'category': '评标办法',
                        'is_price_criteria': is_price,
                    }
                )
                continue

            # 处理只有项目名称和分数的情况
            item_score_pattern = r'([^\(]+)\((\d{1,2}(?:\.\d)?)分\)'
            item_score_match = re.search(item_score_pattern, line)

            if item_score_match:
                item = item_score_match.group(1).strip()
                score = float(item_score_match.group(2))

                # 验证分数是否有效
                from .utils import is_valid_score

                if not is_valid_score(score):
                    continue  # 跳过无效分数

                # 特殊处理价格相关项
                is_price = '价格' in item or '报价' in item

                rules.append(
                    {
                        'numbering': (str(len(rules) + 1),),
                        'criteria_name': item,
                        'max_score': score,
                        'weight': 1.0,
                        'description': item,  # 使用项目名称作为描述
                        'category': '评标办法',
                        'is_price_criteria': is_price,
                    }
                )

        return rules

    def _process_price_line(self, line: str) -> List[Dict[str, Any]]:
        """处理价格分特殊行"""
        rules = []

        # 处理价格分特殊行
        price_pattern = r'(价格分?|报价)\s*\((\d{1,2}(?:\.\d)?)分\)\s*(.+)'
        price_match = re.search(price_pattern, line)

        if price_match:
            price_item = price_match.group(1).strip()
            price_score = float(price_match.group(2))

            # 验证分数是否有效且合理（价格分通常较高）
            from .utils import is_valid_score

            if price_score > 10 and is_valid_score(price_score):
                price_criteria = price_match.group(3).strip()

                # 格式化价格计算描述，准备交给AI分析
                formatted_description = self._format_price_description(price_criteria)

                # 使用AI分析价格计算公式
                price_formula = self._analyze_price_formula_with_ai(
                    formatted_description
                )

                rules.append(
                    {
                        'numbering': (str(len(rules) + 1),),
                        'criteria_name': '价格分',
                        'max_score': price_score,
                        'weight': 1.0,
                        'description': formatted_description,
                        'price_formula': price_formula,  # 添加价格计算公式
                        'category': '评标办法',
                        'is_price_criteria': True,
                    }
                )

        return rules

    def _merge_broken_cells(self, lines: List[str]) -> List[str]:
        """
        合并可能被换行符分割的单元格内容
        通过检查行尾和行首的特征来判断是否应该合并
        """
        if not lines:
            return lines

        merged_lines = []
        i = 0

        while i < len(lines):
            current_line = lines[i].strip()

            # 如果当前行以某些特殊字符结尾，可能是被截断的单元格
            if current_line and not any(
                ending in current_line for ending in ['分)', '分', ':', '：']
            ):
                # 查看下一行是否以小写字母或数字开头，这可能表示是上一行的延续
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not re.match(r'^[\d\.]+\s*分', next_line)
                        and not any(
                            keyword in next_line
                            for keyword in ['评价项目', '评分项目', '评审项目']
                        )
                    ):
                        # 合并这两行
                        current_line = current_line + ' ' + next_line
                        i += 1  # 跳过下一行，因为它已经被合并了

            merged_lines.append(current_line)
            i += 1

        return merged_lines

    def _format_price_description(self, description: str) -> str:
        """
        格式化价格计算描述，去除不必要的符号
        """
        # 去除换行符和回车符
        formatted = re.sub(r'[\r\n]+', ' ', description)

        # 将中文标点符号替换为英文标点符号
        replacements = {
            '，': ',',
            '。': '.',
            '：': ':',
            '；': ';',
            '（': '(',
            '）': ')',
            '“': '"',
            '”': '"',
            '‘': "'",
            '’': "'",
            '《': '<',
            '》': '>',
        }

        for chinese, english in replacements.items():
            formatted = formatted.replace(chinese, english)

        # 去除多余的空格
        formatted = re.sub(r'\s+', ' ', formatted).strip()

        return formatted

    def _analyze_price_formula_with_ai(self, description: str) -> str:
        """
        使用AI分析价格计算描述，提取价格计算公式
        """
        try:
            # 构建AI分析提示
            prompt = f"""
请分析以下价格评分计算描述，提取其中的价格计算公式和变量定义：

描述: {description}

请按照以下格式返回结果：
1. 价格计算公式:
2. 变量定义:
3. 计算说明:

如果描述中没有明确的价格计算公式，请返回"未找到明确的价格计算公式"
"""

            # 调用AI分析器
            from modules.local_ai_analyzer import LocalAIAnalyzer

            ai_analyzer = LocalAIAnalyzer()
            response = ai_analyzer.analyze_text(prompt)

            if response and not response.startswith('Error:'):
                return response.strip()
            else:
                self.logger.warning(f'AI分析价格公式失败: {response}')
                return 'AI分析失败'

        except Exception as e:
            self.logger.error(f'使用AI分析价格公式时出错: {e}')
            return 'AI分析出错'
