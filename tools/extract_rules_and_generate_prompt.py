#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
提取评分规则并生成AI评分Prompt工具脚本
从数据库中提取最后一个项目的定量规则和定性规则，
结合指定的MD文件，生成一个使用AI大模型进行复合性和定量打分的prompt文件，
以md格式保存到rules下
"""

import os
import sys
import json
import logging
from tkinter import Tk, filedialog
from typing import List, Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from models.database import ScoringRule, TenderProject, SessionLocal

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_last_project(db_session) -> Optional[TenderProject]:
    """
    获取数据库中最后一个项目

    Args:
        db_session: 数据库会话

    Returns:
        TenderProject: 最后一个项目对象，如果不存在则返回None
    """
    try:
        last_project = (
            db_session.query(TenderProject).order_by(TenderProject.id.desc()).first()
        )
        return last_project
    except Exception as e:
        logger.error(f'获取最后一个项目时出错: {e}')
        return None


def get_project_scoring_rules(db_session, project_id: int) -> List[ScoringRule]:
    """
    获取项目的评分规则

    Args:
        db_session: 数据库会话
        project_id: 项目ID

    Returns:
        List[ScoringRule]: 评分规则列表
    """
    try:
        scoring_rules = (
            db_session.query(ScoringRule)
            .filter(ScoringRule.project_id == project_id)
            .all()
        )
        return scoring_rules
    except Exception as e:
        logger.error(f'获取项目评分规则时出错: {e}')
        return []


def extract_qualitative_and_quantitative_rules(
    scoring_rules: List[ScoringRule],
) -> tuple:
    """
    分离定性规则和定量规则

    Args:
        scoring_rules: 评分规则列表

    Returns:
        tuple: (定性规则列表, 定量规则列表)
    """
    qualitative_rules = []
    quantitative_rules = []

    for rule in scoring_rules:
        # 根据is_qualitative和is_quantitative字段判断
        if hasattr(rule, 'is_qualitative') and rule.is_qualitative:
            qualitative_rules.append(rule)
        elif hasattr(rule, 'is_quantitative') and rule.is_quantitative:
            quantitative_rules.append(rule)
        # 如果没有明确标记，根据分数判断
        elif (
            getattr(rule, 'Child_max_score', 0) == 0
            and getattr(rule, 'Parent_max_score', 0) == 0
        ):
            qualitative_rules.append(rule)
        else:
            quantitative_rules.append(rule)

    return qualitative_rules, quantitative_rules


def read_md_file(file_path: str) -> str:
    """
    读取MD文件内容

    Args:
        file_path: MD文件路径

    Returns:
        str: 文件内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        logger.error(f'读取MD文件时出错: {e}')
        return ''


def format_rules_for_prompt(rules: List[ScoringRule]) -> List[Dict[str, Any]]:
    """
    格式化规则用于Prompt

    Args:
        rules: 评分规则列表

    Returns:
        List[Dict[str, Any]]: 格式化后的规则列表
    """
    formatted_rules = []

    for rule in rules:
        rule_dict = {
            '规则名称': getattr(rule, 'Child_Item_Name', '')
            or getattr(rule, 'Parent_Item_Name', ''),
            '最高分': getattr(rule, 'Child_max_score', 0)
            or getattr(rule, 'Parent_max_score', 0),
            '描述': getattr(rule, 'description', ''),
            '是否为否决项': getattr(rule, 'is_veto', False),
            '是否为价格规则': getattr(rule, 'is_price_criteria', False),
        }
        
        # 添加规则使用说明（如果存在）
        if hasattr(rule, 'rule_usage_description') and rule.rule_usage_description:
            rule_dict['规则使用说明'] = rule.rule_usage_description
            
        formatted_rules.append(rule_dict)

    return formatted_rules


