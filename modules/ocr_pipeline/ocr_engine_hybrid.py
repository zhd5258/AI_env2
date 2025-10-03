from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
import cv2
from rapidocr_onnxruntime import RapidOCR
from paddleocr import PaddleOCR

from .models import BBox, OCRLine


class OCREngine:
    """
    混合OCR引擎
    结合RapidOCR的速度和PP-OCRv5的精度
    根据图像特征自动选择最适合的引擎
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
        # 混合引擎特有参数
        use_hybrid: bool = True,
        confidence_threshold: float = 0.8,
        fallback_to_pp_ocrv5: bool = True,
    ) -> None:
        """
        初始化混合OCR引擎
        
        Args:
            use_hybrid: 是否启用混合模式
            confidence_threshold: 置信度阈值，低于此值会尝试PP-OCRv5
            fallback_to_pp_ocrv5: 是否在RapidOCR效果不佳时回退到PP-OCRv5
        """
        self.use_hybrid = use_hybrid
        self.confidence_threshold = confidence_threshold
        self.fallback_to_pp_ocrv5 = fallback_to_pp_ocrv5
        
        if use_gpu:
            print('[INFO] 使用GPU加速 (混合OCR引擎)')
        else:
            print('[INFO] 使用CPU模式 (混合OCR引擎)')
        
        # 初始化RapidOCR (PP-OCRv4) - 快速引擎
        print('[INFO] 初始化RapidOCR (PP-OCRv4) 快速引擎...')
        self.rapid_ocr = RapidOCR(
            use_angle_cls=use_angle_cls,
            use_gpu=use_gpu,
            lang=lang,
            det_limit_side_len=det_limit_side_len,
            rec_batch_num=rec_batch_num,
            enable_mkldnn=enable_mkldnn,
        )
        
        # 初始化PP-OCRv5 - 高精度引擎
        if fallback_to_pp_ocrv5:
            print('[INFO] 初始化PaddleOCR (PP-OCRv5) 高精度引擎...')
            self.pp_ocrv5 = self._init_pp_ocrv5(
                lang, use_angle_cls, use_gpu, det_model_dir, 
                rec_model_dir, cls_model_dir, det_limit_side_len, 
                rec_batch_num, enable_mkldnn
            )
        else:
            self.pp_ocrv5 = None

    def _init_pp_ocrv5(self, lang, use_angle_cls, use_gpu, det_model_dir, 
                      rec_model_dir, cls_model_dir, det_limit_side_len, 
                      rec_batch_num, enable_mkldnn):
        """初始化PP-OCRv5引擎"""
        try:
            # 查找PP-OCRv5模型路径
            model_paths = self._find_pp_ocrv5_models()
            if det_model_dir is None:
                det_model_dir = model_paths.get('det')
            if rec_model_dir is None:
                rec_model_dir = model_paths.get('rec')
            if cls_model_dir is None:
                cls_model_dir = model_paths.get('cls')
            
            return PaddleOCR(
                use_textline_orientation=use_angle_cls,
                lang=lang,
                det_model_dir=det_model_dir,
                rec_model_dir=rec_model_dir,
                cls_model_dir=cls_model_dir,
                det_limit_side_len=det_limit_side_len,
                rec_batch_num=rec_batch_num,
                enable_mkldnn=enable_mkldnn,
                # 优化参数（PaddleOCR 3.2.0兼容）
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                det_db_unclip_ratio=1.6,
            )
        except Exception as e:
            print(f'[WARNING] PP-OCRv5初始化失败: {e}，将仅使用RapidOCR')
            return None

    def _find_pp_ocrv5_models(self) -> dict:
        """查找PP-OCRv5模型路径"""
        model_paths = {}
        home_dir = os.path.expanduser('~')
        
        possible_paths = [
            os.path.join(home_dir, '.paddlex', 'official_models'),
            os.path.join(home_dir, '.paddleocr', 'inference'),
            '/root/.paddlex/official_models',
            '/root/.paddleocr/inference',
        ]
        
        pp_ocrv5_models = {
            'det': 'PP-OCRv5_server_det',
            'rec': 'PP-OCRv5_server_rec',
            'cls': 'ch_ppocr_mobile_v2.0_cls_infer'
        }
        
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
        智能OCR识别
        根据图像特征和RapidOCR结果质量自动选择最佳引擎
        """
        if not self.use_hybrid or self.pp_ocrv5 is None:
            # 仅使用RapidOCR
            return self._infer_rapid(image_bgr)
        
        # 预处理图像
        processed = self._preprocess_image(image_bgr)
        
        # 首先尝试RapidOCR（快速）
        rapid_results = self._infer_rapid(processed)
        
        # 评估RapidOCR结果质量
        if self._is_good_quality(rapid_results):
            print('[INFO] RapidOCR结果质量良好，使用快速结果')
            return rapid_results
        
        # RapidOCR结果质量不佳，尝试PP-OCRv5
        print('[INFO] RapidOCR结果质量不佳，尝试PP-OCRv5高精度识别...')
        pp_ocrv5_results = self._infer_pp_ocrv5(processed)
        
        # 比较两种结果，选择更好的
        if self._compare_results(rapid_results, pp_ocrv5_results):
            print('[INFO] 选择PP-OCRv5结果')
            return pp_ocrv5_results
        else:
            print('[INFO] 选择RapidOCR结果')
            return rapid_results

    def _infer_rapid(self, image_bgr: np.ndarray) -> List[OCRLine]:
        """使用RapidOCR进行识别"""
        try:
            result, _ = self.rapid_ocr(image_bgr)
            lines = []
            
            if result:
                for entry in result:
                    if not entry or len(entry) < 3:
                        continue
                    
                    bbox_points = entry[0]
                    text = str(entry[1])
                    score = float(entry[2])
                    
                    if bbox_points and text:
                        xs = [int(p[0]) for p in bbox_points]
                        ys = [int(p[1]) for p in bbox_points]
                        bbox = BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                        lines.append(OCRLine(text=text, score=score, bbox=bbox, words=[]))
            
            lines.sort(key=lambda l: (l.bbox.y1, l.bbox.x1))
            return lines
        except Exception as e:
            print(f'[ERROR] RapidOCR识别失败: {e}')
            return []

    def _infer_pp_ocrv5(self, image_bgr: np.ndarray) -> List[OCRLine]:
        """使用PP-OCRv5进行识别"""
        if self.pp_ocrv5 is None:
            return []
        
        try:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            result = self.pp_ocrv5.ocr(image_rgb)
            lines = []
            
            if result:
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
        except Exception as e:
            print(f'[ERROR] PP-OCRv5识别失败: {e}')
            return []

    def _is_good_quality(self, results: List[OCRLine]) -> bool:
        """评估OCR结果质量"""
        if not results:
            return False
        
        # 检查平均置信度
        avg_confidence = sum(line.score for line in results) / len(results)
        if avg_confidence < self.confidence_threshold:
            return False
        
        # 检查是否有合理的文本长度
        valid_texts = [line.text for line in results if len(line.text.strip()) > 0]
        if len(valid_texts) == 0:
            return False
        
        # 检查是否有过多乱码
        garbage_chars = sum(1 for text in valid_texts if self._is_garbage_text(text))
        if garbage_chars / len(valid_texts) > 0.5:  # 超过50%是乱码
            return False
        
        return True

    def _is_garbage_text(self, text: str) -> bool:
        """判断文本是否为乱码"""
        if not text or len(text.strip()) == 0:
            return True
        
        # 检查是否包含过多特殊字符
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        if special_chars / len(text) > 0.3:  # 超过30%是特殊字符
            return True
        
        # 检查是否包含过多问号（可能是识别失败）
        if text.count('?') / len(text) > 0.2:  # 超过20%是问号
            return True
        
        return False

    def _compare_results(self, rapid_results: List[OCRLine], pp_ocrv5_results: List[OCRLine]) -> bool:
        """比较两种OCR结果，返回True表示PP-OCRv5更好"""
        if not pp_ocrv5_results:
            return False
        
        if not rapid_results:
            return True
        
        # 比较文本数量
        if len(pp_ocrv5_results) > len(rapid_results) * 1.2:  # PP-OCRv5识别到更多文本
            return True
        
        # 比较平均置信度
        rapid_avg_conf = sum(line.score for line in rapid_results) / len(rapid_results)
        pp_ocrv5_avg_conf = sum(line.score for line in pp_ocrv5_results) / len(pp_ocrv5_results)
        
        if pp_ocrv5_avg_conf > rapid_avg_conf + 0.1:  # PP-OCRv5置信度明显更高
            return True
        
        return False

    def _preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """图像预处理"""
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr
        
        # 如果图像太小，进行放大
        h, w = image_bgr.shape[:2]
        if h < 32 or w < 32:
            scale = max(32 / h, 32 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        # 简单的对比度增强
        if len(image_bgr.shape) == 3:
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            image_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return image_bgr
