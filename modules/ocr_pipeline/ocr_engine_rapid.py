from __future__ import annotations

from typing import List

import numpy as np
import cv2
from rapidocr_onnxruntime import RapidOCR

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
        enable_mkldnn: bool = True,
    ) -> None:
        # RapidOCR uses ONNX Runtime, which handles GPU automatically
        if use_gpu:
            print('[INFO] 使用GPU加速 (ONNX Runtime)')
        else:
            print('[INFO] 使用CPU模式 (ONNX Runtime)')
        
        # Initialize RapidOCR
        self.ocr = RapidOCR(
            use_angle_cls=use_angle_cls,
            use_gpu=use_gpu,
            lang=lang,
            det_limit_side_len=det_limit_side_len,
            rec_batch_num=rec_batch_num,
            enable_mkldnn=enable_mkldnn,
        )

    def infer(self, image_bgr: np.ndarray) -> List[OCRLine]:
        # Preprocess image to improve OCR on watermarked/signed documents
        processed = self._preprocess_image(image_bgr)
        
        # RapidOCR expects BGR format
        result, _ = self.ocr(processed)
        
        lines: List[OCRLine] = []
        if not result:
            return lines
        
        # Handle RapidOCR result format
        # result is a list of [bbox, text, score]
        for entry in result:
            if not entry or len(entry) < 3:
                continue
            
            bbox_points = entry[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = str(entry[1])
            score = float(entry[2])
            
            if bbox_points and text:
                # Convert bbox points to bounding box
                xs = [int(p[0]) for p in bbox_points]
                ys = [int(p[1]) for p in bbox_points]
                bbox = BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                lines.append(OCRLine(text=text, score=score, bbox=bbox, words=[]))
        
        lines.sort(key=lambda l: (l.bbox.y1, l.bbox.x1))
        return lines

    def _preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """Preprocess image to improve OCR on watermarked/signed documents"""
        # Ensure image is valid
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr
        
        # Convert to grayscale for processing
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        
        # Denoise with stronger parameters for watermarked documents
        denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Enhance contrast using CLAHE with stronger parameters
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # Try different thresholding approaches
        # Method 1: Otsu's threshold
        _, binary1 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Method 2: Adaptive threshold
        binary2 = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
        )
        
        # Combine both methods
        combined = cv2.bitwise_and(binary1, binary2)
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        
        # Convert back to BGR
        result = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
        return result
