import json
import re
import logging
import traceback
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.pdf_processor import PDFProcessor
from modules.price_manager import PriceManager
from modules.database import BidDocument, ScoringRule, AnalysisResult
from modules.bid_analyzer_helpers import BidAnalyzerHelpers

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
            bid_doc = self.db.query(BidDocument).filter(BidDocument.id == self.bid_document_id).first()
            self.bidder_name = bid_doc.bidder_name if bid_doc else '未知投标方'
        else:
            self.bidder_name = '未知投标方'

        # 优化：如果已提供提取好的文本，则直接使用
        if extracted_text is not None:
            self.bid_pages = extracted_text
            self.bid_processor = None  # 不需要再创建PDF处理器
            self.logger.info(f'IntelligentBidAnalyzer initialized with pre-extracted text for {self.bid_file_path}.')
        else:
            # 保持旧的兼容性，如果未提供文本，则初始化处理器以便后续提取
            self.logger.warning(f'No pre-extracted text provided for {self.bid_file_path}. PDFProcessor will be used.')
            self.bid_processor = PDFProcessor(self.bid_file_path)
            self.bid_pages = None

    def _update_progress(self, completed, total, current_rule, partial_results=None):
        if not (self.db and self.bid_document_id):
            return
        try:
            bid_doc = self.db.query(BidDocument).filter(BidDocument.id == self.bid_document_id).first()
            if bid_doc:
                bid_doc.progress_total_rules = total
                bid_doc.progress_completed_rules = completed
                progress_info = f"{self.bidder_name} - {current_rule}"
                bid_doc.progress_current_rule = progress_info[:100]
                bid_doc.detailed_progress_info = progress_info
                if partial_results is not None:
                    bid_doc.partial_analysis_results = json.dumps(partial_results[:5], ensure_ascii=False)
                self.db.commit()
                self.logger.info(f'进度更新: {completed}/{total} - {progress_info}')
        except Exception as e:
            self.logger.error(f'更新进度时出错: {e}')
            self.db.rollback()

    def _build_rules_tree_from_db(self, rules_from_db: list) -> list:
        """将从数据库获取的扁平化评分规则列表转换为树形结构。"""
        rule_map = {rule.id: {
            "id": rule.id,
            "criteria_name": rule.Child_Item_Name,
            "max_score": rule.Child_max_score,
            "description": rule.description,
            "is_price_criteria": rule.is_price_criteria,
            "is_veto": rule.is_veto,
            "parent_id": None,  # 简化处理
            "children": []
        } for rule in rules_from_db if rule.Child_Item_Name is not None}

        tree = []
        for rule_id, rule_node in rule_map.items():
            tree.append(rule_node)
        return tree

    def _get_bid_pages(self):
        """获取投标文件页面内容，优先使用已加载的文本。"""
        # 如果文本已在初始化时提供，直接返回
        if self.bid_pages is not None:
            return self.bid_pages

        # 作为后备方案，如果文本未提供，则调用PDF处理器
        if self.bid_processor:
            self.logger.info(f"No pre-extracted text found, processing PDF for {self.bid_file_path} on demand.")
            self.bid_pages = self.bid_processor.process_pdf_per_page()
            self._save_failed_pages_info(self.bid_processor)
            return self.bid_pages
        
        # 如果既没有预提取的文本，也没有处理器，则返回错误
        self.logger.error(f"Cannot get bid pages: No pre-extracted text and no PDF processor available for {self.bid_file_path}.")
        return []

    def analyze(self):
        try:
            # 1. 从数据库加载评分规则
            self.logger.info(f"正在为项目 {self.project_id} 从数据库加载评分规则...")
            if not self.db or not self.project_id:
                return {'error': '数据库会话或项目ID未提供，无法加载评分规则。'}
            
            rules_from_db = self.db.query(ScoringRule).filter(ScoringRule.project_id == self.project_id).all()
            if not rules_from_db:
                return {'error': f'项目 {self.project_id} 在数据库中没有找到评分规则。'}
            
            scoring_rules_tree = self._build_rules_tree_from_db(rules_from_db)
            self.logger.info(f"成功从数据库加载并构建了 {len(rules_from_db)} 条评分规则的树形结构。")

            # 2. 提取投标文件内容（使用缓存）
            bid_pages = self._get_bid_pages()
            if not bid_pages or not any(bid_pages):
                return {'error': '从投标文件中提取有效文本失败。'}

            # 3. 提取价格
            prices = self.price_manager.extract_prices_from_content(bid_pages)
            self.logger.info(f"投标人 {self.bidder_name} 提取到的所有价格: {prices}")
            best_price = self.price_manager.select_best_price(prices, bid_pages)
            self.logger.info(f"投标人 {self.bidder_name} 选择的最佳价格: {best_price}")

            # 4. 执行AI分析 - 首先分析子项规则
            # 获取所有子项规则（非价格规则且有Child_Item_Name的规则）
            child_rules = [rule for rule in rules_from_db 
                          if not rule.is_price_criteria and rule.Child_Item_Name is not None]
            
            self.progress_counter = 0
            self.total_rules_to_analyze = len(child_rules)
            self._update_progress(0, self.total_rules_to_analyze, f'[{self.bidder_name}] 初始化分析...', [])
            
            # 分析每个子项规则
            analyzed_scores = []  # 改为列表格式以匹配数据库期望的格式
            analyzed_scores_for_progress = []
            for rule in child_rules:
                self.progress_counter += 1
                current_rule_name = f'分析规则 {self.progress_counter}/{self.total_rules_to_analyze}: {rule.Child_Item_Name}'
                self.logger.info(f'正在为投标人 {self.bidder_name} 分析子项规则: {rule.Child_Item_Name}')
                
                # 查找相关上下文（复用已提取的文本）
                relevant_context = self._find_relevant_context_for_child_rule(rule, bid_pages)
                
                # 创建prompt
                prompt = self._create_prompt_for_child_rule(rule, relevant_context)
                
                # 提交AI分析
                ai_response = self.ai_analyzer.analyze_text(prompt)
                if 'Error:' in ai_response:
                    score, reason = 0, f'AI分析失败: {ai_response}'
                else:
                    score, reason = self._parse_ai_score_response(ai_response, rule.Child_max_score)
                
                # 保存分析结果到列表
                analyzed_rule = {
                    'Child_Item_Name': rule.Child_Item_Name,
                    'max_score': rule.Child_max_score,
                    'score': score,
                    'reason': reason,
                    'Parent_Item_Name': rule.Parent_Item_Name
                }
                analyzed_scores.append(analyzed_rule)
                
                # 为进度更新创建一个单独的列表
                analyzed_rule_for_progress = {
                    'Child_Item_Name': rule.Child_Item_Name,
                    'max_score': rule.Child_max_score,
                    'score': score,
                    'reason': reason,
                    'Parent_Item_Name': rule.Parent_Item_Name
                }
                analyzed_scores_for_progress.append(analyzed_rule_for_progress)
                
                # 更新进度
                self._update_progress(self.progress_counter, self.total_rules_to_analyze, current_rule_name, analyzed_scores_for_progress)
            
            # 5. 计算价格分（注意：价格分应该在所有投标人都分析完成后统一计算，这里仅保存提取的价格）
            price_score = 0
            price_rule = next((rule for rule in rules_from_db if rule.is_price_criteria), None)
            if price_rule:
                self.logger.info(f'投标人 {self.bidder_name} 提取到价格: {best_price}')
                # 价格分将在所有投标人分析完成后统一计算，这里仅保存提取的价格
                self._save_extracted_price(best_price)
            else:
                # 没有价格规则也保存提取的价格
                self._save_extracted_price(best_price)
            
            # 6. 计算总分
            total_score = sum(item['score'] for item in analyzed_scores)
            self._update_progress(self.total_rules_to_analyze, self.total_rules_to_analyze, '分析完成', analyzed_scores_for_progress)

            # 7. 准备并返回结果
            analysis_result = {
                'total_score': total_score,
                'detailed_scores': analyzed_scores,  # 现在是列表格式
                'extracted_price': best_price,
                'analysis_summary': '分析完成。',
                'ai_model': self.ai_analyzer.model,
            }
            self._save_extracted_price(best_price)
            return analysis_result

        except Exception as e:
            self.logger.error(f'分析过程中发生意外错误: {e}')
            self.logger.error(traceback.format_exc())
            return {'error': f'分析过程中发生意外错误: {str(e)}'}

    def _find_relevant_context_for_child_rule(self, rule, pages, context_window=2):
        """为子项规则查找相关上下文"""
        keywords = set(re.split(r'\s|，|。', rule.Child_Item_Name + ' ' + (rule.description or '')))
        keywords = {k for k in keywords if k and len(k) > 1}
        relevant_pages_indices = set()
        for i, page_text in enumerate(pages):
            if any(keyword.lower() in page_text.lower() for keyword in keywords):
                for j in range(i, min(i + context_window + 1, len(pages))):
                    relevant_pages_indices.add(j)
        if not relevant_pages_indices:
            return '\n'.join(pages[:3])
        sorted_indices = sorted(list(relevant_pages_indices))
        grouped_pages = []
        if not sorted_indices: return ''
        start = end = sorted_indices[0]
        for i in range(1, len(sorted_indices)):
            if sorted_indices[i] == end + 1:
                end = sorted_indices[i]
            else:
                grouped_pages.append((start, end))
                start = end = sorted_indices[i]
        grouped_pages.append((start, end))
        context_parts = [f'--- Pages {s+1}-{e+1} ---\n' + '\n'.join(pages[s:e+1]) for s, e in grouped_pages]
        return '\n\n'.join(context_parts)

    def _create_prompt_for_child_rule(self, rule, context_text):
        """为子项规则创建prompt"""
        max_context_len = 8000
        context_text = context_text[:max_context_len] + ('\n... (内容已截断)' if len(context_text) > max_context_len else '')
        return f"""
        **角色:** 专业的评标专家
        **任务:** 根据具体的评分标准，评估一份投标文件。

        **评分标准:**
        - **名称:** {rule.Child_Item_Name}
        - **描述:** {rule.description or 'N/A'}
        - **满分:** {rule.Child_max_score}

        **投标文件相关内容:**
        ---
        {context_text}
        ---

        **指令:**
        1.  仔细阅读上方提供的投标文件内容。
        2.  **仅根据**提供的内容，评估投标文件的满足程度。
        3.  给出一个介于 0 到 {rule.Child_max_score} 之间的分数。
        4.  用清晰、简洁的理由来证明你的打分，并引用文本内容作为依据。
        5.  先在  标签中进行思考，最后仅输出一个 JSON 对象。

        **重要:** 你的最终输出必须是且仅是一个格式正确的JSON对象，不要在JSON代码块之外包含任何解释性文字。

        **必需的输出格式:**
        ```json
        {{
          "score": <你的分数>,
          "reason": "<你的理由>"
        }}
        ```
        """

    def _calculate_price_score(self, price_rule, best_price):
        """计算价格分"""
        # 获取项目中所有投标文件的价格
        all_bids = self.db.query(BidDocument).filter(BidDocument.project_id == self.project_id).all()
        project_prices = {}
        
        # 添加当前投标文件的价格
        if best_price is not None:
            project_prices[self.bidder_name] = best_price
        
        # 获取其他投标文件的价格
        for bid in all_bids:
            if bid.id != self.bid_document_id:
                if bid.analysis_result and bid.analysis_result.extracted_price is not None:
                    project_prices[bid.bidder_name] = bid.analysis_result.extracted_price
        
        # 只有当至少有两个有效报价时才计算价格分
        if len(project_prices) >= 2 and best_price is not None:
            # 使用价格管理器计算价格分
            price_scores = self.price_manager.calculate_project_price_scores(project_prices, [price_rule])
            
            # 获取当前投标人的价格分
            current_bidder_score = price_scores.get(self.bidder_name, 0)
        else:
            # 如果没有足够的报价，给予0分
            current_bidder_score = 0
        
        return {
            'criteria_name': price_rule.Parent_Item_Name,
            'max_score': price_rule.Parent_max_score,
            'score': current_bidder_score,
            'reason': f'根据价格评分规则计算得出。提取到的报价为: {best_price}' if best_price is not None else '未提取到有效报价，价格分设为0',
            'is_price_criteria': True,
            'extracted_price': best_price
        }

    def _parse_ai_score_response(self, response, max_score):
        try:
            # 使用正则表达式从响应中提取JSON块，这能抵抗额外的解释性文本
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{.*?\})', response, re.DOTALL)

            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                score = result.get('score', 0)
                reason = result.get('reason', '未提供理由。')

                if not isinstance(score, (int, float)):
                    score = 0
                score = max(0, min(float(score), float(max_score)))
                return score, reason
            else:
                # 如果无法找到JSON，作为备用方案，尝试从文本中提取分数
                score_match = re.search(r'(\d+(?:\.\d+)?)\s*分', response)
                if score_match:
                    score = float(score_match.group(1))
                    score = max(0, min(score, max_score))
                    return score, f'无法解析JSON，但从文本中提取到分数。原始响应: {response[:200]}...'
                
                return 0, f'无法从AI响应中解析出有效的JSON或分数。响应: {response[:200]}...'

        except (json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"解析AI响应时出错: {e}\n响应内容: {response}")
            return 0, f'解析AI响应失败。错误: {e}'

    def _save_failed_pages_info(self, pdf_processor):
        """保存PDF处理失败的页面信息"""
        if not (self.db and self.bid_document_id):
            return
        try:
            bid_doc = self.db.query(BidDocument).filter(BidDocument.id == self.bid_document_id).first()
            if bid_doc and hasattr(pdf_processor, 'failed_pages') and pdf_processor.failed_pages:
                bid_doc.failed_pages_info = json.dumps(pdf_processor.failed_pages, ensure_ascii=False)
                self.db.commit()
        except Exception as e:
            self.logger.error(f'保存失败页面信息时出错: {e}')
            self.db.rollback()

    def _save_extracted_price(self, price):
        """保存提取到的价格"""
        if not (self.db and self.bid_document_id):
            return
        try:
            bid_doc = self.db.query(BidDocument).filter(BidDocument.id == self.bid_document_id).first()
            if bid_doc:
                # 确保分析结果存在
                if not bid_doc.analysis_result:
                    analysis_result = AnalysisResult(
                        project_id=self.project_id,
                        bid_document_id=self.bid_document_id,
                        bidder_name=self.bidder_name,
                        extracted_price=float(price) if price is not None else None
                    )
                    self.db.add(analysis_result)
                else:
                    bid_doc.analysis_result.extracted_price = float(price) if price is not None else None
                
                # 同时更新投标文档中的价格状态
                bid_doc.price_extracted = price is not None
                bid_doc.price_extraction_attempts += 1
                
                self.db.commit()
        except Exception as e:
            self.logger.error(f'保存提取价格时出错: {e}')
            self.db.rollback()
            # 可选：将错误信息保存到数据库
            if bid_doc:
                bid_doc.price_extraction_error = str(e)[:500]
                self.db.commit()

    def clear_pdf_cache(self):
        """清理PDF文本缓存"""
        self.bid_processor.clear_cache()
