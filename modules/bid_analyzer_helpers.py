"""
投标分析辅助模块
包含投标分析相关的辅助函数
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from modules.database import BidDocument, AnalysisResult


class BidAnalyzerHelpers:
    """投标分析辅助类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _send_progress_update(
        self, completed, total, current_rule, partial_results=None
    ):
        """移除HTTP进度更新，改用轮询方式"""
        # 不再发送HTTP请求，前端将通过轮询获取进度
        pass

    def _update_progress(self, completed, total, current_rule, partial_results=None):
        """更新分析进度

        Args:
            completed (int): 已完成的规则数量
            total (int): 总规则数量
            current_rule (str): 当前正在分析的规则名称
            partial_results (list): 部分分析结果，用于动态展示
        """
        if hasattr(self, 'db') and hasattr(self, 'bid_document_id') and self.db and self.bid_document_id:
            try:
                bid_doc = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                if bid_doc:
                    # 确保总规则数正确设置
                    if total > 0:
                        bid_doc.progress_total_rules = total
                    # 更新已完成规则数
                    bid_doc.progress_completed_rules = completed
                    
                    # 使用更新后的投标人名称（如果已提取）
                    bidder_name_to_use = self.bidder_name if hasattr(self, 'bidder_name') and self.bidder_name != '未知投标方' else bid_doc.bidder_name
                    progress_info = f"{bidder_name_to_use} - {current_rule}" if current_rule else bidder_name_to_use
                    
                    # 限制规则名称长度，避免前端显示问题
                    bid_doc.progress_current_rule = (
                        progress_info[:100] if progress_info else None
                    )
                    # 同时更新详细进度信息
                    bid_doc.detailed_progress_info = progress_info

                    # 如果有部分结果，也保存到数据库中供前端展示
                    if partial_results is not None:
                        # 只保存前5个结果以避免数据过大
                        bid_doc.partial_analysis_results = json.dumps(
                            partial_results[:5], ensure_ascii=False
                        )

                    # 每次都提交进度更新，确保前端能及时获取到进度变化
                    self.db.commit()
                    logging.info(f'进度更新: {completed}/{total} - {progress_info}')

            except Exception as e:
                logging.error(f'更新进度时出错: {e}')
                if hasattr(self, 'db'):
                    self.db.rollback()

    def _flatten_rules(self, rules):
        """将树状规则列表扁平化，用于进度计算"""
        flat_list = []
        for rule in rules:
            # 只对没有子节点的规则（叶子节点）进行计数
            if not rule.get('children'):
                flat_list.append(rule)
            else:
                flat_list.extend(self._flatten_rules(rule['children']))
        return flat_list

    def _analyze_rules_recursively(self, rules, bid_pages, accumulated_results):
        """递归分析评分规则"""
        analyzed_results = []

        for rule in rules:
            # 检查是否为否决项规则
            if rule.get('is_veto', False):
                # 否决项规则不参与评分，但需要记录
                analyzed_rule = {
                    'criteria_name': rule['criteria_name'],
                    'max_score': 0,
                    'score': 0,
                    'reason': '否决项规则，需人工核查是否违反',
                    'children': [],
                    'is_veto': True,
                }
                analyzed_results.append(analyzed_rule)
                accumulated_results.append(analyzed_rule)
                continue

            # 检查是否存在子规则
            if rule.get('children'):
                # 如果是父节点，则递归分析子节点
                analyzed_children = self._analyze_rules_recursively(
                    rule['children'], bid_pages, accumulated_results
                )

                # 父节点的分数是子节点分数之和
                parent_score = sum(child.get('score', 0) for child in analyzed_children)

                analyzed_rule = {
                    'criteria_name': rule['criteria_name'],
                    'max_score': rule['max_score'],
                    'score': parent_score,
                    'reason': '分数由子项汇总得出。',
                    'children': analyzed_children,
                }

                # 将父节点结果添加到累积结果中
                accumulated_results.append(analyzed_rule)
            else:
                # 如果是叶子节点，进行AI分析
                if hasattr(self, 'progress_counter'):
                    self.progress_counter += 1
                else:
                    self.progress_counter = 1
                    
                current_rule_name = f'正在分析规则 {self.progress_counter}/{getattr(self, "total_rules_to_analyze", 0)}: {rule["criteria_name"]}'
                detailed_progress_info = f'[{getattr(self, "bidder_name", "未知投标方")}] {current_rule_name}'
                # 此处可以优化，收集一些结果后再更新进度

                # 清理规则名称中的特殊字符，避免日志编码问题
                clean_rule_name = (
                    rule['criteria_name'].replace('☑', '[已选]').replace('□', '[未选]')
                )
                logging.info(
                    f'正在为投标人 {getattr(self, "bidder_name", "未知投标方")} 分析规则: {clean_rule_name}'
                )

                # 检查是否是价格分项，如果是则进行特殊处理
                if rule.get('is_price_criteria', False):
                    # 价格分需要等所有投标方分析完成后才能计算
                    # 这里只提取价格信息，不进行评分
                    analyzed_rule = self._handle_price_criteria(rule, bid_pages)
                else:
                    # 其他评分项正常进行AI分析
                    relevant_context = self._find_relevant_context(rule, bid_pages)
                    prompt = self._create_prompt(rule, relevant_context)
                    ai_response = self.ai_analyzer.analyze_text(prompt)

                    if 'Error:' in ai_response:
                        score, reason = 0, f'AI分析失败: {ai_response}'
                    else:
                        score, reason = self._parse_ai_score_response(
                            ai_response, rule['max_score']
                        )

                    analyzed_rule = {
                        'criteria_name': rule['criteria_name'],
                        'max_score': rule['max_score'],
                        'score': score,
                        'reason': reason,
                    }

                accumulated_results.append(analyzed_rule)

                # 每分析一个规则就更新进度，确保前端能及时看到进度变化
                self._update_progress(
                    self.progress_counter,
                    getattr(self, "total_rules_to_analyze", 0),
                    detailed_progress_info,
                    accumulated_results,
                )

            analyzed_results.append(analyzed_rule)

        return analyzed_results

    def _is_price_criteria(self, rule):
        """检查是否是价格分项"""
        criteria_name = rule.get('criteria_name', '').lower()
        return any(
            keyword in criteria_name
            for keyword in ['价格', 'price', '报价', '投标报价']
        )

    def _handle_price_criteria(self, rule, bid_pages):
        """处理价格分项，只提取价格信息，不进行评分"""
        # 从投标文件中提取价格信息
        prices = self.price_manager.extract_prices_from_content(bid_pages)
        best_price = self.price_manager.select_best_price(prices, bid_pages)

        # 创建价格分项结果，分数为0，等待后续综合计算
        analyzed_rule = {
            'criteria_name': rule['criteria_name'],
            'max_score': rule['max_score'],
            'score': 0,  # 初始分数为0，等待综合计算
            'reason': f'价格分需要等所有投标方分析完成后综合计算。已提取报价: {best_price}',
            'extracted_price': best_price,  # 保存提取的价格信息
            'is_price_criteria': True,  # 标记为价格分项
        }

        return analyzed_rule

    def _find_relevant_context(self, rule, pages, context_window=2):
        keywords = set(
            re.split(r'\s|，|。', rule['criteria_name'] + ' ' + rule['description'])
        )
        keywords = {k for k in keywords if k and len(k) > 1}  # Basic filtering

        relevant_pages_indices = set()
        for i, page_text in enumerate(pages):
            if any(keyword.lower() in page_text.lower() for keyword in keywords):
                for j in range(i, min(i + context_window + 1, len(pages))):
                    relevant_pages_indices.add(j)

        if not relevant_pages_indices:
            # If no keywords found, fall back to the first few pages
            return '\n'.join(pages[:3])

        sorted_indices = sorted(list(relevant_pages_indices))

        # Group consecutive pages
        grouped_pages = []
        if not sorted_indices:
            return ''

        start = sorted_indices[0]
        end = sorted_indices[0]
        for i in range(1, len(sorted_indices)):
            if sorted_indices[i] == end + 1:
                end = sorted_indices[i]
            else:
                grouped_pages.append((start, end))
                start = end = sorted_indices[i]
        grouped_pages.append((start, end))

        # Build context string with separators
        context_parts = []
        for start, end in grouped_pages:
            context_parts.append(
                f'--- Pages {start + 1}-{end + 1} ---\n'
                + '\n'.join(pages[start : end + 1])
            )

        return '\n\n'.join(context_parts)

    def _create_prompt(self, rule, context_text):
        # Limit context size to avoid overly long prompts
        max_context_len = 8000
        if len(context_text) > max_context_len:
            context_text = context_text[:max_context_len] + '\n... (content truncated)'

        prompt = f"""
        **Role:** Professional Bid Evaluator
        **Task:** Evaluate a bid document based on a specific scoring criterion.

        **Scoring Criterion:**
        - **Name:** {rule['criteria_name']}
        - **Description:** {rule['description']}
        - **Max Score:** {rule['max_score']}

        **Relevant Bid Document Content:**
        ---
        {context_text}
        ---

        **Instructions:**
        1. Carefully review the provided content from the bid document.
        2. Assess how well the bid meets the scoring criterion based *only* on this content.
        3. Provide a score between 0 and {rule['max_score']}.
        4. Justify your score with a clear and concise reason, referencing the provided text.

        **IMPORTANT:** You must respond with ONLY a valid JSON object. Do not include any thinking process, explanations, or additional text outside the JSON.

        **Required Output Format:**
        {{
          "score": <your_score>,
          "reason": "<your_reason>"
        }}
        """
        return prompt

    def _parse_ai_score_response(self, response, max_score):
        try:
            # 处理包含思考过程的响应
            clean_response = response.strip()

            # 移除思考标签
            if '思考过程' in clean_response and '最终答案' in clean_response:
                # 提取最终答案部分
                final_answer_start = clean_response.find('最终答案')
                if final_answer_start != -1:
                    clean_response = clean_response[final_answer_start:]

            # 移除代码块标记
            clean_response = (
                clean_response.replace('```json', '').replace('```', '').strip()
            )

            # 尝试解析JSON
            result = json.loads(clean_response)
            score = result.get('score', 0)
            reason = result.get('reason', 'No reason provided.')

            if not isinstance(score, (int, float)):
                score = 0
            score = max(0, min(float(score), float(max_score)))

            return score, reason
        except (json.JSONDecodeError, TypeError):
            # 如果JSON解析失败，尝试从响应中提取数字
            # 寻找可能的分数值
            score_patterns = [
                r'"score":\s*(\d+(?:\.\d+)?)',  # JSON格式的score
                r'score["\']?\s*[:=]\s*(\d+(?:\.\d+)?)',  # 其他格式的score
                r'(\d+(?:\.\d+)?)\s*分',  # 中文格式
                r'(\d+(?:\.\d+)?)',  # 任何数字
            ]

            for pattern in score_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    score = float(match.group(1))
                    score = max(0, min(score, max_score))
                    return (
                        score,
                        f'从AI响应中提取到分数: {score}。原始响应: {response[:200]}...',
                    )

            # 如果无法提取分数，返回默认值
            return (
                0,
                f'无法从AI响应中提取有效分数。响应内容: {response[:200]}...',
            )

    def _save_failed_pages_info(self, bid_processor):
        """保存PDF处理失败页面信息到数据库"""
        if hasattr(self, 'db') and hasattr(self, 'bid_document_id') and self.db and self.bid_document_id:
            try:
                failed_pages_info = bid_processor.get_failed_pages_info()
                if failed_pages_info:
                    bid_doc = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        bid_doc.failed_pages_info = json.dumps(
                            failed_pages_info, ensure_ascii=False
                        )
                        self.db.commit()
                        logging.info(
                            f'已记录 {len(failed_pages_info)} 个PDF处理失败页面到数据库'
                        )
            except Exception as e:
                logging.error(f'保存PDF处理失败页面信息到数据库时出错: {e}')

    def _save_extracted_price(self, best_price):
        """将提取的价格保存到数据库"""
        if hasattr(self, 'db') and hasattr(self, 'bid_document_id') and self.db and self.bid_document_id:
            try:
                # 查找与此投标文档关联的分析结果记录
                analysis_record = self.db.query(AnalysisResult).filter(
                    AnalysisResult.bid_document_id == self.bid_document_id
                ).first()
                if analysis_record:
                    analysis_record.extracted_price = best_price
                    self.db.commit()
                    logging.info(f"成功将提取的价格 {best_price} 保存到数据库")
            except Exception as e:
                logging.error(f"保存提取的价格到数据库时出错: {e}")
                if hasattr(self, 'db'):
                    self.db.rollback()