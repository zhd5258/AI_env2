import re
import json
import logging
from typing import List


class IntelligentScoringExtractor:
    def __init__(self, pages: List[str]):
        self.pages = pages
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def extract_scoring_rules(self):
        rules = []

        # 更灵活的模式来查找评分表信息
        # 允许更多的变体和格式
        table_header_pattern = re.compile(
            r'([一二三四五六七八九十][\s\.、]*(评分|评审|打分)|'  # 匹配"三、评分"这样的格式
            r'评分[表细]则|'  # 匹配"评分细则"
            r'(评分项|评审因素|评分内容|项目|评分要素|评分指标)\s*'
            r'(分值|满分|分数|得分|评分)?)\s*'
            r'(评审标准|评分标准|评分方法|说明)?',
            re.DOTALL | re.MULTILINE,
        )

        start_page_index = -1
        header_match = None

        self.logger.info(f'开始处理文档，共 {len(self.pages)} 页')

        # First, find the page where the scoring table header appears
        for i, page_text in enumerate(self.pages):
            # Replace newlines with spaces for multi-line header matching
            normalized_text = page_text.replace('\n', ' ')
            self.logger.debug(f'正在检查第 {i + 1} 页的评分表标题')
            header_match = table_header_pattern.search(normalized_text)
            if header_match:
                start_page_index = i
                self.logger.info(
                    f'在第 {i + 1} 页找到评分表标题: {header_match.group(0)}'
                )
                break

        if start_page_index == -1:
            self.logger.warning('未找到评分表标题，将尝试其他提取方法')
            # 尝试寻找包含"分"字的段落
            for i, page_text in enumerate(self.pages):
                if '分' in page_text and re.search(r'\d+\s*分', page_text):
                    self.logger.info(f'在第 {i + 1} 页找到含有分值的内容')
                    start_page_index = i
                    break

            if start_page_index == -1:
                self.logger.error('未能找到任何评分相关内容')
                return rules  # No scoring table found

        # The table starts on the found page, after the header
        # We'll process this and all subsequent pages
        # We use the original page_text to preserve line breaks for row parsing
        relevant_text = self.pages[start_page_index][header_match.end() :]
        if start_page_index + 1 < len(self.pages):
            relevant_text += '\n'.join(self.pages[start_page_index + 1 :])

        # Split into lines and process
        lines = relevant_text.split('\n')

        current_category = '未知'
        category_pattern = re.compile(
            r'^[一二三四五六七八九十\d]+[、.\s]*(.*?)(评分|标准|细则|得分|分值).*$'
        )

        accumulated_text = ''

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 尝试识别类别
            cat_match = category_pattern.match(line)
            if cat_match:
                current_category = cat_match.group(1).strip() or current_category
                accumulated_text = ''  # 重置累积文本
                continue

            # 累积文本以处理跨行的评分规则
            accumulated_text += line + ' '

            # 尝试从累积的文本中提取评分规则
            score_matches = re.finditer(
                r'([^。；，\n]*?)(\d+(?:\.\d+)?)\s*分(?:[^。；，\n]*?)(?:[。；，]|$)',
                accumulated_text,
            )

            for match in score_matches:
                criteria_text, score = match.groups()

                # 清理评分项名称
                criteria_name = re.sub(r'^\s*\d*[\.)、]?\s*', '', criteria_text).strip()
                if not criteria_name:
                    continue

                # 提取描述（如果有）
                full_match_text = match.group(0)
                description_start = accumulated_text.find(full_match_text) + len(
                    full_match_text
                )
                description = accumulated_text[description_start:].strip()

                # 如果找到分值，添加规则
                rule = {
                    'category': current_category,
                    'criteria_name': criteria_name,
                    'max_score': float(score),
                    'weight': 0,  # 权重计算需要更多上下文
                    'description': description,
                }

                self.logger.info(f'找到评分规则：{criteria_name} ({score}分)')
                rules.append(rule)

                # 清除已处理的文本
                accumulated_text = accumulated_text[description_start:]

        # 验证提取的规则
        if not rules:
            self.logger.error('未能提取到任何评分规则')
            # 记录原始内容的一部分以帮助调试
            sample_text = '\n'.join(self.pages[:2])  # 只记录前两页
            self.logger.debug(
                f'文档前两页内容示例：\n{sample_text[:500]}...'
            )  # 只记录前500个字符
        else:
            total_score = sum(rule['max_score'] for rule in rules)
            self.logger.info(
                f'共提取到 {len(rules)} 条评分规则，总分值: {total_score}分'
            )

        return rules

    def parse_evaluation_criteria(self):
        # This method can be expanded to parse more complex criteria
        return self.extract_scoring_rules()

    def generate_scoring_template(self):
        rules = self.extract_scoring_rules()
        return json.dumps(rules, ensure_ascii=False, indent=2)
