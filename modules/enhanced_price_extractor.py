import re
from typing import List, Dict, Any, Optional
import logging

# 设置日志
logger = logging.getLogger(__name__)


class ChineseNumberConverter:
    """
    一个更强大的中文数字转换器，支持大写、小写、单位（万、亿）和基本的小数处理。
    """
    def __init__(self):
        self.num_map = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9,
            '两': 2,
        }
        self.unit_map = {'十': 10, '百': 100, '千': 1000, '拾': 10, '佰': 100, '仟': 1000}
        self.large_unit_map = {'万': 10000, '亿': 100000000}

    def chinese_to_number(self, text: str) -> Optional[float]:
        """
        将中文数字字符串（包括大写）转换为阿拉伯数字浮点数。
        """
        if not text:
            return None
        
        # 移除常见非数字字符
        text = re.sub(r'[元圆角分整人民币\s]', '', text)
        
        # 处理亿和万
        if '亿' in text:
            parts = text.split('亿')
            high = self._convert_segment(parts[0]) * self.large_unit_map['亿']
            low = self._convert_segment(parts[1]) if parts[1] else 0
            return high + low
        if '万' in text:
            parts = text.split('万')
            high = self._convert_segment(parts[0]) * self.large_unit_map['万']
            low = self._convert_segment(parts[1]) if parts[1] else 0
            return high + low
            
        return self._convert_segment(text)

    def _convert_segment(self, segment: str) -> float:
        """转换万或亿内部的数字部分"""
        if not segment:
            return 0
        
        total = 0
        current_num = 0
        for char in segment:
            if char in self.num_map:
                current_num = self.num_map[char]
            elif char in self.unit_map:
                total += (current_num or 1) * self.unit_map[char]
                current_num = 0
            else:
                # 忽略无法识别的字符
                pass
        total += current_num
        return total


