#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
查看分析结果详细评分的GUI工具
提供图形界面选择项目和投标文件，并展示analysis_result表中detailed_scores字段的值
"""

import sys
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.database import SessionLocal, TenderProject, BidDocument, AnalysisResult


def get_projects():
    """获取所有项目"""
    db = SessionLocal()
    try:
        projects = db.query(TenderProject).all()
        return [(p.id, p.name) for p in projects]
    except Exception as e:
        print(f'获取项目列表时出错: {e}')
        return []
    finally:
        db.close()


def get_bid_documents(project_id):
    """获取指定项目的所有投标文件"""
    db = SessionLocal()
    try:
        bid_docs = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
        )
        return [(d.id, d.bidder_name) for d in bid_docs]
    except Exception as e:
        print(f'获取投标文件列表时出错: {e}')
        return []
    finally:
        db.close()


def get_analysis_result(bid_document_id):
    """获取指定投标文件的分析结果"""
    db = SessionLocal()
    try:
        result = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.bid_document_id == bid_document_id)
            .first()
        )
        return result
    except Exception as e:
        print(f'获取分析结果时出错: {e}')
        return None
    finally:
        db.close()


class AnalysisResultViewer:
    def __init__(self, root):
        self.root = root
        self.root.title('分析结果查看器')
        self.root.geometry('1200x800')

        # 创建主框架
        self.main_frame = ttk.Frame(root, padding='10')
        self.main_frame.grid(row=0, column=0, sticky='nesw')

        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(2, weight=1)

        # 创建选择框架
        self.selection_frame = ttk.LabelFrame(
            self.main_frame, text='选择项目和投标文件', padding='10'
        )
        self.selection_frame.grid(
            row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10)
        )

        # 项目选择
        ttk.Label(self.selection_frame, text='项目:').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5)
        )
        self.project_var = tk.StringVar()
        self.project_combo = ttk.Combobox(
            self.selection_frame, textvariable=self.project_var, width=50
        )
        self.project_combo.grid(row=0, column=1, sticky='ew', padx=(0, 10))
        self.project_combo.bind('<<ComboboxSelected>>', self.on_project_selected)

        # 投标文件选择
        ttk.Label(self.selection_frame, text='投标文件:').grid(
            row=0, column=2, sticky=tk.W, padx=(0, 5)
        )
        self.bid_document_var = tk.StringVar()
        self.bid_document_combo = ttk.Combobox(
            self.selection_frame, textvariable=self.bid_document_var, width=50
        )
        self.bid_document_combo.grid(row=0, column=3, sticky='ew')
        self.bid_document_combo.bind(
            '<<ComboboxSelected>>', self.on_bid_document_selected
        )

        # 刷新按钮
        self.refresh_btn = ttk.Button(
            self.selection_frame, text='刷新', command=self.refresh_data
        )
        self.refresh_btn.grid(row=0, column=4, padx=(10, 0))

        # 加载项目数据
        self.load_projects()

        # 创建结果显示框架
        self.result_frame = ttk.LabelFrame(
            self.main_frame, text='分析结果详情', padding='10'
        )
        self.result_frame.grid(
            row=1, column=0, columnspan=2, sticky='nesw', pady=(0, 10)
        )
        self.result_frame.columnconfigure(0, weight=1)
        self.result_frame.rowconfigure(1, weight=1)

        # 基本信息显示
        self.info_frame = ttk.Frame(self.result_frame)
        self.info_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.info_frame.columnconfigure(1, weight=1)

        ttk.Label(self.info_frame, text='投标人:').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5)
        )
        self.bidder_name_label = ttk.Label(self.info_frame, text='')
        self.bidder_name_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(self.info_frame, text='总分:').grid(
            row=0, column=2, sticky=tk.W, padx=(20, 5)
        )
        self.total_score_label = ttk.Label(self.info_frame, text='')
        self.total_score_label.grid(row=0, column=3, sticky=tk.W)

        ttk.Label(self.info_frame, text='价格分:').grid(
            row=0, column=4, sticky=tk.W, padx=(20, 5)
        )
        self.price_score_label = ttk.Label(self.info_frame, text='')
        self.price_score_label.grid(row=0, column=5, sticky=tk.W)

        ttk.Label(self.info_frame, text='提取价格:').grid(
            row=0, column=6, sticky=tk.W, padx=(20, 5)
        )
        self.extracted_price_label = ttk.Label(self.info_frame, text='')
        self.extracted_price_label.grid(row=0, column=7, sticky=tk.W)

        # 详细评分显示
        self.scores_frame = ttk.Frame(self.result_frame)
        self.scores_frame.grid(row=1, column=0, sticky='nesw')
        self.scores_frame.columnconfigure(0, weight=1)
        self.scores_frame.rowconfigure(0, weight=1)

        # 创建原始数据查看框架
        self.raw_data_frame = ttk.LabelFrame(
            self.main_frame, text='原始数据查看', padding='10'
        )
        self.raw_data_frame.grid(row=2, column=0, columnspan=2, sticky='nesw')
        self.raw_data_frame.columnconfigure(0, weight=1)
        self.raw_data_frame.rowconfigure(0, weight=1)

        # 添加标签页控件来切换视图
        self.notebook = ttk.Notebook(self.raw_data_frame)
        self.notebook.grid(row=0, column=0, sticky='nesw')

        # 详细评分标签页
        self.scores_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.scores_tab, text='详细评分')
        self.scores_tab.columnconfigure(0, weight=1)
        self.scores_tab.rowconfigure(0, weight=1)

        # 原始数据标签页
        self.raw_data_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_data_tab, text='原始数据')
        self.raw_data_tab.columnconfigure(0, weight=1)
        self.raw_data_tab.rowconfigure(0, weight=1)

        # 创建Treeview来显示详细评分
        self.tree = ttk.Treeview(
            self.scores_tab,
            columns=('规则名称', '满分', '得分', '理由'),
            show='headings',
        )
        self.tree.heading('规则名称', text='规则名称')
        self.tree.heading('满分', text='满分')
        self.tree.heading('得分', text='得分')
        self.tree.heading('理由', text='理由')

        # 设置列宽
        self.tree.column('规则名称', width=300)
        self.tree.column('满分', width=80, anchor=tk.CENTER)
        self.tree.column('得分', width=80, anchor=tk.CENTER)
        self.tree.column('理由', width=500)

        # 添加滚动条
        tree_scroll_y = ttk.Scrollbar(
            self.scores_tab, orient=tk.VERTICAL, command=self.tree.yview
        )
        tree_scroll_x = ttk.Scrollbar(
            self.scores_tab, orient=tk.HORIZONTAL, command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set
        )

        # 布局Treeview和滚动条
        self.tree.grid(row=0, column=0, sticky='nesw')
        tree_scroll_y.grid(row=0, column=1, sticky='ns')
        tree_scroll_x.grid(row=1, column=0, sticky='ew')

        # 配置scores_tab的行和列权重
        self.scores_tab.rowconfigure(0, weight=1)
        self.scores_tab.columnconfigure(0, weight=1)

        # 在原始数据标签页中放置文本框
        self.raw_data_text = scrolledtext.ScrolledText(
            self.raw_data_tab, width=80, height=20
        )
        self.raw_data_text.grid(row=0, column=0, sticky='nesw', padx=5, pady=5)
        self.raw_data_text.columnconfigure(0, weight=1)
        self.raw_data_text.rowconfigure(0, weight=1)

        # 添加垂直滚动条到原始数据文本框
        raw_data_scroll = ttk.Scrollbar(
            self.raw_data_tab, orient=tk.VERTICAL, command=self.raw_data_text.yview
        )
        raw_data_scroll.grid(row=0, column=1, sticky='ns')
        self.raw_data_text.configure(yscrollcommand=raw_data_scroll.set)

    def load_projects(self):
        """加载项目列表"""
        projects = get_projects()
        self.project_combo['values'] = [f'{p[0]} - {p[1]}' for p in projects]
        self.project_map = {f'{p[0]} - {p[1]}': p[0] for p in projects}

    def on_project_selected(self, event=None):
        """当项目被选择时"""
        selected = self.project_var.get()
        if selected and selected in self.project_map:
            project_id = self.project_map[selected]
            self.load_bid_documents(project_id)

    def load_bid_documents(self, project_id):
        """加载投标文件列表"""
        bid_docs = get_bid_documents(project_id)
        self.bid_document_combo['values'] = [f'{d[0]} - {d[1]}' for d in bid_docs]
        self.bid_document_map = {f'{d[0]} - {d[1]}': d[0] for d in bid_docs}

    def on_bid_document_selected(self, event=None):
        """当投标文件被选择时"""
        selected = self.bid_document_var.get()
        if selected and selected in self.bid_document_map:
            bid_document_id = self.bid_document_map[selected]
            self.display_analysis_result(bid_document_id)

    def display_analysis_result(self, bid_document_id):
        """显示分析结果"""
        result = get_analysis_result(bid_document_id)
        if not result:
            messagebox.showwarning('警告', '未找到分析结果')
            return

        # 显示基本信息
        self.bidder_name_label.config(text=result.bidder_name or '未知')
        self.total_score_label.config(text=str(result.total_score or 0))
        self.price_score_label.config(text=str(result.price_score or 0))
        self.extracted_price_label.config(text=str(result.extracted_price or 0))

        # 清空Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 解析并显示详细评分
        detailed_scores = result.detailed_scores

        # 只有在确实是字符串时才尝试解析
        if isinstance(detailed_scores, str):
            try:
                detailed_scores = json.loads(detailed_scores)
            except json.JSONDecodeError:
                detailed_scores = []

        if isinstance(detailed_scores, list):
            for score_item in detailed_scores:
                if isinstance(score_item, dict):
                    rule_name = score_item.get('Child_Item_Name', '未知规则')
                    max_score = score_item.get('max_score', 0)
                    score = score_item.get('score', 0)
                    reason = score_item.get('reason', '')

                    # 如果是定性规则，显示结果而不是分数
                    if 'result' in score_item:
                        score = score_item.get('result', '未知')
                        reason = score_item.get('reason', '')

                    self.tree.insert(
                        '', tk.END, values=(rule_name, max_score, score, reason)
                    )
        else:
            print(f'Warning: detailed_scores is not a list: {type(detailed_scores)}')

        # 显示原始数据
        self.raw_data_text.delete(1.0, tk.END)
        try:
            # 格式化显示原始数据
            formatted_data = json.dumps(detailed_scores, ensure_ascii=False, indent=2)
            self.raw_data_text.insert(tk.END, formatted_data)
        except Exception as e:
            self.raw_data_text.insert(tk.END, f'无法格式化显示原始数据: {e}\n')
            self.raw_data_text.insert(tk.END, str(detailed_scores))

    def refresh_data(self):
        """刷新数据"""
        # 重新加载项目列表
        self.load_projects()

        # 清空投标文件列表
        self.bid_document_combo['values'] = []
        self.bid_document_var.set('')

        # 清空显示
        self.bidder_name_label.config(text='')
        self.total_score_label.config(text='')
        self.price_score_label.config(text='')
        self.extracted_price_label.config(text='')

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.raw_data_text.delete(1.0, tk.END)


def main():
    """主函数"""
    root = tk.Tk()
    app = AnalysisResultViewer(root)
    root.mainloop()


if __name__ == '__main__':
    main()
