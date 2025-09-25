import logging
import numpy as np
import cv2
from paddleocr import PaddleOCR
import paddle
import warnings

warnings.filterwarnings('ignore')  # 忽略警告信息


class PPOCRPaddleProcessor:
    """
    使用PaddleOCR引擎进行OCR处理的类
    (代码来自参考项目 ocr_engine_pp_ocrv5.py)
    """

    def __init__(self, use_gpu: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_gpu = use_gpu
        self.ocr_engine = None

        try:
            # 尝试初始化PaddleOCR引擎
            if self.use_gpu:
                try:
                    if not paddle.is_compiled_with_cuda():
                        self.logger.warning('PaddlePaddle未编译CUDA支持，将使用CPU模式')
                        self.use_gpu = False
                except ImportError:
                    self.logger.warning('PaddlePaddle未安装，将使用CPU模式')
                    self.use_gpu = False

            self.ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang='ch',
                # paddleocr会自动在默认路径查找模型，无需手动指定det/rec/cls_model_dir
                # 默认路径包括 ~/.paddlex/official_models/
            )
            self.logger.info('PaddleOCR引擎初始化成功')
        except ImportError as e:
            self.logger.error('PaddleOCR库未安装: %s', e)
            self.ocr_engine = None
        except Exception as e:
            self.logger.error('PaddleOCR引擎初始化失败: %s', e, exc_info=True)
            self.ocr_engine = None

    def _preprocess_image(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        对输入图像进行预处理以提高OCR效果。
        (代码来自参考项目 ocr_engine_pp_ocrv5.py)
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(
            gray, h=10, templateWindowSize=7, searchWindowSize=21
        )
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        _, binary1 = cv2.threshold(
            enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        binary2 = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
        )

        combined = cv2.bitwise_and(binary1, binary2)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        return cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)

    def ocr_single_page(self, image_bgr: np.ndarray) -> str:
        """
        对单张图像（PDF页面）执行OCR，并返回拼接好的字符串。

        Args:
            image (np.ndarray): 从PDF页面转换来的OpenCV图像 (BGR格式)

        Returns:
            str: 识别出的所有文本，按行拼接
        """
        if self.ocr_engine is None:
            self.logger.error('OCR引擎未初始化，无法执行OCR')
            return ''

        if image_bgr is None or image_bgr.size == 0:
            self.logger.warning('输入图像为空或无效')
            return ''

        try:
            # 1. 预处理图像
            processed_image = self._preprocess_image(image_bgr)
            if processed_image is None or processed_image.size == 0:
                self.logger.warning('图像预处理失败，使用原始图像')
                processed_image = image_bgr

            # 2. 执行OCR (paddleocr需要RGB格式)
            image_rgb = cv2.cvtColor(processed_image, cv2.COLOR_BGR2RGB)
            result = self.ocr_engine.ocr(image_rgb)  # 移除cls参数

            # 3. 格式化结果
            if not result or not result[0]:
                self.logger.debug('OCR未识别到任何文本')
                return ''

            lines = []
            confidence_scores = []
            for res in result[0]:
                if len(res) >= 2:
                    # res 格式: [[[x1, y1], [x2, y2], [x3, y3], [x4, y4]], ('文本', 置信度)]
                    text, score = res[1]
                    if text and isinstance(text, str) and text.strip():
                        lines.append(text.strip())
                        confidence_scores.append(score)

            if lines:
                avg_confidence = sum(confidence_scores) / len(confidence_scores)
                self.logger.debug(
                    'OCR识别完成，文本行数: %d，平均置信度: %.2f',
                    len(lines),
                    avg_confidence,
                )
                return '\n'.join(lines)
            else:
                self.logger.debug('OCR未识别到有效文本')
                return ''

        except cv2.error as e:
            self.logger.error('OpenCV图像处理错误: %s', e)
            return ''
        except Exception as e:
            self.logger.error('OCR处理过程中发生错误: %s', e, exc_info=True)
            return ''