def generate_ai_prompt(
    qualitative_rules: List[Dict[str, Any]],
    quantitative_rules: List[Dict[str, Any]],
    md_content: str,
) -> str:
    """
    生成AI评分Prompt

    Args:
        qualitative_rules: 定性规则列表
        quantitative_rules: 定量规则列表
        md_content: MD文件内容

    Returns:
        str: 生成的Prompt
    """
    prompt = f"""# AI评标专家评分指南

你是一个资深的专业评标专家，请根据以下招标文件的评分规则，对投标文件进行评分。

## 评分规则说明

评分规则分为两类：
1. **定性规则（符合性审查规则）**：这些规则用于判断投标文件是否符合要求，只需判断符合/不符合
2. **定量规则（评分规则）**：这些规则需要根据投标文件内容进行打分，满分为各自规则的最高分

## 定性规则（符合性审查规则）

这些规则用于判断投标文件是否符合要求，只需判断符合/不符合：

{json.dumps(qualitative_rules, ensure_ascii=False, indent=2)}

## 定量规则（评分规则）

这些规则需要根据投标文件内容进行打分，满分为各自规则的最高分：

{json.dumps(quantitative_rules, ensure_ascii=False, indent=2)}

## 待评分的投标文件内容

```
{md_content}
```

## 评分要求

### 定性规则处理
对于定性规则，请判断每项是否符合要求：
- 如果符合，标记为"符合"
- 如果不符合，标记为"不符合"，并简要说明原因

### 定量规则处理
对于定量规则，请根据投标文件内容进行打分：
- 每项规则的得分不能超过其最高分
- 请给出打分理由

## 输出格式要求

请严格按照以下JSON格式输出结果，不要包含其他内容：

```json
{{
  "定性规则结果": [
    {{
      "规则名称": "示例规则名称",
      "是否符合": true,
      "不符合原因": "如果不符合，请说明原因"
    }}
  ],
  "定量规则结果": [
    {{
      "规则名称": "示例规则名称",
      "得分": 5.0,
      "打分理由": "请详细说明打分依据"
    }}
  ]
}}
```

请开始评分：
"""

    return prompt


def save_prompt_to_file(prompt: str, output_path: str):
    """
    保存Prompt到文件

    Args:
        prompt: Prompt内容
        output_path: 输出文件路径
    """
    try:
        # 确保rules目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        logger.info(f'Prompt已保存到: {output_path}')
    except Exception as e:
        logger.error(f'保存Prompt到文件时出错: {e}')


def select_md_file() -> str:
    """
    使用文件选择对话框选择MD文件

    Returns:
        str: 选择的文件路径
    """
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    file_path = filedialog.askopenfilename(
        title='选择要评分的投标文件(MD格式)', filetypes=[('Markdown files', '*.md'), ('All files', '*.*')]
    )
    root.destroy()
    return file_path


def main():
    """主函数"""
    logger.info('开始提取评分规则并生成AI评分Prompt...')

    try:
        # 创建数据库会话
        db_session = SessionLocal()

        # 获取最后一个项目
        last_project = get_last_project(db_session)
        if not last_project:
            logger.error('未找到任何项目')
            return

        logger.info(f'使用项目: {last_project.name} (ID: {last_project.id})')

        # 获取项目的评分规则
        scoring_rules = get_project_scoring_rules(db_session, last_project.id)
        if not scoring_rules:
            logger.warning('该项目没有评分规则')
            return

        logger.info(f'找到 {len(scoring_rules)} 条评分规则')

        # 分离定性规则和定量规则
        qualitative_rules, quantitative_rules = (
            extract_qualitative_and_quantitative_rules(scoring_rules)
        )
        logger.info(f'定性规则数量: {len(qualitative_rules)}')
        logger.info(f'定量规则数量: {len(quantitative_rules)}')

        # 格式化规则用于Prompt
        formatted_qualitative = format_rules_for_prompt(qualitative_rules)
        formatted_quantitative = format_rules_for_prompt(quantitative_rules)

        # 选择MD文件
        logger.info('请选择要评分的投标文件MD文件...')
        md_file_path = select_md_file()

        if not md_file_path or not os.path.exists(md_file_path):
            logger.error('未选择有效的MD文件')
            return

        logger.info(f'选择的MD文件: {md_file_path}')

        # 读取MD文件内容
        md_content = read_md_file(md_file_path)
        if not md_content:
            logger.error('未能读取MD文件内容')
            return

        # 生成AI Prompt
        prompt = generate_ai_prompt(
            formatted_qualitative, formatted_quantitative, md_content
        )

        # 保存Prompt到rules目录
        md_filename = os.path.basename(md_file_path)
        output_filename = f'ai_scoring_prompt_{last_project.id}_{md_filename}'
        output_path = os.path.join(project_root, 'rules', output_filename)
        save_prompt_to_file(prompt, output_path)

        logger.info('AI评分Prompt生成完成!')

    except Exception as e:
        logger.error(f'生成AI评分Prompt时出错: {e}', exc_info=True)
    finally:
        # 关闭数据库会话
        try:
            db_session.close()
        except:
            pass


if __name__ == '__main__':
    main()