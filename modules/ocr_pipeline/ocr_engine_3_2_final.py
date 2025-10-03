
from __future__ import annotations

import os
from typing import List

import numpy as np
import cv2
import paddle
from paddleocr import PaddleOCR

from .models import BBox, OCRLine


class OCREngine:
    """
    PaddleOCR 3.2.0兼容的OCR引擎
    """

    def __init__(
        self,
        lang: str = 'ch',
        use_angle_cls: bool = True,
        use_gpu: bool = True,
        det_model_dir: str | None = None,
        rec_model_dir: str | None = None,
        cls_model_dir: str | None = None,
        det_limit_side_len: int = 960,
        rec_batch_num: int = 6,
        enable_mkldnn: bool = True,
    ) -> None:
        """
        初始化PaddleOCR 3.2.0兼容引擎
        """
        self.use_gpu = use_gpu
        
        # 设置设备 - PaddleOCR 3.2.0不再支持use_gpu参数
        if use_gpu:
            if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
                paddle.set_device('gpu:0')
                print('[INFO] PaddleOCR 3.2.0使用GPU加速')
            else:
                paddle.set_device('cpu')
                print('[WARNING] GPU不可用，PaddleOCR 3.2.0使用CPU模式')
        else:
            paddle.set_device('cpu')
            print('[INFO] PaddleOCR 3.2.0使用CPU模式')

        # 构建PaddleOCR 3.2.0兼容参数
        ocr_params = {
            'lang': lang,
            # 使用新的参数名（3.2.0版本）
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
        
        # 初始化PaddleOCR 3.2.0
        self.ocr = PaddleOCR(**ocr_params)

    def infer(self, image_bgr: np.ndarray) -> List[OCRLine]:
        """
        执行OCR识别（3.2.0版本兼容）
        """
        # 预处理图像
        processed = self._preprocess_image(image_bgr)
        
        # 转换BGR到RGB
        image_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        
        # 执行OCR识别
        result = self.ocr.ocr(image_rgb)
        
        lines: List[OCRLine] = []
        if not result:
            return lines
        
        # 处理PaddleOCR 3.2.0结果格式
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
                    try:
                        xs = [int(float(p[0])) for p in points]
                        ys = [int(float(p[1])) for p in points]
                        bbox = BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                        lines.append(OCRLine(text=text, score=score, bbox=bbox, words=[]))
                    except (ValueError, TypeError):
                        continue
        
        lines.sort(key=lambda l: (l.bbox.y1, l.bbox.x1))
        return lines

    def _preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """图像预处理"""
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr
        
        # 简单的对比度增强
        if len(image_bgr.shape) == 3:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        
        return image_bgr
