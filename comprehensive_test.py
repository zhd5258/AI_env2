#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试脚本
用于检查所有模块是否能正常工作
"""

def test_all_modules():
    """测试所有模块"""
    print("开始全面测试...")
    
    # 1. 测试数据库模块
    try:
        from modules.database import SessionLocal, TenderProject, BidDocument, AnalysisResult, ScoringRule
        print("✓ 数据库模块导入成功")
    except Exception as e:
        print(f"✗ 数据库模块导入失败: {e}")
        return False
    
    # 2. 测试评分规则提取模块
    try:
        from modules.scoring_extractor import IntelligentScoringExtractor
        extractor = IntelligentScoringExtractor()
        print("✓ 评分规则提取模块导入并实例化成功")
    except Exception as e:
        print(f"✗ 评分规则提取模块导入或实例化失败: {e}")
        return False
    
    # 3. 测试投标文件分析模块
    try:
        from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
        print("✓ 投标文件分析模块导入成功")
    except Exception as e:
        print(f"✗ 投标文件分析模块导入失败: {e}")
        return False
    
    # 4. 测试价格管理模块
    try:
        from modules.price_manager import PriceManager
        price_manager = PriceManager()
        print("✓ 价格管理模块导入并实例化成功")
    except Exception as e:
        print(f"✗ 价格管理模块导入或实例化失败: {e}")
        return False
    
    # 5. 测试价格评分计算器模块
    try:
        from modules.price_score_calculator import PriceScoreCalculator
        price_calculator = PriceScoreCalculator()
        print("✓ 价格评分计算器模块导入并实例化成功")
    except Exception as e:
        print(f"✗ 价格评分计算器模块导入或实例化失败: {e}")
        return False
    
    # 6. 测试PDF处理器模块
    try:
        from modules.pdf_processor import PDFProcessor
        # PDFProcessor需要一个file_path参数，这里只测试导入
        print("✓ PDF处理器模块导入成功")
    except Exception as e:
        print(f"✗ PDF处理器模块导入失败: {e}")
        return False
    
    # 7. 测试AI分析器模块
    try:
        from modules.local_ai_analyzer import LocalAIAnalyzer
        ai_analyzer = LocalAIAnalyzer()
        print("✓ AI分析器模块导入并实例化成功")
    except Exception as e:
        print(f"✗ AI分析器模块导入或实例化失败: {e}")
        return False
    
    # 8. 测试增强价格提取器模块
    try:
        from modules.enhanced_price_extractor import EnhancedPriceExtractor
        price_extractor = EnhancedPriceExtractor()
        print("✓ 增强价格提取器模块导入并实例化成功")
    except Exception as e:
        print(f"✗ 增强价格提取器模块导入或实例化失败: {e}")
        return False
    
    # 9. 测试投标方名称提取器模块
    try:
        from modules.bidder_name_extractor import extract_bidder_name_from_file
        print("✓ 投标方名称提取器模块导入成功")
    except Exception as e:
        print(f"✗ 投标方名称提取器模块导入失败: {e}")
        return False
    
    # 10. 测试Excel处理器模块
    try:
        from modules.excel_processor import ExcelProcessor
        excel_processor = ExcelProcessor()
        print("✓ Excel处理器模块导入并实例化成功")
    except Exception as e:
        print(f"✗ Excel处理器模块导入或实例化失败: {e}")
        return False
    
    # 11. 测试摘要生成器模块
    try:
        from modules.summary_generator import generate_summary_data
        print("✓ 摘要生成器模块导入成功")
    except Exception as e:
        print(f"✗ 摘要生成器模块导入失败: {e}")
        return False
    
    print("\n所有模块测试通过！")
    return True

if __name__ == "__main__":
    success = test_all_modules()
    if success:
        print("✓ 全面测试成功完成")
    else:
        print("✗ 全面测试失败")
        exit(1)