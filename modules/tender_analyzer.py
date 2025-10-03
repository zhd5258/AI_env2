import logging
import json
import re
import os
import hashlib
from typing import List, Dict, Any
from .pdf_processor import PDFProcessor
from .database import ScoringRule
from modules.analysis_manager import AnalysisManager
from modules.scoring_rules_manager import ScoringRulesManager


class TenderAnalyzer:
    """
    招标文件分析器
    负责提取招标文件文本并识别评分规则
    """

    def __init__(self, tender_file_path: str, db_session=None, project_id: int = None):
        self.tender_file_path = tender_file_path
        self.db = db_session
        self.project_id = project_id
        self.logger = logging.getLogger(__name__)
        # AI Analyzer is no longer needed here directly, it's used within the extractor
        # self.ai_analyzer = LocalAIAnalyzer()

    def _get_cache_key(self, file_path: str) -> str:
        """获取文件的缓存键"""
        try:
            st = os.stat(file_path)
            key = f'{file_path}|{st.st_size}|{int(st.st_mtime)}'
        except Exception:
            # 回退到路径作为键（极端情况下）
            key = file_path
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def _load_from_temp_word(self, file_path: str) -> List[str]:
        """
        从temp_word目录加载文本

        Args:
            file_path: 原始文件路径

        Returns:
            List[str]: 加载的文本内容，按页面分割
        """
        try:
            # 生成基于文件路径的唯一文件名
            file_key = self._get_cache_key(file_path)
            temp_word_filename = f'{file_key}.txt'
            temp_word_dir = 'temp_word'
            temp_word_path = os.path.join(temp_word_dir, temp_word_filename)

            if os.path.exists(temp_word_path):
                with open(temp_word_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
                self.logger.info('从temp_word目录加载文本: %s', temp_word_path)
                # 按照页面分割文本（这里简单按换行符分割，实际可能需要更复杂的逻辑）
                pages_text = full_text.split('\n\n')  # 假设页面之间有两个换行符
                return pages_text
            else:
                self.logger.warning('temp_word目录中未找到文件: %s', temp_word_path)
        except Exception as e:
            self.logger.warning('从temp_word目录加载文本失败: %s', e)
        return []

    def extract_and_save_tender_text(self) -> List[str]:
        """
        提取招标文件文本并保存到temp_word目录
        """
        self.logger.info('开始提取招标文件文本: %s', self.tender_file_path)

        try:
            # 首先尝试从temp_word目录加载已处理的文本
            pages_text = self._load_from_temp_word(self.tender_file_path)

            # 如果temp_word目录中没有文件，则使用PDFProcessor处理
            if not pages_text:
                # 使用PDFProcessor提取文本
                processor = PDFProcessor(self.tender_file_path, file_type='tender')
                pages_text = processor.extract_text_per_page()

                if not pages_text or not any(pages_text):
                    raise ValueError('未能提取到有效的招标文件文本内容')

                self.logger.info('成功提取招标文件文本，共 %d 页', len(pages_text))

                # 确保文本也保存到temp_word目录
                processor._save_to_temp_word(pages_text)
                self.logger.info('招标文件文本已保存到temp_word目录')
            else:
                self.logger.info(
                    '从temp_word目录加载招标文件文本，共 %d 页', len(pages_text)
                )

            return pages_text

        except Exception as e:
            self.logger.error(f'提取招标文件文本时出错: {e}', exc_info=True)
            raise

    def _extract_scoring_rules_from_markdown(
        self, markdown_text: str
    ) -> List[Dict[str, Any]]:
        """
        从Markdown文本中提取评分规则

        Args:
            markdown_text: Markdown格式的文本

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        self.logger.info('开始从Markdown文本中提取评分规则...')

        scoring_rules = []

        # 查找评分标准相关的标题
        scoring_section_patterns = [
            r'##\s*评分标准',
            r'##\s*评分细则',
            r'##\s*评审标准',
            r'#\s*评分标准',
            r'#\s*评分细则',
            r'#\s*评审标准',
        ]

        scoring_section_start = -1
        for pattern in scoring_section_patterns:
            match = re.search(pattern, markdown_text, re.IGNORECASE)
            if match:
                scoring_section_start = match.end()
                break

        if scoring_section_start == -1:
            self.logger.warning('未找到评分标准章节，尝试在整个文档中查找')
            scoring_section_text = markdown_text
        else:
            # 提取评分标准章节的内容
            # 查找下一个章节标题或文档结尾
            next_section_match = re.search(
                r'^[#]{1,2}\s', markdown_text[scoring_section_start:], re.MULTILINE
            )
            if next_section_match:
                scoring_section_end = scoring_section_start + next_section_match.start()
                scoring_section_text = markdown_text[
                    scoring_section_start:scoring_section_end
                ]
            else:
                scoring_section_text = markdown_text[scoring_section_start:]

        # 使用正则表达式提取评分规则格式如：1. 技术方案（20分）
        # 匹配父项规则
        parent_patterns = [
            r'(\d+)\.\s*([^\n]*?)[（(]([\d\.]+)分[)）]',
            r'(\d+)\.\s*([^\n]*?)[（(]满分([\d\.]+)分[)）]',
            r'(\d+)\.\s*([^\n]*?)[（(]标准分([\d\.]+)分[)）]',
        ]

        # 匹配子项规则
        child_patterns = [
            r'\s+(\d+)\.\s*([^\n]*?)[（(]([\d\.]+)分[)）]',
            r'\s+(\d+)\.\s*([^\n]*?)[（(]满分([\d\.]+)分[)）]',
            r'\s+(\d+)\.\s*([^\n]*?)[（(]标准分([\d\.]+)分[)）]',
        ]

        # 存储父项信息
        current_parent = None
        numbering_counter = 1

        # 按行处理文本
        lines = scoring_section_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否为父项
            is_parent = False
            for pattern in parent_patterns:
                match = re.search(pattern, line)
                if match:
                    is_parent = True
                    number = match.group(1)
                    criteria_name = match.group(2).strip()
                    max_score = float(match.group(3))

                    # 检查是否为价格评分规则
                    is_price_criteria = (
                        '价格' in criteria_name or '报价' in criteria_name
                    )

                    # 创建评分规则（父项）
                    rule = {
                        'criteria_name': criteria_name,
                        'max_score': max_score,
                        'description': '',  # 描述信息需要进一步提取
                        'is_price_criteria': is_price_criteria,
                        'children': [],
                    }

                    # 特别处理价格评分规则，提取价格计算公式
                    if is_price_criteria:
                        # 从当前行及后续行中提取价格计算公式
                        price_formula = self._extract_price_formula_from_text(
                            line, lines
                        )
                        rule['price_formula'] = price_formula

                    scoring_rules.append(rule)
                    current_parent = len(scoring_rules) - 1
                    numbering_counter = 1
                    break

            # 如果不是父项，检查是否为子项
            if not is_parent and current_parent is not None:
                for pattern in child_patterns:
                    match = re.search(pattern, line)
                    if match:
                        number = match.group(1)
                        criteria_name = match.group(2).strip()
                        max_score = float(match.group(3))

                        # 检查是否为价格评分规则
                        is_price_criteria = (
                            '价格' in criteria_name or '报价' in criteria_name
                        )

                        # 创建子项规则
                        child_rule = {
                            'criteria_name': criteria_name,
                            'max_score': max_score,
                            'description': '',
                            'is_price_criteria': is_price_criteria,
                        }

                        # 特别处理价格评分规则，提取价格计算公式
                        if is_price_criteria:
                            # 从当前行及后续行中提取价格计算公式
                            price_formula = self._extract_price_formula_from_text(
                                line, lines
                            )
                            child_rule['price_formula'] = price_formula

                        scoring_rules[current_parent]['children'].append(child_rule)
                        numbering_counter += 1
                        break

        self.logger.info(f'成功从Markdown文本中提取了 {len(scoring_rules)} 条评分规则')
        return scoring_rules

    def _extract_price_formula_from_text(self, line: str, lines: List[str]) -> str:
        """
        从文本中提取价格计算公式

        Args:
            line: 当前行文本
            lines: 所有行文本

        Returns:
            str: 提取到的价格计算公式
        """
        # 首先尝试提取"价格计算公式:"后的内容
        if '价格计算公式:' in line:
            parts = line.split('价格计算公式:', 1)  # 只分割一次
            if len(parts) > 1:
                formula = parts[1].strip()
                # 如果公式中包含换行符，只取第一行
                if '\n' in formula:
                    formula = formula.split('\n', 1)[0]
                return formula

        # 如果没有找到特定格式，尝试提取包含数学符号的内容作为公式
        possible_formulas = []
        formula_patterns = [
            r'投标报价得分\s*[:：]?\s*[=＝][^;\n]*',
            r'价格分\s*[:：]?\s*[=＝][^;\n]*',
            r'得分\s*[:：]?\s*[=＝][^;\n]*',
            r'评标基准价\s*[:：]?\s*[=＝][^;\n]*',
            r'[评标基准价投标报价价格分得分][\s\S]*?[=＝][\s\S]*?',
        ]

        for pattern in formula_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                possible_formulas.append(match.group(0))

        # 返回最可能的公式，否则返回前200个字符
        return possible_formulas[0] if possible_formulas else line[:200]

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        从招标文件Markdown中提取评分规则，不再使用AI大模型分析
        """
        self.logger.info('开始从Markdown文件中提取评分规则...')

        try:
            # 1. 首先提取招标文件文本并保存到temp_word目录
            pages_text = self.extract_and_save_tender_text()

            # 2. 将所有页面文本合并为一个字符串
            full_text = '\n'.join(pages_text)

            # 3. 从Markdown文本中提取评分规则
            scoring_rules = self._extract_scoring_rules_from_markdown(full_text)

            if not scoring_rules:
                self.logger.warning('未能从Markdown文本中提取到任何评分规则。')
                return []

            # 4. 转换为字典格式（扁平化结构）
            rules_data = []
            for rule in scoring_rules:
                # 添加父项
                parent_rule = {
                    'criteria_name': rule['criteria_name'],
                    'max_score': rule['max_score'],
                    'is_price_criteria': rule['is_price_criteria'],
                    'description': rule['description'],
                    'price_formula': rule.get('price_formula', ''),
                }
                rules_data.append(parent_rule)

                # 添加子项
                for child in rule.get('children', []):
                    child_rule = {
                        'criteria_name': child['criteria_name'],
                        'max_score': child['max_score'],
                        'is_price_criteria': child['is_price_criteria'],
                        'description': child['description'],
                        'price_formula': child.get('price_formula', ''),
                    }
                    rules_data.append(child_rule)

            self.logger.info('成功提取 %d 条评分规则', len(rules_data))
            return rules_data

        except Exception as e:
            self.logger.error(
                '从Markdown文件中提取评分规则时出错: %s',
                e,
                exc_info=True,
            )
            return []

    def save_scoring_rules_to_db(self, rules: List[Dict[str, Any]]) -> bool:
        """
        将评分规则保存到数据库
        """
        if not (self.db and self.project_id):
            self.logger.error('数据库会话或项目ID未提供')
            return False

        try:
            # 使用统一的评分规则管理器保存评分规则
            # ScoringRulesManager 已在顶部导入，无需重复导入

            rules_manager = ScoringRulesManager(db_session=self.db)
            save_result = rules_manager.save_scoring_rules(self.project_id, rules)
            return save_result

        except Exception as e:
            self.logger.error(f'保存评分规则到数据库时出错: {e}', exc_info=True)
            return False
