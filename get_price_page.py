#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-12 20:01:24
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-12 20:06:36
# 文件相对于项目的路径   : \AI_env2\get_price_page.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import pdfplumber
import json


class BiddingEvaluationFinder:
    def __init__(self, pdf_path, qwen_api_url=None):
        self.pdf_path = pdf_path
        self.qwen_api_url = qwen_api_url
        self.pdf = pdfplumber.open(pdf_path)

    def find_sections_by_text(self):
        """基于文本定位可能的页面"""
        sections = []
        for page_num, page in enumerate(self.pdf.pages, 1):
            text = page.extract_text()
            if '评标办法' in text or '评分标准' in text or '评标标准' in text:
                sections.append(
                    {
                        'page': page_num,
                        'has_tables': len(page.extract_tables()) > 0,
                        'text_length': len(text),
                        'keywords': self._count_keywords(text),
                    }
                )
        return sections

    def _count_keywords(self, text):
        """统计相关关键词"""
        keywords = ['评标', '评分', '标准', '商务', '技术', '价格', '分值']
        return {kw: text.count(kw) for kw in keywords}

    def analyze_with_qwen(self, text_content, table_content=None):
        """使用Qwen进行深度分析"""
        if not self.qwen_api_url:
            return '未配置Qwen API'

        prompt = f"""
        你是一个招标文件分析专家。请分析以下内容是否包含评标办法的详细信息：
        
        文本内容：
        {text_content[:1500]}
        
        """

        if table_content:
            table_text = ''
            for row in table_content[:50]:  # 限制行数
                table_text += (
                    ' | '.join(str(cell) if cell else '' for cell in row) + '\n'
                )
            prompt += f'\n表格内容：\n{table_text}'

        prompt += """
        请回答：
        1. 是否包含评标办法详细信息：是/否
        2. 如果是，主要包含哪些内容
        3. 如果有表格，表格的主要结构是什么
        
        简洁回答。
        """

        try:
            response = requests.post(
                self.qwen_api_url,
                json={'prompt': prompt, 'max_tokens': 600, 'temperature': 0.3},
            )
            return response.json()['text']
        except Exception as e:
            return f'Qwen分析失败: {str(e)}'

    def find_evaluation_tables(self):
        """主方法：找出评标办法表格"""
        results = {
            'text_based_pages': self.find_sections_by_text(),
            'qwen_analyzed_tables': [],
            'recommended_pages': [],
        }

        # 分析每个可能的页面
        for section in results['text_based_pages']:
            page_num = section['page']
            page = self.pdf.pages[page_num - 1]

            text = page.extract_text()
            tables = page.extract_tables()

            # 对包含表格的页面进行详细分析
            if tables:
                for table_index, table in enumerate(tables):
                    if table:
                        analysis = self.analyze_with_qwen(text, table)
                        if '是否包含评标办法详细信息：是' in analysis:
                            results['qwen_analyzed_tables'].append(
                                {
                                    'page': page_num,
                                    'table_index': table_index,
                                    'analysis': analysis,
                                    'table_preview': [
                                        row[:3] for row in table[:5]
                                    ],  # 预览前5行前3列
                                }
                            )
                            if page_num not in results['recommended_pages']:
                                results['recommended_pages'].append(page_num)
            else:
                # 只有文本没有表格的页面
                analysis = self.analyze_with_qwen(text)
                if '是否包含评标办法详细信息：是' in analysis:
                    results['recommended_pages'].append(page_num)

        return results

    def close(self):
        self.pdf.close()


# 使用示例
finder = BiddingEvaluationFinder(
    r'D:\user\PythonProject\AI_env2\uploads\1_tender_招标文件正文.pdf',
    'http://localhost:11434/api/generate',  # 替换为实际的Qwen API地址
)

results = finder.find_evaluation_tables()
print(json.dumps(results, ensure_ascii=False, indent=2))

finder.close()
