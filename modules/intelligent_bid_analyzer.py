import json
import re
import logging
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.pdf_processor import PDFProcessor
from modules.database import BidDocument, ScoringRule, AnalysisResult
from modules.bid_analyzer_helpers import BidAnalyzerHelpers
from modules.price_manager import PriceManager


class IntelligentBidAnalyzer(BidAnalyzerHelpers):
    def __init__(
        self,
        tender_file_path,
        bid_file_path,
        db_session=None,
        bid_document_id=None,
        project_id=None,
        extracted_text: list = [],
    ):
        super().__init__()
        self.tender_file_path = tender_file_path
        self.bid_file_path = bid_file_path
        self.db = db_session
        self.bid_document_id = bid_document_id
        self.project_id = project_id
        self.ai_analyzer = LocalAIAnalyzer()
        self.price_manager = PriceManager()
        self.logger = logging.getLogger(__name__)

        if self.db and self.bid_document_id:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            self.bidder_name = bid_doc.bidder_name if bid_doc else '未知投标方'
        else:
            self.bidder_name = '未知投标方'

        # 优化：如果已提供提取好的文本，则直接使用
        if extracted_text is not None:
            self.bid_pages = extracted_text
            self.bid_processor = None  # 不需要再创建PDF处理器
            self.logger.info(
                f'IntelligentBidAnalyzer initialized with pre-extracted text for {self.bid_file_path}.'
            )
        else:
            # 保持旧的兼容性，如果未提供文本，则初始化处理器以便后续提取
            self.logger.warning(
                f'No pre-extracted text provided for {self.bid_file_path}. PDFProcessor will be used.'
            )
            # 从环境变量获取GPU配置
            import os

            use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
            self.bid_processor = PDFProcessor(
                self.bid_file_path, use_gpu=use_gpu, file_type='bid'
            )  # 投标文件使用ONNX
            self.bid_pages = []  # 初始化为空列表而不是None

        # 存储分析结果的累积数据
        self.accumulated_results = {'投标人名称': '', '投标总价': '', '评分结果': [{}]}
        self.bidder_names = []  # 存储所有提取到的投标人名称
        self.total_prices = []  # 存储所有提取到的投标总价

    def analyze_bidding_document(self):
        """
        分析投标文件的新方法，按照新的分析思路实现
        改为全部读取文本后再处理的模式
        """
        self.logger.info(f'开始分析投标文件: {self.bid_file_path}')

        try:
            # 1. 提取投标文件文本（使用新的全文本处理模式）
            if not self.bid_pages or len(self.bid_pages) == 0:
                self.logger.info('提取投标文件文本...')
                if self.bid_processor:
                    # 使用新的全文本处理模式
                    self.bid_pages = self.bid_processor.process_pdf_full_text()
                else:
                    # 如果没有PDF处理器，使用默认的文本提取方法
                    self.bid_pages = []

            # 修正：检查bid_pages是否包含有效文本
            if not self.bid_pages or not any(page.strip() for page in self.bid_pages):
                raise ValueError('未能提取到有效的投标文件文本内容')

            self.logger.info(f'成功提取投标文件文本，共 {len(self.bid_pages)} 页')

            # 2. 从数据库获取评分规则
            rules_from_db = self._get_scoring_rules_from_db()
            if not rules_from_db:
                # 检查是否有项目ID，如果没有说明流程有问题
                if not self.project_id:
                    raise ValueError('未能从数据库获取评分规则：项目ID未设置')
                else:
                    raise ValueError(
                        f'项目 {self.project_id} 没有评分规则，请确保已从招标文件中正确提取评分规则'
                    )

            self.logger.info(f'从数据库获取到 {len(rules_from_db)} 条评分规则')

            # 3. 构建AI分析Prompt
            prompt = self._build_analysis_prompt(rules_from_db)

            # 4. 调用AI分析（使用全部文本）
            analyzed_result = self._analyze_with_full_text(prompt)

            # 5. 保存分析结果
            self._save_analysis_results(analyzed_result)

            return {
                'status': 'success',
                'message': '分析完成',
                'details': analyzed_result,
            }

        except Exception as e:
            error_msg = f'分析投标文件时出错: {str(e)}'
            self.logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'message': error_msg}

    def _get_scoring_rules_from_db(self):
        """
        从数据库获取评分规则
        """
        if not (self.db and self.project_id):
            self.logger.error('数据库会话或项目ID未提供')
            return []

        try:
            rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == self.project_id)
                .all()
            )

            # 记录获取到的评分规则数量和详细信息
            self.logger.info(f'从数据库获取到 {len(rules)} 条评分规则')
            for rule in rules:
                self.logger.info(
                    f'评分规则: Parent_Item_Name={rule.Parent_Item_Name}, Child_Item_Name={rule.Child_Item_Name}, is_price_criteria={rule.is_price_criteria}'
                )

            return rules
        except Exception as e:
            self.logger.error(f'从数据库获取评分规则时出错: {e}')
            return []

    def _build_analysis_prompt(self, rules_from_db):
        """
        构建AI分析Prompt，将评分规则作为Prompt的一部分
        优化：只发送Child_Item_Name项，剔除价格规则和Parent_Item_Name项
        """
        # 将评分规则转换为文本格式，只包含Child_Item_Name项
        scoring_rules_text = ''
        for rule in rules_from_db:
            # 剔除价格规则和Parent_Item_Name项，只保留Child_Item_Name项
            if not rule.is_price_criteria and rule.Child_Item_Name:
                scoring_rules_text += f'    {rule.Child_Item_Name}：，本项最高分{rule.Child_max_score}，{rule.description}；\n'

        # 返回评分规则部分，不包含投标文件文本（因为会在分块处理时添加）
        prompt = f"""你是一个资深评标专家，现在需要根据如下评分规则：
{{
{scoring_rules_text}
}}"""

        self.logger.info(f'构建的评分规则Prompt:\n{prompt}')
        return prompt

    def _analyze_with_full_text(self, prompt):
        """
        使用全部文本进行AI分析
        将全部投标文件文本与评分规则合并生成prompt,发送给AI大模型智能分析打分
        """
        self.logger.info('开始使用全部文本进行AI分析...')

        # 获取评分规则部分
        scoring_rules_section = prompt

        # 合并所有页面文本
        full_text = '\n'.join(self.bid_pages)

        # 构建完整的prompt
        json_format_example = """{
    "投标人名称": "投标方公司名称",  
    "投标总价": "投标总价",  
    "评分结果": [
        {
            "规则名称1": "50分",
            "规则名称2": "50分"
        }
    ]
}"""

        full_prompt = f"""{scoring_rules_section},投标方的投标文本内容为：
『{full_text}』
请分析该投标文本，分析出该投标方的投标人名称、投标总价，并根据评分规则进行打分，请返回json格式的结果：
{json_format_example}"""

        self.logger.info('使用全部文本进行AI分析...')
        ai_response = self.ai_analyzer.analyze_text(full_prompt)

        # 解析AI响应
        try:
            # 清理响应文本
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            # 解析JSON
            result = json.loads(clean_response)
            self.logger.info(
                f'AI分析完成，提取到投标人名称: {result.get("投标人名称")}'
            )
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f'AI响应JSON解析失败: {e}')
            self.logger.error(f'AI响应内容: {ai_response}')
            raise
        except Exception as e:
            self.logger.error(f'AI分析过程中发生未知错误: {e}')
            raise

    def _save_analysis_results(self, analyzed_result):
        """
        保存分析结果到数据库

        Args:
            analyzed_result: AI分析结果
        """
        try:
            if not self.db or not self.bid_document_id:
                self.logger.warning('数据库会话或投标文件ID未设置，无法保存分析结果')
                return

            # 获取分析结果记录
            analysis_result = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == self.bid_document_id)
                .first()
            )

            if not analysis_result:
                self.logger.warning('未找到分析结果记录，无法保存分析结果')
                return

            # 准备详细评分数据
            detailed_scores = []
            scores_data = analyzed_result.get('评分结果', [])
            if scores_data and isinstance(scores_data, list):
                for score_dict in scores_data:
                    if isinstance(score_dict, dict):
                        for rule_name, score in score_dict.items():
                            detailed_scores.append(
                                {
                                    'Child_Item_Name': rule_name,
                                    'score': float(
                                        str(score).rstrip('分')
                                    ),  # 移除"分"字并转换为数值
                                    'reason': f'根据评分规则对{rule_name}项进行评分',
                                }
                            )

            # 更新分析结果
            analysis_result.detailed_scores = json.dumps(
                detailed_scores, ensure_ascii=False
            )

            # 记录投标人名称和投标总价
            if '投标人名称' in analyzed_result and analyzed_result['投标人名称']:
                analysis_result.bidder_name = analyzed_result['投标人名称']

            if '投标总价' in analyzed_result and analyzed_result['投标总价']:
                try:
                    price_value = self._extract_numeric_price(
                        analyzed_result['投标总价']
                    )
                    if price_value is not None:
                        analysis_result.extracted_price = price_value
                except (ValueError, TypeError) as e:
                    self.logger.warning(
                        f'无法解析投标总价: {analyzed_result["投标总价"]}, 错误: {e}'
                    )

            # 计算总分
            total_score = sum(item.get('score', 0) for item in detailed_scores)
            analysis_result.total_score = total_score

            self.db.commit()
            self.logger.info(
                f'分析结果保存成功，投标人: {analysis_result.bidder_name}, 总分: {total_score}, 投标总价: {analysis_result.extracted_price}'
            )

        except Exception as e:
            self.logger.error(f'保存分析结果时出错: {e}')
            if self.db:
                self.db.rollback()

    def _extract_numeric_price(self, price_str):
        """
        从价格字符串中提取数值，支持汉字大写数字转换
        """
        if not price_str:
            return None

        # 如果是数值字符串，直接转换
        try:
            # 移除常见的非数字字符
            cleaned_price = re.sub(r'[^\d\.万元亿]', '', str(price_str))
            # 处理万元、亿元等单位
            multiplier = 1
            if '万' in cleaned_price:
                multiplier = 10000
                cleaned_price = cleaned_price.replace('万', '')
            elif '亿' in cleaned_price:
                multiplier = 100000000
                cleaned_price = cleaned_price.replace('亿', '')

            # 转换为浮点数
            if cleaned_price:
                numeric_price = float(cleaned_price) * multiplier
                return numeric_price
        except (ValueError, TypeError):
            pass  # 继续尝试汉字数字解析

        # 尝试处理汉字大写数字
        try:
            # 简单的汉字数字映射
            chinese_nums = {
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
                '十': 10,
                '百': 100,
                '千': 1000,
                '万': 10000,
                '亿': 100000000,
            }

            # 清理价格字符串，只保留汉字数字相关字符
            cleaned_chinese = re.sub(r'[^\u4e00-\u9fa5]', '', str(price_str))

            # 简单处理常见的汉字数字格式
            if cleaned_chinese in chinese_nums:
                return float(chinese_nums[cleaned_chinese])

            # 处理"一百"、"一千"等格式
            # 这里可以添加更复杂的汉字数字解析逻辑
            # 暂时返回None，表示无法解析
        except (ValueError, TypeError):
            pass

        # 如果所有方法都失败，返回None
        return None
