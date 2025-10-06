import logging
import json
from typing import List, Dict, Any
from .pdf_processor import PDFProcessor
from .database import ScoringRule
from .correct_scoring_extractor import CorrectScoringExtractor


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

    def extract_and_save_tender_text(self) -> List[str]:
        """
        提取招标文件文本并保存到temp_word目录
        """
        self.logger.info(f'开始提取招标文件文本: {self.tender_file_path}')

        try:
            # 使用PDFProcessor提取文本，但不再保存到temp_word目录
            processor = PDFProcessor(self.tender_file_path, file_type='tender')
            pages_text = processor.extract_text_per_page()

            if not pages_text or not any(pages_text):
                raise ValueError('未能提取到有效的招标文件文本内容')

            self.logger.info(f'成功提取招标文件文本，共 {len(pages_text)} 页')

            # 不再保存到temp_word目录，直接返回提取的文本
            return pages_text

        except Exception as e:
            self.logger.error(f'提取招标文件文本时出错: {e}', exc_info=True)
            raise

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        从招标文件PDF中提取评分规则，使用 CorrectScoringExtractor。
        """
        self.logger.info('开始使用 CorrectScoringExtractor 提取评分规则...')

        try:
            # 直接使用PDF文件路径初始化提取器（严格按照用户要求）
            extractor = CorrectScoringExtractor(self.tender_file_path)
            
            # 提取规则
            rules = extractor.extract_scoring_rules()

            if not rules:
                self.logger.warning('CorrectScoringExtractor 未能提取到任何评分规则。')
                return []

            self.logger.info(f'成功提取 {len(rules)} 条评分规则')
            return rules

        except Exception as e:
            self.logger.error(f'使用 CorrectScoringExtractor 提取评分规则时出错: {e}', exc_info=True)
            return []

    def save_scoring_rules_to_db(self, rules: List[Dict[str, Any]]) -> bool:
        """
        将评分规则保存到数据库
        """
        if not (self.db and self.project_id):
            self.logger.error('数据库会话或项目ID未提供')
            return False

        try:
            # 先删除该项目已有的评分规则
            self.db.query(ScoringRule).filter(
                ScoringRule.project_id == self.project_id
            ).delete()

            # 保存新的评分规则
            for rule_data in rules:
                # The new extractor provides a nested structure, we need to flatten it for DB insertion
                self._save_rule_and_children(rule_data)

            self.db.commit()
            self.logger.info(f'成功保存评分规则到数据库')
            return True

        except Exception as e:
            self.logger.error(f'保存评分规则到数据库时出错: {e}', exc_info=True)
            self.db.rollback()
            return False

    def _save_rule_and_children(self, rule_data: Dict[str, Any], parent_name: str = '', parent_score: float = 0.0):
        """
        递归保存父项和子项规则
        """
        # Create the main rule object for the DB
        rule = ScoringRule(
            project_id=self.project_id,
            Parent_Item_Name=parent_name if parent_name else rule_data.get('criteria_name', ''),
            Parent_max_score=parent_score if parent_name else rule_data.get('max_score', 0),
            Child_Item_Name=rule_data.get('criteria_name', '') if parent_name else None,
            Child_max_score=rule_data.get('max_score', 0) if parent_name else None,
            description=rule_data.get('description', ''),
            is_price_criteria=rule_data.get('is_price_criteria', False),
            is_veto=rule_data.get('is_veto', False),
            price_formula=rule_data.get('price_formula', '')
        )
        self.db.add(rule)

        # If there are children, recurse
        if 'children' in rule_data and rule_data['children']:
            for child_rule_data in rule_data['children']:
                self._save_rule_and_children(
                    child_rule_data,
                    parent_name=rule_data.get('criteria_name', ''),
                    parent_score=rule_data.get('max_score', 0)
                )
