#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投标文件预处理器
使用AI模型对投标文件进行详细分析，提炼出用于后续分析的标准文本
"""

import os
import logging
import requests
import json
from typing import List, Dict, Any, Optional
from modules.local_ai_analyzer import LocalAIAnalyzer

logger = logging.getLogger(__name__)


class BidDocumentPreprocessor:
    """投标文件预处理器"""

    def __init__(self, ai_analyzer: Optional[LocalAIAnalyzer] = None):
        """
        初始化预处理器

        Args:
            ai_analyzer: AI分析器实例，如果为None则创建新的
        """
        self.ai_analyzer = ai_analyzer or LocalAIAnalyzer()
        self.logger = logger

        # 配置embedding和reranker模型
        self.embedding_model = 'qwen3-embedding:latest'
        self.reranker_model = 'dengcao/Qwen3-Reranker-8B:Q5_K_M'
        self.ollama_host = 'http://localhost:11434'

        # 添加缓存机制
        self._cache = {}
        self._cache_timeout = 3600  # 1小时缓存过期

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        获取文本的embedding向量

        Args:
            texts: 文本列表

        Returns:
            embedding向量列表
        """
        try:
            url = f'{self.ollama_host}/api/embeddings'
            payload = {
                'model': self.embedding_model,
                'prompt': texts[0] if texts else '',  # Ollama API只接受单个文本
            }

            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            if 'embedding' in result:
                embeddings = [result['embedding']]
            else:
                embeddings = []

            self.logger.info(f'成功获取 {len(embeddings)} 个embedding向量')
            return embeddings

        except Exception as e:
            self.logger.error(f'获取embedding时出错: {e}')
            return []

    def _rerank_documents(
        self, query: str, documents: List[str], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        使用AI模型对文档进行重排序

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前k个最相关的文档

        Returns:
            重排序后的文档列表，包含分数
        """
        try:
            # 构建重排序prompt
            documents_text = '\n'.join(
                [f'{i + 1}. {doc}' for i, doc in enumerate(documents)]
            )

            prompt = f"""对以下文档按相关性排序，只返回JSON格式：

查询：{query}
文档：{documents_text}

返回格式：{{"results":[{{"index":0,"relevance_score":0.9}}]}}"""

            # 使用AI分析器进行重排序
            response = self.ai_analyzer.analyze_text(prompt)

            # 解析AI响应
            import json

            try:
                result = json.loads(response)
                reranked_docs = []

                for item in result.get('results', []):
                    index = item.get('index', 0)
                    score = item.get('relevance_score', 0.5)
                    if 0 <= index < len(documents):
                        reranked_docs.append(
                            {
                                'text': documents[index],
                                'score': float(score),
                                'index': index,
                            }
                        )

                # 按分数排序
                reranked_docs.sort(key=lambda x: x['score'], reverse=True)

                self.logger.info(f'成功重排序 {len(reranked_docs)} 个文档')
                return reranked_docs[:top_k]

            except json.JSONDecodeError:
                self.logger.warning('AI响应不是有效的JSON格式，使用简单排序')
                # 简单的关键词匹配排序
                return self._simple_keyword_ranking(query, documents, top_k)

        except Exception as e:
            self.logger.error(f'重排序文档时出错: {e}')
            # 如果重排序失败，返回原始文档
            return [
                {'text': doc, 'score': 1.0, 'index': i}
                for i, doc in enumerate(documents[:top_k])
            ]

    def _simple_keyword_ranking(
        self, query: str, documents: List[str], top_k: int
    ) -> List[Dict[str, Any]]:
        """简单的关键词匹配排序"""
        query_words = set(query.lower().split())
        scored_docs = []

        for i, doc in enumerate(documents):
            doc_words = set(doc.lower().split())
            # 计算词汇重叠度
            overlap = len(query_words.intersection(doc_words))
            score = overlap / len(query_words) if query_words else 0
            scored_docs.append({'text': doc, 'score': score, 'index': i})

        # 按分数排序
        scored_docs.sort(key=lambda x: x['score'], reverse=True)
        return scored_docs[:top_k]

    def preprocess_bid_document(
        self, bid_file_path: str, scoring_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        预处理投标文件，提炼出标准化的分析文本

        Args:
            bid_file_path: 投标文件路径
            scoring_rules: 评分规则列表

        Returns:
            预处理结果字典
        """
        try:
            # 检查缓存
            cache_key = f'{bid_file_path}_{hash(str(scoring_rules))}'
            if cache_key in self._cache:
                cached_result, timestamp = self._cache[cache_key]
                import time

                if time.time() - timestamp < self._cache_timeout:
                    self.logger.info(f'使用缓存的预处理结果: {bid_file_path}')
                    return cached_result

            self.logger.info(f'开始预处理投标文件: {bid_file_path}')

            # 1. 加载投标文件内容
            bid_content = self._load_bid_content(bid_file_path)
            if not bid_content:
                self.logger.error(f'无法加载投标文件内容: {bid_file_path}')
                return {}

            # 2. 提取关键信息
            key_info = self._extract_key_information(bid_content, scoring_rules)

            # 3. 生成标准化分析文本
            standardized_text = self._generate_standardized_text(
                key_info, scoring_rules
            )

            # 4. 保存预处理结果
            result = {
                'original_file_path': bid_file_path,
                'key_information': key_info,
                'standardized_text': standardized_text,
                'processing_status': 'completed',
            }

            # 5. 保存到缓存
            import time

            self._cache[cache_key] = (result, time.time())

            self.logger.info(f'投标文件预处理完成: {bid_file_path}')
            return result

        except Exception as e:
            self.logger.error(f'预处理投标文件时出错: {e}')
            import traceback

            self.logger.error(traceback.format_exc())
            return {'processing_status': 'error', 'error': str(e)}

    def _load_bid_content(self, file_path: str) -> str:
        """加载投标文件内容"""
        try:
            # 优先尝试从MD文件加载
            md_file_path = self._get_md_file_path(file_path)
            if md_file_path and os.path.exists(md_file_path):
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.logger.info(f'从MD文件加载内容: {md_file_path}')
                return content

            # 根据项目设计，所有分析都应该基于OCR处理后的MD文件
            # 如果MD文件不存在，不应该直接从PDF加载，而应该报错
            self.logger.error(f'找不到对应的MD文件，无法加载内容: {md_file_path}')
            return ''

        except Exception as e:
            self.logger.error(f'加载投标文件内容时出错: {e}')
            return ''

    def _get_md_file_path(self, file_path: str) -> str:
        """获取对应的MD文件路径"""
        if file_path.endswith('.pdf'):
            # 将PDF路径转换为MD路径
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            return os.path.join('output', f'{base_name}.md')
        return file_path

    def _extract_key_information(
        self, content: str, scoring_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用embedding和reranker提取关键信息"""
        try:
            # 1. 将投标文件内容分块
            content_chunks = self._split_content_into_chunks(content, chunk_size=1000)
            self.logger.info(f'将投标文件分为 {len(content_chunks)} 个块')

            # 2. 构建查询语句
            queries = self._build_queries_from_rules(scoring_rules)

            # 3. 使用reranker为每个查询找到最相关的文档块
            key_information = {}

            for category, query in queries.items():
                try:
                    # 使用简单排序而不是reranker，提高速度
                    relevant_chunks = self._simple_keyword_ranking(
                        query, content_chunks, top_k=3
                    )

                    # 合并相关文档块
                    relevant_content = ' '.join(
                        [chunk['text'] for chunk in relevant_chunks]
                    )

                    # 使用AI进一步提炼信息
                    refined_info = self._refine_information_with_ai(
                        category, query, relevant_content
                    )
                    key_information[category] = refined_info

                except Exception as e:
                    self.logger.error(f'处理类别 {category} 时出错: {e}')
                    key_information[category] = '提取失败'

            self.logger.info('成功提取关键信息')
            return key_information

        except Exception as e:
            self.logger.error(f'提取关键信息时出错: {e}')
            return {
                '企业资质信息': '提取失败',
                '技术能力信息': '提取失败',
                '项目业绩信息': '提取失败',
                '商务信息': '提取失败',
                '其他重要信息': '提取失败',
            }

    def _split_content_into_chunks(
        self, content: str, chunk_size: int = 1000
    ) -> List[str]:
        """将内容分割成块"""
        chunks = []
        for i in range(0, len(content), chunk_size):
            chunk = content[i : i + chunk_size]
            if chunk.strip():  # 只保留非空块
                chunks.append(chunk.strip())
        return chunks

    def _build_queries_from_rules(
        self, scoring_rules: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """根据评分规则构建查询语句"""
        queries = {
            '企业资质信息': '营业执照 认证证书 质量管理体系 环境管理体系 职业健康管理体系 资质证书 许可证',
            '技术能力信息': '技术方案 技术团队 技术设备 技术创新 技术能力 技术实力 技术优势',
            '项目业绩信息': '项目业绩 同类项目 项目经验 项目案例 业绩证明 项目规模 项目成果',
            '商务信息': '投标价格 报价 价格 付款方式 交货期 质保期 商务条件 合同条款',
            '其他重要信息': '投标文件 完整性 承诺 风险控制 质量保证 服务承诺 特殊要求',
        }
        return queries

    def _refine_information_with_ai(
        self, category: str, query: str, content: str
    ) -> str:
        """使用AI进一步提炼信息"""
        try:
            prompt = f"""你是一个专业的投标文件分析专家，请从以下内容中提取与"{category}"相关的关键信息：

【查询关键词】
{query}

【相关内容】
{content[:2000]}  # 限制内容长度

【提取要求】
1. 提取与{category}直接相关的信息
2. 内容简洁明了，不超过300字
3. 重点突出关键信息
4. 如果找不到相关信息，请返回"未找到相关信息"

请直接返回提取的信息，不要包含任何格式标记："""

            response = self.ai_analyzer.analyze_text(prompt)
            return response.strip()

        except Exception as e:
            self.logger.error(f'提炼信息时出错: {e}')
            return '提炼失败'

    def _build_rules_summary(self, scoring_rules: List[Dict[str, Any]]) -> str:
        """构建评分规则概览"""
        summary_parts = []
        for rule in scoring_rules:
            rule_name = rule.get('Child_Item_Name', '未知规则')
            rule_desc = rule.get('description', '无描述')
            max_score = rule.get('Child_max_score', 0)
            summary_parts.append(f'- {rule_name} (满分: {max_score}分): {rule_desc}')

        return '\n'.join(summary_parts)

    def _generate_standardized_text(
        self, key_info: Dict[str, Any], scoring_rules: List[Dict[str, Any]]
    ) -> str:
        """生成标准化的分析文本"""
        try:
            # 构建生成标准化文本的prompt
            rules_summary = self._build_rules_summary(scoring_rules)

            prompt = f"""你是一个专业的投标文件分析专家，请根据提取的关键信息和评分规则，生成标准化的分析文本：

【评分规则】
{rules_summary}

【提取的关键信息】
{self._format_key_info(key_info)}

【生成要求】
请生成一个简洁、结构化的分析文本，包含以下内容：

1. 企业资质分析：基于提取的资质信息，分析是否符合评分要求
2. 技术能力分析：基于提取的技术信息，分析技术方案的完整性和可行性
3. 项目业绩分析：基于提取的业绩信息，分析项目经验和能力
4. 商务条件分析：基于提取的商务信息，分析商务条件的合理性
5. 综合评估：基于以上分析，给出综合评估结论

要求：
- 文本简洁明了，每个部分不超过200字
- 重点突出与评分规则相关的信息
- 便于后续AI分析使用
- 不要包含具体的分数，只提供分析内容

请直接返回分析文本，不要包含任何格式标记："""

            # 调用AI分析
            response = self.ai_analyzer.analyze_text(prompt)

            self.logger.info('成功生成标准化分析文本')
            return response

        except Exception as e:
            self.logger.error(f'生成标准化文本时出错: {e}')
            return '生成标准化文本失败'

    def _format_key_info(self, key_info: Dict[str, Any]) -> str:
        """格式化关键信息"""
        formatted_parts = []
        for key, value in key_info.items():
            formatted_parts.append(f'{key}: {value}')
        return '\n'.join(formatted_parts)

    def _generate_personalized_query(
        self, rule_name: str, rule_description: str
    ) -> str:
        """
        根据规则类型生成个性化查询语句

        Args:
            rule_name: 规则名称
            rule_description: 规则描述

        Returns:
            个性化查询语句
        """
        # 根据规则名称和描述生成个性化关键词
        personalized_keywords = []

        # 企业资质相关
        if any(
            keyword in rule_name for keyword in ['企业证书', '认证体系', '资质', '证书']
        ):
            personalized_keywords.extend(
                [
                    'ISO9001',
                    'ISO14001',
                    'ISO45001',
                    '质量管理体系',
                    '环境管理体系',
                    '职业健康管理体系',
                    '认证证书',
                    '资质证书',
                ]
            )

        # 技术能力相关
        elif any(keyword in rule_name for keyword in ['技术', '能力', '方案', '团队']):
            personalized_keywords.extend(
                ['技术方案', '技术团队', '技术能力', '技术设备', '技术创新', '技术实力']
            )

        # 项目业绩相关
        elif any(keyword in rule_name for keyword in ['业绩', '项目', '经验', '案例']):
            personalized_keywords.extend(
                ['项目业绩', '同类项目', '项目经验', '项目案例', '业绩证明', '项目规模']
            )

        # 商务信息相关
        elif any(
            keyword in rule_name for keyword in ['价格', '报价', '商务', '付款', '交货']
        ):
            personalized_keywords.extend(
                ['投标价格', '报价', '付款方式', '交货期', '质保期', '商务条件']
            )

        # 标书完整性相关
        elif any(keyword in rule_name for keyword in ['完整性', '标书', '文件']):
            personalized_keywords.extend(
                [
                    '投标文件',
                    '完整性',
                    '投标函',
                    '法人身份证明',
                    '授权委托书',
                    '保证金证明',
                ]
            )

        # 默认关键词
        if not personalized_keywords:
            personalized_keywords = [rule_name, rule_description]

        return ' '.join(personalized_keywords)

    def get_standardized_text_for_rule(
        self, standardized_text: str, rule_name: str, rule_description: str
    ) -> str:
        """
        根据特定规则从标准化文本中提取相关信息，使用个性化分析

        Args:
            standardized_text: 标准化分析文本
            rule_name: 规则名称
            rule_description: 规则描述

        Returns:
            与特定规则相关的文本片段
        """
        try:
            # 1. 根据规则类型生成个性化查询
            query = self._generate_personalized_query(rule_name, rule_description)

            # 2. 将标准化文本分块
            text_chunks = self._split_content_into_chunks(
                standardized_text, chunk_size=500
            )

            # 3. 使用简单排序找到最相关的文本块（提高速度）
            relevant_chunks = self._simple_keyword_ranking(query, text_chunks, top_k=2)

            # 4. 合并相关文本块
            relevant_text = ' '.join([chunk['text'] for chunk in relevant_chunks])

            # 5. 如果找到相关文本，使用AI进一步个性化分析
            if relevant_text and len(relevant_text.strip()) > 50:
                return relevant_text.strip()
            else:
                # 回退到AI分析
                prompt = f"""你是一个专业的文本分析专家，请从以下标准化分析文本中提取与特定评分规则相关的信息：

【评分规则】
规则名称: {rule_name}
规则描述: {rule_description}

【标准化分析文本】
{standardized_text[:1000]}  # 限制长度

【提取要求】
请提取与分析规则直接相关的文本片段，要求：
1. 内容简洁，不超过500字
2. 重点突出与规则要求相关的信息
3. 便于后续评分分析使用
4. 如果找不到相关信息，请返回"未找到相关信息"

请直接返回提取的文本内容："""

                response = self.ai_analyzer.analyze_text(prompt)
                return response.strip()

        except Exception as e:
            self.logger.error(f'提取规则相关文本时出错: {e}')
            return '提取失败'
