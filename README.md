# AI_env2

## 项目概述

AI_env2 是一个基于AI的投标文件分析系统，用于处理PDF格式的招标文件，提取关键信息并进行评分计算。

## 核心功能

- PDF文件处理与结构解析
- OCR识别与文本提取
- 投标价格提取与评分规则分析
- 数据库存储与查询
- 结果展示与导出

## 技术架构

- 后端：Python + FastAPI
- 前端：Jinja2 + 原生 JS + CSS
- OCR：PyTesseract + pdfplumber + pikepdf
- 数据库：SQLAlchemy

## 部署与运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行服务
uvicorn main:app --reload
```