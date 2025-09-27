# Linter配置说明

## 已完成的配置

### 1. VS Code设置 (`.vscode/settings.json`)
- 禁用了pylint的日志格式相关警告
- 配置了诊断严重性覆盖
- 设置了忽略模式

### 2. Pylint配置 (`.pylintrc`)
- 禁用了以下警告：
  - `logging-format-interpolation`
  - `logging-fstring-interpolation`
  - `logging-not-lazy`

### 3. 项目配置 (`pyproject.toml`)
- 配置了pylint、flake8和pyright
- 设置了忽略模式和行长度限制

## 如何应用配置

### 方法1：重启VS Code
1. 完全关闭VS Code
2. 重新打开项目
3. 配置应该自动生效

### 方法2：重新加载VS Code窗口
1. 按 `Ctrl+Shift+P` 打开命令面板
2. 输入 "Developer: Reload Window"
3. 选择并执行

### 方法3：手动重新加载Python扩展
1. 按 `Ctrl+Shift+P` 打开命令面板
2. 输入 "Python: Restart Language Server"
3. 选择并执行

## 验证配置是否生效

运行以下命令检查linter错误：
```bash
python -c "import main; print('检查完成')"
```

如果仍然看到"Use lazy % formatting in logging functions"警告，请：
1. 确保已重启VS Code
2. 检查Python扩展是否已更新
3. 确认配置文件语法正确

## 配置文件位置

- `.vscode/settings.json` - VS Code设置
- `.pylintrc` - Pylint配置
- `setup.cfg` - 通用配置
- `pyproject.toml` - 现代Python项目配置
