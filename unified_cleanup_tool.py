#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一清理工具
合并了数据库清理和临时文件清理功能，提供图形界面选择清理内容
"""

import os
import shutil
import sqlite3
import logging
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Dict, List, Callable
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入数据库模块
try:
    from modules.database import (
        SessionLocal,
        TenderProject,
        BidDocument,
        AnalysisResult,
        ScoringRule,
        ScoreModificationHistory,
        ProjectAuditLog,
    )

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logger.warning('数据库模块不可用，跳过数据库清理功能')

# 定义需要保留的根目录配置文件
ROOT_CONFIG_FILES = [
    'config.json',
    'settings.json',
    'runtime_config.json',
    'runtime_settings.json',
    'MinerU_API_token.txt',
    'pyproject.toml',
    'setup.cfg',
    '.pylintrc',
]


class UnifiedCleanupTool:
    """统一清理工具"""

    def __init__(self):
        self.root = None
        self.progress_var = None
        self.progress_bar = None
        self.progress_label = None
        self.log_text = None
        self.start_button = None
        self.cleanup_options = {}
        self.is_running = False

        # 定义清理选项
        self.cleanup_items = {
            'temp_uploads': {
                'name': '临时上传文件 (temp_uploads)',
                'description': '清理上传过程中的临时文件',
                'type': 'directory',
                'path': 'temp_uploads',
                'default': True,
            },
            'temp_word': {
                'name': '临时文档文件 (temp_word)',
                'description': '清理PDF转换的临时文档文件',
                'type': 'directory',
                'path': 'temp_word',
                'default': True,
            },
            'uploads': {
                'name': '上传文件 (uploads)',
                'description': '清理所有已上传的文件',
                'type': 'directory',
                'path': 'uploads',
                'default': False,
            },
            'temp_pdf_cache': {
                'name': 'PDF缓存文件 (temp_pdf_cache)',
                'description': '清理PDF处理缓存文件',
                'type': 'directory',
                'path': 'temp_pdf_cache',
                'default': True,
            },
            'root_temp_files': {
                'name': '根目录临时文件',
                'description': '清理根目录下的非必要JSON/TXT文件',
                'type': 'function',
                'function': self._clean_root_temp_files,
                'default': True,
            },
            'database': {
                'name': '数据库内容',
                'description': '清空数据库中的所有数据（保留表结构）',
                'type': 'function',
                'function': self._clean_database,
                'default': False,
            },
            'log_files': {
                'name': '日志文件',
                'description': '清理项目生成的日志文件',
                'type': 'pattern',
                'patterns': ['*.log', '*.log.*'],
                'default': True,
            },
        }

    def create_gui(self):
        """创建图形界面"""
        self.root = tk.Tk()
        self.root.title('统一清理工具')
        self.root.geometry('600x700')
        self.root.resizable(False, False)

        # 设置窗口居中
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.root.winfo_screenheight() // 2) - (700 // 2)
        self.root.geometry(f'600x700+{x}+{y}')

        # 创建主框架
        main_frame = ttk.Frame(self.root, padding='10')
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 标题
        title_label = ttk.Label(
            main_frame, text='统一清理工具', font=('微软雅黑', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # 清理选项框架
        options_frame = ttk.LabelFrame(
            main_frame, text='选择要清理的内容', padding='10'
        )
        options_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10)
        )

        # 创建清理选项复选框
        self.cleanup_options = {}
        row = 0
        for key, item in self.cleanup_items.items():
            var = tk.BooleanVar(value=item['default'])
            self.cleanup_options[key] = var

            checkbox = ttk.Checkbutton(options_frame, text=item['name'], variable=var)
            checkbox.grid(row=row, column=0, sticky=tk.W, pady=2)

            # 添加描述标签
            desc_label = ttk.Label(
                options_frame,
                text=item['description'],
                foreground='gray',
                font=('微软雅黑', 8),
            )
            desc_label.grid(row=row, column=1, sticky=tk.W, padx=(10, 0), pady=2)

            row += 1

        # 全选/全不选按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(button_frame, text='全选', command=self._select_all).grid(
            row=0, column=0, padx=(0, 5)
        )

        ttk.Button(button_frame, text='全不选', command=self._deselect_all).grid(
            row=0, column=1, padx=5
        )

        ttk.Button(
            button_frame, text='推荐选择', command=self._select_recommended
        ).grid(row=0, column=2, padx=(5, 0))

        # 进度条
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10)
        )

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        self.progress_label = ttk.Label(progress_frame, text='就绪')
        self.progress_label.grid(row=0, column=1)

        progress_frame.columnconfigure(0, weight=1)

        # 日志显示区域
        log_frame = ttk.LabelFrame(main_frame, text='清理日志', padding='5')
        log_frame.grid(
            row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10)
        )

        # 创建文本框和滚动条
        text_frame = ttk.Frame(log_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.log_text = tk.Text(
            text_frame, height=15, width=70, wrap=tk.WORD, font=('Consolas', 9)
        )
        scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        # 操作按钮
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))

        self.start_button = ttk.Button(
            action_frame,
            text='开始清理',
            command=self._start_cleanup,
            style='Accent.TButton',
        )
        self.start_button.grid(row=0, column=0, padx=(0, 10))

        ttk.Button(action_frame, text='清空日志', command=self._clear_log).grid(
            row=0, column=1, padx=10
        )

        ttk.Button(action_frame, text='退出', command=self.root.quit).grid(
            row=0, column=2, padx=(10, 0)
        )

        # 配置权重
        main_frame.rowconfigure(4, weight=1)
        main_frame.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

    def _select_all(self):
        """全选所有清理选项"""
        for var in self.cleanup_options.values():
            var.set(True)

    def _deselect_all(self):
        """取消选择所有清理选项"""
        for var in self.cleanup_options.values():
            var.set(False)

    def _select_recommended(self):
        """选择推荐的清理选项"""
        for key, var in self.cleanup_options.items():
            var.set(self.cleanup_items[key]['default'])

    def _clear_log(self):
        """清空日志显示"""
        self.log_text.delete(1.0, tk.END)

    def _log_message(self, message: str, level: str = 'INFO'):
        """在GUI中显示日志消息"""
        if self.log_text:
            timestamp = time.strftime('%H:%M:%S')
            log_line = f'[{timestamp}] {level}: {message}\n'

            self.log_text.insert(tk.END, log_line)
            self.log_text.see(tk.END)  # 自动滚动到底部
            self.root.update_idletasks()

        # 同时输出到控制台
        if level == 'ERROR':
            logger.error(message)
        elif level == 'WARNING':
            logger.warning(message)
        else:
            logger.info(message)

    def _update_progress(self, value: float, text: str):
        """更新进度条"""
        if self.progress_var and self.progress_label:
            self.progress_var.set(value)
            self.progress_label.config(text=text)
            self.root.update_idletasks()

    def _start_cleanup(self):
        """开始清理操作"""
        if self.is_running:
            return

        # 获取选中的清理项
        selected_items = [key for key, var in self.cleanup_options.items() if var.get()]

        if not selected_items:
            messagebox.showwarning('警告', '请至少选择一个清理项！')
            return

        # 确认对话框
        items_text = '\n'.join(
            [f'• {self.cleanup_items[key]["name"]}' for key in selected_items]
        )
        confirm_msg = (
            f'确定要执行以下清理操作吗？\n\n{items_text}\n\n注意：此操作无法撤销！'
        )

        if not messagebox.askyesno('确认清理', confirm_msg):
            return

        # 在后台线程中执行清理
        self.is_running = True
        self.start_button.config(state='disabled', text='清理中...')
        self._clear_log()

        cleanup_thread = threading.Thread(
            target=self._execute_cleanup, args=(selected_items,), daemon=True
        )
        cleanup_thread.start()

    def _execute_cleanup(self, selected_items: List[str]):
        """执行清理操作"""
        try:
            total_items = len(selected_items)
            self._log_message('开始清理操作...')

            for i, item_key in enumerate(selected_items):
                item = self.cleanup_items[item_key]
                progress = (i / total_items) * 100

                self._update_progress(progress, f'正在清理: {item["name"]}')
                self._log_message(f'正在清理: {item["name"]}')

                try:
                    if item['type'] == 'directory':
                        self._clean_directory(item['path'])
                    elif item['type'] == 'function':
                        item['function']()
                    elif item['type'] == 'pattern':
                        self._clean_by_pattern(item['patterns'])

                    self._log_message(f'✓ 完成: {item["name"]}')

                except Exception as e:
                    self._log_message(f'✗ 失败: {item["name"]} - {str(e)}', 'ERROR')

                time.sleep(0.1)  # 短暂停顿，让界面更新

            self._update_progress(100, '清理完成')
            self._log_message('所有清理操作已完成！')

            messagebox.showinfo('完成', '清理操作已完成！')

        except Exception as e:
            self._log_message(f'清理过程中发生错误: {str(e)}', 'ERROR')
            messagebox.showerror('错误', f'清理过程中发生错误: {str(e)}')

        finally:
            self.is_running = False
            self.start_button.config(state='normal', text='开始清理')

    def _clean_directory(self, directory_path: str, remove_empty_dir: bool = True):
        """清理指定目录"""
        directory = Path(directory_path)

        if not directory.exists():
            self._log_message(f'目录 {directory_path} 不存在，无需清理')
            return

        if not directory.is_dir():
            self._log_message(f'{directory_path} 不是一个目录', 'WARNING')
            return

        file_count = 0
        for item in directory.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    file_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    file_count += 1
            except Exception as e:
                self._log_message(f'删除 {item} 失败: {str(e)}', 'WARNING')

        # 删除空目录
        if remove_empty_dir and not any(directory.iterdir()):
            try:
                directory.rmdir()
                self._log_message(f'已删除空目录: {directory_path}')
            except Exception as e:
                self._log_message(f'删除空目录失败: {str(e)}', 'WARNING')

        self._log_message(f'目录 {directory_path} 清理完成，删除了 {file_count} 个项目')

    def _clean_by_pattern(self, patterns: List[str]):
        """根据文件模式清理文件"""
        import glob

        total_deleted = 0
        for pattern in patterns:
            files = glob.glob(pattern)
            for file_path in files:
                try:
                    os.remove(file_path)
                    total_deleted += 1
                    self._log_message(f'已删除: {file_path}')
                except Exception as e:
                    self._log_message(f'删除 {file_path} 失败: {str(e)}', 'WARNING')

        self._log_message(f'按模式清理完成，删除了 {total_deleted} 个文件')

    def _clean_root_temp_files(self):
        """清理根目录下的临时文件"""
        root_dir = Path('.')
        deleted_count = 0

        for item in root_dir.iterdir():
            if item.is_file() and (
                item.suffix.lower() in ['.json', '.txt', '.tmp', '.temp']
            ):
                if item.name not in ROOT_CONFIG_FILES:
                    try:
                        item.unlink()
                        deleted_count += 1
                        self._log_message(f'已删除根目录临时文件: {item.name}')
                    except Exception as e:
                        self._log_message(f'删除 {item} 失败: {str(e)}', 'WARNING')
                else:
                    self._log_message(f'保留配置文件: {item.name}')

        self._log_message(f'根目录临时文件清理完成，删除了 {deleted_count} 个文件')

    def _clean_database(self):
        """清理数据库"""
        if not DATABASE_AVAILABLE:
            self._log_message('数据库模块不可用，跳过数据库清理', 'WARNING')
            return

        try:
            self._log_message('开始清理数据库...')
            db = SessionLocal()

            # 按照外键依赖顺序删除数据
            tables_cleared = 0

            # 删除有外键依赖的表
            count = db.query(ScoreModificationHistory).count()
            if count > 0:
                db.query(ScoreModificationHistory).delete()
                self._log_message(
                    f'清理 ScoreModificationHistory 表，删除 {count} 条记录'
                )
                tables_cleared += 1

            count = db.query(ProjectAuditLog).count()
            if count > 0:
                db.query(ProjectAuditLog).delete()
                self._log_message(f'清理 ProjectAuditLog 表，删除 {count} 条记录')
                tables_cleared += 1

            count = db.query(AnalysisResult).count()
            if count > 0:
                db.query(AnalysisResult).delete()
                self._log_message(f'清理 AnalysisResult 表，删除 {count} 条记录')
                tables_cleared += 1

            count = db.query(ScoringRule).count()
            if count > 0:
                db.query(ScoringRule).delete()
                self._log_message(f'清理 ScoringRule 表，删除 {count} 条记录')
                tables_cleared += 1

            count = db.query(BidDocument).count()
            if count > 0:
                db.query(BidDocument).delete()
                self._log_message(f'清理 BidDocument 表，删除 {count} 条记录')
                tables_cleared += 1

            count = db.query(TenderProject).count()
            if count > 0:
                db.query(TenderProject).delete()
                self._log_message(f'清理 TenderProject 表，删除 {count} 条记录')
                tables_cleared += 1

            db.commit()
            self._log_message(f'数据库清理完成，清理了 {tables_cleared} 个表')

        except Exception as e:
            self._log_message(f'清理数据库时出错: {str(e)}', 'ERROR')
            if 'db' in locals():
                db.rollback()

        finally:
            if 'db' in locals():
                db.close()

    def run(self):
        """运行GUI"""
        self.create_gui()
        self._log_message('统一清理工具已启动')
        self._log_message("请选择要清理的内容，然后点击'开始清理'")
        self.root.mainloop()


def main():
    """主函数"""
    # 检查是否在正确的目录中运行
    if not os.path.exists('modules'):
        print('错误: 请在项目根目录中运行此脚本')
        return

    try:
        app = UnifiedCleanupTool()
        app.run()
    except Exception as e:
        print(f'程序运行时出错: {e}')
        messagebox.showerror('错误', f'程序运行时出错: {e}')


if __name__ == '__main__':
    main()
