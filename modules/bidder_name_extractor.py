#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
投标人名称提取模块
专门负责从投标文件中提取投标人名称
"""

import re
import logging
import os
import hashlib
from typing import List, Optional
from .pdf_processor import PDFProcessor

# Configure logging
import sys

# 初始化缓存字典
_bidder_name_cache = {}


def setup_logger():
    logger = logging.getLogger(__name__)
    # 检查标准输出是否可用，如果不可用则使用基本配置
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            stream=sys.stdout,
            force=True,
        )
    except (ValueError, AttributeError):
        # 当stdout被重定向或分离时使用基本配置
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                force=True,
            )
        except Exception:
            # 最后的备用方案
            pass
    return logger


logger = setup_logger()


def _filter_bidder_name(bidder_name: str) -> str:
    """
    Filters and cleans the extracted bidder name to remove unwanted parts.
    """
    if not bidder_name:
        return ''

    # Strip leading/trailing whitespace and colons
    bidder_name = bidder_name.strip().lstrip(':：').strip()

    # Remove leading special characters like #, *, etc.
    bidder_name = re.sub(r'^[#*●■◆▲▼※·]+', '', bidder_name).strip()

    # Define stop words/phrases that signal the end of the company name
    stop_phrases = [
        '法定代表',
        '授权代表',
        '单位地址',
        '通信地址',
        '电话',
        '传真',
        '(盖单位章)',
        '（盖单位章）',
        '投标单位',
        '投标人',
        '（盖章）',
        '(盖章)',
        '地址',
        '邮政编码',
        '联系人',
        '手机',
    ]

    for phrase in stop_phrases:
        if phrase in bidder_name:
            bidder_name = bidder_name.split(phrase)[0].strip()

    # Remove any remaining parenthesized or bracketed text
    bidder_name = re.sub(r'[\(（$$.*?[\)）\]]】〕]', '', bidder_name).strip()

    # Remove orphan leading/trailing bracket characters
    bidder_name = bidder_name.strip('()（）[]【】〔〕')

    # Remove stray unmatched single brackets inside
    bidder_name = (
        bidder_name.replace('[', '')
        .replace(']', '')
        .replace('（', '')
        .replace('）', '')
        .replace('(', '')
        .replace(')', '')
    )

    # Final check for common suffixes that are not part of the name
    unwanted_suffixes = ['公司章', '公章', '单位章']
    for suffix in unwanted_suffixes:
        if bidder_name.endswith(suffix):
            bidder_name = bidder_name[: -len(suffix)].strip()

    # Normalize whitespace
    bidder_name = re.sub(r'\s+', ' ', bidder_name).strip()

    return bidder_name


def _looks_garbled_or_incomplete(name: str) -> bool:
    """
    判断名称是否疑似乱码或不完整。
    规则：包含孤立括号/方括号残留、包含明显非汉字噪声比例较高、长度过短等。
    """
    if not name:
        return True
    if len(name) < 6:
        return True
    # 孤立括号或方括号
    if any(
        ch in name for ch in ['[', ']', '(', ')', '（', '）', '【', '】', '〔', '〕']
    ):
        return True
    # 噪声字符比例（非汉字、非字母数字与常用公司字）
    noise = sum(
        1
        for ch in name
        if not re.match(r'[\u4e00-\u9fa5a-zA-Z0-9·．\.（）()有限公司集团股份]+', ch)
    )
    # 如果噪声字符比例超过20%，则认为是乱码
    if noise > len(name) * 0.2:
        return True
    return noise > max(1, len(name) // 6)


def _is_valid_company_name(bidder_name: str) -> bool:
    """
    Checks if a string is a valid company name.
    """
    if not bidder_name or len(bidder_name) <= 5:
        return False
    company_keywords = ['公司', '有限', '股份', '集团', '厂', '院', '所', '社', '中心']
    if not any(keyword in bidder_name for keyword in company_keywords):
        return False
    # Further checks to exclude common false positives
    invalid_keywords = [
        '招标',
        '投标',
        '项目',
        '文件',
        '正本',
        '副本',
        '单位章',
        '法定代表',
        '中车眉山车辆有限公司',  # 明确排除招标方名称
        '#',  # 排除以#开头的奇怪名称
        '*',  # 排除以*开头的奇怪名称
        '●',  # 排除以●开头的奇怪名称
        '■',  # 排除以■开头的奇怪名称
        '◆',  # 排除以◆开头的奇怪名称
        '▲',  # 排除以▲开头的奇怪名称
        '▼',  # 排除以▼开头的奇怪名称
        '※',  # 排除以※开头的奇怪名称
        '·',  # 排除以·开头的奇怪名称
    ]
    if any(keyword in bidder_name for keyword in invalid_keywords):
        return False
    # 检查是否以特殊字符开头
    if bidder_name.startswith(('#', '*', '●', '■', '◆', '▲', '▼', '※', '·')):
        return False
    # 检查是否包含过多的特殊符号
    special_chars = sum(1 for ch in bidder_name if ch in '#*●■◆▲▼※·')
    if special_chars > 2:  # 如果特殊符号超过2个，认为是无效名称
        return False
    return True


def _search_bidder_name_in_special_sections(pages: list[str]) -> str | None:
    """
    在"授权委托书""投标一览表"等关键章节中继续检索公司名称。
    策略：
    - 定位章节锚点页索引；
    - 在该页以及后一页内用更宽松的正则提取公司名；
    - 返回第一个通过过滤与校验的名称。
    """
    if not pages:
        return None

    anchors = [
        '授权委托书',
        '法定代表人授权书',
        '投标一览表',
        '投标报价一览表',
        '开标一览表',
        '投标函',
        '资格审查',
        '制造商名称',
        '法定代表人（单位负责人）身份证明'
    ]
    candidate_indices = []
    for idx, text in enumerate(pages):
        if any(anchor in text for anchor in anchors):
            candidate_indices.append(idx)

    # 扩大检索窗口到命中页、前一页和后一页
    indices = sorted(
        set(
            candidate_indices + 
            [i - 1 for i in candidate_indices if i - 1 >= 0] +
            [i + 1 for i in candidate_indices if i + 1 < len(pages)]
        )
    )
    patterns = [
        r'(?:投标人|投标单位|供应商|单位名称)\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',
        r'(?:投标人|投标单位|供应商|单位名称)[:：\s]*([^\n]+?公司)',
        r'([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?有限公司)',
        r'^\s*([^\n]+?有限公司)\s*$',
        # 法定代表人身份证明抬头
        r'本人(?:[^\n]+?)系(?:[^\n]+?)的法定代表人',
        r'本人(?:[^\n]+?)系([^\n]+?)的法定代表人',
        # 授权委托书中提取
        r'本(?:单位|公司)授权(?:[^\n]+?)为(?:[^\n]+?)的合法代理人',
        r'本(?:单位|公司)授权(?:[^\n]+?)为([^\n]+?)的合法代理人',
        # 投标一览表前一行
        r'(?<=\n)([^\n]+?有限公司)(?=\n.*?投标一览表)',
        r'(?<=\n)([^\n]+?公司)(?=\n.*?投标一览表)',
        # 制造商名称字段（用于回退提取投标方/制造商公司名）
        r'(?:制造商名称|制造厂家|生产厂家)\s*[:：]\s*([^\n]+?公司)',
        r'(?:制造商名称|制造厂家|生产厂家)\s*[:：]\s*([^\n]+?有限公司)',
        # 投标函末尾盖章行
        r'(投标人|投标单位)：\s*([^\s]+?公司)(?:\s*（盖单位章）)?',
    ]

    # 尝试在每个候选页面中查找投标方名称
    for i in indices:
        text = pages[i]
        # 尝试每个模式
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for m in matches:
                # 获取匹配的组，通常是第一个捕获组
                matched_text = m.group(1) if len(m.groups()) >= 1 else m.group(0)
                name = _filter_bidder_name(matched_text)
                if _is_valid_company_name(name) and not _looks_garbled_or_incomplete(
                    name
                ):
                    logger.info(
                        'Found bidder name in special section on page %s: %s',
                        i + 1,
                        name,
                    )
                    return name
    return None


def _extract_bidder_name_by_regex(text_to_search: str) -> str | None:
    """
    Uses regular expressions to extract the bidder name.
    """
    patterns = [
        r'投\s*标\s*人\s*[:：\s]([^\n]+)',
        r'投标(?:人|单位|方)名称\s*[:：\s]([^\n]+)',
        r'供\s*应\s*商\s*名\s*称\s*[:：\s]([^\n]+)',
        r'致\s*[:：\s]([^\n]+?)(?:\s*公司|\s*单位)',
        r'^\s*([^\n]+?公司)\s*$',  # A line that is just a company name
        r'投标人名称\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',  # 更精确的投标人名称匹配
        # 新增更强大的模式来匹配公司名称
        r'(?:投标单位|投标人|供应商|单位名称)\s*[:：]?\s*([^\n]*[有限公司|公司|集团|厂|院|所][^\n]*)',
        r'([^\n]*[有限公司|公司|集团|厂|院|所][^\n]*)\s*(?:法定代表人|授权代表|地址|电话)',
        # 特别处理以特殊字符开头的名称
        r'^\s*[#*●■◆▲▼※·]?\s*([^\n]*[有限公司|公司|集团|厂|院|所][^\n]*)\s*$',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text_to_search, re.MULTILINE)
        for match in matches:
            potential_name = match.group(1).strip()
            logger.info("Regex pattern '%s' matched: '%s'", pattern, potential_name)

            filtered_name = _filter_bidder_name(potential_name)

            if _is_valid_company_name(filtered_name):
                logger.info(f"Valid bidder name found via regex: '{filtered_name}'")
                return filtered_name
            else:
                logger.info(
                    "Filtered name '%s' is not a valid company name.", filtered_name
                )

    return None


def _extract_bidder_name_from_markdown(text_to_search: str) -> str | None:
    """
    从Markdown文本中提取投标人名称。
    """
    # 查找投标人信息相关的标题
    bidder_section_patterns = [
        r'##\s*投标人信息',
        r'##\s*投标单位信息',
        r'##\s*供应商信息',
        r'#\s*投标人信息',
        r'#\s*投标单位信息',
        r'#\s*供应商信息',
    ]

    bidder_section_start = -1
    for pattern in bidder_section_patterns:
        match = re.search(pattern, text_to_search, re.IGNORECASE)
        if match:
            bidder_section_start = match.end()
            break

    if bidder_section_start == -1:
        logger.info('未找到投标人信息章节，尝试在整个文档中查找')
        bidder_section_text = text_to_search
    else:
        # 提取投标人信息章节的内容
        # 查找下一个章节标题或文档结尾
        next_section_match = re.search(
            r'^[#]{1,2}\s', text_to_search[bidder_section_start:], re.MULTILINE
        )
        if next_section_match:
            bidder_section_end = bidder_section_start + next_section_match.start()
            bidder_section_text = text_to_search[
                bidder_section_start:bidder_section_end
            ]
        else:
            bidder_section_text = text_to_search[bidder_section_start:]

    # 在投标人信息章节中查找投标人名称
    patterns = [
        r'投标人名称\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',
        r'投标单位\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',
        r'供应商\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',
        r'单位名称\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, bidder_section_text, re.MULTILINE)
        for match in matches:
            potential_name = match.group(1).strip()
            logger.info("Markdown pattern '%s' matched: '%s'", pattern, potential_name)

            filtered_name = _filter_bidder_name(potential_name)

            if _is_valid_company_name(filtered_name):
                logger.info(f"Valid bidder name found via Markdown: '{filtered_name}'")
                return filtered_name
            else:
                logger.info(
                    "Filtered name '%s' is not a valid company name.", filtered_name
                )

    return None


def _extract_bidder_name_by_ai(text_to_search: str) -> str | None:
    """
    Uses an AI model to extract the bidder name.
    """
    try:
        # 延迟导入，避免循环依赖
        from .local_ai_analyzer import LocalAIAnalyzer
        ai_analyzer = LocalAIAnalyzer()
        prompt = f"""
        请从以下投标文件内容中，仅抽取出完整的投标公司名称。

        要求：
        1.  **精准提取**：只返回公司的全名，例如 "XX市XX科技有限公司"。
        2.  **排除干扰**：不要包含任何其他信息，如 "法定代表人"、"地址"、"电话"、"（盖章）" 等。
        3.  **错误示例**：不要返回 "三江市 0屯吐一八活单位章) 法定代表..." 这样的错误结果。
        4.  **唯一结果**：只返回最终的公司名称，不要任何解释或多余的文字。
        5.  **特别注意**：不要将招标方名称（如"中车眉山车辆有限公司"）误认为是投标方名称。
        6.  **格式要求**：不要返回以特殊符号（如 #, *, ●, ■, ◆, ▲, ▼, ※, ·）开头的名称。
        7.  如果找不到，返回 "未找到"。

        待分析的文本内容：
        ---
        {text_to_search[:2000]}
        ---

        投标公司名称是：
        """
        response = ai_analyzer.analyze_text(prompt)

        if response and '未找到' not in response:
            # 清理AI响应，只保留第一行
            potential_name = response.strip().split('\n')[0].strip()
            logger.info("AI extracted: '%s'", potential_name)

            # 对AI提取的结果也进行过滤和验证
            filtered_name = _filter_bidder_name(potential_name)

            if _is_valid_company_name(
                filtered_name
            ) and not _looks_garbled_or_incomplete(filtered_name):
                logger.info(f"Valid bidder name found via AI: '{filtered_name}'")
                return filtered_name
            else:
                logger.info(
                    "AI filtered name '%s' is not a valid company name.", filtered_name
                )

    except Exception as e:
        logger.error(f'Error during AI bidder name extraction: {e}')

    return None


def _get_cache_key(file_path: str) -> str:
    """获取文件的缓存键"""
    try:
        st = os.stat(file_path)
        key = f'{file_path}|{st.st_size}|{int(st.st_mtime)}'
    except Exception:
        # 回退到路径作为键（极端情况下）
        key = file_path
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def _load_from_temp_word(file_path: str) -> str:
    """
    从temp_word目录加载文本

    Args:
        file_path: 原始文件路径

    Returns:
        str: 加载的文本内容
    """
    try:
        # 生成基于文件路径的唯一文件名
        file_key = _get_cache_key(file_path)
        temp_word_filename = f'{file_key}.txt'
        temp_word_dir = 'temp/md'
        temp_word_path = os.path.join(temp_word_dir, temp_word_filename)

        if os.path.exists(temp_word_path):
            with open(temp_word_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
            logger.info('从temp_word目录加载文本: %s', temp_word_path)
            return full_text
        else:
            logger.warning('temp_word目录中未找到文件: %s', temp_word_path)
    except Exception as e:
        logger.warning('从temp_word目录加载文本失败: %s', e)
    return ''


def extract_bidder_name_from_file_after_analysis(file_path: str) -> str | None:
    """
    在分析完成后从文件中提取投标人名称。
    处理流程：先解析PDF，优先正则提取，其次从Markdown文件中提取，若名称疑似乱码或不完整，则在"授权委托书/投标一览表"等章节中继续检索。

    参数：
        file_path: 投标文件的绝对路径

    返回：
        提取到的投标公司全名；若未找到则返回 None
    """
    logger.info(f'在分析完成后提取投标人名称: {file_path}')
    if not file_path:
        return None

    try:
        # 1. 首先尝试从temp_word目录加载已处理的Markdown文本
        # 这些文本是由MinerU处理PDF文件生成的Markdown文件
        text_to_search = _load_from_temp_word(file_path)

        # 如果temp_word目录中没有文件，检查是否是MD文件，并直接读取内容
        if not text_to_search and file_path.lower().endswith('.md'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_to_search = f.read()
                logger.info('直接从MD文件加载文本: %s', file_path)
            except Exception as e:
                logger.warning('直接读取MD文件失败: %s', e)

        # 如果以上方法都失败，则使用PDFProcessor处理
        if not text_to_search:
            # Process PDF to get text content
            pdf_processor = PDFProcessor(file_path)
            pages = pdf_processor.extract_text_per_page()
            if not pages:
                logger.warning('PDF processing yielded no text pages.')
                return None

            # 合并所有页面以提升检索效率
            text_to_search = '\n'.join(pages)

        # 2. Attempt extraction with Regex
        bidder_name = _extract_bidder_name_by_regex(text_to_search)
        if (
            bidder_name
            and _is_valid_company_name(bidder_name)
            and not _looks_garbled_or_incomplete(bidder_name)
        ):
            logger.info(f"Valid bidder name found via regex: '{bidder_name}'")
            return bidder_name

        # 3. 从Markdown文件中提取投标人名称
        logger.info('Regex extraction failed, falling back to Markdown extraction.')
        bidder_name = _extract_bidder_name_from_markdown(text_to_search)
        if (
            bidder_name
            and _is_valid_company_name(bidder_name)
            and not _looks_garbled_or_incomplete(bidder_name)
        ):
            logger.info(f"Valid bidder name found via Markdown: '{bidder_name}'")
            return bidder_name

        # 4. 基于表格的回退提取（整合）：优先从"制造商名称/投标人名称"列获取
        try:
            # 延迟导入，避免循环依赖
            from .table_analyzer import TableAnalyzer

            analyzer = TableAnalyzer(file_path)
            merged = analyzer.extract_and_merge_tables()
            tables = analyzer.convert_to_structured_format(merged)

            # 查找包含"投标人名称"或"制造商名称"的表格列
            for table in tables:
                headers = table.get('headers', [])
                rows = table.get('rows', [])

                # 查找投标人名称或制造商名称列
                name_col_index = None
                for i, header in enumerate(headers):
                    if any(
                        keyword in header
                        for keyword in [
                            '投标人名称',
                            '制造商名称',
                            '制造厂家',
                            '生产厂家',
                        ]
                    ):
                        name_col_index = i
                        break

                if name_col_index is not None:
                    # 从该列提取名称
                    for row in rows:
                        row_values = list(row.values())
                        if len(row_values) > name_col_index:
                            potential_name = row_values[name_col_index]
                            if potential_name:
                                filtered_name = _filter_bidder_name(potential_name)
                                if _is_valid_company_name(
                                    filtered_name
                                ) and not _looks_garbled_or_incomplete(filtered_name):
                                    logger.info(
                                        f"Valid bidder name found via table: '{filtered_name}'"
                                    )
                                    return filtered_name
        except Exception as table_e:
            logger.warning(f'表格提取投标人名称失败: {table_e}')

        # 5. 在特殊章节中搜索（授权委托书等）
        logger.info(
            'Markdown extraction failed, falling back to special section search.'
        )
        # 将文本分割为页面列表以适应_search_bidder_name_in_special_sections函数
        pages = text_to_search.split('\n\n')  # 简单按双换行符分割页面
        bidder_name = _search_bidder_name_in_special_sections(pages)
        if bidder_name:
            return bidder_name

        # 6. 最后的回退方案：使用AI提取（如果需要）
        logger.info('Special section search failed, falling back to AI extraction.')
        bidder_name = _extract_bidder_name_by_ai(text_to_search)
        if (
            bidder_name
            and _is_valid_company_name(bidder_name)
            and not _looks_garbled_or_incomplete(bidder_name)
        ):
            logger.info(f"Valid bidder name found via AI: '{bidder_name}'")
            return bidder_name

    except Exception as e:
        logger.error(f'提取投标人名称时发生错误: {e}', exc_info=True)

    logger.warning('未能从文件中提取到有效的投标人名称')
    return None


def extract_bidder_name_from_file(file_path: str) -> str:
    """
    从文件中提取投标人名称的主函数
    """
    try:
        logger.info(f"开始从文件提取投标人名称: {file_path}")
        
        # 获取缓存键
        cache_key = _get_cache_key(file_path)
        
        # 尝试从缓存获取
        if cache_key in _bidder_name_cache:
            cached_result = _bidder_name_cache[cache_key]
            logger.info(f"从缓存获取投标人名称: {cached_result}")
            return cached_result

        # 确定文件类型并选择合适的处理方法
        if file_path.lower().endswith('.pdf'):
            # 对于PDF文件，使用PDFProcessor处理
            from .pdf_processor import PDFProcessor
            processor = PDFProcessor(file_path)
            pages = processor.extract_text_per_page()
        elif file_path.lower().endswith('.md'):
            # 对于MD文件，直接读取内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            pages = content.split('\n\n---\n\n')
        else:
            # 对于其他文件类型，尝试直接读取
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            pages = [content]

        if not pages:
            logger.warning(f"文件 {file_path} 没有内容")
            # 返回文件名作为备用方案
            filename = os.path.basename(file_path)
            bidder_name = os.path.splitext(filename)[0]
            _bidder_name_cache[cache_key] = bidder_name
            return bidder_name

        # 在特殊章节中搜索投标人名称
        name = _search_bidder_name_in_special_sections(pages)
        if name:
            logger.info(f"在特殊章节中找到投标人名称: {name}")
            _bidder_name_cache[cache_key] = name
            return name

        # 尝试使用正则表达式提取
        combined_text = '\n'.join(pages)
        name = _extract_bidder_name_by_regex(combined_text)
        if name:
            logger.info(f"通过正则表达式找到投标人名称: {name}")
            _bidder_name_cache[cache_key] = name
            return name

        # 尝试从Markdown格式提取
        name = _extract_bidder_name_from_markdown(combined_text)
        if name:
            logger.info(f"从Markdown格式找到投标人名称: {name}")
            _bidder_name_cache[cache_key] = name
            return name

        # 最后尝试使用AI提取
        name = _extract_bidder_name_by_ai(combined_text)
        if name:
            logger.info(f"通过AI找到投标人名称: {name}")
            _bidder_name_cache[cache_key] = name
            return name

        # 如果所有方法都失败，返回文件名作为备用方案
        filename = os.path.basename(file_path)
        bidder_name = os.path.splitext(filename)[0]
        logger.warning(f"无法从文件内容提取投标人名称，使用文件名作为备用: {bidder_name}")
        _bidder_name_cache[cache_key] = bidder_name
        return bidder_name

    except Exception as e:
        logger.error(f"从文件 {file_path} 提取投标人名称时出错: {e}", exc_info=True)
        # 出错时返回文件名作为备用方案
        try:
            filename = os.path.basename(file_path)
            bidder_name = os.path.splitext(filename)[0]
            logger.warning(f"提取出错，使用文件名作为备用: {bidder_name}")
            return bidder_name
        except:
            return "未知投标方"
