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
    PaddleOCR 3.2.0版本专用OCR引擎
    充分利用3.2.0版本的新功能和优化
    """

    def __init__(
        self,
        lang: str = 'ch',
        use_angle_cls: bool = True,
        use_gpu: bool = True,  # 默认启用GPU
        det_model_dir: str | None = None,
        rec_model_dir: str | None = None,
        cls_model_dir: str | None = None,
        det_limit_side_len: int = 960,
        rec_batch_num: int = 6,
        enable_mkldnn: bool = True,
        # 3.2.0版本新增参数
        use_tensorrt: bool = False,
        precision: str = 'fp32',
        gpu_mem: int = 500,
    ) -> None:
        """
        初始化PaddleOCR 3.2.0专用引擎

        Args:
            lang: 语言设置，默认为中文
            use_angle_cls: 是否使用文字方向分类
            use_gpu: 是否使用GPU加速（默认True）
            det_model_dir: 检测模型目录
            rec_model_dir: 识别模型目录
            cls_model_dir: 分类模型目录
            det_limit_side_len: 检测模型输入图像最大边长
            rec_batch_num: 识别模型批处理数量
            enable_mkldnn: 是否启用MKL-DNN加速
            use_tensorrt: 是否使用TensorRT加速（3.2.0新功能）
            precision: 精度设置（fp32/fp16/int8）
            gpu_mem: GPU内存限制（MB）
        """
        self.use_gpu = use_gpu
        self.use_tensorrt = use_tensorrt

        # 设置设备
        device = self._setup_device()

        # 获取模型路径
        if det_model_dir is None or rec_model_dir is None or cls_model_dir is None:
            model_paths = self._find_models(lang)
            if det_model_dir is None:
                det_model_dir = model_paths.get('det')
            if rec_model_dir is None:
                rec_model_dir = model_paths.get('rec')
            if cls_model_dir is None:
                cls_model_dir = model_paths.get('cls')

        # 构建PaddleOCR 3.2.0参数
        ocr_params = {
            'use_angle_cls': use_angle_cls,
            'lang': lang,
            'det_model_dir': det_model_dir,
            'rec_model_dir': rec_model_dir,
            'cls_model_dir': cls_model_dir,
            'det_limit_side_len': det_limit_side_len,
            'rec_batch_num': rec_batch_num,
            'enable_mkldnn': enable_mkldnn,
            'use_gpu': use_gpu,
            # 3.2.0版本新增参数
            'use_tensorrt': use_tensorrt,
            'precision': precision,
            'gpu_mem': gpu_mem,
            # 优化参数
            'det_db_thresh': 0.3,
            'det_db_box_thresh': 0.5,
            'det_db_unclip_ratio': 1.6,
            'rec_image_inverse': True,  # 图像反色处理
            'drop_score': 0.5,  # 置信度阈值
        }

        print('[INFO] 初始化PaddleOCR 3.2.0引擎')
        print(f'[INFO] 设备: {"GPU" if device == "gpu" else "CPU"}')
        if use_tensorrt:
            print('[INFO] TensorRT加速: 启用')
        print(f'[INFO] 精度: {precision}')

        # 初始化PaddleOCR 3.2.0
        self.ocr = PaddleOCR(**ocr_params)

    def _setup_device(self) -> str:
        """设置计算设备"""
        device = 'cpu'

        if self.use_gpu:
            try:
                # 检查CUDA编译支持
                has_cuda = paddle.device.is_compiled_with_cuda()
                if not has_cuda:
                    print('[WARNING] PaddlePaddle未编译CUDA支持')
                    device = 'cpu'
                else:
                    # 检查GPU设备数量
                    gpu_count = paddle.device.cuda.device_count()
                    if gpu_count == 0:
                        print('[WARNING] 未检测到GPU设备')
                        device = 'cpu'
                    else:
                        device = 'gpu'
                        paddle.set_device('gpu:0')
                        print(
                            f'[INFO] 成功启用GPU加速，设备: gpu:0 (共{gpu_count}个GPU)'
                        )

                        # 显示GPU信息
                        if gpu_count > 0:
                            try:
                                gpu_name = paddle.device.cuda.get_device_name(0)
                                gpu_memory = paddle.device.cuda.get_device_properties(
                                    0
                                ).total_memory
                                print(f'[INFO] GPU型号: {gpu_name}')
                                print(f'[INFO] GPU显存: {gpu_memory / 1024**3:.1f}GB')
                            except:
                                pass
            except Exception as e:
                print(f'[WARNING] GPU检测失败: {e}，切换到CPU模式')
                device = 'cpu'

        if device == 'cpu':
            paddle.set_device('cpu')
            print('[INFO] 使用CPU模式')

        return device

    def _find_models(self, lang: str) -> dict:
        """查找模型路径"""
        model_paths = {}

        # 获取用户主目录
        home_dir = os.path.expanduser('~')

        # 3.2.0版本模型路径
        possible_paths = [
            os.path.join(home_dir, '.paddleocr', 'whl'),
            os.path.join(home_dir, '.paddlex', 'official_models'),
            os.path.join(home_dir, '.paddleocr', 'inference'),
            '/root/.paddleocr/whl',
            '/root/.paddlex/official_models',
            '/root/.paddleocr/inference',
        ]

        # 3.2.0版本模型名称（优先使用最新模型）
        model_name_map = {
            'ch': {
                'det': [
                    'ch_PP-OCRv4_det_infer',  # 最新检测模型
                    'ch_PP-OCRv3_det_infer',
                    'ch_ppocr_mobile_v2.0_det_infer',
                ],
                'rec': [
                    'ch_PP-OCRv4_rec_infer',  # 最新识别模型
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
                    det_path = os.path.join(base_path, 'det', lang, det_name)
                    if os.path.exists(det_path):
                        model_paths['det'] = det_path
                        print(f'[INFO] 找到检测模型: {det_path}')
                        break

                # 查找识别模型
                for rec_name in lang_models['rec']:
                    rec_path = os.path.join(base_path, 'rec', lang, rec_name)
                    if os.path.exists(rec_path):
                        model_paths['rec'] = rec_path
                        print(f'[INFO] 找到识别模型: {rec_path}')
                        break

                # 查找分类模型
                for cls_name in lang_models['cls']:
                    cls_path = os.path.join(base_path, 'cls', cls_name)
                    if os.path.exists(cls_path):
                        model_paths['cls'] = cls_path
                        print(f'[INFO] 找到分类模型: {cls_path}')
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
        """
        执行OCR识别（3.2.0版本优化）

        Args:
            image_bgr: BGR格式的输入图像

        Returns:
            OCR识别结果列表
        """
        # 3.2.0版本优化的预处理
        processed = self._preprocess_image_v3_2(image_bgr)

        # 转换BGR到RGB（PaddleOCR需要RGB格式）
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

    def _preprocess_image_v3_2(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        3.2.0版本优化的图像预处理
        """
        # 确保图像有效
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        # 获取图像尺寸
        h, w = image_bgr.shape[:2]

        # 图像尺寸优化
        if h < 32 or w < 32:
            # 图像太小，进行放大
            scale = max(32 / h, 32 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(
                image_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC
            )
        elif max(h, w) > 2048:
            # 图像太大，进行适当缩放
            scale = 2048 / max(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            image_bgr = cv2.resize(
                image_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA
            )

        # 3.2.0版本优化的图像增强
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

        return image_bgr

    def infer_batch(
        self, images: List[np.ndarray], workers: int = 4
    ) -> List[List[OCRLine]]:
        """
        批量处理多个图像（3.2.0版本优化）
        """
        if workers <= 1:
            return [self.infer(img) for img in images]

        # 3.2.0版本优化的批处理
        batch_size = max(1, len(images) // workers)
        results = []

        for i in range(0, len(images), batch_size):
            batch = images[i : i + batch_size]
            batch_results = [self.infer(img) for img in batch]
            results.extend(batch_results)

        return results

    def get_gpu_info(self) -> dict:
        """获取GPU信息"""
        info = {
            'cuda_available': paddle.device.is_compiled_with_cuda(),
            'gpu_count': 0,
            'gpu_names': [],
            'gpu_memory': [],
        }

        if info['cuda_available']:
            info['gpu_count'] = paddle.device.cuda.device_count()
            for i in range(info['gpu_count']):
                try:
                    name = paddle.device.cuda.get_device_name(i)
                    props = paddle.device.cuda.get_device_properties(i)
                    memory = props.total_memory / 1024**3
                    info['gpu_names'].append(name)
                    info['gpu_memory'].append(memory)
                except:
                    info['gpu_names'].append(f'GPU {i}')
                    info['gpu_memory'].append(0)

        return info
