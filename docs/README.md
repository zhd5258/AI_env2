# 智能招投标文件分析系统

## 项目概述

本项目是一个智能招投标文件分析系统，旨在自动化处理招标和投标文件，提取关键信息并进行评分分析。

## 功能特性

- 招标文件评分规则自动提取
- 投标文件自动分析
- 投标人名称自动识别
- 投标价格自动提取
- 自动评分计算
- 结果展示与导出
- 项目管理
- 文件上传与管理
- 分析进度跟踪

## 技术架构

### 后端
- Python 3.8+
- Flask Web框架
- SQLite数据库

### AI服务
- Ollama本地AI服务
- MinerU OCR服务

### 前端
- HTML5
- CSS3
- JavaScript
- Bootstrap框架

## 目录结构

```
.
├── app.py                 # 应用入口文件
├── config/                # 配置文件目录
├── controllers/           # 控制器目录
├── middleware/            # 中间件目录
├── models/                # 数据模型目录
├── modules/               # 核心功能模块目录
├── routes/                # 路由目录
├── static/                # 静态资源目录
├── templates/             # 模板文件目录
├── tools/                 # 工具脚本目录
├── requirements.txt       # Python依赖包列表
└── README.md             # 项目说明文档
```

## 安装部署

1. 安装Python 3.8+
2. 安装依赖：`pip install -r requirements.txt`
3. 配置Ollama和MinerU服务
4. 运行应用：`python app.py`

## 使用说明

1. 启动应用后访问 http://localhost:8000
2. 创建新项目并上传招标文件和投标文件
3. 系统自动分析文件并提取评分规则
4. 确认投标人名称后开始分析
5. 查看分析结果和评分

## 系统维护

- 定期清理临时文件
- 监控系统资源使用情况
- 备份数据库文件
