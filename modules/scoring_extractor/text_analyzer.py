import re
import logging
from typing import List, Dict, Any

# 为避免循环导入，将这些函数作为静态方法实现
class TextAnalyzerMixin:
    """文本分析混入类，提供文本形式评分规则提取功能"""
    
    def _extract_scoring_rules_from_text(self) -> List[Dict[str, Any]]:
        """
        传统的文本分析方法提取评分规则
        """
        try:
            full_text = '\n'.join(self.texts) if self.texts else ''
            if not full_text.strip():
                self.logger.warning('输入文本为空')
                return []

            self.logger.info(f'开始分析招标文件，总长度: {len(full_text)} 字符')

            # 1. 提取评标相关的章节内容
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

        # 如果仍然没找到，不使用全文，而是返回空
        if start_idx == -1:
            self.logger.warning('未找到明确的评标章节标题，不提取评分规则')
            return ''

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
        if len(scoring_section) < 500:  # 减少阈值到500字符
            self.logger.warning('提取的评标章节较短，扩大搜索范围')
            # 扩大搜索范围，包含更多内容
            expanded_end = min(start_idx + 200, len(lines))  # 减少到200行
            scoring_section = '\n'.join(lines[start_idx:expanded_end])
            self.logger.info(f'扩大后的评标章节，长度: {len(scoring_section)} 字符')

        # 如果章节内容仍然很短，尝试从开始位置往后取更多内容直到找到明显的结束标记
        if len(scoring_section) < 500:
            self.logger.warning('评标章节内容仍然较短，尝试获取更多相关内容')
            # 查找包含评分关键字的段落
            extended_end = start_idx
            found_end_marker = False
            for i in range(start_idx, min(start_idx + 500, len(lines))):
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
                extended_end = min(start_idx + 500, len(lines))

            scoring_section = '\n'.join(lines[start_idx:extended_end])
            self.logger.info(
                f'进一步扩大后的评标章节，长度: {len(scoring_section)} 字符'
            )

        # 如果内容仍然不够，返回更大的范围
        if len(scoring_section) < 800:
            self.logger.warning('评标章节内容仍然不足，返回更大的文本范围')
            larger_start = max(0, start_idx - 50)
            larger_end = min(len(lines), start_idx + 500)
            scoring_section = '\n'.join(lines[larger_start:larger_end])
            self.logger.info(f'返回更大的文本范围，长度: {len(scoring_section)} 字符')

        return scoring_section
        
    def _parse_rules_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析出所有结构化的评分规则项"""
        # 优化正则表达式以更好地匹配评分规则，兼容中英文括号
        rule_patterns = [
            # 价格分特别处理: 价格分... (30分) or 价格分... 30分，限制分数范围避免错误识别
            r'^\s*([（\(]?\s*(?:价格分|报价分)\s*[）\)]?.*?)[\s（\(]+(\d{1,2}(?:\.\d)?)\s*分[\)）]?',
            # 其他评分项匹配模式，限制分数范围避免错误识别
            r'([^\n\(]*?[\u4e00-\u9fa5]+[^\n\)]*?)\s*[\(（]\s*(\d{1,2}(?:\.\d)?)\s*分\s*[\)）]',
            r'([^\n\(]*?[\u4e00-\u9fa5]+[^\n\)]*?)\s+(\d{1,2}(?:\.\d)?)\s*分',
        ]

        # 存储提取的评分规则
        rules = []

        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            # 尝试每种模式匹配
            for pattern in rule_patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        criteria_name = match[0].strip()
                        score_str = match[1]
                    else:
                        continue

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

                    rules.append(
                        {
                            'numbering': (str(len(rules) + 1),),
                            'criteria_name': criteria_name,
                            'max_score': score,
                            'weight': 1.0,
                            'description': criteria_name,
                            'category': '评标办法',
                            'is_price_criteria': is_price_criteria,
                        }
                    )

            i += 1

        # 移除重复规则
        rules = self._remove_duplicate_rules(rules)
        return rules

    def _clean_criteria_name(self, name: str) -> str:
        """清理评分项名称"""
        # 移除多余的空白字符
        name = re.sub(r'\s+', ' ', name.strip())

        # 移除常见的前缀和后缀
        name = re.sub(r'^[（\(]*\d+[\.\-]?\d*[）\)]*\s*', '', name)
        name = re.sub(r'\s*[（\(]*\d+分?[）\)]*$', '', name)

        # 移除特殊字符
        name = re.sub(r'[※★▲●○◆■□△▽◇◆]', '', name)

        return name.strip()

    def _is_similar_criteria(self, name1: str, name2: str) -> bool:
        """判断两个评分项名称是否相似"""
        # 清理名称
        clean_name1 = self._clean_criteria_name(name1)
        clean_name2 = self._clean_criteria_name(name2)

        # 如果完全相等
        if clean_name1 == clean_name2:
            return True

        # 如果一个包含另一个
        if clean_name1 in clean_name2 or clean_name2 in clean_name1:
            return True

        # 计算相似度（简单实现）
        common_chars = set(clean_name1) & set(clean_name2)
        total_chars = set(clean_name1) | set(clean_name2)

        if len(total_chars) == 0:
            return False

        similarity = len(common_chars) / len(total_chars)
        return similarity > 0.8

    def _find_and_add_price_rule(self, text: str, structured_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从文本中查找价格分计算公式，并将其添加/更新到规则列表中"""
        # 查找价格分计算公式
        price_patterns = [
            r'(评标基准价.*?价格分.*?)',
            r'(价格分.*?评标基准价.*?)',
            r'(基准价.*?价格分.*?)',
            r'价格分计算[：:]\s*(.*?)(?=\n\n|\Z)',
            r'价格评分[：:]\s*(.*?)(?=\n\n|\Z)',
        ]

        price_description = ''
        for pattern in price_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                price_description = match.group(1).strip()
                break

        # 查找价格分值，限制分数范围避免错误识别
        score_patterns = [
            r'价格分\s*[:：]?\s*(\d{1,2}(?:\.\d)?)\s*分',
            r'(\d{1,2}(?:\.\d)?)\s*分\s*\(价格分\)',
            r'价格.*?(\d{1,2}(?:\.\d)?)\s*分',
        ]

        price_score = 0.0
        for pattern in score_patterns:
            match = re.search(pattern, text)
            if match:
                # 只有当分数合理时才接受（通常价格分较高）
                score = float(match.group(1))
                if score > 10:
                    price_score = score
                    break

        # 如果找到了价格分信息
        if price_score > 0:
            # 检查是否已存在价格分规则
            existing_price_rule = None
            for rule in structured_rules:
                if rule.get('is_price_criteria'):
                    existing_price_rule = rule
                    break

            price_rule = {
                'numbering': ('99',),  # 价格分通常放在最后
                'criteria_name': '价格分',
                'max_score': price_score,
                'weight': 1.0,
                'description': price_description if price_description else '价格分计算',
                'category': '评标办法',
                'is_price_criteria': True,
            }

            if existing_price_rule:
                # 更新现有价格规则
                existing_price_rule.update(price_rule)
            else:
                # 添加新的价格规则
                structured_rules.append(price_rule)

        return structured_rules

    def _remove_duplicate_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """移除重复的评分规则"""
        if not rules:
            return rules

        unique_rules = []

        for rule in rules:
            criteria_name = rule.get('criteria_name', '')

            # 检查是否已存在相似规则
            is_duplicate = False
            duplicate_index = -1
            for i, existing_rule in enumerate(unique_rules):
                existing_name = existing_rule.get('criteria_name', '')
                if self._is_similar_criteria(criteria_name, existing_name):
                    is_duplicate = True
                    duplicate_index = i
                    break

            if is_duplicate:
                # 如果是重复规则，保留分数更高的
                if rule['max_score'] > unique_rules[duplicate_index]['max_score']:
                    unique_rules[duplicate_index] = rule
            else:
                unique_rules.append(rule)

        return unique_rules