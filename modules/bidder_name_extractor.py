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
        '文件',
        '响应',
        '投标函',
        '法定代表人',
        '授权委托',
        '签字',
        '盖章',
        '日期',
        '页',
        '第',
        '评审',
        '评标',
        '中标',
        '成交',
        '供应商',
        '代理',
        '公告',
        '公示',
    ]
    if any(keyword in bidder_name for keyword in invalid_keywords):
        return False
    # 检查是否包含足够的中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', bidder_name)
    return len(chinese_chars) >= 2


def _looks_garbled_or_incomplete(name: str) -> bool:
    """
    检查名称是否看起来是乱码或不完整。
    """
    if not name:
        return True
    # 检查乱码字符
    garbled_patterns = [
        r'[äåçèéêëìíîïðñòóôõöøüýþÿ]',
        r'[àáâãäåæçèéêëìíîï]',
        r'[ðñòóôõöøùúûüýþÿ]',
        r'[Ā-ž]',  # Latin Extended-A 和部分 Extended-B
        r'â\x80\x99',  # 特定乱码序列
    ]
    if any(re.search(pattern, name) for pattern in garbled_patterns):
        return True
    # 检查是否以常见非公司名称结尾
    if name.endswith(('投标文件', '响应文件', '公司声明')):
        return True
    # 检查是否太短
    if len(name) < 4:
        return True
    return False


def _filter_bidder_name(name: str) -> str:
    """
    清理投标人名称，移除常见的干扰字符。
    """
    if not name:
        return ''

    # 移除常见的干扰字符和多余空格
    name = re.sub(r'[（\(].*?[）\)]', '', name)  # 移除括号及其中内容
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)  # 移除控制字符
    name = re.sub(r'[^\S\r\n]+', '', name)  # 移除多余空格但保留换行符
    name = name.strip(' \t\n\r\v\f\ufeff' + '【】〔〕［］' + '：:;|·.,，。、/\\')
    # 移除常见的后缀干扰
    name = re.sub(r'(有限公司|股份公司|集团公司|集团|公司|厂|院|所|社|中心)+[：:;|·.,，。、/\\]*$', r'\1', name)
    return name.strip()


def _search_bidder_name_in_special_sections(pages: list[str]) -> str | None:
    """
    在特殊章节中搜索投标人名称，如"授权委托书"、"投标一览表"等。
    """
    special_section_keywords = [
        '授权委托书',
        '法定代表人身份证明',
        '投标一览表',
        '投标函',
        '投标人基本情况',
    ]
    # 合并所有页面以搜索特殊章节
    full_text = '\n'.join(pages)

    for keyword in special_section_keywords:
        # 查找特殊章节开始位置
        start_pos = full_text.find(keyword)
        if start_pos != -1:
            # 从章节开始位置向后搜索约500字符以查找投标人名称
            section_text = full_text[start_pos : start_pos + 500]
            # 使用正则表达式查找可能的公司名称
            # 匹配以"单位名称"、"投标人"、"供应商"等开头的行
            patterns = [
                r'单位名称\s*[:：\s]*([^\n]+)',
                r'投标人\s*[:：\s]*([^\n]+)',
                r'供应商\s*[:：\s]*([^\n]+)',
                r'^\s*([^\n]+?公司)\s*$',
            ]
            for pattern in patterns:
                matches = re.finditer(pattern, section_text, re.MULTILINE)
                for match in matches:
                    potential_name = (
                        match.group(1).strip() if len(match.groups()) >= 1 else match.group(0).strip()
                    )
                    filtered_name = _filter_bidder_name(potential_name)
                    if _is_valid_company_name(filtered_name) and not _looks_garbled_or_incomplete(
                        filtered_name
                    ):
                        logger.info(
                            'Found bidder name in special section (%s): %s', keyword, filtered_name
                        )
                        return filtered_name
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
        pdf_processor = PDFProcessor(
            file_path, file_type='bid'
        )  # 投标文件使用ONNX        pages = pdf_processor.extract_text_with_ocr_when_needed()
        if not pages:
            logger.warning('PDF processing yielded no text pages.')
            return None

        # 合并前若干页以提升检索效率
        text_to_search = '\n'.join(pages[:3])

        # 2. Attempt extraction with Regex
        bidder_name = _extract_bidder_name_by_regex(text_to_search)
        if (
            bidder_name
            and _is_valid_company_name(bidder_name)
            and not _looks_garbled_or_incomplete(bidder_name)
        ):
            logger.info(f"Valid bidder name found via regex: '{bidder_name}'")
            return bidder_name

        # 3. 回退到AI提取
        logger.info('Regex extraction failed, falling back to AI.')
        bidder_name = _extract_bidder_name_by_ai(text_to_search)
        if (
            bidder_name
            and _is_valid_company_name(bidder_name)
            and not _looks_garbled_or_incomplete(bidder_name)
        ):
            logger.info(f"Valid bidder name found via AI: '{bidder_name}'")
            return bidder_name

        # 4. 基于表格的回退提取（整合）：优先从"制造商名称/投标人名称"列获取
        try:
            from .table_analyzer import TableAnalyzer  # 延迟导入，避免循环依赖

            analyzer = TableAnalyzer(file_path)
            merged = analyzer.extract_and_merge_tables()
            tables = analyzer.convert_to_structured_format(merged)

            candidate_headers = ['制造商名称', '投标人名称', '供应商名称', '单位名称']
            for table in tables:
                headers = table.get('headers') or []
                rows = table.get('rows') or []
                # 直接按中文表头匹配
                header_to_idx = {h: i for i, h in enumerate(headers)}
                hit_header = next(
                    (
                        h
                        for h in candidate_headers
                        if any(h in (hh or '') for hh in headers)
                    ),
                    None,
                )
                if hit_header and rows:
                    # 找到包含该关键列的真实列名
                    real_header = next(
                        (hh for hh in headers if hit_header in (hh or '')), None
                    )
                    if real_header:
                        for row in rows:
                            raw_val = row.get(real_header) or ''
                            name = _filter_bidder_name(raw_val)
                            if _is_valid_company_name(
                                name
                            ) and not _looks_garbled_or_incomplete(name):
                                logger.info(
                                    "Valid bidder name found via tables(%s): '%s'",
                                    real_header,
                                    name,
                                )
                                return name
        except Exception as e:
            logger.debug('表格回退提取失败: %s', e)

        # 5. 若名称疑似乱码或不完整，则在关键章节继续检索
        fallback_name = _search_bidder_name_in_special_sections(pages)
        if (
            fallback_name
            and _is_valid_company_name(fallback_name)
            and not _looks_garbled_or_incomplete(fallback_name)
        ):
            logger.info(
                f"Valid bidder name found in special sections: '{fallback_name}'"
            )
            return fallback_name

        logger.warning(f'Failed to extract bidder name from {file_path}')
        return None

    except Exception as e:
        logger.error(
            f'An error occurred in extract_bidder_name_from_file for {file_path}: {e}'
        )
        return None