# 智能投标文件评标系统

## 项目简介

智能投标文件评标系统是一个基于AI技术的自动化评标工具，旨在提高评标效率和准确性。系统能够自动解析招标文件和投标文件，提取评分规则，并对投标文件进行智能分析和评分。

## 主要功能

1. **PDF文件处理**：支持多种格式的PDF文件处理，包括图形、签名、加密等复杂内容
2. **评分规则提取**：自动从招标文件中提取评分规则
3. **投标文件分析**：对投标文件进行智能分析，提取关键信息
4. **自动评分**：根据评分规则对投标文件进行自动评分
5. **并行处理**：支持大文件的分块并行处理，提高处理速度
6. **Web界面**：提供友好的Web操作界面

## 技术架构

- **后端**：Python + Flask
- **前端**：HTML + CSS + JavaScript
- **数据库**：SQLite
- **AI引擎**：MinerU + 自研分析模块
- **OCR**：支持多种OCR技术

## 依赖项

请查看 [requirements.txt](requirements.txt) 文件获取完整的依赖列表。

## 安装指南

1. 克隆项目代码：
   ```bash
   git clone <repository-url>
   cd tender-evaluation-system
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 安装MinerU：
   请参考 [MinerU官方文档](https://github.com/opendatalab/MinerU) 进行安装。

4. 初始化数据库：
   ```bash
   python migrate_db.py
   ```

5. 启动应用：
   ```bash
   python app.py
   ```

## 项目结构

```
.
├── app.py                 # 主应用文件
├── config/                # 配置文件
├── controllers/           # 控制器
├── middleware/            # 中间件
├── models/                # 数据库模型
├── modules/               # 核心功能模块
├── routes/                # 路由
├── static/                # 静态资源
├── templates/             # 模板文件
├── tools/                 # 工具脚本
├── requirements.txt       # 依赖清单
└── README.md             # 项目说明
```

## 核心模块

### PDF处理器
- `advanced_pdf_processor.py`：高级PDF处理器，支持多种OCR技术
- `chunked_parallel_processor.py`：分块并行PDF处理器，支持大文件并行处理

### 分析管理器
- `analysis_manager.py`：分析管理器，统一处理项目分析流程
- `intelligent_bid_analyzer.py`：智能投标文件分析器
- `scoring_rules_manager.py`：评分规则管理器

### 数据提取器
- `bidder_name_extractor.py`：投标人名称提取器
- `price_score_calculator.py`：价格分计算器
- `correct_scoring_extractor.py`：评分规则提取器

## 使用说明

1. 访问 `http://localhost:8000`
2. 上传招标文件和投标文件
3. 系统自动分析并生成评分结果
4. 可在界面中查看和导出评分结果

## 注意事项

1. 请确保已正确安装MinerU及其依赖
2. 大文件处理可能需要较长时间，请耐心等待
3. 系统需要足够的内存和存储空间

## 许可证

本项目采用MIT许可证，详情请见 [LICENSE](LICENSE) 文件。
