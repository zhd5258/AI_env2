from __future__ import annotations

import os
from typing import List

import numpy as np
import cv2
from paddleocr import PaddleOCR

from .models import BBox, OCRLine


class OCREngine:
    """
    优化的PP-OCRv5 OCR引擎
    针对速度和识别效果进行优化
    """

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
        enable_mkldnn: bool = True,
    ) -> None:
        """
        初始化优化的PP-OCRv5 OCR引擎
        """
        # 设置设备
        if use_gpu:
            print('[INFO] 使用GPU加速 (PaddleOCR PP-OCRv5 优化版)')
        else:
            print('[INFO] 使用CPU模式 (PaddleOCR PP-OCRv5 优化版)')

        # 如果没有指定模型路径，使用PP-OCRv5默认模型
        if det_model_dir is None or rec_model_dir is None or cls_model_dir is None:
            model_paths = self._find_pp_ocrv5_models()
            if det_model_dir is None:
                det_model_dir = model_paths.get('det')
            if rec_model_dir is None:
                rec_model_dir = model_paths.get('rec')
            if cls_model_dir is None:
                cls_model_dir = model_paths.get('cls')

        # 优化参数设置
        self.det_limit_side_len = det_limit_side_len
        self.rec_batch_num = rec_batch_num

        # 初始化PaddleOCR 3.2.0 PP-OCRv5（优化配置）
        ocr_params = {
            'use_angle_cls': use_angle_cls,  # 3.2.0版本使用标准参数名
            'lang': lang,
            'det_model_dir': det_model_dir,
            'rec_model_dir': rec_model_dir,
            'cls_model_dir': cls_model_dir,
            'det_limit_side_len': det_limit_side_len,
            'rec_batch_num': rec_batch_num,
            'enable_mkldnn': enable_mkldnn,
            # 优化参数（PaddleOCR 3.2.0兼容）
            'det_db_thresh': 0.3,  # 降低检测阈值，提高召回率
            'det_db_box_thresh': 0.5,  # 降低框阈值
            'det_db_unclip_ratio': 1.6,  # 调整框扩展比例
        }

        # PaddleOCR 3.2.0版本GPU支持
        if use_gpu:
            ocr_params['use_gpu'] = True
            print('[INFO] 优化版PP-OCRv5将使用GPU加速 (PaddleOCR 3.2.0)')
        else:
            ocr_params['use_gpu'] = False
            print('[INFO] 优化版PP-OCRv5将使用CPU模式 (PaddleOCR 3.2.0)')

        self.ocr = PaddleOCR(**ocr_params)

    def _find_pp_ocrv5_models(self) -> dict:
        """
        查找PP-OCRv5模型路径
        """
        model_paths = {}

        # 获取用户主目录
        home_dir = os.path.expanduser('~')

        # PP-OCRv5模型路径
        possible_paths = [
            os.path.join(home_dir, '.paddlex', 'official_models'),
            os.path.join(home_dir, '.paddleocr', 'inference'),
            '/root/.paddlex/official_models',
            '/root/.paddleocr/inference',
        ]

        # PP-OCRv5模型名称
        pp_ocrv5_models = {
            'det': 'PP-OCRv5_server_det',
            'rec': 'PP-OCRv5_server_rec',
            'cls': 'ch_ppocr_mobile_v2.0_cls_infer',  # 分类模型使用v2.0
        }

        # 在可能的路径中查找PP-OCRv5模型
        for base_path in possible_paths:
            if os.path.exists(base_path):
                for model_type, model_name in pp_ocrv5_models.items():
                    model_path = os.path.join(base_path, model_name)
                    if os.path.exists(model_path):
                        model_paths[model_type] = model_path
                        print(f'[INFO] 找到PP-OCRv5 {model_type}模型: {model_path}')

        return model_paths

    def infer(self, image_bgr: np.ndarray) -> List[OCRLine]:
        """
        执行OCR识别（优化版）
        """
        # 轻量级预处理，避免过度处理
        processed = self._light_preprocess_image(image_bgr)

        # 转换BGR到RGB（PaddleOCR需要RGB格式）
        image_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

        # 执行OCR识别
        result = self.ocr.ocr(image_rgb)

        lines: List[OCRLine] = []
        if not result:
            return lines

        # 处理PaddleOCR结果格式
        for page_result in result:
            if not page_result:
                continue
            for entry in page_result:
                if not entry or len(entry) < 2:
                    continue

                points = entry[0]  # 边界框点坐标
                text_info = entry[1]  # 文本和置信度

                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    text = str(text_info[0])
                    score = float(text_info[1])
                else:
                    text = str(text_info)
                    score = 1.0

                if points and text:
                    try:
                        # 转换边界框点坐标
                        xs = [int(float(p[0])) for p in points]
                        ys = [int(float(p[1])) for p in points]
                        bbox = BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                        lines.append(
                            OCRLine(text=text, score=score, bbox=bbox, words=[])
                        )
                    except (ValueError, TypeError):
                        # 如果坐标转换失败，跳过这个检测框
                        continue

        # 按位置排序（从上到下，从左到右）
        lines.sort(key=lambda l: (l.bbox.y1, l.bbox.x1))
        return lines

    def _light_preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        轻量级图像预处理（优化速度）
        """
        # 确保图像有效
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        # 如果图像太小，进行放大
        h, w = image_bgr.shape[:2]
        if h < 32 or w < 32:
            scale = max(32 / h, 32 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(
                image_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC
            )

        # 如果图像太大，进行适当缩放（保持长宽比）
        max_size = self.det_limit_side_len
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(
                image_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA
            )

        # 简单的对比度增强
        if len(image_bgr.shape) == 3:
            # 转换到LAB色彩空间进行亮度调整
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)

            # 对L通道进行CLAHE增强
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)

            # 合并通道并转换回BGR
            lab = cv2.merge([l, a, b])
            image_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return image_bgr

    def infer_batch(
        self, images: List[np.ndarray], workers: int = 4
    ) -> List[List[OCRLine]]:
        """
        批量处理多个图像（优化版）
        """
        if workers <= 1:
            return [self.infer(img) for img in images]

        # 使用较小的批处理大小以提高效率
        batch_size = max(1, len(images) // workers)
        results = []

        for i in range(0, len(images), batch_size):
            batch = images[i : i + batch_size]
            batch_results = [self.infer(img) for img in batch]
            results.extend(batch_results)

        return results
