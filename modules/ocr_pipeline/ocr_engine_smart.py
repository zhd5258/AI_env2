from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
import cv2
from rapidocr_onnxruntime import RapidOCR

from .models import BBox, OCRLine


class OCREngine:
    """
    智能OCR引擎
    基于RapidOCR (PP-OCRv4) 进行优化，提供最佳的速度和精度平衡
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
        初始化智能OCR引擎
        """
        if use_gpu:
            print('[INFO] 使用GPU加速 (智能OCR引擎 - PP-OCRv4优化版)')
        else:
            print('[INFO] 使用CPU模式 (智能OCR引擎 - PP-OCRv4优化版)')
        
        # 优化参数设置
        self.det_limit_side_len = det_limit_side_len
        self.rec_batch_num = rec_batch_num
        
        # 初始化RapidOCR (PP-OCRv4) 优化配置
        self.ocr = RapidOCR(
            use_angle_cls=use_angle_cls,
            use_gpu=use_gpu,
            lang=lang,
            det_limit_side_len=det_limit_side_len,
            rec_batch_num=rec_batch_num,
            enable_mkldnn=enable_mkldnn,
        )

    def infer(self, image_bgr: np.ndarray) -> List[OCRLine]:
        """
        执行智能OCR识别
        """
        # 智能预处理
        processed = self._smart_preprocess_image(image_bgr)
        
        # 执行OCR识别
        result, _ = self.ocr(processed)
        
        lines: List[OCRLine] = []
        if not result:
            return lines
        
        # 处理RapidOCR结果格式
        for entry in result:
            if not entry or len(entry) < 3:
                continue
            
            bbox_points = entry[0]
            text = str(entry[1])
            score = float(entry[2])
            
            if bbox_points and text:
                # 转换边界框点坐标
                xs = [int(p[0]) for p in bbox_points]
                ys = [int(p[1]) for p in bbox_points]
                bbox = BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                
                # 文本后处理
                processed_text = self._postprocess_text(text)
                if processed_text:  # 只添加非空文本
                    lines.append(OCRLine(text=processed_text, score=score, bbox=bbox, words=[]))
        
        # 按位置排序（从上到下，从左到右）
        lines.sort(key=lambda l: (l.bbox.y1, l.bbox.x1))
        
        # 文本行合并优化
        lines = self._merge_nearby_lines(lines)
        
        return lines

    def _smart_preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        智能图像预处理
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr
        
        h, w = image_bgr.shape[:2]
        
        # 1. 图像尺寸优化
        if h < 32 or w < 32:
            # 图像太小，进行放大
            scale = max(32 / h, 32 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        elif max(h, w) > self.det_limit_side_len:
            # 图像太大，进行适当缩放
            scale = self.det_limit_side_len / max(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 2. 对比度增强
        if len(image_bgr.shape) == 3:
            # 转换到LAB色彩空间进行亮度调整
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # 对L通道进行CLAHE增强
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # 合并通道并转换回BGR
            lab = cv2.merge([l, a, b])
            image_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # 3. 去噪处理（仅在需要时）
        if self._needs_denoising(image_bgr):
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
            image_bgr = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        
        return image_bgr

    def _needs_denoising(self, image: np.ndarray) -> bool:
        """
        判断图像是否需要去噪
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # 计算图像的方差，方差小说明图像平滑，可能需要去噪
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        return variance < 100  # 阈值可调整

    def _postprocess_text(self, text: str) -> str:
        """
        文本后处理
        """
        if not text:
            return ""
        
        # 去除首尾空白
        text = text.strip()
        
        # 去除过多的问号（可能是识别失败）
        if text.count('?') / len(text) > 0.3:
            return ""
        
        # 去除过短的文本（可能是噪声）
        if len(text) < 2:
            return ""
        
        return text

    def _merge_nearby_lines(self, lines: List[OCRLine]) -> List[OCRLine]:
        """
        合并相近的文本行
        """
        if len(lines) <= 1:
            return lines
        
        merged_lines = []
        current_line = lines[0]
        
        for next_line in lines[1:]:
            # 检查是否应该合并
            if self._should_merge_lines(current_line, next_line):
                # 合并文本
                current_line.text += " " + next_line.text
                # 更新边界框
                current_line.bbox = BBox(
                    x1=min(current_line.bbox.x1, next_line.bbox.x1),
                    y1=min(current_line.bbox.y1, next_line.bbox.y1),
                    x2=max(current_line.bbox.x2, next_line.bbox.x2),
                    y2=max(current_line.bbox.y2, next_line.bbox.y2)
                )
                # 更新置信度（取平均值）
                current_line.score = (current_line.score + next_line.score) / 2
            else:
                # 不合并，添加当前行到结果
                merged_lines.append(current_line)
                current_line = next_line
        
        # 添加最后一行
        merged_lines.append(current_line)
        
        return merged_lines

    def _should_merge_lines(self, line1: OCRLine, line2: OCRLine) -> bool:
        """
        判断两个文本行是否应该合并
        """
        # 垂直距离检查
        vertical_distance = abs(line1.bbox.y1 - line2.bbox.y1)
        if vertical_distance > 30:  # 超过30像素不合并
            return False
        
        # 水平重叠检查
        horizontal_overlap = min(line1.bbox.x2, line2.bbox.x2) - max(line1.bbox.x1, line2.bbox.x1)
        if horizontal_overlap < 0:  # 没有重叠
            return False
        
        # 文本长度检查（避免合并过长的文本）
        if len(line1.text) + len(line2.text) > 100:
            return False
        
        return True

    def infer_batch(self, images: List[np.ndarray], workers: int = 4) -> List[List[OCRLine]]:
        """
        批量处理多个图像
        """
        if workers <= 1:
            return [self.infer(img) for img in images]
        
        # 使用较小的批处理大小以提高效率
        batch_size = max(1, len(images) // workers)
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            batch_results = [self.infer(img) for img in batch]
            results.extend(batch_results)
        
        return results
