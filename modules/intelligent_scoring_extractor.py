import re
import json
import logging
from typing import List, Dict, Any
from modules.local_ai_analyzer import LocalAIAnalyzer


class IntelligentScoringExtractor:
    def __init__(self, pages: List[str]):
        self.pages = pages
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.ai_analyzer = LocalAIAnalyzer()

    def _build_tree_from_flat_list(
        self, flat_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从扁平的规则列表构建层级树结构，确保正确区分子项和母项"""
        if not flat_list:
            return []

        # 按编号排序，确保层级关系正确
        flat_list.sort(key=lambda x: x['numbering'])

        tree = []
        # 使用一个栈来追踪当前层级的父节点
        parent_stack: List[Dict[str, Any]] = []

        for item in flat_list:
            item['children'] = []
            level = len(item['numbering'])

            # 根据当前项的层级调整父节点栈
            # 只有当父节点的层级小于当前项时才保留
            while parent_stack and len(parent_stack[-1]['numbering']) >= level:
                parent_stack.pop()

            if not parent_stack:
                # 如果栈为空，说明是顶级节点
                tree.append(item)
            else:
                # 否则，是栈顶节点的子节点
                parent_stack[-1]['children'].append(item)

            # 将当前项压入栈，作为后续节点的潜在父节点
            parent_stack.append(item)

        # 验证层级结构，确保没有重叠
        self._validate_tree_structure(tree)

        return tree

    def _validate_tree_structure(self, tree: List[Dict[str, Any]]):
        """验证树结构，确保没有重叠和错误"""
        for rule in tree:
            if rule['children']:
                # 检查子项分数之和是否等于父项分数
                children_sum = sum(child['max_score'] for child in rule['children'])
                if abs(rule['max_score'] - children_sum) > 0.1:
                    self.logger.warning(
                        f"父项 '{rule['criteria_name']}' 分数 ({rule['max_score']}) "
                        f'与子项分数之和 ({children_sum}) 不匹配'
                    )

                # 递归验证子项
                self._validate_tree_structure(rule['children'])

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        从招标文件的"评标办法"章节提取所有评分规则，包括结构化评分项和文字描述的价格分计算公式。
        """
        try:
            full_text = '\n'.join(self.pages)
            self.logger.info(f'开始分析招标文件，总长度: {len(full_text)} 字符')

            # 1. 定位并提取"评标办法"章节的文本内容
            evaluation_section_text = self._extract_scoring_section(full_text)

            # 记录提取的章节信息
            if evaluation_section_text:
                self.logger.info(
                    f'提取的评标章节长度: {len(evaluation_section_text)} 字符'
                )
            else:
                self.logger.warning('未能提取到评标章节内容')
                # 如果无法提取特定章节，则使用全文进行分析
                evaluation_section_text = full_text
                self.logger.info('使用全文进行评分规则提取')

            # 2. 从章节文本中提取所有结构化的评分项
            #    使用正则表达式匹配如"1.1.1 xxx (10分)"的模式
            structured_rules = self._parse_rules_from_text(evaluation_section_text)

            # 3. 专门查找表格中的评分规则
            table_rules = self._extract_table_scoring_rules(evaluation_section_text)
            if table_rules:
                structured_rules.extend(table_rules)
                self.logger.info(f'从表格中提取到 {len(table_rules)} 条评分规则')

            # 4. 从章节文本中专门查找价格分计算公式，并将其添加/更新到规则列表中
            final_rules = self._find_and_add_price_rule(
                evaluation_section_text, structured_rules
            )

            # 5. 如果规则提取失败，尝试使用AI辅助分析整个章节
            if not final_rules:
                self.logger.warning('结构化规则提取失败，尝试使用AI辅助分析...')
                # 使用全文进行AI分析，而不仅仅是章节内容
                final_rules = self._ai_extract_rules(full_text)

            # 6. 如果AI分析也失败，使用默认规则
            if not final_rules:
                self.logger.warning('AI分析也失败，使用默认评分规则...')
                final_rules = self._get_default_scoring_rules()

            # 7. 将扁平的规则列表构建成层级树
            if final_rules:
                tree = self._build_tree_from_flat_list(final_rules)
                self._verify_and_adjust_scores(tree)  # 验证并调整分数
                self.logger.info(f'成功提取到 {len(final_rules)} 条评分规则')
                return tree

            self.logger.warning('未能从评标办法章节提取到任何评分规则。')
            return []
        except Exception as e:
            self.logger.error(f'提取评分规则时发生严重错误: {e}', exc_info=True)
            # 发生严重错误时返回默认规则
            try:
                default_rules = self._get_default_scoring_rules()
                if default_rules:
                    tree = self._build_tree_from_flat_list(default_rules)
                    self._verify_and_adjust_scores(tree)
                    return tree
            except Exception as fallback_e:
                self.logger.error(f'回退到默认规则也失败: {fallback_e}')
            return []

    def _extract_table_scoring_rules(self, text: str) -> List[Dict[str, Any]]:
        """专门提取表格格式的评分规则"""
        table_rules = []

        # 查找包含评分标准的表格区域
        # 匹配类似"评价项目...分)"的模式
        table_patterns = [
            r'([\u4e00-\u9fa5]+[^\n]*)\s*\((\d+(?:\.\d+)?)\s*分\)',
            r'([\u4e00-\u9fa5]+[^\n]*)\s*\(0-(\d+(?:\.\d+)?)\s*分\)',
            r'([\u4e00-\u9fa5]+[^\n]*)\s*\(\s*(\d+(?:\.\d+)?)\s*分\s*\)',
            # 新增模式：处理类似"评价项目(5分)"的格式
            r'([\u4e00-\u9fa5]+.*?)\s*\((\d+(?:\.\d+)?)\s*分\)',
            # 新增模式：处理类似"评价项目 5分"的格式
            r'([\u4e00-\u9fa5]+.*?)\s+(\d+(?:\.\d+)?)\s*分',
        ]

        lines = text.split('\n')
        for line in lines:
            # 检查是否包含评分相关关键词
            if any(
                keyword in line
                for keyword in ['分)', '分)', '评分', '评价', '技术参数']
            ):
                # 尝试每种模式匹配
                for pattern in table_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        criteria_name = match[0].strip()
                        score_str = match[1]

                        # 过滤掉太短或太长的名称
                        if 2 < len(criteria_name) < 100:
                            # 清理评分项名称，去除多余的描述
                            criteria_name = re.sub(
                                r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', criteria_name
                            ).strip()
                            criteria_name = re.sub(r'\s+', ' ', criteria_name).strip()

                            # 检查是否包含价格相关关键词
                            is_price_criteria = (
                                '价格' in criteria_name
                                or '报价' in criteria_name
                                or '单价' in criteria_name
                                or '金额' in criteria_name
                                or '基准价' in criteria_name
                            )

                            # 检查是否已存在相同名称的规则
                            existing_rule = None
                            for rule in table_rules:
                                if rule['criteria_name'] == criteria_name:
                                    existing_rule = rule
                                    break

                            if existing_rule:
                                # 如果已存在，更新分数（取最大值）
                                existing_rule['max_score'] = max(
                                    existing_rule['max_score'], float(score_str)
                                )
                            else:
                                table_rules.append(
                                    {
                                        'numbering': (str(len(table_rules) + 1),),
                                        'criteria_name': criteria_name,
                                        'max_score': float(score_str),
                                        'weight': 1.0,
                                        'description': criteria_name,
                                        'category': '评标办法',
                                        'is_price_criteria': is_price_criteria,
                                    }
                                )

    # 特殊处理价格分
    price_pattern = r'价格分[^\n]*?(\d+(?:\.\d+)?)\s*分'
    price_matches = re.findall(price_pattern, text)
    for match in price_matches:
        if float(match) > 10:  # 价格分通常较高
            table_rules.append(
                {
                    'numbering': ('99',),
                    'criteria_name': '价格分',
                    'max_score': float(match),
                    'weight': 1.0,
                    'description': '价格分计算',
                    'category': '评标办法',
                    'is_price_criteria': True,
                }
            )

    # 特殊处理范围评分（如0-5分）
    range_pattern = r'([\u4e00-\u9fa5]+.*?)\s*\(0-(\d+(?:\.\d+)?)\s*分\)'
    range_matches = re.findall(range_pattern, text)
    for match in range_matches:
        criteria_name = match[0].strip()
        max_score = match[1]

        # 过滤掉太短或太长的名称
        if 2 < len(criteria_name) < 100:
            # 清理评分项名称
            criteria_name = re.sub(
                r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', criteria_name
            ).strip()
            criteria_name = re.sub(r'\s+', ' ', criteria_name).strip()

            # 检查是否已存在相同名称的规则
            existing_rule = None
            for rule in table_rules:
                if rule['criteria_name'] == criteria_name:
                    existing_rule = rule
                    break

            if not existing_rule:
                table_rules.append(
                    {
                        'numbering': (str(len(table_rules) + 1),),
                        'criteria_name': criteria_name,
                        'max_score': float(max_score),
                        'weight': 1.0,
                        'description': criteria_name,
                        'category': '评标办法',
                        'is_price_criteria': False,
                    }
                )

    return table_rules

    def _parse_rules_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析出所有结构化的评分规则项"""
        # 匹配各种编号格式，如 1. | (1) | 一、 | （一）等 - 扩展更多模式
        # 优化正则表达式以更好地匹配评分规则
        rule_patterns = [
            # 标准格式：1.1.1 评分项名称 (10分)
            r'^\s*(\d+(?:\.\d+)*)\s*([^\n]*?)\s*\((\d+(?:\.\d+)?)\s*分\)',
            # 格式：(1) 评分项名称 10分
            r'^\s*\((\d+(?:\.\d+)*)\)\s*([^\n]*?)\s*(\d+(?:\.\d+)?)\s*分',
            # 格式：一、评分项名称 (10分)
            r'^\s*([一二三四五六七八九十]+[、\.]?)\s*([^\n]*?)\s*\((\d+(?:\.\d+)?)\s*分\)',
            # 格式：1. 评分项名称 10分
            r'^\s*(\d+(?:\.\d+)*)[、\.]?\s*([^\n]*?)\s*(\d+(?:\.\d+)?)\s*分',
            # 格式：A. 评分项名称 (10分)
            r'^\s*([A-Z])[、\.]?\s*([^\n]*?)\s*\((\d+(?:\.\d+)?)\s*分\)',
            # 格式：评分项名称 10分（没有编号前缀）
            r'^\s*([^\n]*?)\s*\((\d+(?:\.\d+)?)\s*分\)',
            # 新增格式：评分项名称 10分（在行尾）
            r'([^\n]*?)\s+(\d+(?:\.\d+)?)\s*分[^\n]*$',
        ]

        flat_rules = []

        # 尝试每种模式
        for i, pattern in enumerate(rule_patterns):
            rule_pattern = re.compile(pattern, re.MULTILINE)
            for match in rule_pattern.finditer(text):
                groups = match.groups()

                # 根据不同的模式解析组
                if i == 0:  # 标准格式：编号、名称、分数
                    numbering_str = groups[0]
                    criteria_name = groups[1].strip()
                    score_str = groups[2]
                elif i == 1:  # 格式：(编号) 名称 分数
                    numbering_str = groups[0]
                    criteria_name = groups[1].strip()
                    score_str = groups[2]
                elif i == 2:  # 格式：中文编号 名称 (分数)
                    numbering_str = groups[0]
                    criteria_name = groups[1].strip()
                    score_str = groups[2]
                elif i == 3:  # 格式：数字编号 名称 分数
                    numbering_str = groups[0]
                    criteria_name = groups[1].strip()
                    score_str = groups[2]
                elif i == 4:  # 格式：字母编号 名称 (分数)
                    numbering_str = groups[0]
                    criteria_name = groups[1].strip()
                    score_str = groups[2]
                elif i == 5:  # 无编号前缀的格式
                    numbering_str = ''
                    criteria_name = groups[0].strip()
                    score_str = groups[1]
                elif i == 6:  # 行尾格式
                    criteria_name = groups[0].strip()
                    score_str = groups[1]
                    numbering_str = ''
                else:
                    continue

                # 清理编号和名称
                if numbering_str:
                    numbering_str = numbering_str.strip('()（）、. ')
                    # 将中文数字和带点的数字统一处理
                    numbering_tuple = tuple(
                        part for part in re.split(r'[.\-、]', numbering_str) if part
                    )
                else:
                    # 对于无编号的条目，使用行号作为编号
                    line_num = len(flat_rules) + 1
                    numbering_tuple = (str(line_num),)

                # 忽略无效的匹配
                if not criteria_name or not score_str:
                    continue

                # 过滤掉明显不是评分项的内容
                if len(criteria_name) > 100 or len(criteria_name) < 2:
                    continue

                # 检查是否包含价格相关关键词
                is_price_criteria = (
                    '价格' in criteria_name
                    or '报价' in criteria_name
                    or '单价' in criteria_name
                    or '金额' in criteria_name
                    or '基准价' in criteria_name
                )

                flat_rules.append(
                    {
                        'numbering': numbering_tuple,
                        'criteria_name': criteria_name,
                        'max_score': float(score_str),
                        'weight': 1.0,
                        'description': criteria_name,  # 默认描述为名称
                        'category': '评标办法',
                        'is_price_criteria': is_price_criteria,
                    }
                )

        self.logger.info(f'从文本中解析出 {len(flat_rules)} 条结构化评分规则。')

        # 如果没有解析到规则，尝试更宽松的匹配
        if len(flat_rules) == 0:
            self.logger.warning('未通过标准模式匹配到评分规则，尝试更宽松的匹配...')
            # 查找包含"分"的所有行
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if '分' in line and len(line.strip()) > 5:
                    # 尝试提取分数
                    score_match = re.search(r'(\d+(?:\.\d+)?)\s*分', line)
                    if score_match:
                        score = float(score_match.group(1))
                        # 提取评分项名称（去除分数部分）
                        name = re.sub(r'\s*\d+(?:\.\d+)?\s*分.*$', '', line).strip()
                        name = re.sub(
                            r'^\s*[\d\.\(\)（）、一二三四五六七八九十]+[、\.]?\s*',
                            '',
                            name,
                        ).strip()

                        if name and len(name) > 2 and len(name) < 100:
                            flat_rules.append(
                                {
                                    'numbering': (str(len(flat_rules) + 1),),
                                    'criteria_name': name,
                                    'max_score': score,
                                    'weight': 1.0,
                                    'description': name,
                                    'category': '评标办法',
                                    'is_price_criteria': '价格' in name
                                    or '报价' in name
                                    or '基准价' in name,
                                }
                            )

            self.logger.info(f'通过宽松匹配解析出 {len(flat_rules)} 条评分规则。')

        # 如果仍然没有解析到规则，尝试在整个文本中查找评分相关的内容
        if len(flat_rules) == 0:
            self.logger.warning('仍然未匹配到评分规则，尝试在整个文本中查找...')
            # 查找包含评分关键词的段落
            scoring_keywords = ['评分', '评审', '评价', '打分', '技术分', '商务分']
            for keyword in scoring_keywords:
                # 查找包含关键词的段落
                pattern = rf'({keyword}.*?)(\d+(?:\.\d+)?)\s*分'
                matches = re.findall(pattern, text, re.DOTALL)
                for match in matches:
                    name = match[0].strip()
                    score = float(match[1])
                    if name and len(name) > 2 and len(name) < 100:
                        flat_rules.append(
                            {
                                'numbering': (str(len(flat_rules) + 1),),
                                'criteria_name': name,
                                'max_score': score,
                                'weight': 1.0,
                                'description': name,
                                'category': '评标办法',
                                'is_price_criteria': '价格' in name
                                or '报价' in name
                                or '基准价' in name,
                            }
                        )

            self.logger.info(f'通过关键词查找解析出 {len(flat_rules)} 条评分规则。')

        return flat_rules

    def _find_and_add_price_rule(
        self, text: str, rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """在文本中查找价格分计算公式，并将其添加或更新到规则列表中"""
        # 价格分计算公式的常见关键字 - 扩展更多关键字
        price_keywords = [
            '价格分',
            '报价得分',
            '投标报价得分',
            '评标基准价',
            '价格得分',
            '报价分',
            '投标报价分',
            '评标价',
            '基准价',
            '价格计算',
            '报价计算',
            '价格评分',
            '最低评标价',
            '评标基准价格',
            '投标基准价',
        ]

        # 更全面的价格分计算公式匹配模式
        price_formula_patterns = [
            r'.*?((?:评标基准价|投标报价|评标价|基准价)[^\n]*?(?:价格分|报价)[^\n]*?计算[^\n]+)',
            r'.*?((?:价格分|报价得分|价格评分)[^\n]*?计算[^\n]+)',
            r'.*?((?:基准价|评标价|最低评标价)[^\n]*?(?:得分|分值)[^\n]*?计算[^\n]+)',
            r'.*?(\d+分[^\n]*?(?:价格|报价)[^\n]*?计算[^\n]+)',
            r'.*?((?:价格|报价)[^\n]*?(?:计算方法|计算公式)[^\n]+)',
            r'.*?((?:评标基准价|投标报价|评标价|基准价)\s*=\s*[^\n]+)',
        ]

        formula_text = ''
        # 尝试每种模式
        for pattern in price_formula_patterns:
            price_formula_pattern = re.compile(pattern, re.IGNORECASE)
            formula_match = price_formula_pattern.search(text)
            if formula_match:
                formula_text = formula_match.group(1).strip()
                # 清理公式文本
                formula_text = re.sub(r'\s+', ' ', formula_text)  # 合并多个空格
                formula_text = formula_text.strip('：: \t\n\r')  # 清理首尾字符
                if formula_text:
                    break

        # 如果没找到公式，尝试查找包含价格关键词的句子
        if not formula_text:
            lines = text.split('\n')
            for line in lines:
                # 查找包含价格关键词且相对较长的行
                if (
                    any(keyword in line for keyword in price_keywords)
                    and '分' in line
                    and len(line.strip()) > 10
                ):
                    formula_text = line.strip()
                    break

        # 如果仍然没找到，尝试更宽松的匹配
        if not formula_text:
            # 查找包含"价格"和"分"的行
            lines = text.split('\n')
            for line in lines:
                if (
                    ('价格' in line or '报价' in line)
                    and '分' in line
                    and len(line.strip()) > 5
                ):
                    formula_text = line.strip()
                    break

        if not formula_text:
            self.logger.warning('在评标办法中未找到明确的价格分计算公式。')
            # 即使没有找到公式，也要确保有一个价格分规则
            # 检查现有规则中是否已经有价格分规则
            has_price_rule = any(rule.get('is_price_criteria', False) for rule in rules)
            if not has_price_rule and rules:
                # 如果没有价格分规则，但有其他规则，尝试从现有规则中识别可能的价格规则
                for rule in rules:
                    criteria_name = rule.get('criteria_name', '')
                    if any(keyword in criteria_name for keyword in ['价格', '报价']):
                        rule['is_price_criteria'] = True
                        rule['description'] = '价格分计算公式：根据招标文件要求计算'
                        self.logger.info(f"标记 '{criteria_name}' 为价格分规则")
                        return rules

            return rules

        self.logger.info(f'成功提取到价格分计算公式: {formula_text}')

        # 查找现有的价格分规则项以便更新
        price_rule_found = False
        for rule in rules:
            if rule.get('is_price_criteria'):
                self.logger.info(
                    f"找到现有的价格分规则 '{rule['criteria_name']}'，将更新其描述为计算公式。"
                )
                rule['description'] = formula_text
                rule['is_price_criteria'] = True  # 确保标记
                price_rule_found = True
                break

        # 如果没有找到现有的价格分规则项，则创建一个新的
        if not price_rule_found:
            self.logger.info(
                '未找到结构化的价格分规则，将根据提取的公式创建一个新的规则项。'
            )

            # 尝试从公式文本中提取价格分满分
            max_score_match = re.search(r'(\d+(?:\.\d+)?)\s*分', formula_text)
            max_score = (
                float(max_score_match.group(1)) if max_score_match else 30.0
            )  # 默认30分

            rules.append(
                {
                    'numbering': ('99',),  # 给一个特殊的编号，使其排在最后
                    'criteria_name': '价格分',
                    'max_score': max_score,
                    'weight': 1.0,
                    'description': formula_text,
                    'category': '评标办法',
                    'is_price_criteria': True,
                    'children': [],  # 确保有children字段
                }
            )

        return rules

    def _extract_evaluation_rules_from_table(self, text: str) -> List[Dict[str, Any]]:
        """此函数不再使用，逻辑已合并到 extract_scoring_rules 和 _parse_rules_from_text 中"""
        self.logger.warning('_extract_evaluation_rules_from_table 已被弃用。')
        return []

    def _build_hierarchical_structure(
        self, flat_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """此函数不再使用，逻辑已合并到 _build_tree_from_flat_list 中"""
        self.logger.warning('_build_hierarchical_structure 已被弃用。')
        return []

    def _extract_qualification_rules(self, text: str) -> List[Dict[str, Any]]:
        """提取资格审查规则（投标人须知等章节）"""
        qualification_keywords = ['投标人须知', '资格要求', '资质条件', '资格审查']
        qualification_rules = []

        lines = text.split('\n')
        in_qualification_section = False
        current_section = ''

        for line in lines:
            # 检查是否进入资格审查章节
            if any(keyword in line for keyword in qualification_keywords):
                in_qualification_section = True
                current_section = line.strip()
                continue

            # 如果在资格审查章节中
            if in_qualification_section:
                # 检查是否离开资格审查章节（遇到其他章节标题）
                if line.strip() and (
                    line.strip().startswith('第')
                    and '章' in line
                    or line.strip().startswith('章')
                    or '评标' in line
                    or '评分' in line
                ):
                    in_qualification_section = False
                    break

                # 提取带*号的否决项规则
                if '*' in line and len(line.strip()) > 5:
                    qualification_rules.append(
                        {
                            'criteria_name': line.strip(),
                            'max_score': 0,  # 资格审查规则不参与评分
                            'weight': 0,
                            'description': '资格审查规则，违反则否决投标',
                            'category': '资格审查',
                            'children': [],
                            'is_veto': True,  # 标记为否决项
                        }
                    )

        return qualification_rules

    def _extract_veto_rules(self, text: str) -> List[Dict[str, Any]]:
        """提取否决项规则（带*标记的条款）"""
        veto_rules = []

        lines = text.split('\n')
        for line in lines:
            # 查找带*号的条款
            if '*' in line and len(line.strip()) > 5:
                # 提取*号后的内容作为规则名称
                rule_name = line.split('*')[-1].strip()
                if rule_name:
                    veto_rules.append(
                        {
                            'criteria_name': rule_name,
                            'max_score': 0,  # 否决项不参与评分
                            'weight': 0,
                            'description': '否决项规则，违反则否决投标',
                            'category': '否决项',
                            'children': [],
                            'is_veto': True,
                        }
                    )

        return veto_rules

    def _extract_evaluation_rules(self, text: str) -> List[Dict[str, Any]]:
        """提取评分项规则（评标办法等章节）"""
        # 寻找评标办法相关的章节
        evaluation_keywords = ['评标办法', '评分标准', '评审标准', '打分标准']

        lines = text.split('\n')
        start_idx = -1
        end_idx = len(lines)

        # 查找评标办法章节的开始位置
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in evaluation_keywords):
                start_idx = i
                break

        if start_idx == -1:
            return []  # 没有找到评标办法章节

        # 查找章节结束位置
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip()
            if line and (
                line.startswith('第')
                and '章' in line
                or line.startswith('章')
                or '合同' in line
                or '附件' in line
            ):
                end_idx = i
                break

        # 提取评标办法章节内容
        evaluation_section = '\n'.join(lines[start_idx:end_idx])

        # 在评标办法章节中提取评分规则
        # 查找包含分数的行
        scoring_lines = []
        for line in evaluation_section.split('\n'):
            if '分' in line and re.search(r'\d+(?:\.\d+)?', line):
                scoring_lines.append(line.strip())

        # 解析评分规则
        flat_rules = []
        for i, line in enumerate(scoring_lines):
            # 尝试提取评分项名称和分数
            # 模式: "评分项名称 X分" 或 "评分项名称(X分)"
            match = re.search(r'^([^(\n]+?)\s*(\d+(?:\.\d+)?)\s*分', line)
            if not match:
                match = re.search(r'^([^(\n]+?)\s*\((\d+(?:\.\d+)?)\s*分\)', line)

            if match:
                name, score = match.groups()
                flat_rules.append(
                    {
                        'numbering': [i + 1],
                        'criteria_name': name.strip(),
                        'max_score': float(score),
                        'weight': 1.0,
                        'description': '',
                        'category': '评分项',
                    }
                )

        # 构建层级结构
        if flat_rules:
            structured_rules = self._build_tree_from_flat_list(flat_rules)
            self._verify_and_adjust_scores(structured_rules)
            return structured_rules

        return []

    def _ai_analyze_scoring_rules(
        self, scoring_section: str, extracted_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """使用AI辅助分析评分规则，确保总分不超过100分"""
        try:
            # 构建AI分析提示词
            prompt = f"""
请分析以下招标文件中的评分规则，并返回正确的评分规则结构。

招标文件内容：
{scoring_section}

当前提取的评分规则：
{json.dumps(extracted_rules, ensure_ascii=False, indent=2)}

请仔细分析并返回正确的评分规则，要求：
1. 总分必须等于100分
2. 保持规则的层级结构
3. 确保父项分数等于子项分数之和
4. 如果发现重复或错误的规则，请修正
5. 对于价格分规则，请保留"is_price_rule": true标记
6. 只返回JSON格式的评分规则，不要包含其他内容

返回格式示例：
[
  {{
    "criteria_name": "技术方案",
    "max_score": 60,
    "weight": 1.0,
    "children": [
      {{
        "criteria_name": "技术方案完整性",
        "max_score": 30,
        "weight": 1.0,
        "children": []
      }},
      {{
        "criteria_name": "技术方案可行性",
        "max_score": 30,
        "weight": 1.0,
        "children": []
      }}
    ]
  }},
  {{
    "criteria_name": "商务报价",
    "max_score": 40,
    "weight": 1.0,
    "children": []
  }}
]
"""

            # 调用AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)

            # 解析AI响应
            if ai_response and not ai_response.startswith('Error:'):
                try:
                    # 尝试从AI响应中提取JSON
                    json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
                    if json_match:
                        ai_rules = json.loads(json_match.group())

                        # 验证AI返回的规则
                        total_score = sum(rule['max_score'] for rule in ai_rules)
                        if abs(total_score - 100.0) < 0.1:  # 允许小的浮点数误差
                            self.logger.info('AI分析完成，总分: %s', total_score)
                            return ai_rules
                        else:
                            self.logger.warning(
                                'AI返回的规则总分不正确: %s，使用原始规则', total_score
                            )
                    else:
                        self.logger.warning(
                            'AI响应中未找到有效的JSON格式，使用原始规则'
                        )
                except json.JSONDecodeError as e:
                    self.logger.warning('AI响应JSON解析失败: %s，使用原始规则', e)
            else:
                self.logger.warning('AI分析失败: %s，使用原始规则', ai_response)

        except Exception as e:
            self.logger.error('AI分析过程中发生错误: %s，使用原始规则', e)

        # 如果AI分析失败，返回原始规则
        return extracted_rules

    def _ai_extract_rules(self, text: str) -> List[Dict[str, Any]]:
        """使用AI辅助从文本中提取评分规则"""
        try:
            # 如果文本太长，进行截取以避免超出AI模型的处理能力
            max_length = 15000  # 限制在15000字符以内
            if len(text) > max_length:
                self.logger.info(
                    f'文本长度 {len(text)} 超过限制，截取前 {max_length} 个字符'
                )
                text = text[:max_length]

            # 构建AI分析提示词 - 增强提示词以更好地处理各种格式
            prompt = f"""
你是一个专业的招投标评标专家，请从以下招标文件内容中提取评分规则，并以指定的JSON格式返回。

招标文件内容：
{text}

请仔细分析并返回评分规则，要求：
1. 总分必须等于100分
2. 保持规则的层级结构
3. 确保父项分数等于子项分数之和
4. 正确识别价格分规则并标记"is_price_criteria": true
5. 只返回JSON格式的评分规则，不要包含其他内容
6. 如果内容中包含表格形式的评分标准，请特别注意提取
7. 注意识别"评价项目"、"评价内容"、"评分标准"、"评标办法"等标题下的内容
8. 价格分通常包含"价格"、"报价"、"基准价"等关键词
9. 请分析整个文档内容，不要只关注某一部分
10. 如果找不到明确的评分规则，请根据文档内容推断合理的评分标准

返回格式示例：
[
  {{
    "numbering": ["1"],
    "criteria_name": "技术方案",
    "max_score": 60,
    "weight": 1.0,
    "description": "技术方案评分",
    "category": "评标办法",
    "children": [
      {{
        "numbering": ["1", "1"],
        "criteria_name": "技术方案完整性",
        "max_score": 30,
        "weight": 1.0,
        "description": "技术方案完整性评分",
        "category": "评标办法",
        "children": [],
        "is_price_criteria": false
      }},
      {{
        "numbering": ["1", "2"],
        "criteria_name": "技术方案可行性",
        "max_score": 30,
        "weight": 1.0,
        "description": "技术方案可行性评分",
        "category": "评标办法",
        "children": [],
        "is_price_criteria": false
      }}
    ],
    "is_price_criteria": false
  }},
  {{
    "numbering": ["2"],
    "criteria_name": "价格分",
    "max_score": 40,
    "weight": 1.0,
    "description": "价格分计算公式...",
    "category": "评标办法",
    "children": [],
    "is_price_criteria": true
  }}
]
"""

            # 调用AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)

            # 解析AI响应
            if ai_response and not ai_response.startswith('Error:'):
                try:
                    # 尝试从AI响应中提取JSON
                    # 更宽松的JSON提取，处理可能的格式问题
                    json_match = re.search(r'\[[\s\S]*\]', ai_response, re.DOTALL)
                    if not json_match:
                        # 如果没有找到方括号，尝试查找大括号包围的对象数组
                        json_match = re.search(r'\{{[\s\S]*\}}', ai_response, re.DOTALL)

                    if json_match:
                        json_str = json_match.group()
                        # 清理JSON字符串，移除可能的注释和多余内容
                        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

                        ai_rules = json.loads(json_str)

                        # 验证AI返回的规则
                        if isinstance(ai_rules, list) and len(ai_rules) > 0:
                            total_score = sum(
                                rule.get('max_score', 0) for rule in ai_rules
                            )
                            if abs(total_score - 100.0) < 10.0:  # 放宽到10分的误差
                                self.logger.info(
                                    f'AI辅助提取完成，提取到 {len(ai_rules)} 条规则，总分: {total_score}'
                                )
                                return ai_rules
                            else:
                                self.logger.warning(
                                    f'AI返回的规则总分不正确: {total_score}，使用默认规则'
                                )
                        else:
                            self.logger.warning(
                                'AI响应中未找到有效的规则列表，使用默认规则'
                            )
                    else:
                        self.logger.warning(
                            'AI响应中未找到有效的JSON格式，使用默认规则'
                        )
                        # 尝试直接解析整个响应
                        try:
                            ai_rules = json.loads(ai_response)
                            if isinstance(ai_rules, list) and len(ai_rules) > 0:
                                self.logger.info(
                                    f'直接解析AI响应成功，提取到 {len(ai_rules)} 条规则'
                                )
                                return ai_rules
                        except json.JSONDecodeError:
                            pass
                except json.JSONDecodeError as e:
                    self.logger.warning(f'AI响应JSON解析失败: {e}，使用默认规则')
                    self.logger.debug(f'AI响应内容: {ai_response}')
            else:
                self.logger.warning(f'AI分析失败: {ai_response}，使用默认规则')

        except Exception as e:
            self.logger.error(f'AI分析过程中发生错误: {e}', exc_info=True)

        # 如果AI分析失败，返回默认规则
        return self._get_default_scoring_rules()

    def _get_default_scoring_rules(self) -> List[Dict[str, Any]]:
        """返回默认的评分规则，确保总分为100分"""
        self.logger.info('使用默认评分规则')
        return [
            {
                'numbering': ['1'],
                'criteria_name': '技术方案',
                'max_score': 60.0,
                'weight': 1.0,
                'description': '技术方案评分',
                'category': '评标办法',
                'children': [
                    {
                        'numbering': ['1', '1'],
                        'criteria_name': '技术方案完整性',
                        'max_score': 30.0,
                        'weight': 1.0,
                        'description': '技术方案完整性评分',
                        'category': '评标办法',
                        'children': [],
                        'is_price_criteria': False,
                    },
                    {
                        'numbering': ['1', '2'],
                        'criteria_name': '技术方案可行性',
                        'max_score': 30.0,
                        'weight': 1.0,
                        'description': '技术方案可行性评分',
                        'category': '评标办法',
                        'children': [],
                        'is_price_criteria': False,
                    },
                ],
                'is_price_criteria': False,
            },
            {
                'numbering': ['2'],
                'criteria_name': '价格分',
                'max_score': 40.0,
                'weight': 1.0,
                'description': '价格分计算公式：评标基准价为各有效投标人投标报价的算术平均值，价格分=评标基准价/投标报价*价格分值',
                'category': '评标办法',
                'children': [],
                'is_price_criteria': True,
            },
        ]

    def _extract_scoring_section(self, full_text: str) -> str:
        """提取评标相关的章节内容"""
        # 寻找评标相关的章节标题 - 扩展更多可能的关键字
        scoring_keywords = [
            '评标办法',
            '评分标准',
            '评审标准',
            '评价标准',
            '评分细则',
            '评标细则',
            '评价项目',
            '评价内容',
            '评审内容',
            '打分标准',
            '评分要求',
            '评审要求',
            '技术评分',
            '商务评分',
            '价格评分',
            '综合评分',
            '评分方法',
            '评审方法',
        ]

        # 章节结束标记 - 扩展更多结束标记
        end_keywords = [
            '合同',
            '附件',
            '附录',
            '格式',
            '投标文件格式',
            '附表',
            '投标文件',
            '第四章',
            '第四部分',
            '四、',
            '五、',
            '第五章',
            '第五部分',
            '投标须知',
            '投标人须知',
            '投标保证金',
            '投标有效期',
        ]

        lines = full_text.split('\n')
        start_idx = -1
        end_idx = len(lines)

        # 查找评标章节开始位置 - 改进匹配逻辑
        for i, line in enumerate(lines):
            line_clean = re.sub(r'\s+', '', line)  # 去除所有空白字符便于匹配
            # 检查行中是否包含评分关键字
            if (
                any(keyword in line for keyword in scoring_keywords)
                and len(line_clean) < 100
            ):
                # 进一步检查是否为章节标题（通常在行首）
                line_stripped = line.strip()
                if (
                    line_stripped.startswith(
                        (
                            '第',
                            '一',
                            '二',
                            '三',
                            '四',
                            '五',
                            '六',
                            '七',
                            '八',
                            '九',
                            '十',
                        )
                    )
                    or line_stripped.endswith(('、', '.'))
                    or any(keyword in line_stripped for keyword in scoring_keywords)
                    or re.match(r'^\d+\.', line_stripped)
                    or re.match(r'^[A-Z]\.', line_stripped)
                ):
                    start_idx = i
                    self.logger.info(f'找到评标章节开始位置: {line.strip()}')
                    break

        # 如果没找到明确的章节标题，尝试查找包含评分关键字的内容
        if start_idx == -1:
            for i, line in enumerate(lines):
                if (
                    any(keyword in line for keyword in scoring_keywords)
                    and '分' in line
                ):
                    start_idx = max(0, i - 10)  # 向前回溯更多行
                    self.logger.info(
                        f'通过评分关键字定位到评标内容开始位置: {lines[start_idx].strip()}'
                    )
                    break

        # 如果仍然没找到，尝试在整个文档中查找评分相关的内容
        if start_idx == -1:
            self.logger.warning('未找到明确的评标章节标题，将在全文中查找评分相关内容')
            # 查找包含评分关键词且有分数的段落
            for i, line in enumerate(lines):
                if any(keyword in line for keyword in scoring_keywords) and re.search(
                    r'\d+\s*分', line
                ):
                    start_idx = max(0, i - 20)  # 向前回溯更多行
                    end_idx = min(len(lines), i + 100)  # 向后扩展更多行
                    self.logger.info(
                        f'在全文中找到评分相关内容，从行 {start_idx} 到 {end_idx}'
                    )
                    # 返回找到的相关内容
                    content = '\n'.join(lines[start_idx:end_idx])
                    self.logger.info(f'提取的评分相关内容长度: {len(content)} 字符')
                    return content

        if start_idx == -1:
            self.logger.warning('未找到评标章节，将使用全文进行评分规则提取')
            # 如果仍然找不到，返回一个较大的文本片段以供分析
            mid_point = len(lines) // 2
            start_idx = max(0, mid_point - 200)
            end_idx = min(len(lines), mid_point + 200)
            full_section = '\n'.join(lines[start_idx:end_idx])
            self.logger.info(
                f'使用文档中间部分进行分析，长度: {len(full_section)} 字符'
            )
            return full_section

        # 查找章节结束位置 - 增加更多结束标记和更智能的判断
        chapter_end_keywords = [
            '合同',
            '附件',
            '附录',
            '格式',
            '投标文件格式',
            '附表',
            '第四章',
            '第四部分',
            '四、',
            '投标须知',
            '投标人须知',
            '投标保证金',
            '投标有效期',
            '投标函',
            '法定代表人',
            '第五章',
            '第五部分',
            '五、',
            '六、',
            '第六章',
            '第六部分',
            '投标报价',
            '投标文件递交',
            '开标',
            '中标',
        ]

        # 从开始位置往后查找结束标记
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip()
            if line:
                # 检查是否是新的章节标题
                is_new_chapter = (
                    (line.startswith('第') and '章' in line)
                    or re.match(r'^[一二三四五六七八九十]+、', line)  # 中文章节标题
                    or re.match(r'^\d+\.', line)  # 数字章节标题
                    or re.match(r'^[A-Z]\.', line)  # 字母章节标题
                    or any(keyword in line for keyword in chapter_end_keywords)
                )

                # 如果是新的章节标题且不是评分相关的内容
                if is_new_chapter and not any(
                    keyword in line
                    for keyword in scoring_keywords + ['价格', '报价', '评分', '评审']
                ):
                    end_idx = i
                    self.logger.info(f'找到评标章节结束位置: {line}')
                    break

        scoring_section = '\n'.join(lines[start_idx:end_idx])
        self.logger.info(f'提取评标章节，长度: {len(scoring_section)} 字符')

        # 如果提取的章节太短，使用更大的范围
        if len(scoring_section) < 2000:  # 增加阈值到2000字符
            self.logger.warning('提取的评标章节较短，扩大搜索范围')
            # 扩大搜索范围，包含更多内容
            expanded_end = min(start_idx + 500, len(lines))  # 增加到500行
            scoring_section = '\n'.join(lines[start_idx:expanded_end])
            self.logger.info(f'扩大后的评标章节，长度: {len(scoring_section)} 字符')

        # 如果章节内容仍然很短，尝试从开始位置往后取更多内容直到找到明显的结束标记
        if len(scoring_section) < 2000:
            self.logger.warning('评标章节内容仍然较短，尝试获取更多相关内容')
            # 查找包含评分关键字的段落
            extended_end = start_idx
            found_end_marker = False
            for i in range(start_idx, min(start_idx + 1000, len(lines))):
                line = lines[i]
                # 如果找到明显的结束标记
                if (
                    any(keyword in line for keyword in ['合同', '附件', '附录'])
                    and len(line.strip()) < 30
                ):
                    extended_end = i
                    found_end_marker = True
                    break
                # 继续扩展直到有足够的内容
                extended_end = i

            if not found_end_marker:
                extended_end = min(start_idx + 1000, len(lines))

            scoring_section = '\n'.join(lines[start_idx:extended_end])
            self.logger.info(
                f'进一步扩大后的评标章节，长度: {len(scoring_section)} 字符'
            )

        # 如果内容仍然不够，返回更大的范围
        if len(scoring_section) < 3000:
            self.logger.warning('评标章节内容仍然不足，返回更大的文本范围')
            larger_start = max(0, start_idx - 100)
            larger_end = min(len(lines), start_idx + 1000)
            scoring_section = '\n'.join(lines[larger_start:larger_end])
            self.logger.info(f'返回更大的文本范围，长度: {len(scoring_section)} 字符')

        return scoring_section

    def _verify_and_adjust_scores(self, rules: List[Dict[str, Any]]):
        """递归验证并调整父项的分数，确保总分不超过100分"""
        total_score = 0
        for rule in rules:
            if rule['children']:
                # 递归处理子项
                self._verify_and_adjust_scores(rule['children'])

                # 计算子项分数之和
                children_score_sum = sum(
                    child['max_score'] for child in rule['children']
                )

                # 如果父项分数与子项之和不匹配，进行调整
                if abs(rule['max_score'] - children_score_sum) > 0.1:  # 使用浮点数容差
                    self.logger.warning(
                        f"调整父项 '{rule['criteria_name']}' 的分数: {rule['max_score']} -> {children_score_sum}"
                    )
                    rule['max_score'] = children_score_sum
            total_score += rule['max_score']

        # 如果是顶层调用且总分不为100，进行整体调整
        if hasattr(self, '_top_level_call') and self._top_level_call:
            if abs(total_score - 100.0) > 0.1:
                self.logger.warning(f'总分 {total_score} 不等于100，需要调整')
        else:
            # 设置标志表示这是顶层调用
            self._top_level_call = True
            if abs(total_score - 100.0) > 0.1:
                self.logger.warning(f'总分 {total_score} 不等于100，需要调整')

    def parse_evaluation_criteria(self):
        return self.extract_scoring_rules()

    def generate_scoring_template(self):
        rules = self.extract_scoring_rules()

        # 自定义一个JSON编码器来处理嵌套结构
        def default_serializer(o):
            return o.__dict__

        return json.dumps(
            rules, ensure_ascii=False, indent=2, default=default_serializer
        )
