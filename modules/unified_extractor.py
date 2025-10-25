#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-08 06:39:37
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-08 06:44:08
# 文件相对于项目的路径   : \AI_ENV2\modules\unified_extractor.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
统一提取器模块
合并投标人名称和投标总价提取功能
"""

import os
import logging
import glob
import json
import datetime
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy.orm import Session
from models.database import BidDocument, AnalysisResult

# 导入现有的提取器
from modules.bidder_name_extractor import extract_bidder_name_from_file
from modules.price_extraction_manager import PriceExtractionManager
from modules.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


class UnifiedExtractor:
    """统一提取器，用于同时提取投标人名称和投标总价"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.price_manager = PriceExtractionManager()
        self.logger = logging.getLogger(__name__)

    def extract_all_bidders_info(self, project_id: int) -> List[Dict[str, Any]]:
        """
        提取所有投标人的信息（名称和价格）

        Args:
            project_id: 项目ID

        Returns:
            List[Dict]: 包含投标人信息的列表
        """
        self.logger.info(f'开始提取项目 {project_id} 的所有投标人信息')

        # 获取项目下的所有投标文件
        bid_documents = (
            self.db.query(BidDocument)
            .filter(BidDocument.project_id == project_id)
            .all()
        )

        bidders_info = []

        # 遍历每个投标文件
        for bid_doc in bid_documents:
            try:
                self.logger.info(f'处理投标文件: {bid_doc.file_path}')

                # 提取投标人名称和价格
                bidder_name, bid_price = self.extract_bidder_info(bid_doc.file_path)

                if bidder_name:
                    # 保存到数据库
                    self.save_bidder_info_to_db(bid_doc.id, bidder_name, bid_price)

                    # 添加到结果列表
                    bidders_info.append(
                        {
                            'bid_document_id': bid_doc.id,
                            'bidder_name': bidder_name,
                            'bid_price': bid_price,
                            'file_path': bid_doc.file_path,
                        }
                    )

                    self.logger.info(f"成功提取投标人信息: {bidder_name} - {bid_price or '未找到'}")
                else:
                    self.logger.warning(
                        f'未能提取到有效的投标人信息: {bid_doc.file_path}'
                    )

            except Exception as e:
                self.logger.error(f'处理投标文件 {bid_doc.file_path} 时出错: {e}')
                continue

        self.logger.info(f'完成提取，共处理 {len(bidders_info)} 个投标人')
        return bidders_info

    def extract_bidder_info(
        self, file_path: str
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        从单个文件中提取投标人名称和投标总价

        Args:
            file_path: 文件路径

        Returns:
            Tuple[Optional[str], Optional[float]]: (投标人名称, 投标总价)
        """
        try:
            self.logger.info(f'开始提取文件信息: {file_path}')

            # 1. 提取投标人名称
            bidder_name = self.extract_bidder_name(file_path)
            if not bidder_name:
                self.logger.warning(f'未能提取到投标人名称: {file_path}')
                # 使用文件名作为备用
                filename = os.path.basename(file_path)
                bidder_name = os.path.splitext(filename)[0]
                if not bidder_name or not bidder_name.strip():
                    bidder_name = '未知投标方'
                self.logger.info(f'使用文件名作为备用投标人名称: {bidder_name}')

            # 2. 提取投标总价
            bid_price = self.extract_bid_price(file_path)
            if bid_price is None:
                self.logger.warning(f'未能提取到投标总价: {file_path}')
                # 不返回None，而是返回一个默认值或者继续处理
                # 这里我们仍然返回提取到的投标人名称

            self.logger.info(
                f'提取结果 - 投标人名称: {bidder_name}, 投标总价: {bid_price}'
            )
            return bidder_name, bid_price

        except Exception as e:
            self.logger.error(f'提取文件信息时出错 {file_path}: {e}', exc_info=True)
            # 即使出错也返回默认值，确保流程能继续
            filename = os.path.basename(file_path)
            bidder_name = os.path.splitext(filename)[0]
            if not bidder_name or not bidder_name.strip():
                bidder_name = '未知投标方'
            return bidder_name, None

    def extract_bidder_name(self, file_path: str) -> Optional[str]:
        """
        提取投标人名称

        Args:
            file_path: 文件路径

        Returns:
            Optional[str]: 投标人名称
        """
        try:
            # 使用现有的投标人名称提取器
            bidder_name = extract_bidder_name_from_file(file_path)

            # 确保名称有效
            if bidder_name and bidder_name.strip() and bidder_name != '未提取':
                return bidder_name.strip()
            else:
                # 使用文件名作为备用
                filename = os.path.basename(file_path)
                bidder_name = os.path.splitext(filename)[0]
                if bidder_name and bidder_name.strip():
                    return bidder_name.strip()

            return None
        except Exception as e:
            self.logger.error(f'提取投标人名称时出错: {e}')
            # 即使出错也返回默认值，确保流程能继续
            filename = os.path.basename(file_path)
            bidder_name = os.path.splitext(filename)[0]
            if bidder_name and bidder_name.strip():
                return bidder_name.strip()
            return None

    def _get_md_file_path(self, file_path: str) -> str:
        """
        获取对应的MD文件路径

        Args:
            file_path: 原始文件路径

        Returns:
            str: MD文件路径
        """
        # 获取文件名（不含扩展名）
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]

        # 构造MD文件路径
        md_file_path = os.path.join('output', f'{name_without_ext}.md')
        return md_file_path

    def extract_bid_price(self, file_path: str) -> Optional[float]:
        """
        提取投标总价

        Args:
            file_path: 文件路径

        Returns:
            Optional[float]: 投标总价
        """
        try:
            self.logger.info(f'开始提取投标总价: {file_path}')

            # 获取MD文件路径
            md_file_path = self._get_md_file_path(file_path)
            self.logger.info(f'MD文件路径: {md_file_path}')

            # 优先从MD文件提取价格
            if os.path.exists(md_file_path):
                self.logger.info(f'MD文件存在，从中提取价格: {md_file_path}')
                from modules.md_price_extractor import MDPriceExtractor

                md_extractor = MDPriceExtractor()
                price = md_extractor.extract_price_from_md_file(md_file_path)
                if price is not None and price > 0:
                    self.logger.info(f'从MD文件成功提取到价格: {price}')
                    return float(price)
                else:
                    self.logger.warning(f'从MD文件未提取到有效价格: {md_file_path}')

            # 如果MD文件不存在或提取失败，则回退到从PDF提取
            self.logger.info(f'回退到从PDF文件提取价格: {file_path}')
            pdf_processor = PDFProcessor(file_path=file_path, file_type='bid')
            pages = pdf_processor.extract_text_per_page()
            if not pages:
                self.logger.error(f'从PDF文件提取文本失败: {file_path}')
                return None

            price = self.price_manager.extract_and_select_price(pages)
            if price is not None and price > 0:
                self.logger.info(f'从PDF文件成功提取到价格: {price}')
                return float(price)
            else:
                self.logger.warning(f'从PDF文件未提取到有效价格: {file_path}')
                return None

        except Exception as e:
            self.logger.error(f'提取投标总价时出错: {e}', exc_info=True)
            return None

    def save_bidder_info_to_db(
        self, bid_document_id: int, bidder_name: str, bid_price: Optional[float]
    ):
        """
        将投标人信息保存到数据库

        Args:
            bid_document_id: 投标文件ID
            bidder_name: 投标人名称
            bid_price: 投标总价
        """
        try:
            # 更新投标文件记录
            bid_document = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == bid_document_id)
                .first()
            )

            if bid_document:
                bid_document.bidder_name = bidder_name
                bid_document.price_extracted = True
                bid_document.price_extraction_error = ''
                self.db.commit()
                self.logger.info(f'更新投标文件记录: {bidder_name}')

            # 更新或创建分析结果记录
            analysis_result = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == bid_document_id)
                .first()
            )

            if analysis_result:
                analysis_result.bidder_name = bidder_name
                if bid_price is not None:
                    analysis_result.extracted_price = bid_price
            else:
                # 创建新的分析结果记录
                bid_document_project_id = (
                    getattr(bid_document, 'project_id', 0)
                    if bid_document and hasattr(bid_document, 'project_id')
                    else 0
                )
                analysis_result = AnalysisResult(
                    project_id=bid_document_project_id,
                    bid_document_id=bid_document_id,
                    bidder_name=bidder_name,
                    extracted_price=bid_price if bid_price is not None else 0.0,
                    total_score=0.0,
                    price_score=0.0,
                    detailed_scores={},
                    analysis_summary='',
                    scoring_method='AI',
                    is_modified=False,
                    original_scores={},
                    modification_count=0,
                    last_modified_at=datetime.datetime.now(),
                    last_modified_by='system',
                )
                self.db.add(analysis_result)

            self.db.commit()
            self.logger.info(f'保存投标人信息到数据库: {bidder_name} - {bid_price}')

        except Exception as e:
            self.logger.error(f'保存投标人信息到数据库时出错: {e}')
            self.db.rollback()


def create_bidder_price_array(bidders_info: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    创建投标人价格数组
    格式: {"投标人名称1": 投标人1的投标总价, "投标人名称2": 投标人2的投标总价, ...}

    Args:
        bidders_info: 投标人信息列表

    Returns:
        Dict[str, float]: 投标人价格字典
    """
    bidder_price_dict = {}

    for bidder in bidders_info:
        bidder_name = bidder.get('bidder_name')
        bid_price = bidder.get('bid_price')

        if bidder_name and bid_price is not None:
            bidder_price_dict[bidder_name] = bid_price

    return bidder_price_dict
