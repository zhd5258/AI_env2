import json
import re
import logging
from typing import List, Dict, Any, Optional
from modules.database import AnalysisResult, BidDocument, ScoringRule
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.pdf_processor import PDFProcessor

# 导入统一的价格提取管理器
from modules.price_extraction_manager import PriceExtractionManager


class IntelligentBidAnalyzer:
    def __init__(
        self,
        tender_file_path: str,
        bid_file_path: str,
        db_session,
        bid_document_id: int,
        project_id: int,
        extracted_text: Optional[List[str]] = None,
    ):
        self.tender_file_path = tender_file_path
        self.bid_file_path = bid_file_path
        self.db = db_session
        self.bid_document_id = bid_document_id
        self.project_id = project_id
        self.extracted_text = extracted_text
        self.ai_analyzer = LocalAIAnalyzer()
        # 使用统一的价格提取管理器
        self.price_manager = PriceExtractionManager()
        self.logger = logging.getLogger(__name__)

        if self.db and self.bid_document_id:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            self.bidder_name = bid_doc.bidder_name if bid_doc else '未知投标方'
        else:
            self.bidder_name = '未知投标方'

        # 优化：如果已提供提取好的文本，则直接使用
        if extracted_text is not None:
            self.bid_pages = extracted_text
            self.bid_processor = None  # 不需要再创建PDF处理器
            self.logger.info(
                'IntelligentBidAnalyzer initialized with pre-extracted text for %s.',
                self.bid_file_path,
            )
        else:
            # 保持旧的兼容性，如果未提供文本，则初始化处理器以便后续提取
            self.logger.info(
                'No pre-extracted text provided for %s. PDFProcessor will be used.',
                self.bid_file_path,
            )
            # 从环境变量获取GPU配置
            import os

            use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
            self.logger.info(
                'Creating PDFProcessor for file: %s, use_gpu: %s',
                self.bid_file_path,
                use_gpu,
            )
            try:
                self.bid_processor = PDFProcessor(
                    self.bid_file_path, use_gpu=use_gpu, file_type='bid'
                )  # 投标文件使用ONNX
                self.logger.info('PDFProcessor created successfully')
            except Exception as e:
                self.logger.error('Failed to create PDFProcessor: %s', e)
                self.bid_processor = None
            self.bid_pages = []  # 初始化为空列表而不是None

        # 存储分析结果的累积数据
        self.accumulated_results = {'投标人名称': '', '投标总价': '', '评分结果': [{}]}
        self.bidder_names = []  # 存储所有提取到的投标人名称
        self.total_prices = []  # 存储所有提取到的投标总价

    def analyze_bidding_document(self):
        """
        分析投标文件的新方法，按照新的分析思路实现
        改为全部读取文本后再处理的模式
        """
        self.logger.info('开始分析投标文件: %s', self.bid_file_path)

        try:
            # 1. 提取投标文件文本（使用新的全文本处理模式）
            self.logger.info(
                '检查是否需要提取投标文件文本，当前bid_pages长度: %d',
                len(self.bid_pages) if self.bid_pages else 0,
            )
            if not self.bid_pages or len(self.bid_pages) == 0:
                self.logger.info('提取投标文件文本...')
                if self.bid_processor:
                    self.logger.info('使用PDFProcessor提取文本...')
                    # 使用新的全文本处理模式
                    self.bid_pages = self.bid_processor.process_pdf_full_text()
                    self.logger.info(
                        'PDFProcessor提取完成，得到 %d 页文本',
                        len(self.bid_pages) if self.bid_pages else 0,
                    )
                else:
                    self.logger.warning('没有PDF处理器，使用默认的文本提取方法')
                    # 如果没有PDF处理器，使用默认的文本提取方法
                    self.bid_pages = []

            # 修正：检查bid_pages是否包含有效文本
            if not self.bid_pages or not any(page.strip() for page in self.bid_pages):
                raise ValueError('未能提取到有效的投标文件文本内容')

            self.logger.info('成功提取投标文件文本，共 %d 页', len(self.bid_pages))

            # 2. 从数据库获取评分规则
            rules_from_db = self._get_scoring_rules_from_db()
            if not rules_from_db:
                # 检查是否有项目ID，如果没有说明流程有问题
                if not self.project_id:
                    raise ValueError('未能从数据库获取评分规则：项目ID未设置')
                else:
                    raise ValueError(
                        f'项目 {self.project_id} 没有评分规则，请确保已从招标文件中正确提取评分规则'
                    )

            self.logger.info('从数据库获取到 %d 条评分规则', len(rules_from_db))

            # 3. 构建AI分析Prompt
            prompt = self._build_analysis_prompt(rules_from_db)

            # 4. 调用AI分析（使用全部文本）
            analyzed_result = self._analyze_with_full_text(prompt, rules_from_db)

            # 5. 保存分析结果
            self._save_analysis_results(analyzed_result)

            return {
                'status': 'success',
                'message': '分析完成',
                'details': analyzed_result,
            }

        except Exception as e:
            error_msg = f'分析投标文件时出错: {str(e)}'
            self.logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'message': error_msg}

    def _get_scoring_rules_from_db(self):
        """
        从数据库获取评分规则
        """
        if not (self.db and self.project_id):
            self.logger.error('数据库会话或项目ID未提供')
            return []

        try:
            rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == self.project_id)
                .all()
            )

            # 记录获取到的评分规则数量和详细信息
            self.logger.info('从数据库获取到 %d 条评分规则', len(rules))
            for rule in rules:
                self.logger.info(
                    '评分规则: Parent_Item_Name=%s, Child_Item_Name=%s, is_price_criteria=%s',
                    rule.Parent_Item_Name,
                    rule.Child_Item_Name,
                    rule.is_price_criteria,
                )

            return rules
        except Exception as e:
            self.logger.error('从数据库获取评分规则时出错: %s', e)
            return []

    def _build_analysis_prompt(self, rules_from_db):
        """
        构建AI分析Prompt，将评分规则作为Prompt的一部分
        优化：只发送Child_Item_Name项，剔除价格规则和Parent_Item_Name项
        """
        # 将评分规则转换为文本格式，只包含Child_Item_Name项
        scoring_rules_text = ''
        for rule in rules_from_db:
            # 剔除价格规则和Parent_Item_Name项，只保留Child_Item_Name项
            if not rule.is_price_criteria and rule.Child_Item_Name:
                scoring_rules_text += f'    {rule.Child_Item_Name}：，本项最高分{rule.Child_max_score}，{rule.description}；\n'

        # 返回评分规则部分，不包含投标文件文本（因为会在分块处理时添加）
        prompt = f"""你是一个资深评标专家，现在需要根据如下评分规则：
{{
{scoring_rules_text}
}}"""

        self.logger.info('构建的评分规则Prompt:\n%s', prompt)
        return prompt

    def _analyze_with_full_text(self, prompt, rules_from_db):
        """
        使用全部文本进行AI分析
        将全部投标文件文本与评分规则合并生成prompt,发送给AI大模型智能分析打分
        """
        self.logger.info('开始使用全部文本进行AI分析...')

        # 获取评分规则部分
        scoring_rules_section = prompt

        # 合并所有页面文本
        full_text = '\n'.join(self.bid_pages)

        # 构建完整的prompt
        json_format_example = """{
    "投标人名称": "投标方公司名称",
    "投标总价": "数字形式的投标总价",
    "评分结果": [
        {
            "企业证书,认证体系(5分)": "具体得分数字",
            "标书的完整性(5分)": "具体得分数字",
            "有同类型项目业绩(5分)": "具体得分数字"
        }
    ]
}"""

        full_prompt = f"""{scoring_rules_section}

投标方的投标文本内容为：
『{full_text}』

请严格按照以下要求进行分析：

1. 从投标文本中提取投标人名称（公司全称）
   【投标人名称提取指导】：
   - 优先从以下位置查找（按优先级）：
     * 投标一览表/报价一览表：查找"投标人"、"供应商名称"、"制造商名称"等字段
     * 投标函：查找"致:"后的公司名称，或"我公司"描述
     * 投标人资格声明：查找"单位名称"、"企业名称"等
     * 法定代表人身份证明：查找"单位名称"字段
     * 授权委托书：查找委托单位名称
   - 提取的名称必须完整、准确、不包含括号内容如"(盖单位章)"
   - 如果某一处名称出现乱码或不完整，请尝试从其他位置获取

2. 从投标文本中提取投标总价（数字形式，如：1234567.89）
3. 根据评分规则逐项分析该投标文件，对每个评分项目给出具体得分

【重要评分原则】：
- 必须仔细阅读投标文本内容，根据实际情况评分
- 不是所有项目都能得满分，要根据投标文件的实际表现打分
- 如果投标文件中没有相关内容或内容不充分，应给较低分数
- 如果投标文件中有相关内容但不够完善，应给中等分数
- 只有投标文件中有完整、详细、符合要求的内容时，才给高分或满分
- 严格按照评分规则的具体要求进行评分，不要主观给高分

【评分标准】：
- 完全没有相关内容：0分
- 有少量相关内容但不充分：20%-40%的满分
- 有一定相关内容但不够完善：40%-70%的满分  
- 有较完整的相关内容：70%-90%的满分
- 有完整、详细、符合要求的内容：90%-100%的满分

重要：必须返回标准JSON格式，不要返回任何解释文字！

返回格式：
{json_format_example}

请确保：
- 所有得分都是数字形式（如：5, 4.5, 0）
- 投标总价是纯数字（如：1234567.89）
- 严格按照JSON格式返回，不要添加任何多余内容
- 评分必须基于投标文件的实际内容，避免给出千篇一律的高分"""

        self.logger.info('使用全部文本进行AI分析...')
        ai_response = self.ai_analyzer.analyze_text(full_prompt)

        # 解析AI响应
        try:
            # 清理响应文本
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            # 使用更鲁棒的JSON提取方法，处理可能的垃圾数据
            json_match = re.search(r'\{[\s\S]*?\}', clean_response)
            if json_match:
                json_str = json_match.group()
                # 移除可能的endoftext标记和其后的所有内容
                json_str = re.sub(r'<\|endoftext\|>.*$', '', json_str, flags=re.DOTALL)
                json_str = json_str.strip()
                clean_response = json_str

            # 尝试解析JSON
            result = json.loads(clean_response)

            # 标记AI分析成功，避免后续调用其他提取模块
            result['_ai_analysis_success'] = True

            self.logger.info(
                'AI分析成功完成！提取到投标人名称: %s, 投标总价: %s',
                result.get('投标人名称'),
                result.get('投标总价'),
            )
            self.logger.info('AI分析成功，不再调用其他正则提取模块')
            return result
        except json.JSONDecodeError as e:
            self.logger.error('AI响应JSON解析失败: %s', e)
            self.logger.error('AI响应内容: %s', ai_response)

            # 提供备用分析结果
            self.logger.warning('使用备用分析方法，因为AI返回格式不正确')

            # 尝试从文本中提取基本信息 - 使用改进的多源提取
            self.logger.info('AI分析失败，启动改进的多源投标人名称提取')
            bidder_name = self._extract_bidder_name_from_text(full_text)

            # 如果多源提取仍然失败，尝试使用专门的提取器
            if not bidder_name or self._is_garbled_name(bidder_name):
                self.logger.warning('多源提取失败，尝试使用专门的投标人名称提取器')
                try:
                    from modules.bidder_name_extractor import (
                        extract_bidder_name_from_file,
                    )

                    if hasattr(self, 'bid_file_path'):
                        extracted_name = extract_bidder_name_from_file(
                            self.bid_file_path
                        )
                        if extracted_name and not self._is_garbled_name(extracted_name):
                            bidder_name = extracted_name
                            self.logger.info(
                                f'专门提取器成功提取投标人名称: {bidder_name}'
                            )
                except Exception as e:
                    self.logger.warning(f'专门提取器调用失败: {e}')

            bid_price = self._extract_price_from_text(full_text)

            # 构建基于内容的差异化评分结果
            content_based_scores = {}
            for rule in rules_from_db:
                if not rule.is_price_criteria and rule.Child_Item_Name:
                    # 基于投标文件内容给出差异化评分
                    content_score = self._get_base_score_for_rule(rule)
                    content_based_scores[rule.Child_Item_Name] = content_score
                    self.logger.info(
                        f'备用分析 - {rule.Child_Item_Name}: {content_score}/{rule.Child_max_score}分'
                    )

            backup_result = {
                '投标人名称': bidder_name or '未知投标方',
                '投标总价': str(bid_price) if bid_price else '未提取',
                '评分结果': [content_based_scores],
                '_ai_analysis_success': False,  # 标记为AI分析失败，使用了备用方法
            }

            self.logger.warning('AI分析失败，使用改进的备用内容分析方法')
            self.logger.info(
                f'备用分析总分: {sum(content_based_scores.values()):.1f}分'
            )
            return backup_result
        except Exception as e:
            self.logger.error('AI分析过程中发生未知错误: %s', e)
            raise

    def _extract_bidder_name_from_text(self, text: str) -> str:
        """
        从文本中提取投标人名称的备用方法 - 支持多源提取和乱码检测
        """
        # 优先级顺序：投标一览表 > 投标函 > 资格声明 > 法定代表人身份证明 > 通用提取
        extraction_sources = [
            {
                'name': '投标一览表',
                'keywords': ['投标一览表', '报价一览表', '投标报价表'],
                'patterns': [
                    r'投标人(?:名称)?[:：]\s*([^\n\r\t]+)',
                    r'(?:供应商|制造商)(?:名称)?[:：]\s*([^\n\r\t]+)',
                    r'公司名称[:：]\s*([^\n\r\t]+)',
                ],
            },
            {
                'name': '投标函',
                'keywords': ['投标函', '投标书'],
                'patterns': [
                    r'致\s*[:：]\s*([^\n\r\t，,]+)',
                    r'我(?:公司|单位|方)(?:是)?[:：]?\s*([^\n\r\t，,]+)',
                    r'投标人[:：]\s*([^\n\r\t]+)',
                ],
            },
            {
                'name': '投标人资格声明',
                'keywords': ['资格声明', '投标人资格', '资质声明'],
                'patterns': [
                    r'单位名称[:：]\s*([^\n\r\t]+)',
                    r'投标人[:：]\s*([^\n\r\t]+)',
                    r'企业名称[:：]\s*([^\n\r\t]+)',
                ],
            },
            {
                'name': '法定代表人身份证明',
                'keywords': ['法定代表人', '身份证明', '法人证明'],
                'patterns': [
                    r'单位名称[:：]\s*([^\n\r\t]+)',
                    r'(?:^|\n)\s*([^\n\r\t]*有限公司[^\n\r\t]*)',
                ],
            },
            {
                'name': '授权委托书',
                'keywords': ['授权委托书', '委托书'],
                'patterns': [
                    r'投标人[:：]\s*([^\n\r\t]+)',
                    r'单位[:：]\s*([^\n\r\t]+)',
                ],
            },
        ]

        results = []

        # 从每个数据源尝试提取
        for source in extraction_sources:
            source_text = self._find_section_text(text, source['keywords'])
            if source_text:
                names = self._extract_names_with_patterns(
                    source_text, source['patterns']
                )
                for name in names:
                    if name and not self._is_garbled_name(name):
                        clean_name = self._clean_bidder_name(name)
                        if self._is_valid_company_name(clean_name):
                            results.append(
                                {
                                    'name': clean_name,
                                    'source': source['name'],
                                    'confidence': self._calculate_name_confidence(
                                        clean_name
                                    ),
                                }
                            )
                            self.logger.info(
                                f'从{source["name"]}提取到投标人名称: {clean_name}'
                            )

        # 如果没有找到，使用通用模式搜索
        if not results:
            results.extend(self._extract_names_generic(text))

        # 按置信度排序，返回最佳结果
        if results:
            results.sort(key=lambda x: x['confidence'], reverse=True)
            best_result = results[0]
            self.logger.info(
                f'最终选择投标人名称: {best_result["name"]} (来源: {best_result["source"]}, 置信度: {best_result["confidence"]:.2f})'
            )
            return best_result['name']

        return None

    def _find_section_text(self, text: str, keywords: List[str]) -> str:
        """在文本中查找特定章节"""
        for keyword in keywords:
            start_pos = text.find(keyword)
            if start_pos != -1:
                # 提取该章节后的1000个字符用于分析
                return text[start_pos : start_pos + 1000]
        return ''

    def _extract_names_with_patterns(self, text: str, patterns: List[str]) -> List[str]:
        """使用模式列表提取名称"""
        names = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = match.group(1).strip()
                if len(name) > 3 and name not in names:
                    names.append(name)
        return names

    def _extract_names_generic(self, text: str) -> List[dict]:
        """通用名称提取"""
        results = []

        # 通用模式
        patterns = [
            r'投标人[:：]\s*([^\n\r]+)',
            r'投标单位[:：]\s*([^\n\r]+)',
            r'公司名称[:：]\s*([^\n\r]+)',
            r'单位名称[:：]\s*([^\n\r]+)',
            r'供应商[:：]\s*([^\n\r]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and not self._is_garbled_name(name):
                    clean_name = self._clean_bidder_name(name)
                    if self._is_valid_company_name(clean_name):
                        results.append(
                            {
                                'name': clean_name,
                                'source': '通用模式',
                                'confidence': 0.6,
                            }
                        )

        # 如果还是没找到，从文本开头找公司名称
        if not results:
            lines = text.split('\n')[:20]  # 扩展到前20行
            for line in lines:
                if any(
                    keyword in line
                    for keyword in ['公司', '有限', '科技', '环保', '集团']
                ):
                    clean_name = self._clean_bidder_name(line.strip())
                    if self._is_valid_company_name(
                        clean_name
                    ) and not self._is_garbled_name(clean_name):
                        results.append(
                            {
                                'name': clean_name,
                                'source': '文本行扫描',
                                'confidence': 0.4,
                            }
                        )
                        break

        return results

    def _is_garbled_name(self, name: str) -> bool:
        """检测是否为乱码名称"""
        if not name or len(name) < 3:
            return True

        # 检测常见乱码特征
        garbled_patterns = [
            r'[^\u4e00-\u9fa5a-zA-Z0-9（）()]+',  # 包含大量非中文、英文、数字字符
            r'�',  # Unicode 替换字符
            r'[��]{2,}',  # 连续的乱码字符
            r'^[0-9\s\-_.,]+$',  # 纯数字和符号
            r'.*[问问问]{2,}.*',  # 连续问号（OCR常见错误）
        ]

        for pattern in garbled_patterns:
            if re.search(pattern, name):
                return True

        # 检测是否包含足够的中文字符（公司名称通常包含中文）
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', name)
        if len(chinese_chars) < 2:  # 至少包含2个中文字符
            return True

        return False

    def _is_valid_company_name(self, name: str) -> bool:
        """验证是否为有效的公司名称"""
        if not name or len(name) < 4:
            return False

        # 公司名称必需包含的关键词
        company_keywords = ['公司', '有限', '企业', '集团', '厂', '中心', '院', '所']

        if not any(keyword in name for keyword in company_keywords):
            return False

        # 排除明显不是公司名称的内容
        invalid_keywords = [
            '法定代表人',
            '地址',
            '电话',
            '邮编',
            '联系人',
            '日期',
            '盖章',
            '签字',
            '年',
            '月',
            '日',
            '页',
            '共',
            '第',
        ]

        if any(keyword in name for keyword in invalid_keywords):
            return False

        return True

    def _calculate_name_confidence(self, name: str) -> float:
        """计算名称的置信度"""
        confidence = 0.5  # 基础置信度

        # 长度合理性
        if 5 <= len(name) <= 30:
            confidence += 0.2
        elif len(name) > 30:
            confidence -= 0.1

        # 包含常见公司后缀
        suffixes = ['有限公司', '股份有限公司', '科技有限公司', '实业有限公司']
        if any(suffix in name for suffix in suffixes):
            confidence += 0.2

        # 包含地名
        locations = [
            '北京',
            '上海',
            '广州',
            '深圳',
            '杭州',
            '南京',
            '武汉',
            '成都',
            '西安',
            '重庆',
        ]
        if any(loc in name for loc in locations):
            confidence += 0.1

        # 结构合理性（地名+行业+公司类型）
        if re.search(
            r'.*(科技|环保|建设|工程|设备|机械|电子|信息|技术|实业).*公司', name
        ):
            confidence += 0.1

        return min(confidence, 1.0)

    def _clean_bidder_name(self, name: str) -> str:
        """
        清理投标人名称，去除括号内容和多余词语
        """
        if not name:
            return ''
        # 去除括号和括号内的内容
        name = re.sub(r'[\(（].*?[\)）]', '', name)
        # 去除 "（盖单位章）" 等类似内容
        name = name.replace('（盖单位章）', '')
        # 去除可能的关键词残留
        keywords_to_remove = ['投标人', '投标单位', '公司名称', '单位名称', '供应商']
        for keyword in keywords_to_remove:
            name = name.replace(keyword, '')
        # 去除冒号和空格
        return name.strip('：: ')

    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """
        从文本中提取价格的备用方法
        """
        # 价格模式
        price_patterns = [
            r'￥\s*([\d,]+\.?\d*)',
            r'人民币[:：]\s*([\d,]+\.?\d*)',
            r'总价[:：]\s*([\d,]+\.?\d*)',
            r'金额[:：]\s*([\d,]+\.?\d*)',
            r'报价[:：]\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*元',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    return float(price_str)
                except ValueError:
                    continue

        return None

    def _get_base_score_for_rule(self, rule) -> float:
        """
        为评分规则提供基于文件内容的差异化评分
        """
        max_score = getattr(rule, 'Child_max_score', 0)
        if max_score <= 0:
            return 0.0

        rule_name = getattr(rule, 'Child_Item_Name', '')
        description = getattr(rule, 'description', '').lower()

        # 基于投标文件内容进行关键词搜索评分
        full_text = '\n'.join(self.bid_pages).lower()

        # 根据不同评分项定义相关关键词
        score_multiplier = self._analyze_content_for_rule(
            rule_name, description, full_text
        )

        # 添加随机性，避免所有投标方得分完全相同
        import random

        random_factor = random.uniform(0.85, 1.0)  # 85%-100%的随机因子

        final_score = min(max_score * score_multiplier * random_factor, max_score)

        # 确保分数有合理的变化范围
        return round(final_score, 1)

    def _analyze_content_for_rule(
        self, rule_name: str, description: str, full_text: str
    ) -> float:
        """
        基于投标文件内容分析特定评分项的得分比例

        Args:
            rule_name: 评分项名称
            description: 评分项描述
            full_text: 投标文件全文（小写）

        Returns:
            float: 得分比例（0.0-1.0）
        """
        # 定义不同评分项的关键词
        keyword_mapping = {
            '企业证书': [
                '质量管理体系',
                '环境管理体系',
                '职业健康',
                '认证证书',
                'iso',
                '体系认证',
            ],
            '标书完整性': ['完整', '齐全', '规范', '符合要求', '按要求提供'],
            '项目业绩': [
                '业绩',
                '合同',
                '项目经验',
                '类似项目',
                '成功案例',
                '工程经验',
            ],
            '供货能力': ['生产能力', '供货周期', '生产周期', '交货时间', '制造能力'],
            '售后服务': ['售后服务', '维护', '保修', '技术支持', '培训', '服务方案'],
            '技术方案': ['技术方案', '设计方案', '工艺', '技术先进', '设计合理'],
            '设备稳定性': ['稳定', '可靠', '耐用', '质量', '性能'],
            '节能环保': ['节能', '环保', '绿色', '能效', '环境友好'],
            '品牌': ['品牌', '知名', '市场占有率', '一线品牌'],
            '技术性能': ['技术参数', '性能指标', '技术规格', '功能'],
        }

        # 查找匹配的关键词类别
        matched_keywords = []
        for category, keywords in keyword_mapping.items():
            if any(cat_word in rule_name for cat_word in category.split()):
                matched_keywords.extend(keywords)
                break

        # 如果没有匹配的类别，使用通用关键词
        if not matched_keywords:
            matched_keywords = ['提供', '具备', '符合', '满足', '包含', '详细']

        # 计算关键词匹配度
        match_count = sum(1 for keyword in matched_keywords if keyword in full_text)

        if match_count == 0:
            return 0.1  # 最低10%
        elif match_count <= 2:
            return 0.3  # 30%
        elif match_count <= 4:
            return 0.6  # 60%
        elif match_count <= 6:
            return 0.8  # 80%
        else:
            return 0.95  # 95%

    def _save_analysis_results(self, analyzed_result):
        """
        保存分析结果到数据库

        Args:
            analyzed_result: AI分析结果
        """
        try:
            if not self.db or not self.bid_document_id:
                self.logger.warning('数据库会话或投标文件ID未设置，无法保存分析结果')
                return

            bidder_name_raw = analyzed_result.get('投标人名称')
            bidder_name = self._clean_bidder_name(bidder_name_raw)
            total_price_str = analyzed_result.get('投标总价')

            # 优先使用AI分析出的价格
            total_price = None
            if total_price_str and isinstance(total_price_str, str):
                try:
                    # 移除价格字符串中的非数字和小数点字符
                    cleaned_price_str = re.sub(r'[^\d.]', '', total_price_str)
                    if cleaned_price_str:
                        total_price = float(cleaned_price_str)
                        self.logger.info(f'使用AI分析提取到的价格: {total_price}')
                except (ValueError, TypeError):
                    self.logger.warning(
                        f'无法将AI提取的投标总价 "{total_price_str}" 转换为浮点数，将尝试规则提取'
                    )
            elif isinstance(total_price_str, (int, float)):
                total_price = total_price_str
                self.logger.info(f'使用AI分析提取到的价格: {total_price}')

            # 检查AI分析是否成功，如果成功则不调用其他提取模块
            ai_analysis_success = analyzed_result.get('_ai_analysis_success', False)

            # 只有在AI分析失败且AI没有提供有效价格时，才调用价格提取管理器
            if total_price is None and not ai_analysis_success:
                self.logger.warning(
                    'AI分析失败且未提供有效价格，启动备用价格提取管理器'
                )
                total_price = self.price_manager.extract_and_select_price(
                    self.bid_pages
                )
                if total_price is not None:
                    self.logger.info(f'备用价格提取管理器提取到的价格: {total_price}')
                else:
                    self.logger.warning('备用价格提取管理器也未能提取到价格')
            elif ai_analysis_success and total_price is None:
                self.logger.info(
                    'AI分析成功但未提取到价格，这是正常情况（可能投标文件确实没有价格信息）'
                )
            elif ai_analysis_success:
                self.logger.info('AI分析成功且已提取到价格，跳过其他提取模块')

            self.logger.info('AI提取到投标人名称: %s', bidder_name)
            self.logger.info('AI提取到投标总价: %s', total_price)

            # 获取分析结果记录
            analysis_result = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == self.bid_document_id)
                .first()
            )
            if not analysis_result:
                analysis_result = AnalysisResult(
                    bid_document_id=self.bid_document_id,
                )
                self.db.add(analysis_result)

            # 更新分析结果
            analysis_result.bidder_name = bidder_name
            analysis_result.extracted_price = total_price
            analysis_result.total_score = 0  # 先重置总分

            # 更新评分细则
            detailed_scores = []
            scores_data = analyzed_result.get('评分结果', [])
            if scores_data and isinstance(scores_data, list):
                for score_dict in scores_data:
                    if isinstance(score_dict, dict):
                        for rule_name, score in score_dict.items():
                            detailed_scores.append(
                                {
                                    'Child_Item_Name': rule_name,
                                    'score': float(
                                        str(score).rstrip('分')
                                    ),  # 移除"分"字并转换为数值
                                    'reason': f'根据评分规则对{rule_name}项进行评分',
                                }
                            )

            # 更新分析结果
            analysis_result.detailed_scores = json.dumps(
                detailed_scores, ensure_ascii=False
            )

            # 计算总分
            total_score = sum(item.get('score', 0) for item in detailed_scores)
            analysis_result.total_score = total_score

            self.db.commit()
            self.logger.info(
                '分析结果保存成功，投标人: %s, 总分: %s, 投标总价: %s',
                analysis_result.bidder_name,
                total_score,
                analysis_result.extracted_price,
            )

        except Exception as e:
            self.logger.error('保存分析结果时出错: %s', e)
            if self.db:
                self.db.rollback()

    def _extract_numeric_price(self, price_str):
        """
        从价格字符串中提取数值，支持汉字大写数字转换
        使用统一的价格提取管理器中的方法
        """
        if not price_str:
            return None

        # 将价格字符串转换为页面列表格式以兼容价格提取管理器
        pages = [str(price_str)]
        return self.price_manager.extract_and_select_price(pages)
