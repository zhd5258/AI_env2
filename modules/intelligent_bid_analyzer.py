#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
智能投标分析器模块
负责分析投标文件并生成评分
"""

import json
import re
import logging
import traceback
import os
from typing import List, Dict, Any, Optional
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.pdf_processor import PDFProcessor
from modules.price_manager import PriceManager
from modules.database import BidDocument, ScoringRule, AnalysisResult
from modules.bid_analyzer_helpers import BidAnalyzerHelpers


class IntelligentBidAnalyzer(BidAnalyzerHelpers):
    def __init__(
        self,
        tender_file_path: str,
        bid_file_path: str,
        db_session=None,
        bid_document_id=None,
        project_id=None,
        extracted_text: Optional[List[str]] = None,
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
        self.total_rules_to_analyze = 0  # 初始化实例变量

        if self.db and self.bid_document_id:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            # 修复：确保即使数据库中没有投标人名称，也不使用默认值
            self.bidder_name = (
                bid_doc.bidder_name if bid_doc and bid_doc.bidder_name else ''
            )
        else:
            self.bidder_name = ''

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
            )  # 使用新的PDF处理器，指定为投标文件类型
            self.bid_pages = None

    def _update_progress(self, completed, total, current_rule, partial_results=None):
        if not (self.db and self.bid_document_id):
            return
        try:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            if bid_doc:
                bid_doc.progress_total_rules = total
                bid_doc.progress_completed_rules = completed
                # 修复：确保投标人名称不为空时才使用，否则使用文件名
                if self.bidder_name and self.bidder_name.strip():
                    progress_info = f'{self.bidder_name} - {current_rule}'
                else:
                    # 从文件路径提取文件名作为备用
                    filename = os.path.basename(self.bid_file_path)
                    bidder_name = os.path.splitext(filename)[0]
                    progress_info = f'{bidder_name} - {current_rule}'
                bid_doc.progress_current_rule = progress_info[:100]
                bid_doc.detailed_progress_info = progress_info
                if partial_results is not None:
                    bid_doc.partial_analysis_results = json.dumps(
                        partial_results[:5], ensure_ascii=False
                    )
                # 更新处理阶段为"AI分析中"
                bid_doc.processing_phase = 'AI分析中'
                self.db.commit()
                self.logger.info(f'进度更新: {completed}/{total} - {progress_info}')
        except Exception as e:
            self.logger.error(f'更新进度时出错: {e}')
            self.db.rollback()

    def _build_rules_tree_from_db(
        self, rules_from_db: List[Any]
    ) -> List[Dict[str, Any]]:
        """将从数据库获取的扁平化评分规则列表转换为树形结构。"""
        rule_map = {
            rule.id: {
                'id': rule.id,
                'criteria_name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score,
                'description': rule.description,
                'is_price_criteria': rule.is_price_criteria,
                'is_veto': rule.is_veto,
                'parent_id': None,  # 简化处理
                'children': [],
            }
            for rule in rules_from_db
            if rule.Child_Item_Name is not None
        }

        tree = []
        for rule_id, rule_node in rule_map.items():
            tree.append(rule_node)
        return tree

    def _get_bid_pages(self) -> List[str]:
        """获取投标文件页面内容，优先使用已加载的文本。"""
        # 如果文本已在初始化时提供，直接返回
        if self.bid_pages is not None:
            return self.bid_pages

        # 作为后备方案，如果文本未提供，则调用PDF处理器
        if self.bid_processor:
            self.logger.info(
                f'No pre-extracted text found, processing PDF for {self.bid_file_path} on demand.'
            )
            # 不再在这里处理PDF，因为已经在analysis_manager中处理过了
            # 直接从PDF处理器加载内容
            pages_content = self.bid_processor.load_content_from_md_file()
            if pages_content is not None:
                self.bid_pages = pages_content
            else:
                # 如果从MD文件加载失败，则使用extract_text_per_page方法
                self.bid_pages = self.bid_processor.extract_text_per_page()
            self._save_failed_pages_info(self.bid_processor)
            return self.bid_pages

        # 如果既没有预提取的文本，也没有处理器，则返回错误
        self.logger.error(
            f'Cannot get bid pages: No pre-extracted text and no PDF processor available for {self.bid_file_path}.'
        )
        return []

    def _get_md_file_path(self) -> Optional[str]:
        """
        获取投标文件对应的MD文件路径
        MD文件存放在temp_md目录下，文件名基于PDF文件名生成
        """
        if not self.bid_file_path:
            return None

        # 生成MD文件路径
        pdf_filename = os.path.basename(self.bid_file_path)
        file_key = os.path.splitext(pdf_filename)[0]
        md_filename = f'{file_key}.md'

        # MD文件存放在temp/md目录下
        md_file_path = os.path.join('temp/md', md_filename)

        # 检查文件是否存在
        if os.path.exists(md_file_path):
            return md_file_path
        else:
            self.logger.warning(f'MD文件不存在: {md_file_path}')
            return None

    def _load_content_from_md_file(self, md_file_path: str) -> Optional[List[str]]:
        """
        从MD文件中加载内容并转换为页面列表格式
        """
        try:
            if not md_file_path or not os.path.exists(md_file_path):
                self.logger.warning(f'MD文件不存在或路径无效: {md_file_path}')
                return None

            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按页面分隔符分割内容
            pages = content.split('\n\n---\n\n')
            self.logger.info(f'从MD文件 {md_file_path} 加载了 {len(pages)} 页内容')
            return pages
        except Exception as e:
            self.logger.error(f'从MD文件加载内容时出错: {e}')
            return None

    def analyze_rule_parallel(self, rule, bid_pages):
        """并行分析单个评分规则"""
        try:
            self.logger.info(
                f'正在为投标人 {self.bidder_name} 分析子项规则: {rule.Child_Item_Name}'
            )

            # 查找相关上下文（使用从MD文件读取的内容）
            relevant_context = self._find_relevant_context_for_child_rule(
                rule, bid_pages
            )

            # 创建prompt
            prompt = self._create_prompt_for_child_rule(rule, relevant_context)

            # 提交AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)
            if 'Error:' in ai_response:
                score, reason = 0, f'AI分析失败: {ai_response}'
            else:
                score, reason = self._parse_ai_score_response(
                    ai_response, rule.Child_max_score
                )

            # 返回分析结果
            return {
                'Child_Item_Name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score,
                'score': score,
                'reason': reason,
                'Parent_Item_Name': rule.Parent_Item_Name,
            }
        except Exception as e:
            self.logger.error(f'分析规则 {rule.Child_Item_Name} 时出错: {e}')
            return {
                'Child_Item_Name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score,
                'score': 0,
                'reason': f'分析失败: {str(e)}',
                'Parent_Item_Name': rule.Parent_Item_Name,
            }

    def analyze_bidding_document(self):
        """
        分析投标文件并生成评分，包含质量评估和重新转换逻辑
        """
        try:
            self.logger.info(f'开始分析投标文件: {self.bid_file_path}')

            # 获取投标文档记录
            if self.db and self.bid_document_id:
                bid_document = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                if bid_document:
                    # 检查OCR重试次数
                    if bid_document.ocr_retry_count >= 3:
                        self.logger.warning(
                            f'投标人 {self.bidder_name} OCR重试次数已达上限(3次)'
                        )
                        return {
                            'status': 'error',
                            'message': f'投标人 {self.bidder_name} 的PDF文件经过3次OCR重试仍无法满足质量要求',
                        }
            else:
                bid_document = None

            # 1. 从数据库加载评分规则
            self.logger.info(f'正在为项目 {self.project_id} 从数据库加载评分规则...')
            if not self.db or not self.project_id:
                return {'error': '数据库会话或项目ID未提供，无法加载评分规则。'}

            rules_from_db = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == self.project_id)
                .all()
            )
            if not rules_from_db:
                return {'error': f'项目 {self.project_id} 在数据库中没有找到评分规则。'}

            scoring_rules_tree = self._build_rules_tree_from_db(rules_from_db)
            self.logger.info(
                f'成功从数据库加载并构建了 {len(rules_from_db)} 条评分规则的树形结构。'
            )

            # 2. 提取投标文件内容（优先从MD文件读取）
            bid_pages = None

            # 首先尝试从MD文件读取内容
            md_file_path = self._get_md_file_path()
            if md_file_path:
                bid_pages = self._load_content_from_md_file(md_file_path)

            # 如果MD文件读取失败，则从PDF处理结果获取
            if not bid_pages or not any(bid_pages):
                self.logger.info('从MD文件读取内容失败，回退到PDF处理结果')
                # 更新处理阶段为"PDF处理中"
                if self.db and self.bid_document_id:
                    bid_doc = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        bid_doc.processing_phase = 'PDF处理中'
                        self.db.commit()
                # 不再在这里处理PDF，因为已经在analysis_manager中处理过了
                # 直接从PDF处理器加载内容
                bid_pages = self._get_bid_pages()

            if not bid_pages or not any(bid_pages):
                return {'error': '从投标文件中提取有效文本失败。'}

            # 3. 提取价格（优先从MD文件提取）
            # 使用价格管理器提取价格（优先从MD文件）
            best_price = self.price_manager.extract_and_select_price(
                bid_pages, md_file_path
            )
            self.logger.info(
                f'投标人 {self.bidder_name} 提取到的最佳价格: {best_price}'
            )

            # 4. 执行AI分析 - 首先分析子项规则
            # 获取所有子项规则（非价格规则且有Child_Item_Name的规则）
            child_rules = [
                rule
                for rule in rules_from_db
                if not rule.is_price_criteria and rule.Child_Item_Name is not None
            ]

            self.progress_counter = 0
            self.total_rules_to_analyze = len(child_rules)
            self._update_progress(
                0,
                self.total_rules_to_analyze,
                f'[{self.bidder_name}] 初始化分析...',
                [],
            )

            # 并行分析每个子项规则
            analyzed_scores = []  # 改为列表格式以匹配数据库期望的格式
            analyzed_scores_for_progress = []

            # 使用线程池并行处理规则分析（仅AI分析并行，PDF转换不并行）
            import concurrent.futures
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=min(len(child_rules), 5)) as executor:
                # 提交所有任务
                future_to_rule = {
                    executor.submit(self.analyze_rule_parallel, rule, bid_pages): rule
                    for rule in child_rules
                }

                # 收集结果
                completed_count = 0
                for future in as_completed(future_to_rule):
                    rule = future_to_rule[future]
                    try:
                        result = future.result()
                        analyzed_scores.append(result)

                        # 为进度更新创建一个单独的列表
                        analyzed_scores_for_progress.append(result)

                        # 更新进度
                        completed_count += 1
                        current_rule_name = f'分析规则 {completed_count}/{self.total_rules_to_analyze}: {rule.Child_Item_Name}'
                        self._update_progress(
                            completed_count,
                            self.total_rules_to_analyze,
                            current_rule_name,
                            analyzed_scores_for_progress,
                        )

                    except Exception as e:
                        self.logger.error(
                            f'分析规则 {rule.Child_Item_Name} 时发生异常: {e}'
                        )
                        # 添加一个默认的失败结果
                        failed_result = {
                            'Child_Item_Name': rule.Child_Item_Name,
                            'max_score': rule.Child_max_score,
                            'score': 0,
                            'reason': f'分析失败: {str(e)}',
                            'Parent_Item_Name': rule.Parent_Item_Name,
                        }
                        analyzed_scores.append(failed_result)
                        analyzed_scores_for_progress.append(failed_result)

                        # 更新进度
                        completed_count += 1
                        current_rule_name = f'分析规则 {completed_count}/{self.total_rules_to_analyze}: {rule.Child_Item_Name} (失败)'
                        self._update_progress(
                            completed_count,
                            self.total_rules_to_analyze,
                            current_rule_name,
                            analyzed_scores_for_progress,
                        )

            # 5. 计算除价格外的总分
            other_scores_total = sum(item['score'] for item in analyzed_scores)

            # 6. 质量评估和重新转换逻辑
            # 如果除价格外的总分低于30分，或者没有提取到有效价格，则需要重新转换PDF
            if other_scores_total < 30 or best_price is None:
                self.logger.warning(
                    f'投标人 {self.bidder_name} 的评分质量不达标: 总分={other_scores_total}, 价格提取={"成功" if best_price is not None else "失败"}'
                )

                # 检查是否可以重新转换
                if bid_document and bid_document.ocr_retry_count < 3:
                    self.logger.info(
                        f'开始第 {bid_document.ocr_retry_count + 1} 次重新转换PDF: {self.bidder_name}'
                    )

                    # 更新重试次数
                    bid_document.ocr_retry_count += 1
                    bid_document.processing_phase = '重新转换PDF中'
                    self.db.commit()

                    # 删除现有的MD文件（但要确保文件名匹配）
                    if md_file_path and os.path.exists(md_file_path):
                        # 检查文件名是否匹配，避免误删
                        pdf_filename = os.path.basename(self.bid_file_path)
                        md_filename = os.path.basename(md_file_path)
                        file_key = os.path.splitext(pdf_filename)[0]
                        expected_md_filename = f'{file_key}.md'

                        # 只有当文件名匹配时才删除
                        if md_filename == expected_md_filename:
                            os.remove(md_file_path)
                            self.logger.info(
                                f'已删除质量不达标的MD文件: {md_file_path}'
                            )
                        else:
                            self.logger.warning(
                                f'MD文件名不匹配，跳过删除: {md_file_path} (期望: {expected_md_filename})'
                            )

                    # 重新转换PDF
                    retry_result = self._retry_pdf_conversion()
                    if retry_result['status'] == 'success':
                        self.logger.info(f'重新转换PDF成功: {self.bidder_name}')
                        # 递归调用分析函数
                        return self.analyze_bidding_document()
                    else:
                        self.logger.error(f'重新转换PDF失败: {retry_result["message"]}')
                        return retry_result
                else:
                    # 重试次数已达上限或没有bid_document记录
                    warning_msg = (
                        f'投标人 {self.bidder_name} 的PDF文件无法满足质量要求，'
                    )
                    if bid_document:
                        warning_msg += f'已重试 {bid_document.ocr_retry_count} 次'
                    else:
                        warning_msg += '无法获取重试信息'
                    self.logger.warning(warning_msg)
                    return {'status': 'warning', 'message': warning_msg}

            # 7. 计算价格分（注意：价格分应该在所有投标人都分析完成后统一计算，这里仅保存提取的价格）
            price_score = 0
            price_rule = next(
                (rule for rule in rules_from_db if rule.is_price_criteria), None
            )
            if price_rule:
                self.logger.info(f'投标人 {self.bidder_name} 提取到价格: {best_price}')
                # 价格分将在所有投标人分析完成后统一计算，这里仅保存提取的价格
                self._save_extracted_price(best_price)
            else:
                # 没有价格规则也保存提取的价格
                self._save_extracted_price(best_price)

            # 8. 计算总分
            total_score = other_scores_total  # 价格分将在后续统一计算
            self._update_progress(
                self.total_rules_to_analyze,
                self.total_rules_to_analyze,
                '分析完成',
                analyzed_scores_for_progress,
            )

            # 更新处理阶段为"分析完成"
            if self.db and self.bid_document_id:
                bid_document = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                if bid_document:
                    bid_document.processing_phase = '分析完成'
                    self.db.commit()

            # 9. 准备并返回结果
            analysis_result = {
                'status': 'success',
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
            return {'status': 'error', 'message': f'分析过程中发生意外错误: {str(e)}'}

    def _find_relevant_context_for_child_rule(self, rule, pages, context_window=2):
        """为子项规则查找相关上下文"""
        keywords = set(
            re.split(r'\s|，|。', rule.Child_Item_Name + ' ' + (rule.description or ''))
        )
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
        if not sorted_indices:
            return ''
        start = end = sorted_indices[0]
        for i in range(1, len(sorted_indices)):
            if sorted_indices[i] == end + 1:
                end = sorted_indices[i]
            else:
                grouped_pages.append((start, end))
                start = end = sorted_indices[i]
        grouped_pages.append((start, end))
        context_parts = [
            f'--- Pages {s + 1}-{e + 1} ---\n' + '\n'.join(pages[s : e + 1])
            for s, e in grouped_pages
        ]
        return '\n\n'.join(context_parts)

    def _create_prompt_for_child_rule(self, rule, context_text):
        """为子项规则创建prompt"""
        max_context_len = 8000
        context_text = context_text[:max_context_len] + (
            '\n... (内容已截断)' if len(context_text) > max_context_len else ''
        )
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
        all_bids = (
            self.db.query(BidDocument)
            .filter(BidDocument.project_id == self.project_id)
            .all()
        )
        project_prices = {}

        # 添加当前投标文件的价格
        if best_price is not None:
            project_prices[self.bidder_name] = best_price

        # 获取其他投标文件的价格
        for bid in all_bids:
            if bid.id != self.bid_document_id:
                if (
                    bid.analysis_result
                    and bid.analysis_result.extracted_price is not None
                ):
                    project_prices[bid.bidder_name] = (
                        bid.analysis_result.extracted_price
                    )

        # 只有当至少有两个有效报价时才计算价格分
        if len(project_prices) >= 2 and best_price is not None:
            # 使用价格管理器计算价格分
            # 注意：这里应该调用PriceScoreCalculator来计算价格分，而不是PriceManager
            # 由于当前方法在IntelligentBidAnalyzer中，我们暂时返回一个占位符
            current_bidder_score = 0
        else:
            # 如果没有足够的报价，给予0分
            current_bidder_score = 0

        return {
            'criteria_name': price_rule.Parent_Item_Name,
            'max_score': price_rule.Parent_max_score,
            'score': current_bidder_score,
            'reason': f'根据价格评分规则计算得出。提取到的报价为: {best_price}'
            if best_price is not None
            else '未提取到有效报价，价格分设为0',
            'is_price_criteria': True,
            'extracted_price': best_price,
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
                    return (
                        score,
                        f'无法解析JSON，但从文本中提取到分数。原始响应: {response[:200]}...',
                    )

                return (
                    0,
                    f'无法从AI响应中解析出有效的JSON或分数。响应: {response[:200]}...',
                )

        except (json.JSONDecodeError, TypeError) as e:
            self.logger.error(f'解析AI响应时出错: {e}\n响应内容: {response}')
            return 0, f'解析AI响应失败。错误: {e}'

    def _save_failed_pages_info(self, bid_processor):
        """保存PDF处理失败的页面信息"""
        if not (self.db and self.bid_document_id):
            return
        try:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            if (
                bid_doc
                and hasattr(bid_processor, 'failed_pages')
                and bid_processor.failed_pages
            ):
                bid_doc.failed_pages_info = json.dumps(
                    bid_processor.failed_pages, ensure_ascii=False
                )
                self.db.commit()
        except Exception as e:
            self.logger.error(f'保存失败页面信息时出错: {e}')
            self.db.rollback()

    def _save_extracted_price(self, best_price):
        """保存提取到的价格"""
        if not (self.db and self.bid_document_id):
            return
        try:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            if bid_doc:
                # 确保分析结果存在
                if not bid_doc.analysis_result:
                    analysis_result = AnalysisResult(
                        project_id=self.project_id,
                        bid_document_id=self.bid_document_id,
                        bidder_name=self.bidder_name,
                        extracted_price=float(best_price)
                        if best_price is not None
                        else None,
                    )
                    self.db.add(analysis_result)
                else:
                    bid_doc.analysis_result.extracted_price = (
                        float(best_price) if best_price is not None else None
                    )

                # 同时更新投标文档中的价格状态
                bid_doc.price_extracted = best_price is not None
                bid_doc.price_extraction_attempts += 1

                self.db.commit()
        except Exception as e:
            self.logger.error(f'保存提取价格时出错: {e}')
            self.db.rollback()
            # 可选：将错误信息保存到数据库
            try:
                bid_doc = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                if bid_doc:
                    bid_doc.price_extraction_error = str(e)[:500]
                    self.db.commit()
            except Exception as inner_e:
                self.logger.error(f'保存错误信息时出错: {inner_e}')

    def clear_pdf_cache(self):
        """清理PDF文本缓存"""
        if self.bid_processor:
            self.bid_processor.clear_cache()

    def _retry_pdf_conversion(self):
        """
        重新转换PDF文件，增强OCR质量

        Returns:
            dict: 转换结果
        """
        try:
            self.logger.info(f'开始重新转换PDF文件: {self.bid_file_path}')

            # 使用高级PDF处理器重新转换
            from modules.advanced_pdf_processor import AdvancedPDFProcessor

            # 创建临时目录
            temp_dir = 'temp/retry_ocr'
            output_dir = 'temp/md'
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)

            # 创建高级PDF处理器实例
            processor = AdvancedPDFProcessor(output_dir=output_dir, temp_dir=temp_dir)

            # 尝试使用不同的方法重新转换
            methods = ['mineru', 'pymupdf', 'pdfplumber']
            for method in methods:
                try:
                    self.logger.info(f'尝试使用 {method} 方法重新转换PDF')
                    output_file = processor.process_pdf(
                        self.bid_file_path,
                        method=method,
                        enable_formula=True,
                        enable_table=True,
                        language='ch',
                    )

                    # 检查转换后的文件是否存在且非空
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        self.logger.info(
                            f'使用 {method} 方法重新转换PDF成功: {output_file}'
                        )
                        return {
                            'status': 'success',
                            'message': '重新转换PDF成功',
                            'output_file': output_file,
                        }
                    else:
                        self.logger.warning(
                            f'使用 {method} 方法转换后的文件为空或不存在'
                        )
                except Exception as e:
                    self.logger.warning(f'使用 {method} 方法转换PDF时出错: {e}')
                    continue

            # 如果所有方法都失败了
            self.logger.error(f'所有重新转换方法都失败了: {self.bid_file_path}')
            return {'status': 'error', 'message': '所有重新转换方法都失败了'}

        except Exception as e:
            self.logger.error(f'重新转换PDF时发生意外错误: {e}')
            return {
                'status': 'error',
                'message': f'重新转换PDF时发生意外错误: {str(e)}',
            }

    def analyze(self):
        """
        分析投标文件的公共接口方法
        """
        return self.analyze_bidding_document()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='智能投标分析器')
    parser.add_argument('tender_file_path', help='招标文件路径')
    parser.add_argument('bid_file_path', help='投标文件路径')
    parser.add_argument('--db_session', help='数据库会话对象')
    parser.add_argument('--bid_document_id', help='投标文件ID')
    parser.add_argument('--project_id', help='项目ID')
    parser.add_argument('--extracted_text', help='预提取的文本内容')

    args = parser.parse_args()

    analyzer = IntelligentBidAnalyzer(
        tender_file_path=args.tender_file_path,
        bid_file_path=args.bid_file_path,
        db_session=args.db_session,
        bid_document_id=args.bid_document_id,
        project_id=args.project_id,
        extracted_text=args.extracted_text,
    )

    result = analyzer.analyze()
    print(result)
