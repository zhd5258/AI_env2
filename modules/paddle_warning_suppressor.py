#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaddlePaddle警告抑制器
用于消除PaddlePaddle的ccache警告和其他不必要的警告
"""

import warnings
import os
import logging


def suppress_paddle_warnings():
    """抑制PaddlePaddle相关的警告"""

    # 抑制PaddlePaddle的ccache警告
    warnings.filterwarnings('ignore', message='No ccache found.*')
    warnings.filterwarnings(
        'ignore',
        category=UserWarning,
        module='paddle.utils.cpp_extension.extension_utils',
    )

    # 抑制其他PaddlePaddle相关警告
    warnings.filterwarnings('ignore', category=UserWarning, module='paddle')
    warnings.filterwarnings('ignore', category=FutureWarning, module='paddle')

    # 设置环境变量来抑制PaddlePaddle的警告
    os.environ['PADDLE_DISABLE_CCACHE_WARNING'] = '1'
    os.environ['PADDLE_DISABLE_EXTENSION_WARNING'] = '1'

    # 设置日志级别来抑制PaddlePaddle的日志
    logging.getLogger('paddle').setLevel(logging.ERROR)
    logging.getLogger('paddle.utils.cpp_extension').setLevel(logging.ERROR)

    print('PaddlePaddle警告已抑制')


def setup_paddle_environment():
    """设置PaddlePaddle环境以避免警告"""

    # 设置PaddlePaddle相关环境变量
    paddle_env_vars = {
        'PADDLE_DISABLE_CCACHE_WARNING': '1',
        'PADDLE_DISABLE_EXTENSION_WARNING': '1',
        'PADDLE_DISABLE_CUDA_WARNING': '1',
        'PADDLE_DISABLE_GPU_WARNING': '1',
        'PADDLE_DISABLE_DEPRECATION_WARNING': '1',
    }

    for key, value in paddle_env_vars.items():
        os.environ[key] = value

    # 抑制警告
    suppress_paddle_warnings()


# 在模块导入时自动设置
setup_paddle_environment()
