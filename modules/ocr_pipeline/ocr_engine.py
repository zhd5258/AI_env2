from __future__ import annotations

import os
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import paddle
import cv2
from paddleocr import PaddleOCR

from .models import BBox, OCRLine


class OCREngine:
    def __init__(
        self,
        lang: str = 'ch',
        use_angle_cls: bool = True,
        use_gpu: bool = False,
        det_model_dir: str | None = None,
        rec_model_dir: str | None = None,
        cls_model_dir: str | None = None,
        det_limit_side_len: int = 960,
        rec_batch_num: int = 6,
        enable_mkldnn: bool = False,
    ) -> None:
        # 初始化logger
        import logging

        self.logger = logging.getLogger(__name__)

        # 设置设备 - 优化GPU支持
        self.use_gpu = use_gpu
        device = 'cpu'

        if use_gpu:
            try:
                # 检查CUDA编译支持
                has_cuda = paddle.device.is_compiled_with_cuda()
                if not has_cuda:
                    print(
                        '[WARNING] PaddlePaddle未编译CUDA支持，请安装paddlepaddle-gpu版本'
                    )
                    device = 'cpu'
                else:
                    # 检查GPU设备数量
                    gpu_count = paddle.device.cuda.device_count()
                    if gpu_count == 0:
                        print('[WARNING] 未检测到GPU设备，请检查NVIDIA驱动和CUDA安装')
                        device = 'cpu'
                    else:
                        device = 'gpu'
                        paddle.set_device('gpu:0')  # 使用第一个GPU
                        print(
                            f'[INFO] 成功启用GPU加速，使用设备: gpu:0 (共{gpu_count}个GPU)'
                        )
            except Exception as e:
                print(f'[WARNING] GPU检测失败: {e}，自动切换到CPU模式')
                device = 'cpu'

        if device == 'cpu':
            paddle.set_device('cpu')
            print('[INFO] 使用CPU模式')

        # 如果没有指定模型路径，尝试查找系统安装的模型
        if det_model_dir is None or rec_model_dir is None or cls_model_dir is None:
            # 尝试在常见的模型路径中查找
            model_paths = self._find_model_paths(lang)
            if det_model_dir is None:
                det_model_dir = model_paths.get('det')
            if rec_model_dir is None:
                rec_model_dir = model_paths.get('rec')
            if cls_model_dir is None:
                cls_model_dir = model_paths.get('cls')

        # 初始化PaddleOCR 3.2.0，使用新的参数名
        ocr_params = {
            'lang': lang,
            # 使用3.2.0版本的新参数名
            'use_textline_orientation': use_angle_cls,  # 替代use_angle_cls
            'text_det_limit_side_len': det_limit_side_len,  # 替代det_limit_side_len
            'text_recognition_batch_size': rec_batch_num,  # 替代rec_batch_num
        }

        # 添加模型路径（如果指定）
        if det_model_dir:
            ocr_params['text_detection_model_dir'] = det_model_dir
        if rec_model_dir:
            ocr_params['text_recognition_model_dir'] = rec_model_dir
        if cls_model_dir:
            ocr_params['textline_orientation_model_dir'] = cls_model_dir

        # 初始化PaddleOCR 3.2.0（设备通过paddle.set_device设置）
        # 兼容性修复：使用最简参数初始化，避免版本兼容性问题
        try:
            # 首先尝试使用所有参数
            self.ocr = PaddleOCR(**ocr_params)
        except Exception as e:
            self.logger.warning(f'使用完整参数初始化失败: {e}，尝试简化参数')
            # 如果失败，使用最基本的参数
            basic_params = {
                'use_angle_cls': ocr_params.get('use_angle_cls', True),
                'lang': ocr_params.get('lang', 'ch'),
            }
            # 不再包含use_gpu参数，由PaddleOCR自动检测设备
            self.logger.warning('使用基本参数重新初始化PaddleOCR（不包含use_gpu）')
            self.ocr = PaddleOCR(**basic_params)

    def _find_model_paths(self, lang: str) -> dict:
        """
        查找模型路径
        """
        model_paths = {}

        # 获取用户主目录
        home_dir = os.path.expanduser('~')

        # 常见的模型路径
        possible_paths = [
            os.path.join(home_dir, '.paddleocr', 'inference'),
            os.path.join(home_dir, '.paddlex', 'inference'),
            os.path.join(home_dir, '.paddlex', 'official_models'),
            '/root/.paddleocr/inference',
            '/root/.paddlex/inference',
            '/root/.paddlex/official_models',
            '/usr/local/share/paddleocr/inference',
            '/usr/share/paddleocr/inference',
        ]

        # 模型文件夹名称映射
        model_name_map = {
            'ch': {
                'det': [
                    'ch_PP-OCRv4_det_infer',
                    'ch_PP-OCRv3_det_infer',
                    'ch_ppocr_mobile_v2.0_det_infer',
                ],
                'rec': [
                    'ch_PP-OCRv4_rec_infer',
                    'ch_PP-OCRv3_rec_infer',
                    'ch_ppocr_mobile_v2.0_rec_infer',
                ],
                'cls': ['ch_ppocr_mobile_v2.0_cls_infer'],
            },
            'en': {
                'det': ['en_PP-OCRv4_det_infer', 'en_PP-OCRv3_det_infer'],
                'rec': ['en_PP-OCRv4_rec_infer', 'en_PP-OCRv3_rec_infer'],
                'cls': ['ch_ppocr_mobile_v2.0_cls_infer'],
            },
        }

        # 根据语言选择模型名称
        lang_models = model_name_map.get(lang, model_name_map['ch'])

        # 在可能的路径中查找模型
        for base_path in possible_paths:
            if os.path.exists(base_path):
                # 查找检测模型
                for det_name in lang_models['det']:
                    det_path = os.path.join(base_path, det_name)
                    if os.path.exists(det_path):
                        model_paths['det'] = det_path
                        break

                # 查找识别模型
                for rec_name in lang_models['rec']:
                    rec_path = os.path.join(base_path, rec_name)
                    if os.path.exists(rec_path):
                        model_paths['rec'] = rec_path
                        break

                # 查找分类模型
                for cls_name in lang_models['cls']:
                    cls_path = os.path.join(base_path, cls_name)
                    if os.path.exists(cls_path):
                        model_paths['cls'] = cls_path
                        break

                # 如果找到了所有模型，就退出循环
                if (
                    'det' in model_paths
                    and 'rec' in model_paths
                    and 'cls' in model_paths
                ):
                    break

        return model_paths

    def infer(self, image_bgr: np.ndarray) -> List[OCRLine]:
        # Preprocess image to improve OCR on watermarked/signed documents
        processed = self._preprocess_image(image_bgr)
        # Convert BGR to RGB for PaddleOCR compatibility
        image_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        result = self.ocr.ocr(image_rgb)

        lines: List[OCRLine] = []
        if not result:
            return lines

        # Handle PaddleOCR 2.8.1 result format
        # result is a list of pages, each page contains list of [points, (text, score)]
        for page_result in result:
            if not page_result:
                continue
            for entry in page_result:
                if not entry or len(entry) < 2:
                    continue

                points = entry[0]
                text_info = entry[1]

                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    text = str(text_info[0])
                    score = float(text_info[1])
                else:
                    text = str(text_info)
                    score = 1.0

                if points and text:
                    # 确保points是正确的数据类型
                    try:
                        xs = [int(float(p[0])) for p in points]
                        ys = [int(float(p[1])) for p in points]
                        bbox = BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                        lines.append(
                            OCRLine(text=text, score=score, bbox=bbox, words=[])
                        )
                    except (ValueError, TypeError):
                        # 如果转换失败，跳过这个检测框
                        continue

        lines.sort(key=lambda l: (l.bbox.y1, l.bbox.x1))
        return lines

    def infer_batch(
        self, images: List[np.ndarray], workers: int = 4
    ) -> List[List[OCRLine]]:
        """
        并行处理多个图像

        Args:
            images: 图像列表
            workers: 并行处理的工作线程数

        Returns:
            每个图像的OCR结果列表
        """
        if workers <= 1:
            # 如果工作线程数小于等于1，则顺序处理
            return [self.infer(img) for img in images]

        results = [None] * len(images)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交任务
            future_to_index = {
                executor.submit(self.infer, img): i for i, img in enumerate(images)
            }

            # 收集结果
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    print(f'[ERROR] 处理图像 {index} 时出错: {e}')
                    results[index] = []

        return results

    def _preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """Preprocess image to improve OCR on watermarked/signed documents"""
        # Ensure image is valid
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        # Convert to grayscale if needed
        if len(image_bgr.shape) == 3 and image_bgr.shape[2] == 3:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_bgr

        # Apply contrast enhancement
        # Note: This is a simple approach; more sophisticated methods could be used
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Convert back to BGR if needed
        if len(image_bgr.shape) == 3 and image_bgr.shape[2] == 3:
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

        return enhanced
