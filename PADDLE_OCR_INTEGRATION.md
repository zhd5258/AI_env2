# PaddleOCR集成说明

## 概述

本项目已成功集成PaddleOCR作为主要的OCR引擎，用于处理PDF文档中的图像文本识别。

## 主要特性

### 1. 双引擎支持
- **PaddleOCR** (默认): 基于PaddlePaddle的OCR引擎，支持中英文识别
- **ONNX处理器** (备用): 基于ONNX的轻量级OCR引擎

### 2. GPU加速支持
- 自动检测GPU可用性
- 支持CUDA加速（需要PaddlePaddle GPU版本）
- 自动回退到CPU模式

### 3. 智能处理模式
- **混合模式**: 先尝试文本提取，对文本较少的页面使用OCR
- **强制OCR模式**: 对所有页面使用OCR处理
- **缓存机制**: 处理结果自动缓存，提高重复处理效率

## 配置选项

### 环境变量
```bash
# 启用GPU加速
export USE_GPU=true

# 禁用GPU（默认）
export USE_GPU=false
```

### API配置
```bash
# 获取当前OCR配置
GET /api/ocr-config

# 更新OCR配置
POST /api/ocr-config
{
    "use_gpu": true,
    "use_paddle": true
}
```

## 使用方法

### 基本使用
```python
from modules.pdf_processor import PDFProcessor

# 创建处理器实例
processor = PDFProcessor("path/to/file.pdf", use_gpu=True)

# 处理PDF（使用PaddleOCR）
pages_text = processor.process_pdf_per_page(use_paddle=True)

# 强制OCR模式
pages_text = processor.process_pdf_per_page(force_ocr=True, use_paddle=True)
```

### 高级配置
```python
# CPU模式
processor = PDFProcessor("file.pdf", use_gpu=False)

# 混合模式（默认）
pages_text = processor.process_pdf_per_page()

# 强制OCR模式
pages_text = processor.process_pdf_per_page(force_ocr=True)
```

## 使用示例

```python
from modules.pdf_processor import PDFProcessor

# 处理投标文件（使用ONNX）
processor = PDFProcessor('投标文件.pdf', file_type='bid')
pages_text = processor.extract_text_with_ocr_when_needed()

# 处理招标文件（使用PaddleOCR）
processor = PDFProcessor('招标文件.pdf', file_type='tender') 
pages_text = processor.extract_text_with_ocr_when_needed()
```

## 性能优化

### 1. 缓存机制
- 处理结果自动保存到 `temp_pdf_cache/` 目录
- 基于文件路径、大小和修改时间的缓存键
- 支持手动清理缓存

### 2. 并行处理
- 支持多页面并行OCR处理
- 可配置的并发数量
- 超时保护机制

### 3. 内存管理
- 逐页处理，避免大文件内存溢出
- 自动资源清理
- 异常安全处理

## 错误处理

### 常见问题
1. **PaddleOCR未安装**: 自动回退到ONNX处理器
2. **GPU不可用**: 自动切换到CPU模式
3. **模型下载失败**: 提供详细的错误信息

### 日志记录
- 详细的处理日志
- 性能统计信息
- 错误追踪和调试信息

## 依赖要求

### 必需依赖
```bash
pip install paddlepaddle paddleocr opencv-python numpy
```

### 可选依赖（GPU支持）
```bash
pip install paddlepaddle-gpu
```

## 更新日志

### v1.0.0
- 集成PaddleOCR引擎
- 支持GPU加速
- 添加API配置接口
- 增强错误处理
- 优化性能

## 注意事项

1. 首次使用时会自动下载PaddleOCR模型文件
2. GPU模式需要CUDA环境支持
3. 建议在生产环境中启用缓存机制
4. 大文件处理时注意内存使用情况
