# 系统规则管理说明

## 概述

系统规则管理器用于管理系统级别的强制性规则和规范，这些规则在所有项目中永久有效。规则来源于 [rules.txt](../rules.txt) 文件，并被加载到系统中作为必须遵守的原则。

## 规则来源

系统规则最初来源于项目根目录下的 `rules.txt` 文件。该文件包含了一系列强制性规则，这些规则在系统启动时会被自动加载并转换为JSON格式存储在 `system_rules.json` 文件中。

## API端点

### 获取所有系统规则

```
GET /api/system-rules
```

或

```
GET /api/rules/system
```

返回所有系统规则的列表。

### 获取启用的系统规则

```
GET /api/system-rules/enabled
```

或

```
GET /api/rules/system/enabled
```

返回所有启用的系统规则列表。

### 添加系统规则

```
POST /api/rules/system
```

请求体：
```json
{
  "content": "规则内容"
}
```

### 更新系统规则

```
PUT /api/rules/system/{rule_id}
```

请求体：
```json
{
  "content": "新的规则内容",
  "enabled": true/false
}
```

### 删除系统规则

```
DELETE /api/rules/system/{rule_id}
```

### 重新加载系统规则

```
POST /api/rules/system/reload
```

从 rules.txt 文件重新加载系统规则。

## 规则结构

每条规则包含以下字段：

- `id`: 规则的唯一标识符
- `content`: 规则的具体内容
- `enabled`: 规则是否启用（true/false）
- `created_at`: 规则创建时间（暂未使用）

## 使用示例

### Python代码中使用

```python
from modules.system_rules_manager import system_rules_manager

# 获取所有规则
rules = system_rules_manager.get_all_rules()

# 获取启用的规则
enabled_rules = system_rules_manager.get_enabled_rules()

# 检查代码是否符合规则
violations = system_rules_manager.is_compliant(code_content)
```

### API调用示例

```bash
# 获取所有系统规则
curl http://localhost:8000/api/system-rules

# 添加新规则
curl -X POST http://localhost:8000/api/rules/system \
  -H "Content-Type: application/json" \
  -d '{"content": "新规则内容"}'
```

## 规则持久化

系统规则会被自动保存到 `system_rules.json` 文件中，确保规则在系统重启后仍然有效。当 `rules.txt` 文件被修改后，可以通过调用重新加载API来更新系统规则。

## 注意事项

1. 系统规则具有最高优先级，在所有项目中都必须遵守
2. 规则一旦添加或修改，会立即生效并持久化存储
3. 删除规则时请谨慎操作，删除后无法恢复
4. 系统会定期检查代码是否符合规则要求
