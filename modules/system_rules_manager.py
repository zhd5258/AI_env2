#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
系统规则管理器
用于管理系统的强制性规则和规范
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# 系统规则文件路径
SYSTEM_RULES_FILE = Path('system_rules.json')
DEFAULT_RULES_FILE = Path('rules.txt')

logger = logging.getLogger(__name__)


class SystemRulesManager:
    """系统规则管理器，统一管理系统级别的强制性规则和规范"""

    def __init__(self):
        self.rules = []
        # 不在初始化时自动加载规则
        # self.load_rules()

    def load_rules(self) -> bool:
        """
        加载系统规则
        
        Returns:
            bool: 是否加载成功
        """
        try:
            # 首先尝试从JSON文件加载规则
            if SYSTEM_RULES_FILE.exists():
                with open(SYSTEM_RULES_FILE, 'r', encoding='utf-8') as f:
                    self.rules = json.load(f)
                    logger.info(f'从 {SYSTEM_RULES_FILE} 加载了 {len(self.rules)} 条系统规则')
                    return True
            
            # 如果JSON文件不存在，尝试从rules.txt加载
            if DEFAULT_RULES_FILE.exists():
                self.rules = self._load_from_txt_file(DEFAULT_RULES_FILE)
                # 保存为JSON格式以便后续快速加载
                self.save_rules()
                logger.info(f'从 {DEFAULT_RULES_FILE} 加载了 {len(self.rules)} 条系统规则并保存为JSON格式')
                return True
                
            logger.warning('未找到系统规则文件')
            return False
            
        except Exception as e:
            logger.error(f'加载系统规则时出错: {e}', exc_info=True)
            return False

    def _load_from_txt_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        从文本文件加载规则
        
        Args:
            file_path: 规则文件路径
            
        Returns:
            List[Dict[str, Any]]: 规则列表
        """
        rules = []
        try:
            # 尝试不同的编码方式
            encodings = ['utf-8', 'gbk', 'gb2312']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise UnicodeDecodeError("无法使用任何支持的编码读取文件")
                
            lines = content.splitlines()
                
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    # 移除行号和分隔符（如果有的话）
                    if '、' in line:
                        content = line.split('、', 1)[1]
                    else:
                        content = line
                        
                    rules.append({
                        'id': i,
                        'content': content,
                        'enabled': True,
                        'created_at': None
                    })
                    
            return rules
        except Exception as e:
            logger.error(f'从文本文件加载规则时出错: {e}', exc_info=True)
            return []

    def save_rules(self) -> bool:
        """
        保存系统规则到JSON文件
        
        Returns:
            bool: 是否保存成功
        """
        try:
            with open(SYSTEM_RULES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
            logger.info(f'系统规则已保存到 {SYSTEM_RULES_FILE}')
            return True
        except Exception as e:
            logger.error(f'保存系统规则时出错: {e}', exc_info=True)
            return False

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """
        获取所有系统规则
        
        Returns:
            List[Dict[str, Any]]: 所有规则列表
        """
        return self.rules

    def get_enabled_rules(self) -> List[Dict[str, Any]]:
        """
        获取所有启用的系统规则
        
        Returns:
            List[Dict[str, Any]]: 启用的规则列表
        """
        return [rule for rule in self.rules if rule.get('enabled', True)]

    def add_rule(self, content: str) -> bool:
        """
        添加新规则
        
        Args:
            content: 规则内容
            
        Returns:
            bool: 是否添加成功
        """
        try:
            new_rule = {
                'id': len(self.rules) + 1,
                'content': content,
                'enabled': True,
                'created_at': None
            }
            self.rules.append(new_rule)
            logger.info(f'添加新规则: {content}')
            return True
        except Exception as e:
            logger.error(f'添加规则时出错: {e}', exc_info=True)
            return False

    def update_rule(self, rule_id: int, content: str = None, enabled: bool = None) -> bool:
        """
        更新规则
        
        Args:
            rule_id: 规则ID
            content: 新的规则内容（可选）
            enabled: 是否启用（可选）
            
        Returns:
            bool: 是否更新成功
        """
        try:
            for rule in self.rules:
                if rule['id'] == rule_id:
                    if content is not None:
                        rule['content'] = content
                    if enabled is not None:
                        rule['enabled'] = enabled
                    logger.info(f'更新规则 {rule_id}')
                    return True
            logger.warning(f'未找到ID为 {rule_id} 的规则')
            return False
        except Exception as e:
            logger.error(f'更新规则时出错: {e}', exc_info=True)
            return False

    def delete_rule(self, rule_id: int) -> bool:
        """
        删除规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            self.rules = [rule for rule in self.rules if rule['id'] != rule_id]
            logger.info(f'删除规则 {rule_id}')
            return True
        except Exception as e:
            logger.error(f'删除规则时出错: {e}', exc_info=True)
            return False

    def is_compliant(self, code_content: str) -> List[Dict[str, Any]]:
        """
        检查代码是否符合系统规则
        
        Args:
            code_content: 代码内容
            
        Returns:
            List[Dict[str, Any]]: 不符合的规则列表
        """
        violations = []
        enabled_rules = self.get_enabled_rules()
        
        for rule in enabled_rules:
            # 简单的规则检查实现
            # 实际应用中可以根据规则内容进行更复杂的检查
            if '不允许测试文件存放在项目根目录内' in rule['content']:
                if 'test' in code_content and 'import' in code_content:
                    # 这只是一个示例检查，实际检查会更复杂
                    violations.append(rule)
            elif '主程序内不允许写入路由' in rule['content']:
                if 'app.get(' in code_content or 'app.post(' in code_content:
                    if 'main.py' in code_content:
                        violations.append(rule)
            # 可以添加更多规则检查逻辑
        
        return violations


# 不在模块导入时自动创建实例
# 创建全局实例
# system_rules_manager = SystemRulesManager()
