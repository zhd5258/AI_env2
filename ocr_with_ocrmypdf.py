#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
使用OCRmyPDF处理PDF文件的指定页面范围
OCRmyPDF是一个专门用于PDF OCR处理的工具，比Tesseract直接处理PDF效果更好
"""

import os
import subprocess
import sys
from PyPDF2 import PdfReader, PdfWriter


def check_ocrmypdf_installed():
    """
    检查OCRmyPDF是否已安装
    """
    print('开始检查OCRmyPDF是否已安装...')
    print('当前工作目录:', os.getcwd())
    print('PATH环境变量:', os.environ.get('PATH'))

    # 尝试多种方式查找ocrmypdf
    ocrmypdf_paths = [
        '/home/kr/.local/bin/ocrmypdf',  # pipx安装的路径
        'ocrmypdf',  # 直接使用命令名
    ]

    # 通过which命令查找ocrmypdf路径
    try:
        print('尝试使用which命令查找ocrmypdf...')
        which_result = subprocess.run(
            ['which', 'ocrmypdf'], capture_output=True, text=True, timeout=10
        )
        print(
            'which命令执行结果: 返回码={}, 输出={}'.format(
                which_result.returncode, which_result.stdout.strip()
            )
        )
        if which_result.returncode == 0 and which_result.stdout.strip():
            ocrmypdf_paths.insert(0, which_result.stdout.strip())
            print('通过which命令找到ocrmypdf路径:', which_result.stdout.strip())
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        print('which命令执行失败:', e)

    # 尝试各个路径
    for i, ocrmypdf_path in enumerate(ocrmypdf_paths):
        try:
            print('尝试路径{}: {}'.format(i + 1, ocrmypdf_path))
            result = subprocess.run(
                [ocrmypdf_path, '--version'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            print(f'OCRmyPDF版本: {result.stdout.strip()}')
            print('成功找到OCRmyPDF，使用路径:', ocrmypdf_path)
            return ocrmypdf_path
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            print('路径{}失败: {}'.format(i + 1, e))
            continue

    # 如果所有路径都失败了，打印错误信息
    print('OCRmyPDF未安装，请先安装:')
    print('pip install ocrmypdf')
    print('注意：OCRmyPDF还需要安装Tesseract OCR和Ghostscript')
    print('已尝试的路径:')
    for path in ocrmypdf_paths:
        print(f'  - {path}')
    return None


def ocr_pdf_pages(input_pdf, output_pdf, output_text, start_page=1, end_page=None):
    """
    使用OCRmyPDF处理PDF文件的指定页面范围
    :param input_pdf: 输入的PDF文件路径
    :param output_pdf: 输出的PDF文件路径
    :param output_text: 输出的文本文件路径
    :param start_page: 开始页码（从1开始）
    :param end_page: 结束页码（从1开始），如果为None则处理到最后一页
    """
    ocrmypdf_path = check_ocrmypdf_installed()
    if not ocrmypdf_path:
        return False

    # 检查输入文件是否存在
    if not os.path.exists(input_pdf):
        print(f'输入文件不存在: {input_pdf}')
        return False

    # 读取PDF文件
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    if end_page is None:
        end_page = total_pages

    # 检查页码范围是否有效
    if start_page < 1 or end_page > total_pages or start_page > end_page:
        print('无效的页码范围')
        return False

    # 创建输出PDF文件
    writer = PdfWriter()

    # 处理指定页面范围
    for page_num in range(start_page - 1, end_page):
        page = reader.pages[page_num]
        writer.add_page(page)

    # 保存临时PDF文件
    temp_pdf = 'temp.pdf'
    with open(temp_pdf, 'wb') as f:
        writer.write(f)

    # 确保lang变量有默认值
    global lang
    if 'lang' not in globals():
        lang = 'chi_sim+eng'  # 设置默认语言组合
    
    # 构建OCRmyPDF命令
    # 移除了 --clean 和 --remove-background 参数，因为它们依赖于 unpaper 工具
    # 移除了 --skip-text 参数，因为它与 --force-ocr 冲突
    # 修复了 --threshold 参数错误和 --tesseract-timeout 参数位置
    cmd = [
        ocrmypdf_path,  # 使用完整路径
        '--language',
        lang,  # 指定OCR语言
        '--output-type',
        'pdf',  # 输出PDF格式，避免PDF/A可能的编码问题
        '--force-ocr',  # 强制OCR（即使页面已有文本）
        '--deskew',  # 矫正倾斜的页面
        '--rotate-pages',  # 自动旋转页面
        '--pdf-renderer',
        'hocr',  # 使用hocr渲染器可能有助于解决文本编码问题
        '--sidecar',
        output_text,  # sidecar文本文件路径
        '--tesseract-timeout',  # 将超时参数放在输入文件之前
        '120',  # 增加超时时间到120秒，以提高识别质量
        temp_pdf,  # 输入PDF文件（临时文件）
        output_pdf  # 输出PDF文件
    ]

    print(f'执行命令: {" ".join(cmd)}')
    print('正在执行OCR处理，这可能需要几分钟...')

    try:
        # 执行OCRmyPDF命令
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print('OCR处理完成！')
            if result.stdout:
                print(f'标准输出: {result.stdout}')
            # 清理临时文件
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            return True
        else:
            print(f'OCR处理失败，返回码: {result.returncode}')
            if result.stderr:
                print(f'错误信息: {result.stderr}')
            # 清理临时文件
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            return False

    except subprocess.SubprocessError as e:
        print(f'执行OCRmyPDF时出错: {e}')
        # 清理临时文件
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
        return False
    except Exception as e:
        print(f'OCR处理过程中发生错误: {e}')
        # 清理临时文件
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
        return False


def select_file():
    """
    使用文件选择器选择PDF文件（如果tkinter可用）
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # 创建根窗口
        root = tk.Tk()
        root.title("选择要OCR处理的PDF文件")
        
        # 设置窗口尺寸为原来的三倍
        root.geometry("900x600")  # 原来大约是 300x200
        
        # 设置文件选择器属性
        file_path = filedialog.askopenfilename(
            parent=root,
            title="选择要OCR处理的PDF文件",
            filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        # 销毁根窗口
        root.destroy()
        
        return file_path
    except ImportError:
        print("未安装tkinter，无法使用图形文件选择器")
        return None
    except Exception as e:
        print(f"文件选择器出现错误: {e}")
        return None


# 使用示例
if __name__ == '__main__':
    # 检查是否提供了命令行参数
    if len(sys.argv) > 1:
        input_pdf = sys.argv[1]
        print(f"使用命令行参数指定的文件: {input_pdf}")
    else:
        # 尝试使用文件选择器
        print("请选择要处理的PDF文件:")
        # input_pdf = select_file()
        input_pdf = r'/media/kr/软件/user/设备管理/招标评标资料/2025/旧油漆线改造/集装箱/广东创智智能装备有限公司投标文件OCR.pdf'
        # 如果文件选择器不可用或用户未选择文件，则提示用户通过命令行输入
        if not input_pdf:
            print("请输入要处理的PDF文件路径:")
            input_pdf = input().strip()
            
        # 如果仍然没有选择文件，则退出
        if not input_pdf:
            print("未选择文件，程序退出。")
            sys.exit(1)
    
    # 检查输入文件是否存在
    if not os.path.exists(input_pdf):
        print(f"文件不存在: {input_pdf}")
        sys.exit(1)
    
    # 检查文件扩展名
    if not input_pdf.lower().endswith('.pdf'):
        print("警告: 选择的文件可能不是PDF文件")
        confirm = input("是否继续处理？(y/N): ").strip().lower()
        if confirm != 'y':
            sys.exit(1)
    
    # 根据输入文件名自动生成输出文件名
    base_name = os.path.splitext(os.path.basename(input_pdf))[0]
    output_pdf = f'{base_name}_ocr.pdf'
    output_text = f'{base_name}_text.txt'

    # OCR处理指定页面范围（例如第1页到第1页）
    try:
        print('=== 使用OCRmyPDF处理PDF ===')
        print(f'输入文件: {input_pdf}')
        print(f'输出PDF文件: {output_pdf}')
        print(f'输出文本文件: {output_text}')
        
        success = ocr_pdf_pages(
            input_pdf, output_pdf, output_text, start_page=103, end_page=103
        )  # 处理第1页到第1页
        if success:
            print('OCR处理完成！')
        else:
            print('OCR处理失败！')
    except Exception as e:
        print(f'发生错误: {e}')
        import traceback

        traceback.print_exc()

    