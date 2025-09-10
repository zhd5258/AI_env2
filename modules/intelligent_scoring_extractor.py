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
        从招标文件的“评标办法”章节提取所有评分规则，包括结构化评分项和文字描述的价格分计算公式。
        """
        try:
            full_text = '\n'.join(self.pages)

            # 1. 定位并提取“评标办法”章节的文本内容
            evaluation_section_text = self._extract_scoring_section(full_text)
            if not evaluation_section_text:
                self.logger.error("未能找到或提取评标办法章节。")
                return []

            # 2. 从章节文本中提取所有结构化的评分项
            #    使用正则表达式匹配如“1.1.1 xxx (10分)”的模式
            structured_rules = self._parse_rules_from_text(evaluation_section_text)

            # 3. 从章节文本中专门查找价格分计算公式，并将其添加/更新到规则列表中
            final_rules = self._find_and_add_price_rule(evaluation_section_text, structured_rules)
            
            # 4. 将扁平的规则列表构建成层级树
            if final_rules:
                tree = self._build_tree_from_flat_list(final_rules)
                self._verify_and_adjust_scores(tree) # 验证并调整分数
                return tree

            self.logger.warning("未能从评标办法章节提取到任何评分规则。")
            return []
        except Exception as e:
            self.logger.error(f'提取评分规则时发生严重错误: {e}', exc_info=True)
            return []

    def _parse_rules_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析出所有结构化的评分规则项"""
        # 匹配各种编号格式，如 1. | (1) | 一、 | （一）
        rule_pattern = re.compile(
            r"^\s*([（(]?\d+(?:\.\d+)*[)）]?|[一二三四五六七八九十]+、?)\s*([^\n]+?)\s*[（(](\d+(?:\.\d+)?)\s*分[)）]",
            re.MULTILINE
        )
        
        flat_rules = []
        for match in rule_pattern.finditer(text):
            # 正则表达式有4个捕获组，groups()将返回一个包含4个元素的元组
            # 组1: 编号 (e.g., "1.1", "（一）")
            # 组2: 评分项名称
            # 组3: 分数 (e.g., "10", "10.5")
            # 组4: 分数的小数部分 (e.g., ".5") - 我们不需要它，但它会被捕获
            groups = match.groups()
            numbering_str = groups[0]
            criteria_name = groups[1]
            score_str = groups[2]
            
            # 清理编号和名称
            numbering_str = numbering_str.strip('()（）、. ')
            criteria_name = criteria_name.strip()
            
            # 将中文数字和带点的数字统一处理
            numbering_tuple = tuple(part for part in re.split(r'[.\-、]', numbering_str) if part)

            # 忽略无效的匹配
            if not criteria_name or not score_str:
                continue

            flat_rules.append({
                'numbering': numbering_tuple,
                'criteria_name': criteria_name,
                'max_score': float(score_str),
                'weight': 1.0,
                'description': criteria_name, # 默认描述为名称
                'category': '评标办法',
                'is_price_criteria': '价格' in criteria_name or '报价' in criteria_name
            })
        
        self.logger.info(f"从文本中解析出 {len(flat_rules)} 条结构化评分规则。")
        return flat_rules

    def _find_and_add_price_rule(self, text: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """在文本中查找价格分计算公式，并将其添加或更新到规则列表中"""
        # 价格分计算公式的常见关键字
        price_formula_pattern = re.compile(
            r".*?((?:评标基准价|投标报价)[^\n]*?价格分[^\n]*?计算[^\n]+)", 
            re.IGNORECASE
        )
        
        formula_match = price_formula_pattern.search(text)
        
        if not formula_match:
            self.logger.warning("在评标办法中未找到明确的价格分计算公式。")
            return rules

        formula_text = formula_match.group(1).strip()
        self.logger.info(f"成功提取到价格分计算公式: {formula_text}")

        # 查找现有的价格分规则项以便更新
        price_rule_found = False
        for rule in rules:
            if rule.get('is_price_criteria'):
                self.logger.info(f"找到现有的价格分规则 '{rule['criteria_name']}'，将更新其描述为计算公式。")
                rule['description'] = formula_text
                rule['is_price_criteria'] = True # 确保标记
                price_rule_found = True
                break
        
        # 如果没有找到现有的价格分规则项，则创建一个新的
        if not price_rule_found:
            self.logger.info("未找到结构化的价格分规则，将根据提取的公式创建一个新的规则项。")
            
            # 尝试从公式文本中提取价格分满分
            max_score_match = re.search(r'(\d+)\s*分', formula_text)
            max_score = float(max_score_match.group(1)) if max_score_match else 30.0 # 默认30分

            rules.append({
                'numbering': ('99',), # 给一个特殊的编号，使其排在最后
                'criteria_name': '价格分',
                'max_score': max_score,
                'weight': 1.0,
                'description': formula_text,
                'category': '评标办法',
                'is_price_criteria': True
            })
            
        return rules

    def _extract_evaluation_rules_from_table(self, text: str) -> List[Dict[str, Any]]:
        """此函数不再使用，逻辑已合并到 extract_scoring_rules 和 _parse_rules_from_text 中"""
        self.logger.warning("_extract_evaluation_rules_from_table 已被弃用。")
        return []

    def _build_hierarchical_structure(
        self,
        flat_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """此函数不再使用，逻辑已合并到 _build_tree_from_flat_list 中"""
        self.logger.warning("_build_hierarchical_structure 已被弃用。")
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

    def _get_default_scoring_rules(self) -> List[Dict[str, Any]]:
        """返回默认的评分规则，确保总分为100分"""
        self.logger.info('使用默认评分规则')
        return [
            {
                'criteria_name': '技术方案',
                'max_score': 60.0,
                'weight': 1.0,
                'children': [
                    {
                        'criteria_name': '技术方案完整性',
                        'max_score': 30.0,
                        'weight': 1.0,
                        'children': [],
                    },
                    {
                        'criteria_name': '技术方案可行性',
                        'max_score': 30.0,
                        'weight': 1.0,
                        'children': [],
                    },
                ],
            },
            {
                'criteria_name': '商务报价',
                'max_score': 40.0,
                'weight': 1.0,
                'children': [],
            },
        ]

    def _extract_scoring_section(self, full_text: str) -> str:
        """提取评标相关的章节内容"""
        # 寻找评标相关的章节标题
        scoring_keywords = ['评标办法', '评分标准', '评审标准', '评价标准', '评分细则', '评标细则']
        
        # 章节结束标记
        end_keywords = ['合同', '附件', '附录', '格式', '投标文件格式', '附表']

        lines = full_text.split('\n')
        start_idx = -1
        end_idx = len(lines)

        # 查找评标章节开始位置
        for i, line in enumerate(lines):
            line_clean = re.sub(r'\s+', '', line)  # 去除所有空白字符便于匹配
            if any(keyword in line_clean for keyword in scoring_keywords):
                start_idx = i
                self.logger.info(f'找到评标章节开始位置: {line.strip()}')
                break

        if start_idx == -1:
            self.logger.warning('未找到评标章节，将使用全文进行评分规则提取')
            return full_text

        # 查找章节结束位置
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip()
            if line and (
                (line.startswith('第') and '章' in line) or 
                line.startswith('章') or
                any(keyword in line for keyword in end_keywords) or
                re.match(r'^[一二三四五六七八九十]+、', line)  # 新的章节标题
            ):
                end_idx = i
                break

        scoring_section = '\n'.join(lines[start_idx:end_idx])
        self.logger.info(f'提取评标章节，长度: {len(scoring_section)} 字符')

        # 如果提取的章节太短，使用更大的范围
        if len(scoring_section) < 300:  # 降低阈值到300字符
            self.logger.warning('提取的评标章节太短，扩大搜索范围')
            # 扩大搜索范围，包含更多内容
            expanded_end = min(start_idx + 100, len(lines))  # 增加到100行
            scoring_section = '\n'.join(lines[start_idx:expanded_end])
            self.logger.info(f'扩大后的评标章节，长度: {len(scoring_section)} 字符')

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
                self.logger.warning(f"总分 {total_score} 不等于100，需要调整")
        else:
            # 设置标志表示这是顶层调用
            self._top_level_call = True
            if abs(total_score - 100.0) > 0.1:
                self.logger.warning(f"总分 {total_score} 不等于100，需要调整")

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
