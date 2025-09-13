#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
重新处理江西中霖环境科技集团有限公司投标文件的价格
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, BidDocument
from modules.pdf_processor import PDFProcessor
from modules.price_manager import PriceManager

def reprocess_jiangxi_price():
    """
    重新处理江西中霖环境科技集团有限公司投标文件的价格
    """
    print("重新处理江西中霖环境科技集团有限公司投标文件的价格")
    print("=" * 60)
    
    try:
        session = SessionLocal()
        
        # 查找江西中霖环境科技集团有限公司的投标文档（项目6中的）
        jiangxi_doc = session.query(BidDocument).filter(
            BidDocument.project_id == 6,
            BidDocument.bidder_name == "江西中霖环境科技集团有限公司"
        ).first()
        
        if not jiangxi_doc:
            print("错误：未找到江西中霖环境科技集团有限公司的投标文档")
            return
            
        print(f"找到投标文档:")
        print(f"  ID: {jiangxi_doc.id}")
        print(f"  投标方: {jiangxi_doc.bidder_name}")
        print(f"  文件路径: {jiangxi_doc.file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(jiangxi_doc.file_path):
            print(f"错误：文件不存在 {jiangxi_doc.file_path}")
            return
        
        # 处理PDF文件提取价格
        print("\n处理PDF文件提取价格...")
        processor = PDFProcessor(jiangxi_doc.file_path)
        pages = processor.process_pdf_per_page()
        print(f"提取到 {len(pages)} 页文本")
        
        # 提取价格
        price_manager = PriceManager()
        prices = price_manager.extract_prices_from_content(pages)
        best_price = price_manager.select_best_price(prices, pages)
        
        print(f"\n提取到 {len(prices)} 个价格")
        print(f"选择的最佳价格: {best_price}")
        
        # 显示置信度最高的几个价格
        sorted_prices = sorted(prices, key=lambda x: x['confidence'], reverse=True)
        print("\n置信度最高的几个价格:")
        for i, price_info in enumerate(sorted_prices[:5]):
            print(f"  {i+1}. {price_info['value']} (置信度: {price_info['confidence']}, 来源页: {price_info['page']+1})")
        
        # 更新数据库中的价格
        if best_price is not None:
            print(f"\n更新数据库中的价格...")
            if jiangxi_doc.analysis_result:
                old_price = jiangxi_doc.analysis_result.extracted_price
                jiangxi_doc.analysis_result.extracted_price = float(best_price)
                
                # 同时更新详细评分中的价格项
                if jiangxi_doc.analysis_result.detailed_scores:
                    try:
                        scores = json.loads(jiangxi_doc.analysis_result.detailed_scores) \
                            if isinstance(jiangxi_doc.analysis_result.detailed_scores, str) \
                            else jiangxi_doc.analysis_result.detailed_scores
                        
                        # 查找并更新价格评分项
                        for score_item in scores:
                            if score_item.get('is_price_criteria', False):
                                score_item['extracted_price'] = float(best_price)
                                # 更新理由
                                score_item['reason'] = f'根据价格评分规则计算得出。提取到的报价为: {best_price}'
                                break
                        
                        # 保存更新后的详细评分
                        jiangxi_doc.analysis_result.detailed_scores = json.dumps(scores, ensure_ascii=False)
                    except Exception as e:
                        print(f"更新详细评分时出错: {e}")
                
                session.commit()
                print(f"价格更新成功: {old_price} -> {best_price}")
            else:
                print("错误：未找到分析结果")
        else:
            print("错误：未能提取到有效价格")
        
        session.close()
        print("\n处理完成!")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reprocess_jiangxi_price()