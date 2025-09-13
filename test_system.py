#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统完整测试脚本
测试所有模块的导入和基本功能
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_module_imports():
    """测试所有模块导入"""
    print("测试模块导入...")
    
    try:
        # 测试主应用
        import main
        print("✓ main模块导入成功")
        
        # 测试智能评分提取器
        from modules.scoring_extractor import IntelligentScoringExtractor
        print("✓ 评分提取器模块导入成功")
        
        # 测试智能投标分析器
        from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
        print("✓ 投标分析器模块导入成功")
        
        # 测试价格分计算器
        from modules.price_score_calculator import PriceScoreCalculator
        print("✓ 价格分计算器模块导入成功")
        
        # 测试PDF处理器
        from modules.pdf_processor import PDFProcessor
        print("✓ PDF处理器模块导入成功")
        
        # 测试数据库模块
        from modules.database import SessionLocal, TenderProject, BidDocument, AnalysisResult, ScoringRule
        print("✓ 数据库模块导入成功")
        
        # 测试价格管理器
        from modules.price_manager import PriceManager
        print("✓ 价格管理器模块导入成功")
        
        # 测试投标方名称提取器
        from modules.bidder_name_extractor import extract_bidder_name_from_file
        print("✓ 投标方名称提取器模块导入成功")
        
        # 测试摘要生成器
        from modules.summary_generator import generate_summary_data
        print("✓ 摘要生成器模块导入成功")
        
        print("所有模块导入测试通过!")
        return True
        
    except Exception as e:
        print(f"✗ 模块导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_class_instantiation():
    """测试类实例化"""
    print("\n测试类实例化...")
    
    try:
        # 测试评分提取器
        from modules.scoring_extractor import IntelligentScoringExtractor
        extractor = IntelligentScoringExtractor()
        print("✓ 评分提取器实例化成功")
        
        # 测试价格分计算器
        from modules.price_score_calculator import PriceScoreCalculator
        calculator = PriceScoreCalculator()
        print("✓ 价格分计算器实例化成功")
        
        # 测试PDF处理器
        from modules.pdf_processor import PDFProcessor
        processor = PDFProcessor("test.pdf")  # 使用虚拟路径
        print("✓ PDF处理器实例化成功")
        
        # 测试价格管理器
        from modules.price_manager import PriceManager
        price_manager = PriceManager()
        print("✓ 价格管理器实例化成功")
        
        print("类实例化测试通过!")
        return True
        
    except Exception as e:
        print(f"✗ 类实例化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_connection():
    """测试数据库连接"""
    print("\n测试数据库连接...")
    
    try:
        from modules.database import SessionLocal, engine, TenderProject, BidDocument, AnalysisResult, ScoringRule
        
        # 测试创建会话
        db = SessionLocal()
        print("✓ 数据库会话创建成功")
        
        # 测试查询
        projects = db.query(TenderProject).limit(1).all()
        print("✓ 数据库查询成功")
        
        # 关闭会话
        db.close()
        print("✓ 数据库会话关闭成功")
        
        print("数据库连接测试通过!")
        return True
        
    except Exception as e:
        print(f"✗ 数据库连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始系统完整测试...")
    
    tests = [
        test_module_imports,
        test_class_instantiation,
        test_database_connection
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n测试完成: {passed}/{len(tests)} 个测试通过")
    
    if passed == len(tests):
        print("所有测试通过! 系统正常运行。")
        sys.exit(0)
    else:
        print("部分测试失败!")
        sys.exit(1)