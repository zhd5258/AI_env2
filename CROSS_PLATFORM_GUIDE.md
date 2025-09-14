# 跨平台使用指南

## 项目改造说明

已将 `main.py` 改造为跨平台兼容版本，支持 Windows 和 Ubuntu 系统。

### 主要改造内容

1. **路径处理**: 使用 `pathlib.Path` 替代 `os.path`，确保路径分隔符兼容
2. **文件操作**: 使用跨平台安全的目录创建和文件操作
3. **编码处理**: 添加了 Linux/Unix 系统的编码配置
4. **启动脚本**: 提供 Windows 和 Linux 的启动脚本

### 启动方式

#### Windows 系统
1. 双击运行 `run.bat`
2. 或者在命令行中运行:
   ```cmd
   python run.py
   ```

#### Linux/Ubuntu 系统
1. 给启动脚本添加执行权限:
   ```bash
   chmod +x run.sh
   ```
2. 运行启动脚本:
   ```bash
   ./run.sh
   ```
3. 或者直接运行:
   ```bash
   python3 run.py
   ```

#### 通用方式
```bash
python run.py
```

### 服务访问
启动成功后，在浏览器中访问: http://localhost:8000

### 依赖要求
- Python 3.8+
- 依赖包: 见 `requirements.txt`

### 验证测试
运行测试脚本验证跨平台兼容性:
```bash
python test_cross_platform.py
```

## 文件说明

- `main.py` - 主程序文件（已改造为跨平台兼容）
- `run.py` - 跨平台启动脚本
- `run.bat` - Windows 启动批处理文件
- `run.sh` - Linux/Mac 启动脚本
- `test_cross_platform.py` - 跨平台兼容性测试脚本

## 注意事项

1. 确保所有必要的目录存在（uploads, static, templates）
2. 首次运行前安装依赖: `pip install -r requirements.txt`
3. 在 Linux 系统上可能需要安装额外的系统依赖