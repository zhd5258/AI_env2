import pandas as pd
import json
import os
from typing import List, Dict, Any


class ExcelProcessor:
    def __init__(self, excel_file_path: str = '评价.xlsx'):
        self.excel_file_path = excel_file_path
        self.df = None
        self._load_excel()

    def _load_excel(self):
        """加载Excel文件"""
        if os.path.exists(self.excel_file_path):
            self.df = pd.read_excel(self.excel_file_path)
        else:
            raise FileNotFoundError(f'Excel文件 {self.excel_file_path} 不存在')

    def get_scoring_items_from_template(self) -> List[Dict[str, Any]]:
        """从Excel模板中获取评分项列表，严格按照评标办法表格结构"""
        if self.df is None:
            raise ValueError('Excel数据未加载')

        # 从Excel中提取评分项，只提取评标办法中的评分项
        scoring_items = []
        current_parent = None

        # 遍历所有行，提取评分项
        for i, row in self.df.iterrows():
            # 检查是否有父项信息（在Unnamed: 3列中）
            if pd.notna(row.get('Unnamed: 3', '')) and str(row['Unnamed: 3']).strip():
                current_parent = str(row['Unnamed: 3']).strip()

            # 只处理有评价项目且没有投标方名称的行（即评分项行）
            if pd.notna(row['评价项目']) and (
                pd.isna(row['投标方']) or row['投标方'] == ''
            ):
                # 获取评价标准描述，即使为空也要保留评分项
                description = ''
                if '投标方应答相关内容摘要' in self.df.columns:
                    if pd.notna(row['投标方应答相关内容摘要']):
                        description = str(row['投标方应答相关内容摘要']).strip()

                # 如果评价标准为空，尝试从父项或其他地方获取描述
                if not description:
                    # 检查是否是父项（如"商务部分（总分18分）"）
                    criteria_name = str(row['评价项目']).strip()
                    if '总分' in criteria_name and '分' in criteria_name:
                        description = f'{criteria_name}的评分标准'
                    else:
                        description = f'{criteria_name}的评分标准'

                # 确定分类
                category = '评标办法'
                if current_parent:
                    if '商务' in current_parent:
                        category = '商务部分'
                    elif '服务' in current_parent:
                        category = '服务部分'
                    elif '技术' in current_parent:
                        category = '技术部分'
                    elif '价格' in current_parent:
                        category = '价格部分'

                scoring_items.append(
                    {
                        'criteria_name': row['评价项目'],
                        'max_score': float(row['满分分值'])
                        if pd.notna(row['满分分值'])
                        else 0,
                        'weight': 1.0,
                        'description': description,
                        'category': category,
                        'parent_category': current_parent,
                        'is_veto': False,  # 默认为非否决项
                    }
                )

        # 去重，保持顺序
        unique_items = []
        seen_names = set()
        for item in scoring_items:
            if item['criteria_name'] not in seen_names:
                unique_items.append(item)
                seen_names.add(item['criteria_name'])

        return unique_items

    def _normalize_criteria_name(self, name: str) -> str:
        """标准化评分项名称，用于匹配"""
        if not name:
            return ''
        # 移除多余的空白字符
        name = ' '.join(name.split())
        # 移除特殊字符
        name = name.replace('☑', '').replace('□', '').strip()
        return name

    def _find_best_match(self, target_name: str, candidates: List[str]) -> str:
        """找到最佳匹配的评分项名称"""
        target_name = self._normalize_criteria_name(target_name).lower()

        # 精确匹配
        for candidate in candidates:
            candidate_norm = self._normalize_criteria_name(candidate).lower()
            if target_name == candidate_norm:
                return candidate

        # 模糊匹配（包含关系）
        for candidate in candidates:
            candidate_norm = self._normalize_criteria_name(candidate).lower()
            if target_name in candidate_norm or candidate_norm in target_name:
                return candidate

        # 关键词匹配
        target_keywords = set(target_name.split())
        best_match = None
        best_score = 0

        for candidate in candidates:
            candidate_norm = self._normalize_criteria_name(candidate).lower()
            candidate_keywords = set(candidate_norm.split())

            # 计算关键词重叠度
            overlap = len(target_keywords & candidate_keywords)
            total = len(target_keywords | candidate_keywords)
            score = overlap / total if total > 0 else 0

            if score > best_score:
                best_score = score
                best_match = candidate

        return best_match if best_score > 0.3 else None

    def generate_evaluation_table(
        self, analysis_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        生成评标办法表格，严格按照@评价.xlsx格式
        """
        if self.df is None:
            raise ValueError('Excel数据未加载')

        # 获取评分项结构（从Excel模板中提取）
        scoring_items = self.get_scoring_items_from_template()

        # 构建结果表
        evaluation_table = []

        # 为每个分析结果生成表格行
        for result in analysis_results:
            bidder_row = {
                '投标方': result['bidder_name'],
                '总分': result['total_score'],
            }

            # 添加每个评分项的得分
            detailed_scores = result.get('detailed_scores', [])

            # 创建评分项映射，便于查找
            score_map = {}

            def build_score_map(scores):
                if isinstance(scores, list):
                    for score in scores:
                        if 'criteria_name' in score and 'score' in score:
                            # 标准化评分项名称作为键
                            normalized_name = self._normalize_criteria_name(
                                score['criteria_name']
                            )
                            score_map[normalized_name] = score
                            # 也添加原始名称
                            score_map[score['criteria_name']] = score
                        # 递归处理子项
                        if 'children' in score and score['children']:
                            build_score_map(score['children'])

            build_score_map(detailed_scores)

            # 获取所有AI评分项名称
            ai_criteria_names = list(score_map.keys())

            # 按照Excel模板中的评分项顺序添加得分
            for item in scoring_items:
                template_name = item['criteria_name']
                normalized_template_name = self._normalize_criteria_name(template_name)

                # 尝试多种匹配方式
                score_value = 0

                # 1. 精确匹配
                if normalized_template_name in score_map:
                    score_value = score_map[normalized_template_name]['score']
                elif template_name in score_map:
                    score_value = score_map[template_name]['score']
                else:
                    # 2. 模糊匹配
                    best_match = self._find_best_match(template_name, ai_criteria_names)
                    if best_match and best_match in score_map:
                        score_value = score_map[best_match]['score']

                bidder_row[template_name] = score_value

            evaluation_table.append(bidder_row)

        # 按总分排序
        evaluation_table.sort(
            key=lambda x: x['总分'] if x['总分'] != '废标' else -1, reverse=True
        )

        return evaluation_table

    def process_excel_data(self) -> List[Dict[str, Any]]:
        """处理Excel数据，计算每个投标方的总分并排序"""
        if self.df is None:
            raise ValueError('Excel数据未加载')

        # 获取所有投标方
        self.df['投标方'].dropna().tolist()

        # 计算每个投标方的总分
        bidder_scores = {}
        current_bidder = None
        current_total = 0

        for i, row in self.df.iterrows():
            # 如果这一行有投标方名称，说明是新的投标方
            if pd.notna(row['投标方']) and row['投标方'] != '':
                # 保存上一个投标方的总分
                if current_bidder is not None:
                    bidder_scores[current_bidder] = current_total

                # 开始计算新投标方的总分
                current_bidder = row['投标方']
                current_total = 0

            # 如果这一行有得分，累加到当前投标方的总分
            if pd.notna(row['得分']):
                try:
                    # 处理"废标"情况
                    if row['得分'] == '废标':
                        current_total = '废标'
                        break
                    else:
                        current_total += float(row['得分'])
                except (ValueError, TypeError):
                    pass

        # 保存最后一个投标方的总分
        if current_bidder is not None and current_bidder not in bidder_scores:
            bidder_scores[current_bidder] = current_total

        # 按总分排序
        sorted_bidders = sorted(
            bidder_scores.items(),
            key=lambda x: x[1] if x[1] != '废标' else -1,
            reverse=True,
        )

        # 添加排名
        results = []
        for i, (bidder, score) in enumerate(sorted_bidders):
            results.append(
                {
                    'rank': i + 1,
                    'bidder_name': bidder,
                    'total_score': score,
                    'detailed_scores': self._get_detailed_scores(
                        bidder
                    ),  # 获取详细的评分项
                }
            )

        return results

    def _get_detailed_scores(self, bidder_name: str) -> List[Dict[str, Any]]:
        """获取指定投标方的详细评分项"""
        if self.df is None:
            raise ValueError('Excel数据未加载')

        detailed_scores = []
        collecting_scores = False

        for i, row in self.df.iterrows():
            # 检查是否是目标投标方
            if pd.notna(row['投标方']) and row['投标方'] == bidder_name:
                collecting_scores = True
                continue

            # 如果遇到下一个投标方，停止收集
            if (
                pd.notna(row['投标方'])
                and row['投标方'] != bidder_name
                and collecting_scores
            ):
                break

            # 收集评分项数据
            if collecting_scores and pd.notna(row['评价项目']):
                # 获取评价标准描述，即使为空也要保留评分项
                description = ''
                if '投标方应答相关内容摘要' in self.df.columns:
                    if pd.notna(row['投标方应答相关内容摘要']):
                        description = str(row['投标方应答相关内容摘要']).strip()

                # 如果评价标准为空，尝试从父项或其他地方获取描述
                if not description:
                    # 检查是否是父项（如"商务部分（总分18分）"）
                    criteria_name = str(row['评价项目']).strip()
                    if '总分' in criteria_name and '分' in criteria_name:
                        description = f'{criteria_name}的评分标准'
                    else:
                        description = f'{criteria_name}的评分标准'

                detailed_scores.append(
                    {
                        'criteria_name': row['评价项目'],
                        'max_score': float(row['满分分值'])
                        if pd.notna(row['满分分值'])
                        else 0,
                        'score': row['得分'] if pd.notna(row['得分']) else 0,
                        'weight': 1.0,
                        'description': description,
                        'is_veto': False,  # 默认为非否决项
                    }
                )

        return detailed_scores

    def get_scoring_items(self) -> List[Dict[str, Any]]:
        """获取评分项列表，严格按照评标办法表格结构"""
        if self.df is None:
            raise ValueError('Excel数据未加载')

        # 从Excel中提取评分项，只提取评标办法中的评分项
        scoring_items = []

        # 遍历所有行，提取评分项
        for i, row in self.df.iterrows():
            # 只处理有评价项目且没有投标方名称的行（即评分项行）
            if pd.notna(row['评价项目']) and (
                pd.isna(row['投标方']) or row['投标方'] == ''
            ):
                # 获取评价标准描述，即使为空也要保留评分项
                description = ''
                if '投标方应答相关内容摘要' in self.df.columns:
                    if pd.notna(row['投标方应答相关内容摘要']):
                        description = str(row['投标方应答相关内容摘要']).strip()

                # 如果评价标准为空，尝试从父项或其他地方获取描述
                if not description:
                    # 检查是否是父项（如"商务部分（总分18分）"）
                    criteria_name = str(row['评价项目']).strip()
                    if '总分' in criteria_name and '分' in criteria_name:
                        description = f'{criteria_name}的评分标准'
                    else:
                        description = f'{criteria_name}的评分标准'

                scoring_items.append(
                    {
                        'criteria_name': row['评价项目'],
                        'max_score': float(row['满分分值'])
                        if pd.notna(row['满分分值'])
                        else 0,
                        'weight': 1.0,
                        'description': description,
                        'category': '评标办法',
                        'is_veto': False,  # 默认为非否决项
                    }
                )

        # 去重，保持顺序
        unique_items = []
        seen_names = set()
        for item in scoring_items:
            if item['criteria_name'] not in seen_names:
                unique_items.append(item)
                seen_names.add(item['criteria_name'])

        return unique_items


# 测试代码
if __name__ == '__main__':
    processor = ExcelProcessor()
    results = processor.process_excel_data()
    print(json.dumps(results, ensure_ascii=False, indent=2))
