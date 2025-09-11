import pandas as pd
import json
import os
from typing import List, Dict, Any


class ExcelProcessor:
    """
    一个用于处理Excel文件的通用工具类。
    （注意：原有的基于特定模板“评价.xlsx”的评分规则提取和汇总表生成逻辑已被移除，
    因为系统现在直接从招标文件动态提取规则并生成汇总表。）
    """
    def __init__(self, excel_file_path: str = None):
        self.excel_file_path = excel_file_path
        self.df = None
        if excel_file_path:
            self._load_excel()

    def _load_excel(self):
        """加载Excel文件"""
        if self.excel_file_path and os.path.exists(self.excel_file_path):
            self.df = pd.read_excel(self.excel_file_path)
        else:
            # 不再抛出错误，因为这个类现在是通用的
            print(f"Warning: Excel file not found at {self.excel_file_path}")

    # 可以根据未来的需求在这里添加通用的Excel处理方法
    # 例如：
    # def read_sheet_to_dict(self, sheet_name=0):
    #     if self.df is not None:
    #         return self.df.to_dict(orient='records')
    #     return None