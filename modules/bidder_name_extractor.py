import re
import logging
from .local_ai_analyzer import LocalAIAnalyzer
from .pdf_processor import PDFProcessor

# Configure logging
import sys


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
    ]
    if any(keyword in bidder_name for keyword in invalid_keywords):
        return False
    return True


def _filter_bidder_name(bidder_name: str) -> str:
    """
    Filters and cleans the extracted bidder name to remove unwanted parts.
    """
    if not bidder_name:
        return ''

    # Strip leading/trailing whitespace and colons
    bidder_name = bidder_name.strip().lstrip(':：').strip()

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
        '投标函',
        '资格审查',
    ]
    candidate_indices = []
    for idx, text in enumerate(pages):
        if any(anchor in text for anchor in anchors):
            candidate_indices.append(idx)

    # 扩大检索窗口到命中页以及后一页
    indices = sorted(
        set(
            candidate_indices + [i + 1 for i in candidate_indices if i + 1 < len(pages)]
        )
    )
    patterns = [
        r'(?:投标人|投标单位|供应商|单位名称)\s*[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?公司)',
        r'(?:投标人|投标单位|供应商|单位名称)[:：\s]*([^\n]+?公司)',
        r'([\u4e00-\u9fa5a-zA-Z0-9（）()·．\.]+?有限公司)',
        r'^\s*([^\n]+?有限公司)\s*$',
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


def _extract_bidder_name_by_ai(text_to_search: str) -> str | None:
    """
    Uses an AI model to extract the bidder name.
    """
    try:
        ai_analyzer = LocalAIAnalyzer()
        prompt = f"""
        请从以下投标文件内容中，仅抽取出完整的投标公司名称。

        要求：
        1.  **精准提取**：只返回公司的全名，例如 "XX市XX科技有限公司"。
        2.  **排除干扰**：不要包含任何其他信息，如 "法定代表人"、"地址"、"电话"、"（盖章）" 等。
        3.  **错误示例**：不要返回 "三江市 0屯吐一八活单位章) 法定代表..." 这样的错误结果。
        4.  **唯一结果**：只返回最终的公司名称，不要任何解释或多余的文字。
        5.  **特别注意**：不要将招标方名称（如"中车眉山车辆有限公司"）误认为是投标方名称。
        6.  如果找不到，返回 "未找到"。

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

            filtered_name = _filter_bidder_name(potential_name)

            if _is_valid_company_name(filtered_name) and not _looks_garbled_or_incomplete(filtered_name):
                logger.info(f"Valid bidder name found via AI: '{filtered_name}'")
                return filtered_name
            else:
                logger.info(
                    "AI filtered name '%s' is not a valid company name.", filtered_name
                )

    except Exception as e:
        logger.error(f'Error during AI bidder name extraction: {e}')

    return None


def extract_bidder_name_from_file(file_path: str) -> str | None:
    """
    高层方法：从文件中提取投标人名称。
    处理流程：先解析PDF，优先正则提取，其次AI提取，若名称疑似乱码或不完整，则在"授权委托书/投标一览表"等章节中继续检索。

    参数：
        file_path: 投标文件的绝对路径

    返回：
        提取到的投标公司全名；若未找到则返回 None
    """
    logger.info(f'Starting bidder name extraction for file: {file_path}')
    if not file_path:
        return None

    try:
        # 1. Process PDF to get text content
        pdf_processor = PDFProcessor(file_path)
        pages = pdf_processor.process_pdf_per_page()
        if not pages:
            logger.warning('PDF processing yielded no text pages.')
            return None

        # 合并前若干页以提升检索效率
        text_to_search = '\n'.join(pages[:3])

        # 2. Attempt extraction with Regex
        bidder_name = _extract_bidder_name_by_regex(text_to_search)
        if bidder_name and _is_valid_company_name(bidder_name) and not _looks_garbled_or_incomplete(bidder_name):
            logger.info(f"Valid bidder name found via regex: '{bidder_name}'")
            return bidder_name

        # 3. 回退到AI提取
        logger.info('Regex extraction failed, falling back to AI.')
        bidder_name = _extract_bidder_name_by_ai(text_to_search)
        if bidder_name and _is_valid_company_name(bidder_name) and not _looks_garbled_or_incomplete(bidder_name):
            logger.info(f"Valid bidder name found via AI: '{bidder_name}'")
            return bidder_name

        # 4. 若名称疑似乱码或不完整，则在关键章节继续检索
        fallback_name = _search_bidder_name_in_special_sections(pages)
        if fallback_name and _is_valid_company_name(fallback_name) and not _looks_garbled_or_incomplete(fallback_name):
            logger.info(f"Valid bidder name found in special sections: '{fallback_name}'")
            return fallback_name

        logger.warning(f'Failed to extract bidder name from {file_path}')
        return None

    except Exception as e:
        logger.error(
            f'An error occurred in extract_bidder_name_from_file for {file_path}: {e}'
        )
        return None