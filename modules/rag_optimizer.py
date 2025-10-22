#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG优化器模块
用于优化长文档和大量规则的处理效率
"""

import json
import logging
import os
import re
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import requests

logger = logging.getLogger(__name__)


class DocumentChunker:
    """文档分块器"""

    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, pages: List[str]) -> List[Dict[str, Any]]:
        """
        将文档分块

        Args:
            pages: 文档页面列表

        Returns:
            分块结果列表，每个块包含文本和元数据
        """
        chunks = []
        chunk_id = 0

        # 将所有页面合并为一个文本
        full_text = '\n'.join(pages)

        # 按句子分割文本
        sentences = re.split(r'[。！？\n]+', full_text)
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # 如果当前块加上新句子超过块大小，则保存当前块
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(
                    {
                        'id': chunk_id,
                        'text': chunk_text,
                        'length': len(chunk_text),
                        'start_pos': 0,  # 简化处理，实际应用中需要记录位置
                        'end_pos': 0,
                    }
                )
                chunk_id += 1

                # 保留重叠部分
                overlap_sentences = max(1, self.overlap // 50)  # 估算句子数
                current_chunk = (
                    current_chunk[-overlap_sentences:]
                    if len(current_chunk) > overlap_sentences
                    else []
                )
                current_length = sum(len(s) for s in current_chunk)

            # 添加新句子
            current_chunk.append(sentence)
            current_length += sentence_length

        # 处理最后一个块
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(
                {
                    'id': chunk_id,
                    'text': chunk_text,
                    'length': len(chunk_text),
                    'start_pos': 0,
                    'end_pos': 0,
                }
            )

        logger.info(f'文档分块完成，共生成 {len(chunks)} 个块')
        return chunks


class EmbeddingManager:
    """嵌入管理器"""

    def __init__(
        self,
        embedding_model: str = 'qwen3-embedding:latest',
        host: str = 'http://localhost:11434',
    ):
        self.embedding_model = embedding_model
        self.host = host
        self.embeddings_cache = {}  # 缓存嵌入结果

    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        # 检查缓存
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]

        try:
            # 调用Ollama的嵌入API
            embedding_api_url = f'{self.host}/api/embeddings'
            payload = {'model': self.embedding_model, 'prompt': text}

            response = requests.post(embedding_api_url, json=payload, timeout=300)
            response.raise_for_status()

            result = response.json()
            embedding = result.get('embedding', [])

            # 缓存结果
            self.embeddings_cache[text] = embedding
            return embedding
        except Exception as e:
            logger.error(f'获取嵌入向量时出错: {e}')
            # 返回零向量作为回退
            return [0.0] * 128

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        embeddings = []
        for text in texts:
            embeddings.append(self.get_embedding(text))
        return embeddings


class Reranker:
    """重排序器"""

    def __init__(
        self,
        reranker_model: str = 'dengcao/Qwen3-Reranker-8B:Q5_K_M',
        host: str = 'http://localhost:11434',
    ):
        self.reranker_model = reranker_model
        self.host = host

    def rerank(
        self, query: str, candidates: List[str], top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        对候选文档进行重排序

        Args:
            query: 查询文本
            candidates: 候选文档列表
            top_k: 返回前K个结果

        Returns:
            排序结果列表，包含索引和分数
        """
        try:
            # 调用重排序模型
            generate_api_url = f'{self.host}/api/generate'
            scores = []

            for candidate in candidates:
                prompt = f'Query: {query}\nDocument: {candidate}\nRelevance Score:'
                payload = {
                    'model': self.reranker_model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.0,  # 确定性输出
                        'num_predict': 10,  # 只需要分数
                    },
                }

                response = requests.post(generate_api_url, json=payload, timeout=300)
                response.raise_for_status()

                result = response.json()
                response_text = result.get('response', '').strip()

                # 尝试解析分数
                try:
                    # 提取数字作为分数
                    import re

                    numbers = re.findall(r'\d+\.?\d*', response_text)
                    if numbers:
                        score = float(numbers[0])
                    else:
                        score = 0.0
                except:
                    score = 0.0

                scores.append(score)

            # 排序并返回前K个
            indexed_scores = [(i, score) for i, score in enumerate(scores)]
            indexed_scores.sort(key=lambda x: x[1], reverse=True)
            return indexed_scores[:top_k]
        except Exception as e:
            logger.error(f'重排序时出错: {e}')
            # 回退到按索引返回
            return [
                (i, 1.0 - i / len(candidates))
                for i in range(min(top_k, len(candidates)))
            ]


class RuleGrouper:
    """规则分组器"""

    def __init__(self, embedding_manager: EmbeddingManager):
        self.embedding_manager = embedding_manager

    def group_rules(self, rules: List[Any], max_group_size: int = 5) -> List[List[Any]]:
        """
        将规则分组

        Args:
            rules: 规则列表
            max_group_size: 最大组大小

        Returns:
            分组结果
        """
        if len(rules) <= max_group_size:
            return [rules]

        # 基于规则描述的相似度进行分组
        rule_embeddings = []
        for rule in rules:
            description = f'{rule.Child_Item_Name} {rule.description or ""}'
            embedding = self.embedding_manager.get_embedding(description)
            rule_embeddings.append(embedding)

        # 简单的聚类分组（示例实现）
        groups = []
        current_group = []

        for i, rule in enumerate(rules):
            if len(current_group) >= max_group_size:
                groups.append(current_group)
                current_group = []
            current_group.append(rule)

        if current_group:
            groups.append(current_group)

        logger.info(f'规则分组完成，共生成 {len(groups)} 个组')
        return groups


