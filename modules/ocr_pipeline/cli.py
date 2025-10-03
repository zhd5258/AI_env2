from __future__ import annotations

import os
import sys
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import click

from ocr_pipeline.pdf_renderer import render_pdf_to_images
from ocr_pipeline.ocr_engine import OCREngine
from ocr_pipeline.postprocess import group_lines_into_blocks
from ocr_pipeline.table_analyzer import TableAnalyzer
from ocr_pipeline.format_exporters import FormatExporter
from ocr_pipeline.models import DocumentResult, PageResult
from ocr_pipeline.io_utils import (
    ensure_dir,
    save_document_json,
    save_page_image,
    save_page_lines_csv,
)


@click.command(name='ocr-pdf')
@click.argument('pdf_path', type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option(
    '--out',
    'out_dir',
    required=True,
    type=click.Path(file_okay=False, path_type=str),
    help='Output directory',
)
@click.option('--dpi', default=300, show_default=True, type=int)
@click.option('--max-side', default=4000, show_default=True, type=int)
@click.option(
    '--lang', default='ch', show_default=True, help='PaddleOCR language, e.g., ch/en'
)
@click.option(
    '--use-gpu/--cpu',
    default=True,
    show_default=True,
    help='使用GPU加速（PaddleOCR 3.2.0）',
)
@click.option(
    '--det-model-dir',
    type=click.Path(exists=True, file_okay=False, path_type=str),
    default=None,
    help='PaddleOCR det model directory',
)
@click.option(
    '--rec-model-dir',
    type=click.Path(exists=True, file_okay=False, path_type=str),
    default=None,
    help='PaddleOCR rec model directory',
)
@click.option(
    '--cls-model-dir',
    type=click.Path(exists=True, file_okay=False, path_type=str),
    default=None,
    help='PaddleOCR cls model directory',
)
@click.option(
    '--contrast',
    default=1.0,
    show_default=True,
    type=float,
    help='Image contrast enhancement factor',
)
@click.option(
    '--sharpen/--no-sharpen',
    default=False,
    show_default=True,
    help='Apply image sharpening',
)
@click.option(
    '--det-limit-side-len',
    default=960,
    show_default=True,
    type=int,
    help='Detection max side length',
)
@click.option(
    '--rec-batch-num',
    default=6,
    show_default=True,
    type=int,
    help='Recognition batch number',
)
@click.option(
    '--enable-mkldnn/--disable-mkldnn',
    default=False,
    show_default=True,
    help='Enable MKL-DNN acceleration',
)
@click.option('--save-csv/--no-save-csv', default=True, show_default=True)
@click.option('--detect-tables/--no-tables', default=True, show_default=True)
@click.option(
    '--format',
    'output_format',
    type=click.Choice(['json', 'word', 'excel', 'auto']),
    default='auto',
    show_default=True,
    help='Output format: json, word, excel, or auto (recommended)',
)
@click.option('--max-pages', type=int, default=None)
@click.option(
    '--page-range',
    default=None,
    help='Page range to process (e.g., "1-5", "1,3,5", "1-3,5-7")',
)
@click.option(
    '--workers',
    default=4,
    show_default=True,
    type=click.IntRange(1, 32),
    help='Number of parallel workers for processing pages',
)
def main(
    pdf_path: str,
    out_dir: str,
    dpi: int,
    max_side: int,
    lang: str,
    use_gpu: bool,
    det_model_dir: Optional[str],
    rec_model_dir: Optional[str],
    cls_model_dir: Optional[str],
    contrast: float,
    sharpen: bool,
    det_limit_side_len: int,
    rec_batch_num: int,
    enable_mkldnn: bool,
    save_csv: bool,
    detect_tables: bool,
    output_format: str,
    max_pages: Optional[int],
    page_range: Optional[str],
    workers: int,
) -> None:
    ensure_dir(out_dir)
    pages_dir = os.path.join(out_dir, 'pages')
    ensure_dir(pages_dir)

    images = render_pdf_to_images(
        pdf_path,
        dpi=dpi,
        max_pages=max_pages,
        max_side=max_side,
        contrast=contrast,
        sharpen=sharpen,
        page_range=page_range,
    )

    print(f'[INFO] 成功渲染 {len(images)} 页PDF')

    if len(images) == 0:
        print('[ERROR] 没有找到需要处理的页面，请检查页面范围参数是否正确')
        return

    engine = OCREngine(
        lang=lang,
        use_angle_cls=True,
        use_gpu=use_gpu,
        det_model_dir=det_model_dir,
        rec_model_dir=rec_model_dir,
        cls_model_dir=cls_model_dir,
        det_limit_side_len=det_limit_side_len,
        rec_batch_num=rec_batch_num,
        enable_mkldnn=enable_mkldnn,
    )

    table_analyzer = TableAnalyzer() if detect_tables else None
    format_exporter = FormatExporter()

    page_results: list[PageResult] = []

    if workers > 1 and len(images) > 1:
        # 使用并行处理
        print(f'[INFO] 使用 {workers} 个并行工作进程处理 {len(images)} 页')

        # 将图像分批处理
        batch_size = max(1, len(images) // workers)
        batches = [
            images[i : i + batch_size] for i in range(0, len(images), batch_size)
        ]

        # 为每个批次创建一个OCR引擎实例
        def process_batch(batch_data):
            """处理一个批次的页面"""
            batch_results = []

            # 为每个批次创建独立的引擎实例以避免线程问题
            worker_engine = OCREngine(
                lang=lang,
                use_angle_cls=True,
                use_gpu=use_gpu,
                det_model_dir=det_model_dir,
                rec_model_dir=rec_model_dir,
                cls_model_dir=cls_model_dir,
                det_limit_side_len=det_limit_side_len,
                rec_batch_num=rec_batch_num,
                enable_mkldnn=enable_mkldnn,
            )

            for page_index, img_bgr in batch_data:
                try:
                    lines = worker_engine.infer(img_bgr)
                    blocks = group_lines_into_blocks(lines)

                    # Detect tables if enabled
                    tables = []
                    if table_analyzer:
                        tables = table_analyzer.detect_tables(lines)

                    h, w = img_bgr.shape[:2]
                    page_result = PageResult(
                        page_index=page_index,
                        width=w,
                        height=h,
                        lines=lines,
                        text_blocks=blocks,
                        tables=tables,
                    )

                    batch_results.append((page_index, page_result))
                    print(
                        f'[INFO] 完成第 {page_index + 1} 页处理，识别到 {len(lines)} 行文本'
                    )
                except Exception as e:
                    print(f'[ERROR] 处理第 {page_index + 1} 页时出错: {e}')
                    continue

            return batch_results

        # 使用线程池并行处理批次
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有批次
            future_to_batch = {
                executor.submit(process_batch, batch): i
                for i, batch in enumerate(batches)
            }

            # 收集结果
            for future in as_completed(future_to_batch):
                batch_results = future.result()
                for page_index, page_result in batch_results:
                    page_results.append((page_index, page_result))

        # 按页面索引排序
        page_results.sort(key=lambda x: x[0])
        page_results = [pr for _, pr in page_results]
    else:
        # 顺序处理
        print('[INFO] 顺序处理页面')
        for page_index, img_bgr in images:
            try:
                lines = engine.infer(img_bgr)
                blocks = group_lines_into_blocks(lines)

                # Detect tables if enabled
                tables = []
                if table_analyzer:
                    tables = table_analyzer.detect_tables(lines)

                h, w = img_bgr.shape[:2]
                page_result = PageResult(
                    page_index=page_index,
                    width=w,
                    height=h,
                    lines=lines,
                    text_blocks=blocks,
                    tables=tables,
                )
                page_results.append(page_result)

                save_page_image(
                    img_bgr, os.path.join(pages_dir, f'page_{page_index + 1:04d}.jpg')
                )
                if save_csv:
                    save_page_lines_csv(
                        lines, os.path.join(pages_dir, f'page_{page_index + 1:04d}.csv')
                    )

                print(
                    f'[INFO] 完成第 {page_index + 1} 页处理，识别到 {len(lines)} 行文本'
                )
            except Exception as e:
                print(f'[ERROR] 处理第 {page_index + 1} 页时出错: {e}')
                continue

    doc = DocumentResult(
        source_pdf=os.path.abspath(pdf_path), dpi=dpi, pages=page_results
    )

    # 检查是否有识别结果
    total_lines = sum(len(page.lines) for page in page_results)
    print(f'[INFO] 总共识别到 {total_lines} 行文本')

    if total_lines == 0:
        print('[WARNING] 未识别到任何文本内容，可能是以下原因导致：')
        print('  1. PDF文件本身不包含可识别的文本')
        print('  2. 图像质量不佳')
        print('  3. 模型路径配置不正确')
        print('  4. 页面范围参数设置错误')

    # Save JSON (always)
    save_document_json(doc, os.path.join(out_dir, 'document.json'))
    print(f'[OK] JSON已保存: {os.path.join(out_dir, "document.json")}')

    # Export in requested format
    if output_format == 'auto':
        recommended_format = format_exporter.get_recommended_format(doc)
        print(f'[INFO] 推荐格式: {recommended_format}')
        format_exporter.export_document(doc, out_dir, recommended_format)
    else:
        format_exporter.export_document(doc, out_dir, output_format)


if __name__ == '__main__':
    main()
