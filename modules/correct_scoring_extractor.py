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

    def __init__(self, pdf_path: str, use_ai_extraction: bool = False):
        """
        初始化评分规则提取器

        Args:
            pdf_path: PDF文件路径（直接使用原始PDF文件）
            use_ai_extraction: 是否使用AI提取规则（默认False，使用表格解析）
        """
        self.pdf_path = pdf_path
        self.use_ai_extraction = use_ai_extraction
        self.logger = logging.getLogger(__name__)
        # 初始化文本处理器
        self.text_processor = TextProcessor() if TextProcessor else None
        # 如果使用AI提取，初始化AI分析器
        if use_ai_extraction:
            try:
                from modules.local_ai_analyzer import LocalAIAnalyzer
                self.ai_analyzer = LocalAIAnalyzer()
            except ImportError:
                self.logger.warning('无法导入LocalAIAnalyzer，将使用表格解析方式')
                self.use_ai_extraction = False
                self.ai_analyzer = None
        else:
            self.ai_analyzer = None

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        提取评分规则（支持AI提取和表格解析两种方式）

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        if self.use_ai_extraction and self.ai_analyzer:
            return self._extract_rules_with_ai()
        else:
            return self._extract_rules_from_table()
    
    def _extract_rules_from_table(self) -> List[Dict[str, Any]]:
        """
        从PDF表格中提取评分规则（原有方法）

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        self.logger.info(f'开始从PDF表格提取评分规则: {self.pdf_path}')

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

    def _extract_rules_with_ai(self) -> List[Dict[str, Any]]:
        """
        使用AI从招标文件中提取评分规则（优化后的方法）

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        self.logger.info(f'开始使用AI从招标文件提取评分规则: {self.pdf_path}')

        try:
            # 1. 读取招标文件内容（从PDF或MD文件）
            import os
            import fitz
            
            # 尝试读取MD文件（如果存在）
            md_path = self.pdf_path.replace('.pdf', '.md').replace('.PDF', '.md')
            if os.path.exists(md_path):
                with open(md_path, 'r', encoding='utf-8') as f:
                    tender_content = f.read()
                self.logger.info(f'使用MD文件内容: {md_path}')
            else:
                # 从PDF提取文本
                doc = fitz.open(self.pdf_path)
                pages_text = []
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pages_text.append(page.get_text())
                doc.close()
                tender_content = '\n\n'.join(pages_text)
                self.logger.info('从PDF文件提取文本内容')

            # 2. 构建优化的AI提取prompt
            prompt = self._build_ai_extraction_prompt(tender_content)

            # 3. 调用AI提取规则
            self.logger.info('开始调用AI大模型提取评分规则')
            ai_response = self.ai_analyzer.analyze_text(prompt)
            self.logger.info('AI大模型响应接收成功')

            # 4. 解析AI响应
            rules_data = self._parse_ai_extraction_response(ai_response)

            # 5. 转换为标准格式
            hierarchy_rules = self._convert_ai_rules_to_hierarchy(rules_data)

            # 6. 验证规则
            self._validate_scoring_rules(hierarchy_rules)

            self.logger.info(f'AI提取到 {len(hierarchy_rules)} 条评分规则')
            return hierarchy_rules

        except Exception as e:
            self.logger.error(f'使用AI提取评分规则时出错: {e}')
            import traceback
            self.logger.error(f'错误详情: {traceback.format_exc()}')
            # 如果AI提取失败，回退到表格解析方式
            self.logger.info('AI提取失败，回退到表格解析方式')
            return self._extract_rules_from_table()

    def _build_ai_extraction_prompt(self, tender_content: str) -> str:
        """
        构建优化的AI提取规则prompt

        Args:
            tender_content: 招标文件内容

        Returns:
            str: 优化后的prompt
        """
        prompt = f"""你是一个专业的招标文件智能分析引擎。请对提供的招标文件进行深度解析，提取其中的所有评标规则，并按以下要求分类和结构化输出：

1. **定性规则分析**：
   - 提取所有需要定性判断的合规性、资格性或否决性规则。
   - 每条规则应包含：规则名称、规则描述。
   - 这些规则通常涉及资格条件、投标文件形式要求、禁止性条款、偏差处理等。
   - **重点关注否决性规则**：如投标文件格式不符合要求、缺少必要文件、违反禁止性条款等会导致投标被否决的规则。
   - 规则描述应清晰完整，包含判断标准和后果说明。

2. **定量规则分析**：
   - 提取所有可量化的评分规则，例如技术、商务、服务、价格等部分。
   - 每条规则必须包含一个 `item` 子对象，结构如下：
     - `最高分值`：该规则项的满分值（整数或浮点数）。必须准确提取，不能遗漏。
     - `规则描述`：该评分项的完整原文描述或清晰提炼。应包含评分标准、得分条件等关键信息。
     - `是否综合规则`：boolean 值（true/false），判断该规则是否需**综合全部有效投标文件的信息**才能完成评分。
       - **true**：需要对比所有投标文件才能评分，例如：
         * 价格最低者得满分（价格分）
         * 业绩排名第一得5分
         * 方案最优者得高分
         * 技术方案得分最高的得满分
       - **false**：仅根据单个投标文件自身内容即可评分，例如：
         * 具备某项证书得5分
         * 技术方案满足要求得10分
         * 提供售后服务承诺得3分
     - `是否父项规则`：boolean 值（true/false），判断该规则是否为**总分项或汇总项**。
       - **true**：其得分由多个子规则加总而来，例如：
         * "技术部分"（包含多个技术评分项）
         * "商务部分"（包含多个商务评分项）
         * "服务部分"（包含多个服务评分项）
       - **false**：独立评分项，不包含子项，例如：
         * "价格分"（虽然是综合规则，但不是父项）
         * "企业资质"（单个评分项）
         * "业绩证明"（单个评分项）

3. **输出格式要求**：
   - 使用标准 JSON 格式。
   - 不得包含任何打分、评分、判断投标人表现的内容，**仅做规则提取，不进行评分计算**。
   - 所有规则应去重、归一化表述，确保清晰可读。
   - 规则名称应简洁明了，去除冗余词汇。
   - 规则描述应完整准确，保留关键评分标准。

4. **输出结构示例**：

```json
{{
  "定性规则_result": [
    {{
      "规则名称": "投标人资格要求",
      "规则描述": "投标人不得存在与招标人有利害关系、与其他投标人有相同单位负责人、存在控股或管理关系等情形，否则将导致投标被否决。"
    }},
    {{
      "规则名称": "投标文件格式要求",
      "规则描述": "投标文件必须按照招标文件要求的格式编制，缺少关键页签或签字盖章不符合要求的，将导致投标被否决。"
    }}
  ],
  "定量规则_result": [
    {{
      "规则名称": "价格分",
      "item": {{
        "最高分值": 40,
        "规则描述": "满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分，其他投标人的价格分按公式计算：价格分=(评标基准价/投标报价)×价格权重×100。",
        "是否综合规则": true,
        "是否父项规则": false
      }}
    }},
    {{
      "规则名称": "技术部分",
      "item": {{
        "最高分值": 32,
        "规则描述": "技术部分总分，包含技术方案、技术指标、技术能力等子项评分。",
        "是否综合规则": false,
        "是否父项规则": true
      }}
    }},
    {{
      "规则名称": "技术方案",
      "item": {{
        "最高分值": 15,
        "规则描述": "技术方案合理、可行，满足招标文件要求。优秀得15分，良好得10分，一般得5分，不符合要求得0分。",
        "是否综合规则": true,
        "是否父项规则": false
      }}
    }},
    {{
      "规则名称": "企业资质",
      "item": {{
        "最高分值": 5,
        "规则描述": "具备相关资质证书且在有效期内得5分，否则不得分。",
        "是否综合规则": false,
        "是否父项规则": false
      }}
    }}
  ]
}}
```

【招标文件内容】
{tender_content}

【重要提示】
1. **仔细阅读招标文件内容**，特别关注"评标办法"、"评分标准"、"评审标准"等相关章节。
2. **对于定量规则**：
   - 必须准确提取最高分值，不能遗漏任何有分值的规则。
   - 正确识别父项和子项的层级关系。如果某个规则项包含多个子评分项，应标记为父项。
   - 正确判断"是否综合规则"：需要对比所有投标文件才能评分的规则应标记为true。
3. **对于定性规则**：
   - 重点关注会导致投标被否决的规则。
   - 规则描述应包含判断标准和后果说明。
4. **输出格式**：
   - 严格按照JSON格式输出，不要包含任何解释文字。
   - 确保JSON格式正确，可以使用代码块包裹。
   - 如果某个字段无法确定，使用空字符串或合理的默认值。

请开始提取规则："""

        return prompt

    def _parse_ai_extraction_response(self, response: str) -> Dict[str, Any]:
        """
        解析AI提取规则的响应

        Args:
            response: AI响应文本

        Returns:
            Dict[str, Any]: 解析后的规则数据
        """
        import json
        import re

        try:
            # 清理响应，移除代码块标记
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

            # 查找JSON对象
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = cleaned_response

            # 修复JSON格式问题
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 解析JSON
            data = json.loads(json_str)
            return data

        except json.JSONDecodeError as e:
            self.logger.error(f'解析AI响应JSON时出错: {e}')
            self.logger.error(f'响应内容: {response[:500]}...')
            return {"定性规则_result": [], "定量规则_result": []}
        except Exception as e:
            self.logger.error(f'解析AI响应时出错: {e}')
            return {"定性规则_result": [], "定量规则_result": []}

    def _convert_ai_rules_to_hierarchy(self, rules_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将AI提取的规则转换为层级结构

        Args:
            rules_data: AI提取的规则数据

        Returns:
            List[Dict[str, Any]]: 层级结构的规则列表
        """
        hierarchy_rules = []

        # 处理定量规则
        quantitative_rules = rules_data.get("定量规则_result", [])
        qualitative_rules = rules_data.get("定性规则_result", [])

        # 按父项分组定量规则
        parent_rules = {}
        child_rules = []

        for rule in quantitative_rules:
            rule_name = rule.get("规则名称", "").strip()
            if not rule_name:
                continue
                
            item = rule.get("item", {})
            max_score = float(item.get("最高分值", 0))
            description = item.get("规则描述", "")
            is_parent = item.get("是否父项规则", False)
            is_comprehensive = item.get("是否综合规则", False)
            
            # 判断是否为价格规则（从规则名称判断）
            is_price_criteria = (
                '价格' in rule_name or 
                '报价' in rule_name or 
                '投标总价' in rule_name or
                '投标价' in rule_name
            )
            
            # 判断是否为否决项（从规则名称判断，通常以*开头）
            is_veto = rule_name.startswith('*')
            if is_veto:
                rule_name = rule_name.lstrip('*').strip()

            rule_dict = {
                "criteria_name": rule_name,
                "max_score": max_score,
                "description": description,
                "is_parent": is_parent,
                "is_comprehensive": is_comprehensive,
                "is_price_criteria": is_price_criteria,
                "is_qualitative": False,  # 定量规则
                "is_quantitative": True,  # 定量规则
                "is_veto": is_veto,
            }

            if is_parent:
                rule_dict["children"] = []
                parent_rules[rule_name] = rule_dict
            else:
                child_rules.append(rule_dict)

        # 处理定性规则（转换为定量规则格式，分数为0）
        for rule in qualitative_rules:
            rule_name = rule.get("规则名称", "").strip()
            if not rule_name:
                continue
                
            # 判断是否为否决项
            is_veto = rule_name.startswith('*')
            if is_veto:
                rule_name = rule_name.lstrip('*').strip()
                
            rule_dict = {
                "criteria_name": rule_name,
                "max_score": 0,  # 定性规则没有分数
                "description": rule.get("规则描述", ""),
                "is_parent": False,
                "is_comprehensive": False,
                "is_price_criteria": False,  # 定性规则不是价格规则
                "is_qualitative": True,  # 标记为定性规则
                "is_quantitative": False,  # 定性规则不是定量规则
                "is_veto": is_veto,
            }
            child_rules.append(rule_dict)

        # 构建层级结构：尝试匹配父子关系
        # 策略：根据规则名称中的关键词匹配（如"技术部分"和"技术方案"）
        # 如果无法匹配，则保持原有的父子关系标记
        
        # 首先处理明确的父项
        for parent_name, parent_dict in parent_rules.items():
            # 查找可能的子项（通过名称匹配）
            matched_children = []
            remaining_children = []
            
            for child in child_rules:
                child_name = child.get("criteria_name", "")
                # 如果子项名称包含父项的关键词，或者父项名称包含子项的关键词
                # 或者子项名称与父项名称有相似性，则认为是父子关系
                parent_keywords = self._extract_keywords(parent_name)
                child_keywords = self._extract_keywords(child_name)
                
                # 如果子项不属于任何父项，且与当前父项有匹配，则添加到子项
                is_matched = False
                if parent_keywords and child_keywords:
                    # 检查是否有共同关键词
                    common_keywords = set(parent_keywords) & set(child_keywords)
                    if common_keywords:
                        is_matched = True
                
                # 特殊情况：如果父项名称包含"部分"、"项"等，且子项名称不包含这些词
                if not is_matched:
                    if ('部分' in parent_name or '项' in parent_name) and \
                       ('部分' not in child_name and '项' not in child_name):
                        # 检查子项是否可能是该父项的子项
                        if any(keyword in child_name for keyword in parent_keywords[:2] if keyword not in ['部分', '项']):
                            is_matched = True
                
                if is_matched:
                    matched_children.append(child)
                else:
                    remaining_children.append(child)
            
            # 将匹配的子项添加到父项
            if matched_children:
                parent_dict["children"] = matched_children
                hierarchy_rules.append(parent_dict)
            else:
                # 如果没有匹配的子项，但标记为父项，仍然保留父项结构
                hierarchy_rules.append(parent_dict)
            
            # 更新child_rules，移除已匹配的子项
            child_rules = remaining_children
        
        # 添加未匹配到父项的子项（独立规则）
        hierarchy_rules.extend(child_rules)

        return hierarchy_rules
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词（用于匹配父子关系）
        
        Args:
            text: 文本内容
            
        Returns:
            List[str]: 关键词列表
        """
        if not text:
            return []
        
        # 简单的关键词提取：移除常见停用词，保留有意义的词
        stop_words = {'的', '和', '或', '与', '及', '等', '部分', '项', '分', '规则'}
        keywords = []
        
        # 按字符分割，保留2-4个字符的词
        for i in range(len(text)):
            for length in [2, 3, 4]:
                if i + length <= len(text):
                    word = text[i:i+length]
                    if word not in stop_words and len(word) >= 2:
                        keywords.append(word)
        
        return keywords[:5]  # 返回前5个关键词

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

                # 增强文本完整性检查和跨行内容拼接
                first_col = self._ensure_text_completeness(first_col, i, table_data, 0)
                second_col = self._ensure_text_completeness(
                    second_col, i, table_data, 1
                )
                third_col = self._ensure_text_completeness(third_col, i, table_data, 2)

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
                            'is_price_criteria': '价格' in first_info['name']
                            or '报价' in first_info['name']
                            or '投标总价' in first_info['name'],
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

                    # 增强文本完整性检查和跨行内容拼接
                    first_col = self._ensure_text_completeness(
                        first_col, table_data.index(row), table_data, 0
                    )
                    second_col = self._ensure_text_completeness(
                        second_col, table_data.index(row), table_data, 1
                    )
                    third_col = self._ensure_text_completeness(
                        third_col, table_data.index(row), table_data, 2
                    )

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
                                    'rule_usage_description': f'规则名称：{clean_name}，规则描述：{child_description}，满分：{second_info["score"]}分，是否为否决项：{"是" if is_veto else "否"}，规则类型：{"定性规则" if is_qualitative else "定量规则"}',
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
                                'rule_usage_description': f'规则名称：{clean_name}，规则描述：{self._clean_description(third_col)}，满分：{second_info["score"]}分，是否为否决项：{"是" if is_veto else "否"}，规则类型：{"定性规则" if is_qualitative else "定量规则"}',
                            }
                        )

        return rules

    def _ensure_text_completeness(
        self, text: str, row_index: int, table_data: List[List[str]], col_index: int
    ) -> str:
        """
        确保文本完整性，处理被截断的文本内容

        Args:
            text: 原始文本
            row_index: 当前行索引
            table_data: 表格数据
            col_index: 当前列索引

        Returns:
            str: 完整的文本
        """
        if not text:
            return text

        # 特殊处理：对于明显不完整的规则名称
        incomplete_rule_names = [
            '是否接受联合体投',
            '投标人须具备',
            '项目负责人须',
            '具备有效的安全',
        ]

        # 检查是否是不完整的规则名称
        for incomplete_name in incomplete_rule_names:
            if incomplete_name in text and len(text) < len(incomplete_name) + 5:
                # 查找下一行是否有补充内容
                if row_index + 1 < len(table_data):
                    next_row = table_data[row_index + 1]
                    if col_index < len(next_row) and next_row[col_index]:
                        next_text = str(next_row[col_index]).strip()
                        # 如果下一行是明显的补充内容
                        if next_text and (
                            next_text.startswith('标')
                            or any(
                                keyword in next_text
                                for keyword in [
                                    '资质',
                                    '资格',
                                    '证书',
                                    '要求',
                                    '门颁发',
                                ]
                            )
                        ):
                            # 特殊处理规则名称拼接
                            if next_text.startswith('标'):
                                # 避免重复拼接，只取需要的部分
                                if text.endswith('投') and next_text.startswith('标'):
                                    text = text + next_text
                                else:
                                    text = text + next_text
                            else:
                                text = text + next_text
                            self.logger.debug(f'规则名称拼接: {text}')
                            break

        # 检查文本是否可能被截断
        # 如果文本以某些关键词结尾，可能是被截断的
        truncation_indicators = [
            '投',
            '标',
            '要',
            '求',
            '说',
            '明',
            '内',
            '容',
            '条',
            '款',
            '资',
            '质',
            '证',
            '书',
        ]
        if text and text[-1] in truncation_indicators:
            # 查看下一行同一列是否有内容可以拼接
            if row_index + 1 < len(table_data):
                next_row = table_data[row_index + 1]
                if col_index < len(next_row) and next_row[col_index]:
                    next_text = str(next_row[col_index]).strip()
                    # 特殊处理规则名称
                    if '是否接受联合体投' in text and next_text.startswith('标'):
                        # 已经在上面处理过了，避免重复处理
                        pass
                    else:
                        # 如果下一行的文本以某些关键词开头，可能是被截断的延续
                        continuation_indicators = [
                            '标',
                            '求',
                            '明',
                            '容',
                            '款',
                            '。',
                            '，',
                            '；',
                            '资',
                            '质',
                            '证',
                            '书',
                        ]
                        # 检查是否是明显的延续（以特定字符开头或包含列表项）
                        is_continuation = next_text and (
                            next_text[0] in continuation_indicators
                            or any(
                                keyword in next_text
                                for keyword in [
                                    '1.',
                                    '2.',
                                    '3.',
                                    '一、',
                                    '二、',
                                    '三、',
                                ]
                            )
                        )

                        if is_continuation and not ('1.' in text and '2.' in next_text):
                            # 避免将列表项拼接在一起
                            # 拼接文本
                            text = text + next_text
                            self.logger.debug(f'拼接文本: {text}')

        # 特殊处理描述文本拼接
        # 如果当前文本不完整且下一行有补充内容
        if text and len(text) < 30 and row_index + 1 < len(table_data):  # 增加长度限制
            next_row = table_data[row_index + 1]
            if col_index < len(next_row) and next_row[col_index]:
                next_text = str(next_row[col_index]).strip()
                # 如果下一行同一列有内容且当前文本看起来不完整
                if next_text and not text.endswith(
                    ('。', '！', '？', '；', '.', '!', '?', ';')
                ):
                    # 检查是否应该拼接
                    should_concatenate = False

                    # 如果当前文本以某些关键词结尾，可能需要拼接
                    if text.endswith(
                        ('不接受', '接受', '满足', '要求', '下列', '如下', '以下')
                    ):
                        should_concatenate = True

                    # 如果下一行以某些关键词开头，可能是延续
                    if next_text.startswith(
                        (
                            '接受',
                            '应满足',
                            '要求',
                            '下列',
                            '如下',
                            '以下',
                            '1.',
                            '2.',
                            '一、',
                            '二、',
                        )
                    ):
                        should_concatenate = True

                    # 特殊处理用户示例中的情况
                    if text == '接受应满足下列要求：' and next_text.startswith('1.'):
                        should_concatenate = True

                    if should_concatenate:
                        # 避免重复拼接列表项
                        if not (
                            text.endswith(('1.', '2.', '3.'))
                            and next_text.startswith(('1.', '2.', '3.'))
                        ):
                            text = text + next_text
                            self.logger.debug(f'描述文本拼接: {text}')

        # 检查是否需要与上一行拼接
        # 如果文本以标点符号开头，可能是上一行的延续
        if text and text[0] in ['，', '。', '；', '：', '）', ')']:
            # 查看上一行同一列的内容
            if row_index > 0:
                prev_row = table_data[row_index - 1]
                if col_index < len(prev_row) and prev_row[col_index]:
                    prev_text = str(prev_row[col_index]).strip()
                    # 如果上一行文本以非标点符号结尾，可以拼接
                    if prev_text and prev_text[-1] not in [
                        '，',
                        '。',
                        '；',
                        '：',
                        '（',
                        '(',
                    ]:
                        # 拼接文本
                        text = prev_text + text
                        self.logger.debug(f'与上一行拼接文本: {text}')

        # 检查句子完整性（是否以标点符号结尾）
        sentence_endings = ['。', '！', '？', '；', '.', '!', '?', ';']
        if text and text[-1] not in sentence_endings:
            # 如果文本较长但没有以标点符号结尾，可能是被截断的
            if len(text) > 20:  # 增加长度阈值
                # 检查是否是明显的句子片段
                fragment_indicators = ['下列', '如下', '以下', '满足', '具备', '需要']
                if any(indicator in text for indicator in fragment_indicators):
                    # 可能需要与后续内容拼接
                    pass

        return text

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

        # 导入增强的文本清洗工具
        try:
            from tools.enhanced_text_cleaner import clean_scoring_rule_text

            cleaned_text = clean_scoring_rule_text(text)
            if cleaned_text != text:
                self.logger.debug(
                    f'使用增强文本清洗工具清洗文本: {text[:50]}... -> {cleaned_text[:50]}...'
                )
            return cleaned_text
        except Exception as e:
            self.logger.warning(f'使用增强文本清洗工具时出错，回退到原有方法: {e}')

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

        # 导入增强的文本清洗工具
        try:
            from tools.enhanced_text_cleaner import clean_rule_description

            cleaned_description = clean_rule_description(description)
            if cleaned_description != description:
                self.logger.debug(
                    f'使用增强文本清洗工具清洗描述: {description[:50]}... -> {cleaned_description[:50]}...'
                )
            return cleaned_description
        except Exception as e:
            self.logger.warning(
                f'使用增强文本清洗工具清洗描述时出错，回退到原有方法: {e}'
            )

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