class RAGOptimizer:
    """RAG优化器主类"""

    def __init__(
        self,
        embedding_model: str = 'qwen3-embedding:latest',
        reranker_model: str = 'dengcao/Qwen3-Reranker-8B:Q5_K_M',
        host: str = 'http://localhost:11434',
        chunk_size: int = 1000,
        overlap: int = 200,
    ):
        self.embedding_manager = EmbeddingManager(embedding_model, host)
        self.reranker = Reranker(reranker_model, host)
        self.chunker = DocumentChunker(chunk_size, overlap)
        self.rule_grouper = RuleGrouper(self.embedding_manager)

        # 缓存
        self.document_chunks = None
        self.chunk_embeddings = None

    def prepare_document(self, pages: List[str]):
        """
        准备文档（分块和向量化）

        Args:
            pages: 文档页面列表
        """
        logger.info('开始准备文档...')
        self.document_chunks = self.chunker.chunk_document(pages)
        chunk_texts = [chunk['text'] for chunk in self.document_chunks]
        self.chunk_embeddings = self.embedding_manager.get_embeddings_batch(chunk_texts)
        logger.info(f'文档准备完成，共 {len(self.document_chunks)} 个块')

    def find_relevant_chunks(self, rule: Any, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        查找与规则相关的文档块

        Args:
            rule: 评分规则
            top_k: 返回前K个相关块

        Returns:
            相关块列表
        """
        if self.document_chunks is None or self.chunk_embeddings is None:
            logger.warning('文档尚未准备，请先调用prepare_document方法')
            return []

        # 构建查询文本
        query_text = f'{rule.Child_Item_Name} {rule.description or ""}'
        query_embedding = self.embedding_manager.get_embedding(query_text)

        # 计算相似度
        similarities = cosine_similarity([query_embedding], self.chunk_embeddings)[0]

        # 获取最相关的块索引
        top_indices = similarities.argsort()[-top_k:][::-1]

        # 使用重排序器优化结果
        candidates = [self.document_chunks[i]['text'] for i in top_indices]
        reranked_indices = self.reranker.rerank(query_text, candidates, top_k)

        # 返回相关块
        relevant_chunks = []
        for rerank_idx, score in reranked_indices:
            original_idx = top_indices[rerank_idx]
            chunk = self.document_chunks[original_idx].copy()
            chunk['relevance_score'] = score
            relevant_chunks.append(chunk)

        return relevant_chunks

    def optimize_context_for_rule(self, rule: Any, pages: List[str]) -> str:
        """
        为规则优化上下文

        Args:
            rule: 评分规则
            pages: 文档页面列表

        Returns:
            优化后的上下文
        """
        # 如果文档尚未准备，则准备文档
        if self.document_chunks is None:
            self.prepare_document(pages)

        # 查找相关块
        relevant_chunks = self.find_relevant_chunks(rule, top_k=3)

        # 组合上下文
        context_parts = []
        for i, chunk in enumerate(relevant_chunks):
            context_parts.append(
                f'--- 相关段落 {i + 1} (相关性: {chunk.get("relevance_score", 0):.3f}) ---'
            )
            context_parts.append(chunk['text'])

        return '\n\n'.join(context_parts)

    def optimize_context_for_rules_group(
        self, rules_group: List[Any], pages: List[str]
    ) -> str:
        """
        为规则组优化上下文

        Args:
            rules_group: 规则组
            pages: 文档页面列表

        Returns:
            优化后的上下文
        """
        # 如果文档尚未准备，则准备文档
        if self.document_chunks is None:
            self.prepare_document(pages)

        # 收集所有相关块
        all_relevant_chunks = []
        for rule in rules_group:
            chunks = self.find_relevant_chunks(rule, top_k=2)
            all_relevant_chunks.extend(chunks)

        # 去重并排序
        unique_chunks = {}
        for chunk in all_relevant_chunks:
            chunk_id = chunk['id']
            if chunk_id not in unique_chunks or chunk.get(
                'relevance_score', 0
            ) > unique_chunks[chunk_id].get('relevance_score', 0):
                unique_chunks[chunk_id] = chunk

        # 按相关性排序
        sorted_chunks = sorted(
            unique_chunks.values(),
            key=lambda x: x.get('relevance_score', 0),
            reverse=True,
        )

        # 组合上下文（限制数量）
        context_parts = []
        for i, chunk in enumerate(sorted_chunks[:5]):  # 最多5个块
            context_parts.append(
                f'--- 相关段落 {i + 1} (相关性: {chunk.get("relevance_score", 0):.3f}) ---'
            )
            context_parts.append(chunk['text'])

        return '\n\n'.join(context_parts)


# 使用示例
if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 创建RAG优化器
    rag_optimizer = RAGOptimizer()

    # 示例文档页面
    pages = [
        '公司简介：我们是一家专业的智能装备制造商...',
        '技术方案：本项目采用先进的技术方案...',
        '质量保证：我们提供完善的质量保证体系...',
        # ... 更多页面
    ]

    # 示例规则
    class MockRule:
        def __init__(self, name, description):
            self.Child_Item_Name = name
            self.description = description

    rules = [
        MockRule('技术方案完整性', '技术方案应包含详细的设计说明'),
        MockRule('质量保证体系', '投标人应提供完善的质量保证体系'),
    ]

    # 准备文档
    rag_optimizer.prepare_document(pages)

    # 为单个规则优化上下文
    context = rag_optimizer.optimize_context_for_rule(rules[0], pages)
    print('优化后的上下文:')
    print(context)
