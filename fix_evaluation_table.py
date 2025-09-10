#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-07 12:33:55
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-07 12:33:58
# 文件相对于项目的路径   : \AI_env2\fix_evaluation_table.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复评标办法表格生成功能
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, AnalysisResult
from modules.excel_processor import ExcelProcessor


def fix_evaluation_table():
    """修复评标办法表格生成"""
    db = SessionLocal()
    try:
        # 获取最新的项目ID（假设为49）
        project_id = 49

        # 获取分析结果
        results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .all()
        )

        if not results:
            print('未找到分析结果')
            return

        # 转换结果数据格式
        response_data = []
        for res in results:
            response_data.append(
                {
                    'bidder_name': res.bidder_name,
                    'total_score': res.total_score,
                    'detailed_scores': json.loads(res.detailed_scores)
                    if isinstance(res.detailed_scores, str)
                    else res.detailed_scores,
                    'ai_model': res.ai_model,
                }
            )

        print('分析结果:')
        for res in response_data:
            print(f'  投标方: {res["bidder_name"]}, 总分: {res["total_score"]}')

        # 使用Excel处理器生成评标办法表格
        processor = ExcelProcessor()

        # 生成评标办法表格
        evaluation_table = processor.generate_evaluation_table(response_data)

        print('\n生成的评标办法表格:')
        print(json.dumps(evaluation_table, ensure_ascii=False, indent=2))

        print('\n修复完成！评标办法表格已正确生成。')

    except Exception as e:
        print(f'修复评标办法表格时出错: {e}')
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == '__main__':
    fix_evaluation_table()
