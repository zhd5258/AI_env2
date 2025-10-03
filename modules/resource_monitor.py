#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统资源监控和清理模块
当检测到资源耗尽时，自动清理无用的线程和进程
"""

import psutil
import threading
import time
import logging
import gc
import os
import signal
from typing import List, Dict, Any


class ResourceMonitor:
    """系统资源监控器"""

    def __init__(self, memory_threshold=85, cpu_threshold=90):
        """
        初始化资源监控器

        Args:
            memory_threshold: 内存使用率阈值(%)
            cpu_threshold: CPU使用率阈值(%)
        """
        self.memory_threshold = memory_threshold
        self.cpu_threshold = cpu_threshold
        self.logger = logging.getLogger(__name__)
        self.monitoring = False
        self.monitor_thread = None
        self.current_process = psutil.Process()
        self.cleanup_count = 0

    def start_monitoring(self):
        """开始监控"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self.monitor_thread.start()
            self.logger.info('资源监控器已启动')

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info('资源监控器已停止')

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 检查系统资源
                memory_percent = psutil.virtual_memory().percent
                cpu_percent = psutil.cpu_percent(interval=1)

                # 检查当前进程资源
                process_memory = self.current_process.memory_percent()
                process_cpu = self.current_process.cpu_percent()

                self.logger.debug(
                    f'系统资源: 内存 {memory_percent:.1f}%, CPU {cpu_percent:.1f}% | '
                    f'进程资源: 内存 {process_memory:.1f}%, CPU {process_cpu:.1f}%'
                )

                # 检查是否需要清理
                if (
                    memory_percent > self.memory_threshold
                    or cpu_percent > self.cpu_threshold
                    or process_memory > 50
                ):  # 进程内存超过50%也要清理
                    self.logger.warning(
                        f'资源使用率过高！系统内存: {memory_percent:.1f}%, '
                        f'CPU: {cpu_percent:.1f}%, 进程内存: {process_memory:.1f}%'
                    )

                    self._emergency_cleanup()

                time.sleep(30)  # 每30秒检查一次

            except Exception as e:
                self.logger.error(f'资源监控出错: {e}')
                time.sleep(60)  # 出错后等待更长时间

    def _emergency_cleanup(self):
        """紧急资源清理"""
        self.cleanup_count += 1
        self.logger.warning(f'开始第 {self.cleanup_count} 次紧急资源清理')

        try:
            # 1. 强制垃圾回收
            self._force_garbage_collection()

            # 2. 清理僵尸子进程
            self._cleanup_zombie_processes()

            # 3. 清理PaddleOCR相关进程
            self._cleanup_paddle_processes()

            # 4. 清理Python子进程
            self._cleanup_python_subprocesses()

            # 5. 限制线程数量
            self._cleanup_excess_threads()

            # 6. 清理临时文件
            self._cleanup_temp_files()

            self.logger.info('紧急资源清理完成')

        except Exception as e:
            self.logger.error(f'紧急清理失败: {e}')

    def _force_garbage_collection(self):
        """强制垃圾回收"""
        try:
            # 多次执行垃圾回收
            for i in range(3):
                collected = gc.collect()
                self.logger.info(f'垃圾回收第 {i + 1} 轮: 清理了 {collected} 个对象')

            # 清理不可达的循环引用
            gc.set_debug(gc.DEBUG_UNCOLLECTABLE)

        except Exception as e:
            self.logger.error(f'垃圾回收失败: {e}')

    def _cleanup_zombie_processes(self):
        """清理僵尸进程"""
        try:
            zombie_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        self.logger.warning(
                            f'发现僵尸进程: PID {proc.info["pid"]}, 名称 {proc.info["name"]}'
                        )
                        zombie_count += 1
                        # 尝试清理僵尸进程
                        try:
                            os.waitpid(proc.info['pid'], os.WNOHANG)
                        except:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if zombie_count > 0:
                self.logger.info(f'清理了 {zombie_count} 个僵尸进程')

        except Exception as e:
            self.logger.error(f'清理僵尸进程失败: {e}')

    def _cleanup_paddle_processes(self):
        """清理PaddleOCR相关进程"""
        try:
            killed_count = 0
            current_pid = os.getpid()

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue

                    # 检查是否是paddle相关进程
                    name = proc.info['name'].lower()
                    cmdline = ' '.join(proc.info['cmdline'] or []).lower()

                    if (
                        'paddle' in name
                        or 'paddle' in cmdline
                        or 'ppocr' in name
                        or 'ppocr' in cmdline
                        or 'onnx' in name
                        or 'onnx' in cmdline
                    ):
                        # 检查进程运行时间，超过1小时的强制杀死
                        create_time = proc.create_time()
                        if time.time() - create_time > 3600:  # 1小时
                            self.logger.warning(
                                f'杀死长时间运行的paddle进程: PID {proc.info["pid"]}, '
                                f'名称 {proc.info["name"]}'
                            )
                            proc.kill()
                            killed_count += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed_count > 0:
                self.logger.info(f'强制杀死了 {killed_count} 个paddle相关进程')

        except Exception as e:
            self.logger.error(f'清理paddle进程失败: {e}')

    def _cleanup_python_subprocesses(self):
        """清理Python子进程"""
        try:
            killed_count = 0
            current_pid = os.getpid()

            # 获取当前进程的所有子进程
            children = self.current_process.children(recursive=True)

            for child in children:
                try:
                    # 检查子进程运行时间
                    create_time = child.create_time()
                    if time.time() - create_time > 1800:  # 30分钟
                        self.logger.warning(
                            f'杀死长时间运行的子进程: PID {child.pid}, '
                            f'名称 {child.name()}'
                        )
                        child.terminate()
                        # 等待3秒后强制杀死
                        try:
                            child.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            child.kill()
                        killed_count += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed_count > 0:
                self.logger.info(f'清理了 {killed_count} 个子进程')

        except Exception as e:
            self.logger.error(f'清理子进程失败: {e}')

    def _cleanup_excess_threads(self):
        """清理过多的线程"""
        try:
            # 获取当前线程数
            thread_count = threading.active_count()
            self.logger.info(f'当前活跃线程数: {thread_count}')

            if thread_count > 50:  # 如果线程数超过50个
                self.logger.warning(f'线程数过多 ({thread_count})，尝试清理')

                # 强制垃圾回收可能有助于清理死线程
                gc.collect()

                # 记录所有活跃线程
                for thread in threading.enumerate():
                    if thread != threading.current_thread():
                        self.logger.debug(
                            f'活跃线程: {thread.name}, 守护线程: {thread.daemon}'
                        )

        except Exception as e:
            self.logger.error(f'线程清理失败: {e}')

    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            temp_dirs = ['temp_uploads', 'temp_word', 'temp_pdf_cache']
            cleaned_count = 0

            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    try:
                        # 清理超过2小时的临时文件
                        current_time = time.time()
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    if (
                                        current_time - os.path.getmtime(file_path)
                                        > 7200
                                    ):  # 2小时
                                        os.remove(file_path)
                                        cleaned_count += 1
                                except:
                                    pass
                    except Exception as e:
                        self.logger.error(f'清理 {temp_dir} 失败: {e}')

            if cleaned_count > 0:
                self.logger.info(f'清理了 {cleaned_count} 个临时文件')

        except Exception as e:
            self.logger.error(f'临时文件清理失败: {e}')

    def get_resource_info(self) -> Dict[str, Any]:
        """获取当前资源信息"""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)

            process_info = {
                'memory_percent': self.current_process.memory_percent(),
                'cpu_percent': self.current_process.cpu_percent(),
                'num_threads': self.current_process.num_threads(),
                'num_fds': self.current_process.num_fds()
                if hasattr(self.current_process, 'num_fds')
                else 0,
            }

            return {
                'system': {
                    'memory_total': memory.total,
                    'memory_available': memory.available,
                    'memory_percent': memory.percent,
                    'cpu_percent': cpu_percent,
                },
                'process': process_info,
                'cleanup_count': self.cleanup_count,
            }
        except Exception as e:
            self.logger.error(f'获取资源信息失败: {e}')
            return {}


# 全局资源监控器实例
_resource_monitor = None


def get_resource_monitor() -> ResourceMonitor:
    """获取全局资源监控器实例"""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def start_resource_monitoring():
    """启动资源监控"""
    monitor = get_resource_monitor()
    monitor.start_monitoring()


def stop_resource_monitoring():
    """停止资源监控"""
    monitor = get_resource_monitor()
    monitor.stop_monitoring()


def force_cleanup():
    """强制执行资源清理"""
    monitor = get_resource_monitor()
    monitor._emergency_cleanup()
