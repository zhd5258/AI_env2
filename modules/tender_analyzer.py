import logging
import json
import re
from typing import List, Dict, Any
from .pdf_processor import PDFProcessor
from .database import ScoringRule
from .local_ai_analyzer import LocalAIAnalyzer


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
        self.ai_analyzer = LocalAIAnalyzer()
        
    def extract_and_save_tender_text(self) -> List[str]:
        """
        提取招标文件文本并保存到temp_word目录
        """
        self.logger.info(f'开始提取招标文件文本: {self.tender_file_path}')
        
        try:
            # 使用PDFProcessor提取文本
            processor = PDFProcessor(self.tender_file_path, file_type='tender')
            pages_text = processor.extract_text_per_page()
            
            if not pages_text or not any(pages_text):
                raise ValueError('未能提取到有效的招标文件文本内容')
                
            self.logger.info(f'成功提取招标文件文本，共 {len(pages_text)} 页')
            
            # 确保文本也保存到temp_word目录
            processor._save_to_temp_word(pages_text)
            self.logger.info(f'招标文件文本已保存到temp_word目录')
            
            return pages_text
            
        except Exception as e:
            self.logger.error(f'提取招标文件文本时出错: {e}', exc_info=True)
            raise
            
    def extract_scoring_rules(self, pages_text: List[str]) -> List[Dict[str, Any]]:
        """
        从招标文件文本中提取评分规则
        """
        self.logger.info('开始提取评分规则...')
        
        try:
            # 将所有页面文本合并
            full_text = '\n'.join(pages_text)
            
            # 构建Prompt请求AI提取评分规则
            prompt = self._build_rule_extraction_prompt(full_text)
            
            # 调用AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)
            
            # 解析AI响应
            rules = self._parse_scoring_rules_response(ai_response)
            
            self.logger.info(f'成功提取 {len(rules)} 条评分规则')
            return rules
            
        except Exception as e:
            self.logger.error(f'提取评分规则时出错: {e}', exc_info=True)
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
                rule = ScoringRule(
                    project_id=self.project_id,
                    Parent_Item_Name=rule_data.get('Parent_Item_Name', ''),
                    Parent_max_score=rule_data.get('Parent_max_score', 0),  # 添加默认值
                    Child_Item_Name=rule_data.get('Child_Item_Name'),
                    Child_max_score=rule_data.get('Child_max_score'),
                    description=rule_data.get('description', ''),
                    is_price_criteria=rule_data.get('is_price_criteria', False),
                    is_veto=rule_data.get('is_veto', False),
                    price_formula=rule_data.get('price_formula', '')  # 添加默认值
                )
                self.db.add(rule)
                
            self.db.commit()
            self.logger.info(f'成功保存 {len(rules)} 条评分规则到数据库')
            return True
            
        except Exception as e:
            self.logger.error(f'保存评分规则到数据库时出错: {e}', exc_info=True)
            self.db.rollback()
            return False
            
    def _build_rule_extraction_prompt(self, tender_text: str) -> str:
        """
        构建用于提取评分规则的Prompt
        """
        prompt = f"""
请从以下招标文件中提取评分规则，并按照指定的JSON格式返回。

招标文件内容:
{tender_text[:8000]}  # 限制长度避免超出模型上下文窗口

请严格按照以下JSON格式返回评分规则:
[
  {{
    "Parent_Item_Name": "父项名称（如果有的话）",
    "Child_Item_Name": "子项名称",
    "Child_max_score": 评分满分值,
    "description": "评分标准描述",
    "is_price_criteria": 是否为价格评分项（true/false）,
    "is_veto": 是否为一票否决项（true/false）
  }},
  ...
]

注意事项:
1. 仔细识别文件中的评分标准和分值
2. 区分价格评分项和普通评分项
3. 识别一票否决项
4. 返回结果必须是有效的JSON格式
5. 不要包含任何解释性文字，只返回JSON数组
"""
        return prompt
        
    def _parse_scoring_rules_response(self, ai_response: str) -> List[Dict[str, Any]]:
        """
        解析AI返回的评分规则
        """
        try:
            # 清理响应文本
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            # 解析JSON
            rules = json.loads(clean_response)
            return rules
        except json.JSONDecodeError as e:
            self.logger.error(f'AI响应JSON解析失败: {e}')
            self.logger.error(f'AI响应内容: {ai_response}')
            return []