# 智能投标文件评标系统

## 项目简介

智能投标文件评标系统是一个基于人工智能技术的自动化评标工具，专门用于处理和分析投标文件。该系统能够自动提取投标文件中的关键信息，如投标人名称、投标价格等，并根据预设的评分规则进行自动评分。

## 功能特性

1. **PDF文件处理** - 支持多种PDF处理引擎（PyMuPDF、MinerU、OCRmyPDF等）
2. **文本提取与清洗** - 从PDF文件中提取结构化文本内容
3. **关键信息提取** - 自动提取投标人名称、投标价格等关键信息
4. **表格分析** - 智能识别和处理跨页表格
5. **自动评分** - 根据预设规则进行自动评分
6. **结果展示** - 提供友好的Web界面展示分析结果

## 新增功能：文本处理模块

本系统新增了基于textacy库的文本处理模块，提供了以下功能：

1. **文本清洗** - 移除多余的空白字符、换行符等
2. **Markdown文本处理** - 专门处理Markdown格式的文本
3. **关键词提取** - 使用TextRank算法提取文本关键词
4. **文本标准化** - 统一引号、货币符号、百分比等格式
5. **移除不需要元素** - 移除URL、邮箱、电话号码等

详细使用说明请参考 [docs/text_processor_usage.md](docs/text_processor_usage.md)

## 安装依赖

```bash
pip install -r requirements.txt
```

## 安装可选依赖

```bash
# 安装textacy（用于文本处理）
pip install textacy==0.12.0

# 安装spaCy中文模型（可选，用于更好的中文文本处理）
python -m spacy download zh_core_web_sm
```

## 使用方法

```bash
# 启动Web服务
python app.py

# 或者使用命令行工具
tender-eval
```

## 项目结构

```
.
├── app.py                 # 主应用入口
├── requirements.txt       # 项目依赖
├── setup.py              # 安装配置
├── config/               # 配置文件
├── controllers/          # 控制器
├── middleware/           # 中间件
├── models/               # 数据模型
├── modules/              # 核心功能模块
├── routes/               # 路由
├── static/               # 静态文件
├── tasks/                # 定时任务
├── templates/            # 模板文件
├── tools/                # 工具脚本
└── docs/                 # 文档
```

## 核心模块

- `pdf_processor.py` - PDF文件处理模块
- `bidder_name_extractor.py` - 投标人名称提取模块
- `md_price_extractor.py` - 价格提取模块
- `table_analyzer.py` - 表格分析模块
- `text_processor.py` - 文本处理模块（新增）
- `intelligent_bid_analyzer.py` - 智能评标分析模块

## 许可证

MIT License