class EnhancedPriceExtractor:
    def __init__(self):
        self.converter = ChineseNumberConverter()
        # 优先匹配包含明确关键字的模式
        self.total_price_keywords = ['总价', '总报价', '投标报价', '合计', '总计']
        # 匹配 "关键字" 和 数字 的模式
        self.price_patterns = [
            # 格式: (关键字) 金额(阿拉伯数字, 带/不带逗号, 带/不带小数) (可选的大写中文)
            r'({keywords})[:：\s]*?([\d,]+\.?\d*)\s*\(?([\u4e00-\u9fa5]+)\)?'.format(keywords='|'.join(self.total_price_keywords)),
            # 格式: 金额(阿拉伯数字) 后面紧跟 (关键字)
            r'([\d,]+\.?\d*)\s*({keywords})'.format(keywords='|'.join(self.total_price_keywords)),
        ]
        # 通用价格模式，作为补充
        self.general_price_patterns = [
            r'￥\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*元',
        ]

    def extract_enhanced_prices(self, pages: List[str]) -> List[Dict[str, Any]]:
        """
        从PDF页面中提取价格，并为每个价格计算置信度。
        """
        all_prices = []
        
        # 1. 识别关键章节
        price_summary_pages = self._identify_sections(pages, ['投标一览表', '开标一览表'])
        price_doc_pages = self._identify_sections(pages, ['价格文件', '报价部分'])

        for i, page_text in enumerate(pages):
            context = page_text.replace('\n', ' ')
            
            # 2. 在页面中查找所有可能的价格
            # 查找与关键字强相关的价格
            for pattern in self.price_patterns:
                for match in re.finditer(pattern, context):
                    groups = match.groups()
                    price_str = groups[1] if groups[0] in self.total_price_keywords else groups[0]
                    chinese_price_str = groups[2] if len(groups) > 2 else None
                    
                    price_value = self._str_to_float(price_str)
                    if price_value is None:
                        continue

                    confidence = self._calculate_price_confidence(
                        page_index=i,
                        price_value=price_value,
                        keyword_found=True,
                        chinese_price_str=chinese_price_str,
                        price_summary_pages=price_summary_pages,
                        price_doc_pages=price_doc_pages
                    )
                    all_prices.append({'value': price_value, 'page': i, 'confidence': confidence, 'reason': '关键字匹配'})

            # 查找通用价格格式
            for pattern in self.general_price_patterns:
                 for match in re.finditer(pattern, context):
                    price_str = match.group(1)
                    price_value = self._str_to_float(price_str)
                    if price_value is None:
                        continue
                    
                    confidence = self._calculate_price_confidence(
                        page_index=i,
                        price_value=price_value,
                        keyword_found=False,
                        price_summary_pages=price_summary_pages,
                        price_doc_pages=price_doc_pages
                    )
                    all_prices.append({'value': price_value, 'page': i, 'confidence': confidence, 'reason': '通用格式匹配'})

        return all_prices

    def select_best_total_price(self, prices: List[Dict[str, Any]]) -> Optional[float]:
        """
        根据置信度选择最可信的投标总价。
        """
        if not prices:
            return None
        
        # 按置信度降序排序，置信度相同则选择较大的价格
        prices.sort(key=lambda x: (x['confidence'], x['value']), reverse=True)
        
        # 打印排序后的价格列表以供调试
        logger.info("按置信度排序后的价格列表:")
        for p in prices[:5]: # 只打印前5个
            logger.info(f"  - 价格: {p['value']}, 置信度: {p['confidence']}, 来源页: {p['page']+1}, 原因: {p.get('reason', 'N/A')}")

        return prices[0]['value']

    def _calculate_price_confidence(
        self, page_index: int, price_value: float, keyword_found: bool,
        price_summary_pages: List[int], price_doc_pages: List[int],
        chinese_price_str: Optional[str] = None
    ) -> float:
        """
        为提取到的价格计算置信度分数。
        """
        confidence = 0.0

        # 基础分
        if keyword_found:
            confidence += 50  # 找到总价等关键字，基础分高
        else:
            confidence += 10  # 通用价格格式，基础分低

        # 章节加分
        if page_index in price_summary_pages:
            confidence += 40  # 在“投标一览表”中，权重最高
        elif page_index in price_doc_pages:
            confidence += 20  # 在“价格文件”中，权重次之

        # 大写中文验证加分
        if chinese_price_str:
            chinese_value = self.converter.chinese_to_number(chinese_price_str)
            if chinese_value is not None:
                # 允许一定的误差（例如，小数部分）
                if abs(price_value - chinese_value) < 1.0:
                    confidence += 30  # 大小写匹配，置信度极高
        
        # 价格本身也作为一个小的参考因素，避免选到明显的分项价格
        confidence += min(price_value / 1000000, 5) # 每百万加1分，最多5分

        return round(confidence, 2)

    def _identify_sections(self, pages: List[str], keywords: List[str]) -> List[int]:
        """
        识别包含特定关键字的页面索引列表。
        """
        found_pages = []
        pattern = '|'.join(keywords)
        for i, page_text in enumerate(pages):
            if re.search(pattern, page_text):
                found_pages.append(i)
        return found_pages

    def _str_to_float(self, s: str) -> Optional[float]:
        """将可能带逗号的数字字符串转换为浮点数"""
        try:
            return float(s.replace(',', ''))
        except (ValueError, TypeError):
            return None

    def _is_total_price_intelligent(self, context: str, price_value: float) -> bool:
        """
        智能判断上下文中的价格是否为总价
        
        Args:
            context: 包含价格的上下文文本
            price_value: 价格数值
            
        Returns:
            bool: 如果是总价返回True，否则返回False
        """
        # 检查上下文中是否包含价格数值和总价相关关键字
        total_keywords = ['总价', '总报价', '投标报价', '合计', '总计', '报价总额']
        
        # 检查上下文中是否包含总价相关关键字
        context_contains_keyword = any(keyword in context for keyword in total_keywords)
        
        # 检查价格值是否在上下文中（考虑到可能的格式化差异）
        price_str = str(price_value)
        formatted_price_str = f"{price_value:,.2f}"  # 格式化为带逗号和两位小数
        
        # 检查上下文中是否包含价格（原始形式或格式化形式）
        context_contains_price = (price_str in context) or (formatted_price_str in context)
        
        # 如果上下文中同时包含价格和关键字，则很可能是总价
        if context_contains_price and context_contains_keyword:
            return True
            
        # 检查价格值是否较大（总价通常较大）
        # 这是一个启发式判断，假设总价通常大于10000
        if price_value > 10000:
            return True
            
        return False
