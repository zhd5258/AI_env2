#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-12 06:54:29
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-12 06:54:32
# 文件相对于项目的路径   : \AI_ENV2\setup.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

with open('requirements.txt', 'r', encoding='utf-8') as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith('#')
    ]

setup(
    name='tender-evaluation-system',
    version='1.0.0',
    author='KingFreeDom',
    author_email='example@example.com',
    description='智能投标文件评标系统',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/your-username/tender-evaluation-system',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    python_requires='>=3.8',
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'tender-eval=app:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.md', '*.txt', '*.json'],
        'templates': ['*.html'],
        'static': ['*.css', '*.js'],
    },
)
