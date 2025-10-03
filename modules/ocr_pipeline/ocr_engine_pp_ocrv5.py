from __future__ import annotations

import os
from typing import List

import numpy as np
import cv2
from paddleocr import PaddleOCR

from .models import BBox, OCRLine


class OCREngine:
    """
    基于PaddleOCR PP-OCRv5的OCR引擎
    提供与RapidOCR相同的接口，但使用更先进的PP-OCRv5模型
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
        初始化PP-OCRv5 OCR引擎

        Args:
            lang: 语言设置，默认为中文
            use_angle_cls: 是否使用文字方向分类
            use_gpu: 是否使用GPU加速
            det_model_dir: 检测模型目录
            rec_model_dir: 识别模型目录
            cls_model_dir: 分类模型目录
            det_limit_side_len: 检测模型输入图像最大边长
            rec_batch_num: 识别模型批处理数量
            enable_mkldnn: 是否启用MKL-DNN加速
        """
        # 设置设备
        device = 'gpu' if use_gpu else 'cpu'
        if use_gpu:
            print('[INFO] 使用GPU加速 (PaddleOCR PP-OCRv5)')
        else:
            print('[INFO] 使用CPU模式 (PaddleOCR PP-OCRv5)')

        # 如果没有指定模型路径，使用PP-OCRv5默认模型
        if det_model_dir is None or rec_model_dir is None or cls_model_dir is None:
            model_paths = self._find_pp_ocrv5_models()
            if det_model_dir is None:
                det_model_dir = model_paths.get('det')
            if rec_model_dir is None:
                rec_model_dir = model_paths.get('rec')
            if cls_model_dir is None:
                cls_model_dir = model_paths.get('cls')

        # 设置设备 - PaddleOCR 3.2.0不再支持use_gpu参数
        import paddle

        if use_gpu:
            if (
                paddle.device.is_compiled_with_cuda()
                and paddle.device.cuda.device_count() > 0
            ):
                paddle.set_device('gpu:0')
                print('[INFO] PP-OCRv5将使用GPU加速 (PaddleOCR 3.2.0)')
            else:
                paddle.set_device('cpu')
                print('[WARNING] GPU不可用，PP-OCRv5使用CPU模式')
        else:
            paddle.set_device('cpu')
            print('[INFO] PP-OCRv5将使用CPU模式 (PaddleOCR 3.2.0)')

        # 初始化PaddleOCR 3.2.0 PP-OCRv5，使用新参数名
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
        执行OCR识别

        Args:
            image_bgr: BGR格式的输入图像

        Returns:
            OCR识别结果列表
        """
        # 预处理图像以提高OCR效果
        processed = self._preprocess_image(image_bgr)

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

    def _preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        预处理图像以提高OCR效果

        Args:
            image_bgr: BGR格式的输入图像

        Returns:
            预处理后的图像
        """
        # 确保图像有效
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        # 转换为灰度图像进行处理
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        # 去噪处理（针对水印/签名文档优化）
        denoised = cv2.fastNlMeansDenoising(
            gray, h=10, templateWindowSize=7, searchWindowSize=21
        )

        # 使用CLAHE增强对比度
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # 多种阈值化方法组合
        # 方法1: Otsu阈值
        _, binary1 = cv2.threshold(
            enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # 方法2: 自适应阈值
        binary2 = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
        )

        # 组合两种方法
        combined = cv2.bitwise_and(binary1, binary2)

        # 形态学操作清理
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # 转换回BGR格式
        result = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
        return result
