import logging
import json
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

    def extract_and_save_tender_text(self) -> List[str]:
        """
        提取招标文件文本并保存到temp_word目录
        """
        self.logger.info('开始提取招标文件文本: %s', self.tender_file_path)

        try:
            # 使用PDFProcessor提取文本
            processor = PDFProcessor(self.tender_file_path, file_type='tender')
            pages_text = processor.extract_text_per_page()

            if not pages_text or not any(pages_text):
                raise ValueError('未能提取到有效的招标文件文本内容')

            self.logger.info('成功提取招标文件文本，共 %d 页', len(pages_text))

            # 确保文本也保存到temp_word目录
            processor._save_to_temp_word(pages_text)
            self.logger.info('招标文件文本已保存到temp_word目录')

            return pages_text

        except Exception as e:
            self.logger.error(f'提取招标文件文本时出错: {e}', exc_info=True)
            raise

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        从招标文件PDF中提取评分规则，使用统一的分析管理器。
        """
        self.logger.info('开始使用 AnalysisManager 提取评分规则...')

        try:
            # 1. 初始化并使用分析管理器
            analysis_manager = AnalysisManager(db_session=self.db)

            # 2. 提取评分规则
            extract_result = analysis_manager.initialize_project_analysis(
                self.project_id
            )

            if not extract_result:
                self.logger.warning('AnalysisManager 未能提取到任何评分规则。')
                return []

            # 3. 获取提取的评分规则
            rules_manager = ScoringRulesManager(db_session=self.db)
            scoring_rules = rules_manager.get_scoring_rules(self.project_id)

            # 转换为字典格式
            rules_data = []
            for rule in scoring_rules:
                rules_data.append(
                    {
                        'criteria_name': rule.Parent_Item_Name or rule.Child_Item_Name,
                        'max_score': rule.Parent_max_score or rule.Child_max_score,
                        'is_price_criteria': rule.is_price_criteria,
                        'description': rule.description,
                    }
                )

            self.logger.info('成功提取 %d 条评分规则', len(rules_data))
            return rules_data

        except Exception as e:
            self.logger.error(
                '使用 AnalysisManager 提取评分规则时出错: %s',
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
