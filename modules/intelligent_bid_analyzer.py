import json
import re
import logging
import traceback
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
        extracted_text: list = None,
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
            self.bid_processor = PDFProcessor(
                self.bid_file_path, file_type='bid'
            )  # 投标文件使用ONNX
            self.bid_pages = None

        # 存储分析结果的累积数据
        self.accumulated_results = {
            '投标人名称': '',
            '投标总价': '',
            '评分结果': [{}]
        }
        self.bidder_names = []  # 存储所有提取到的投标人名称
        self.total_prices = []  # 存储所有提取到的投标总价

    def analyze_bidding_document(self):
        """
        分析投标文件的新方法，按照新的分析思路实现
        """
        self.logger.info(f'开始分析投标文件: {self.bid_file_path}')

        try:
            # 1. 提取投标文件文本（使用PyMuPDF，对无法提取的页面使用RapidOCR）
            if self.bid_pages is None:
                self.logger.info('提取投标文件文本...')
                # 设置流式处理回调函数
                if self.bid_processor:
                    self.bid_processor.set_stream_callback(self._stream_process_callback)
                    # 使用流式处理
                    self.bid_pages = self.bid_processor.stream_process_pdf(chunk_size=3)
                else:
                    self.bid_pages = self.bid_processor.extract_text_with_ocr_when_needed()

            if not self.bid_pages or not any(self.bid_pages):
                raise ValueError('未能提取到有效的投标文件文本内容')

            self.logger.info(f'成功提取投标文件文本，共 {len(self.bid_pages)} 页')

            # 2. 从数据库获取评分规则
            rules_from_db = self._get_scoring_rules_from_db()
            if not rules_from_db:
                raise ValueError('未能从数据库获取评分规则')

            self.logger.info(f'从数据库获取到 {len(rules_from_db)} 条评分规则')

            # 3. 构建AI分析Prompt
            prompt = self._build_analysis_prompt(rules_from_db)

            # 4. 调用AI分析（分块处理）
            analyzed_result = self._analyze_with_ai_in_chunks(prompt)

            # 5. 保存分析结果
            self._save_analysis_results(analyzed_result)

            # 提取关键信息用于返回
            bidder_name = analyzed_result.get('投标人名称', self.bidder_name)
            total_price = analyzed_result.get('投标总价', '未提取')
            scores = analyzed_result.get('评分结果', [])

            return {
                'status': 'success',
                'message': '投标文件分析完成',
                'details': {
                    'bidder_name': bidder_name,
                    'total_price': total_price,
                    'scores': scores,
                },
            }

        except Exception as e:
            error_msg = f'分析投标文件时出错: {str(e)}'
            self.logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'message': error_msg}

    def _stream_process_callback(self, processed_pages: int, pages_text: list):
        """
        流式处理回调函数，在PDF处理过程中被调用
        
        Args:
            processed_pages: 已处理的页面数
            pages_text: 已处理的页面文本列表
        """
        self.logger.info(f'流式处理回调：已处理 {processed_pages} 页')
        
        # 当处理了足够的页面时，开始进行AI分析
        if processed_pages >= 3:  # 至少处理3页后再进行分析
            # 构建当前已处理文本的分析请求
            current_text = '\n'.join(pages_text[:processed_pages])
            
            # 从数据库获取评分规则
            rules_from_db = self._get_scoring_rules_from_db()
            if rules_from_db:
                # 构建AI分析Prompt
                prompt = self._build_analysis_prompt(rules_from_db)
                
                # 为当前块构建完整的prompt
                chunk_prompt = f"""{prompt.split('}},投标方的投标文本内容为：')[0] + '}}'}},投标方的投标文本内容为：
『{current_text}』
请分析该投标文本，分析出该投标方的投标人名称、投标总价，并根据评分规则，对投标方投标文本内容进行打分，并给出每一项评分结果，请返回一个json格式的打分结果，格式如下：
{{
    "投标人名称": "投标方公司名称",  
    "投标总价": "投标总价",  
    "评分结果": [
        {{
            "规则名称1": "50分",
            "规则名称2": "50分",
            ......
        }}
    ]
}}，其中投标方名称和投标总价为必填项，都可以在投标一览表”提取，其中投标人名称在授权委托书等多处可以提取，需要前后多次提取进行对比验证。而投标总价在投标一览表中，该表可能同时还有投标保证金，也是数字，注意imian二者不能混淆，投标总价同时有汉字大写，需要转换为数字，与从数字提取的投标报价进行对照核实。"""

                # 调用AI分析
                self.logger.info(f'对已处理的 {processed_pages} 页内容进行AI分析...')
                ai_response = self.ai_analyzer.analyze_text(chunk_prompt)
                
                # 解析AI响应并累积结果
                try:
                    # 清理响应文本
                    clean_response = ai_response.strip()
                    if clean_response.startswith('```json'):
                        clean_response = clean_response[7:]
                    if clean_response.endswith('```'):
                        clean_response = clean_response[:-3]
                    clean_response = clean_response.strip()

                    # 解析JSON
                    chunk_result = json.loads(clean_response)
                    
                    # 累积结果
                    self._accumulate_results(chunk_result)
                    
                    self.logger.info(
                        f'第1到{processed_pages}页AI分析完成，提取到投标人名称: {chunk_result.get("投标人名称")}'
                    )
                except json.JSONDecodeError as e:
                    self.logger.error(
                        f'第1到{processed_pages}页AI响应JSON解析失败: {e}'
                    )
                    self.logger.error(f'AI响应内容: {ai_response}')

    def _accumulate_results(self, chunk_result):
        """
        累积分析结果
        
        Args:
            chunk_result: 当前块的分析结果
        """
        # 收集投标人名称
        if '投标人名称' in chunk_result and chunk_result['投标人名称']:
            self.bidder_names.append(chunk_result['投标人名称'])

        # 收集投标总价
        if '投标总价' in chunk_result and chunk_result['投标总价']:
            self.total_prices.append(chunk_result['投标总价'])

        # 合并评分结果
        if '评分结果' in chunk_result and isinstance(chunk_result['评分结果'], list):
            for score_dict in chunk_result['评分结果']:
                if isinstance(score_dict, dict):
                    for rule_name, score in score_dict.items():
                        # 检查是否已存在该规则的评分
                        existing_score = self.accumulated_results['评分结果'][0].get(rule_name)
                        if existing_score:
                            # 累加分数（如果是数值）
                            try:
                                current_score = float(str(existing_score).rstrip('分'))
                                new_score = float(str(score).rstrip('分'))
                                self.accumulated_results['评分结果'][0][rule_name] = (
                                    f'{current_score + new_score}分'
                                )
                            except ValueError:
                                # 如果无法转换为数值，则保留新值
                                self.accumulated_results['评分结果'][0][rule_name] = score
                        else:
                            self.accumulated_results['评分结果'][0][rule_name] = score

        # 选择最常出现的投标人名称
        if self.bidder_names:
            from collections import Counter
            name_counts = Counter(self.bidder_names)
            self.accumulated_results['投标人名称'] = name_counts.most_common(1)[0][0]

        # 选择最常出现的投标总价
        if self.total_prices:
            from collections import Counter
            price_counts = Counter(self.total_prices)
            self.accumulated_results['投标总价'] = price_counts.most_common(1)[0][0]

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
            return rules
        except Exception as e:
            self.logger.error(f'从数据库获取评分规则时出错: {e}')
            return []

    def _build_analysis_prompt(self, rules_from_db):
        """
        构建AI分析Prompt，将评分规则作为Prompt的一部分
        """
        # 将评分规则转换为文本格式
        scoring_rules_text = ''
        for rule in rules_from_db:
            if rule.is_price_criteria:
                scoring_rules_text += f'    {rule.Parent_Item_Name or "价格评分"}：，本项最高分{rule.Child_max_score}，{rule.description}；\n'
            elif rule.Child_Item_Name:
                scoring_rules_text += f'    {rule.Child_Item_Name}：，本项最高分{rule.Child_max_score}，{rule.description}；\n'
            elif rule.Parent_Item_Name:
                scoring_rules_text += f'    {rule.Parent_Item_Name}：，本项最高分{rule.Parent_max_score}，{rule.description}；\n'

        # 返回评分规则部分，不包含投标文件文本（因为会在分块处理时添加）
        prompt = f"""你是一个资深评标专家，现在需要根据如下评分规则：
{{
{scoring_rules_text}
}}"""

        return prompt

    def _analyze_with_ai_in_chunks(self, prompt):
        """
        分块处理投标文件内容并调用AI分析
        实现边解析边给AI大模型进行评价，并保存每次评价的结果，最终合并处理返回结果
        """
        # 如果已经通过流式处理累积了结果，则直接返回累积结果
        if any(self.accumulated_results['评分结果'][0].values()):
            self.logger.info('使用流式处理累积的分析结果')
            return self.accumulated_results
            
        # 始终采用分块处理方式，避免一次性发送过长文本给AI
        self.logger.info('开始分块处理投标文件内容...')

        # 按固定页数分块处理（较小的块大小以适应AI模型上下文限制）
        chunk_size = 3
        all_results = []

        # 提取评分规则部分（所有分块共用）
        scoring_rules_section = prompt.split('}},投标方的投标文本内容为：')[0] + '}}'

        for i in range(0, len(self.bid_pages), chunk_size):
            chunk_pages = self.bid_pages[i : i + chunk_size]
            chunk_text = '\n'.join(chunk_pages)

            # 为每个块构建完整的prompt，包含评分规则和当前块的文本
            chunk_prompt = f"""{scoring_rules_section},投标方的投标文本内容为：
『{chunk_text}』
请分析该投标文本，分析出该投标方的投标人名称、投标总价，并根据评分规则，对投标方投标文本内容进行打分，并给出每一项评分结果，请返回一个json格式的打分结果，格式如下：
{{
    "投标人名称": "投标方公司名称",  
    "投标总价": "投标总价",  
    "评分结果": [
        {{
            "规则名称1": "50分",
            "规则名称2": "50分",
            ......
        }}
    ]
}}，其中投标方名称和投标总价为必填项，都可以在投标一览表”提取，其中投标人名称在授权委托书等多处可以提取，需要前后多次提取进行对比验证。而投标总价在投标一览表中，该表可能同时还有投标保证金，也是数字，注意imian二者不能混淆，投标总价同时有汉字大写，需要转换为数字，与从数字提取的投标报价进行对照核实。"""

            self.logger.info(
                f'分析第{i + 1}到{min(i + chunk_size, len(self.bid_pages))}页内容...'
            )
            ai_response = self.ai_analyzer.analyze_text(chunk_prompt)

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
                chunk_result = json.loads(clean_response)
                all_results.append(chunk_result)
                self.logger.info(
                    f'第{i + 1}到{min(i + chunk_size, len(self.bid_pages))}页AI分析完成，提取到投标人名称: {chunk_result.get("投标人名称")}'
                )
            except json.JSONDecodeError as e:
                self.logger.error(
                    f'第{i + 1}到{min(i + chunk_size, len(self.bid_pages))}页AI响应JSON解析失败: {e}'
                )
                self.logger.error(f'AI响应内容: {ai_response}')

        # 合并结果
        merged_result = self._merge_results(all_results)
        return merged_result

    def _merge_results(self, results):
        """
        合并多个块的分析结果
        """
        if not results:
            return {}

        # 初始化合并结果
        merged = {'投标人名称': '', '投标总价': '', '评分结果': [{}]}

        # 收集所有投标人名称和投标总价，用于后续验证和选择
        bidder_names = []
        total_prices = []

        # 合并评分结果
        merged_scores = {}

        for result in results:
            # 收集投标人名称
            if '投标人名称' in result and result['投标人名称']:
                bidder_names.append(result['投标人名称'])

            # 收集投标总价
            if '投标总价' in result and result['投标总价']:
                total_prices.append(result['投标总价'])

            # 合并评分结果
            if '评分结果' in result and isinstance(result['评分结果'], list):
                for score_dict in result['评分结果']:
                    if isinstance(score_dict, dict):
                        for rule_name, score in score_dict.items():
                            if rule_name in merged_scores:
                                # 累加分数（如果是数值）
                                try:
                                    current_score = float(
                                        str(merged_scores[rule_name]).rstrip('分')
                                    )
                                    new_score = float(str(score).rstrip('分'))
                                    merged_scores[rule_name] = (
                                        f'{current_score + new_score}分'
                                    )
                                except ValueError:
                                    # 如果无法转换为数值，则保留新值
                                    merged_scores[rule_name] = score
                            else:
                                merged_scores[rule_name] = score

        # 选择最常出现的投标人名称
        if bidder_names:
            from collections import Counter

            name_counts = Counter(bidder_names)
            merged['投标人名称'] = name_counts.most_common(1)[0][0]
            self.logger.info(f'选择最常出现的投标人名称: {merged["投标人名称"]}')

        # 选择最常出现的投标总价
        if total_prices:
            from collections import Counter

            price_counts = Counter(total_prices)
            merged['投标总价'] = price_counts.most_common(1)[0][0]
            self.logger.info(f'选择最常出现的投标总价: {merged["投标总价"]}')

        # 更新评分结果
        merged['评分结果'] = [merged_scores]

        return merged

    def _save_analysis_results(self, analyzed_result):
        """
        保存分析结果到数据库，包括投标人名称、投标总价和评分结果
        """
        if not (self.db and self.bid_document_id):
            self.logger.warning('数据库会话或投标文件ID未提供，无法保存分析结果')
            return

        try:
            # 获取或创建分析结果记录
            analysis_result = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == self.bid_document_id)
                .first()
            )

            if not analysis_result:
                analysis_result = AnalysisResult(
                    project_id=self.project_id,
                    bid_document_id=self.bid_document_id,
                    bidder_name=analyzed_result.get('投标人名称', self.bidder_name),
                )
                self.db.add(analysis_result)
            else:
                # 更新投标人名称
                if '投标人名称' in analyzed_result:
                    analysis_result.bidder_name = analyzed_result['投标人名称']

            # 提取并保存投标总价
            if '投标总价' in analyzed_result:
                try:
                    # 尝试将投标总价转换为浮点数
                    price_str = analyzed_result['投标总价']
                    # 使用增强的价格提取方法
                    price_value = self._extract_numeric_price(price_str)
                    if price_value is not None:
                        analysis_result.extracted_price = price_value
                except (ValueError, TypeError) as e:
                    self.logger.warning(
                        f'无法解析投标总价: {analyzed_result["投标总价"]}, 错误: {e}'
                    )

            # 转换评分结果格式以适应现有数据库结构
            detailed_scores = []
            if '评分结果' in analyzed_result and isinstance(
                analyzed_result['评分结果'], list
            ):
                for score_dict in analyzed_result['评分结果']:
                    for rule_name, score in score_dict.items():
                        # 这里需要匹配数据库中的评分规则来获取详细信息
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

            # 计算总分
            total_score = sum(item.get('score', 0) for item in detailed_scores)
            analysis_result.total_score = total_score

            self.db.commit()
            self.logger.info(
                f'分析结果保存成功，投标人: {analysis_result.bidder_name}, 总分: {total_score}, 投标总价: {analysis_result.extracted_price}'
            )

        except Exception as e:
            self.logger.error(f'保存分析结果时出错: {e}')
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
            result = 0
            temp = 0

            for char in cleaned_chinese:
                if char in chinese_nums:
                    num = chinese_nums[char]
                    if num >= 10:
                        if temp == 0 and num >= 10000:  # 直接是万或亿
                            result = num
                        elif temp == 0:
                            temp = num
                        else:
                            result += temp * num
                            temp = 0
                    else:
                        temp = num

            result += temp
            return float(result) if result > 0 else None
        except:
            pass

        return None
