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

- 后端：Python + Flask
- 前端：Jinja2 + 原生 JS + CSS
- OCR：PyTesseract + pdfplumber + pikepdf + MinerU
- 数据库：SQLAlchemy

## 部署与运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行服务
python app.py
```

## 投标文件处理与分析流程

```mermaid
graph TD
    A[开始] --> B[上传招标文件和投标文件]
    B --> C[保存文件到uploads目录]
    C --> D[使用PDF处理器将投标文件转换为MD文件]
    D --> E[保存MD文件到temp/md目录]
    E --> F[从数据库加载评分规则]
    F --> G[为每个投标文件启动独立分析线程]
    G --> H[分析线程读取对应的MD文件]
    H --> I[遍历数据库中的评分规则]
    I --> J[为每个评分规则创建Prompt]
    J --> K[发送Prompt给AI大模型打分]
    K --> L[收集AI打分结果]
    L --> M[保存除价格外的评分结果]
    M --> N[所有投标文件分析完成]
    N --> O[使用统一提取器提取所有投标人信息]
    O --> P[遍历temp/md目录提取投标人名称和价格]
    P --> Q[保存到数据库并创建价格数组]
    Q --> R[获取价格评分规则]
    R --> S[构造AI prompt计算价格分]
    S --> T[调用AI大模型计算价格分]
    T --> U[保存价格分到数据库]
    U --> V[更新项目状态]
    V --> W[结束]
```

## 核心模块

### 1. 统一提取器 (UnifiedExtractor)
- 统一处理投标人名称和投标总价提取
- 避免重复的MD文件处理
- 提供统一的数据提取入口

### 2. 价格计算工作流 (PriceCalculationWorkflow)
- 实现统一的价格提取和计算流程
- 遵循招标文件分析完成后进行价格提取的顺序
- 调用AI大模型计算价格分数

### 3. 智能投标分析器 (IntelligentBidAnalyzer)
- 投标文件智能分析
- AI评分处理
- 进度跟踪和数据库更新

### 4. 评分规则提取器 (CorrectScoringExtractor)
- 从招标文件中提取评分规则
- 支持复杂表格结构识别
- 智能解析评分规则结构

## 常见问题与解决方案

### 1. 关于pydevd警告

在使用VS Code等IDE的调试器运行项目时，可能会遇到以下警告：

```
UserWarning: incompatible copy of pydevd already imported
```

这是由于环境中存在多个版本的pydevd（Python调试器）导致的冲突。这个警告不会影响程序的正常运行，但可以通过以下方式消除：

1. 使用我们提供的`run_without_warnings.bat`脚本运行项目
2. 或者在环境变量中设置`DISABLE_WARNINGS=true`后运行项目

### 2. 高级PDF处理功能

本系统集成了AdvancedPDFProcessor，支持处理图形格式、签名、加密等PDF文件，并能准确识别表格和公式等复杂内容。

#### 特性

- 支持多种OCR技术处理图形格式PDF
- 精确识别表格、公式等复杂内容
- 支持内容级旋转矫正
- 支持加密PDF文件处理
- 输出Markdown格式文档

#### 使用方法

系统会自动检测PDF文件类型并选择最适合的处理方法：
1. 首先尝试直接提取文本
2. 如果文本质量不佳，会自动尝试PyTesseract OCR
3. 如果PyTesseract效果不佳，会尝试OCRmyPDF
4. 最后会使用AdvancedPDFProcessor（MinerU）进行处理
