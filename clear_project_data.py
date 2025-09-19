import argparse
import os
import sys
import hashlib
import logging
from pathlib import Path

# 将项目根目录添加到Python路径中，以便导入模块
# D:\user\PythonProject\AI_env2
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    ScoringRule,
    AnalysisResult,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)


def get_cache_path(file_path: str) -> str:
    """
    根据文件路径、大小和修改时间计算缓存文件的路径。
    这是从 modules/pdf_processor.py 复制并简化的逻辑。
    """
    cache_dir = 'temp_pdf_cache'
    if not os.path.exists(file_path):
        return None
    try:
        st = os.stat(file_path)
        key = f'{file_path}|{st.st_size}|{int(st.st_mtime)}'
        file_key = hashlib.md5(key.encode('utf-8')).hexdigest()
        cache_filename = f'{file_key}.json'
        return os.path.join(cache_dir, cache_filename)
    except Exception as e:
        logging.warning(f'计算缓存路径失败 for {file_path}: {e}')
        return None


def clear_project_data(project_id: int):
    """
    清理指定项目的所有相关数据，包括文件和数据库记录。
    """
    db = SessionLocal()
    try:
        # 1. 查找项目
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            logging.error(f'错误：未找到ID为 {project_id} 的项目。')
            return

        logging.info(f"准备清理项目：'{project.project_name}' (ID: {project.id})")

        # 2. 用户确认
        confirm = input(
            f"这是一个危险操作！将永久删除项目的所有文件和数据。\n请输入项目名称 '{project.project_name}' 以确认: "
        )
        if confirm.strip() != project.project_name:
            logging.warning('项目名称不匹配。操作已取消。')
            return

        logging.info('确认成功，开始清理...')

        # 3. 查找并删除关联的投标文件和缓存
        bid_documents = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
        )
        if bid_documents:
            logging.info(f'找到 {len(bid_documents)} 个关联的投标文件。')
            for doc in bid_documents:
                # 删除物理文件
                if doc.file_path and os.path.exists(doc.file_path):
                    try:
                        os.remove(doc.file_path)
                        logging.info(f'  - 已删除投标文件: {doc.file_path}')
                    except OSError as e:
                        logging.error(f'  - 删除文件失败: {doc.file_path}, 错误: {e}')

                # 删除缓存文件
                cache_file = get_cache_path(doc.file_path)
                if cache_file and os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                        logging.info(f'  - 已删除缓存文件: {cache_file}')
                    except OSError as e:
                        logging.error(f'  - 删除缓存失败: {cache_file}, 错误: {e}')
        else:
            logging.info('未找到关联的投标文件。')

        # 4. 删除数据库记录 (按依赖顺序)
        logging.info('正在删除数据库记录...')

        # 删除分析结果
        deleted_count = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .delete()
        )
        logging.info(f'  - 已删除 {deleted_count} 条分析结果。')

        # 删除评分规则
        deleted_count = (
            db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
        )
        logging.info(f'  - 已删除 {deleted_count} 条评分规则。')

        # 删除投标文件记录
        deleted_count = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).delete()
        )
        logging.info(f'  - 已删除 {deleted_count} 条投标文件记录。')

        # 删除项目本身
        db.delete(project)
        logging.info(f"  - 已删除项目 '{project.project_name}'。")

        # 5. 提交事务
        db.commit()
        logging.info('数据库清理完成。')

        # 6. 清理招标项目文件
        if project.tender_file_path and os.path.exists(project.tender_file_path):
            try:
                os.remove(project.tender_file_path)
                logging.info(f'已删除招标文件: {project.tender_file_path}')
            except OSError as e:
                logging.error(
                    f'删除招标文件失败: {project.tender_file_path}, 错误: {e}'
                )

        logging.info(
            f"\n项目 {project_id} ('{project.project_name}') 的所有数据和文件已成功清理。"
        )

    except Exception as e:
        logging.error(f'清理过程中发生错误: {e}')
        db.rollback()
    finally:
        db.close()


def list_projects():
    """列出所有项目及其ID。"""
    db = SessionLocal()
    try:
        projects = db.query(TenderProject).all()
        if not projects:
            print('数据库中没有项目。')
            return

        print('可用项目列表:')
        print('-' * 40)
        print(f'{"ID":<5} | {"项目名称":<30}')
        print('-' * 40)
        for p in projects:
            print(f'{p.id:<5} | {p.project_name:<30}')
        print('-' * 40)

    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='清理一个招标项目的所有相关数据，包括数据库记录和物理文件。'
    )
    parser.add_argument(
        'project_id',
        type=int,
        nargs='?',
        help='要清理的项目的ID。如果未提供，将列出所有项目。',
    )

    args = parser.parse_args()

    if args.project_id is None:
        list_projects()
        print('\n请提供一个项目ID来执行清理操作。')
        print(f'用法: python {os.path.basename(__file__)} <project_id>')
    else:
        clear_project_data(args.project_id)
