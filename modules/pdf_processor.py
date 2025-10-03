import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any, Callable
import sys
import os
import json
import hashlib
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeoutError,
)
from .pdf_processor_helpers import PDFProcessorHelpers
from .runtime_config import load_config

from .ppocr_paddle_processor import PPOCRPaddleProcessor

# 导入OCR引擎 - 优先使用已验证的智能引擎
try:
    # 导入已验证成功的智能引擎（最稳定）
    from ocr_pipeline.ocr_engine_smart import OCREngine as SmartOCREngine
    from ocr_pipeline.pdf_renderer import render_pdf_to_images

    SMART_OCR_AVAILABLE = True
    print('[INFO] 智能OCR引擎可用 (已验证成功)')
except ImportError:
    SmartOCREngine = None
    render_pdf_to_images = None
    SMART_OCR_AVAILABLE = False
    print('[WARNING] 智能OCR引擎不可用')

try:
    # 尝试导入新版本的ocr_pipeline
    from ocr_pipeline import PDFOCR, extract_pdf_text

    try:
        from ocr_pipeline.ocr_engine_pp_ocrv5_optimized import PPOCRv5Engine
    except ImportError:
        # 如果找不到优化版本，尝试标准版本
        print('[WARNING] 未找到PP-OCRv5优化引擎，使用标准版本')
        PPOCRv5Engine = None

    try:
        from ocr_pipeline.pdf_text_extractor import PDFTextExtractor
    except ImportError:
        print('[WARNING] 未找到PDF文本提取器')
        PDFTextExtractor = None

    NEW_OCR_AVAILABLE = True
    print('[INFO] 使用新版OCR Pipeline v2.0.0')
except ImportError as e:
    # 如果新版本不可用，回退到旧版本
    print(f'[INFO] 新版OCR Pipeline导入失败: {e}')
    from .ocr_pipeline.ocr_engine import OCREngine
    from .ocr_pipeline.ocr_engine_pp_ocrv5 import OCREngine as PPOCRv5Engine
    from .ocr_pipeline.ocr_engine_optimized import OCREngine as OptimizedEngine
    from .ocr_pipeline.ocr_engine_3_2_final import OCREngine as Final32Engine

    NEW_OCR_AVAILABLE = False
    print('[INFO] 使用旧版OCR Pipeline，建议升级到v2.0.0')
import cv2
import numpy as np


class PDFProcessor(PDFProcessorHelpers):
    def __init__(self, file_path, use_gpu: bool = False, file_type: str = 'bid'):
        super().__init__()
        self.file_path = file_path
        self.use_gpu = use_gpu
        self.file_type = file_type  # 'bid' 或 'tender'
        # 载入运行配置（用于控制并发与超时）
        self.runtime_config = load_config()
        # 检查标准输出是否可用，如果不可用则使用基本配置
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                stream=sys.stdout,
            )
        except (ValueError, AttributeError):
            # 当stdout被重定向或分离时使用基本配置
            try:
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                )
            except Exception:
                # 最后的备用方案
                pass

        self.logger = logging.getLogger(__name__)
        # 添加空处理器以防日志记录失败
        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())
        self.failed_pages = []  # 用于记录处理失败的页面
        self.ppocr_processor = None
        self.paddle_processor = None
        self.new_ocr_engine = None  # 新的OCR引擎
        self.ocr_engine_type = os.getenv(
            'OCR_ENGINE_TYPE', 'standard'
        )  # 从环境变量读取引擎类型
        # 读取是否使用PaddleOCR
        # 默认使用PaddleOCR + GPU；若环境变量覆盖则按环境变量
        self.use_paddle_ocr = os.getenv('USE_PADDLE', 'true').lower() == 'true'
        # 全面启用GPU OCR，默认为True
        if os.getenv('USE_GPU') is None:
            os.environ['USE_GPU'] = 'true'
        self.use_gpu = os.getenv('USE_GPU', 'true').lower() == 'true'

        # 初始化缓存相关属性
        self.cache_dir = 'temp_pdf_cache'
        self.cache_enabled = True
        # 添加配置选项控制是否生成JSON缓存文件
        self.json_cache_enabled = False  # 根据todo.md要求，默认不生成JSON缓存文件
        self._ensure_cache_dir()

        # 初始化temp_word目录用于保存文本结果
        self.temp_word_dir = 'temp_word'
        self._ensure_temp_word_dir()

        # 流式处理回调函数
        self.stream_callback = None

    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _ensure_temp_word_dir(self):
        """确保temp_word目录存在"""
        os.makedirs(self.temp_word_dir, exist_ok=True)

    def _get_new_ocr_engine(self):
        """
        获取新的OCR引擎实例，支持GPU加速
        根据配置选择不同的引擎类型，优先使用v2.0.0 API
        """
        if self.new_ocr_engine is None:
            try:
                self.logger.info(
                    '初始化新OCR引擎，GPU模式: %s, 引擎类型: %s',
                    self.use_gpu,
                    self.ocr_engine_type,
                )

                # 优先使用已验证成功的智能引擎
                if SMART_OCR_AVAILABLE and (
                    self.ocr_engine_type in ['new_api', 'smart', 'standard']
                ):
                    # 使用已验证成功的智能引擎 (CPU模式，最稳定)
                    self.new_ocr_engine = SmartOCREngine(
                        lang='ch',
                        use_gpu=False,  # 使用CPU模式，已验证成功
                        use_angle_cls=True,
                    )
                    self.logger.info('新OCR引擎初始化成功: 智能引擎 (已验证成功)')

                elif NEW_OCR_AVAILABLE:
                    # 使用新版本OCR Pipeline v2.0.0
                    if self.ocr_engine_type == 'ppocrv5' and PPOCRv5Engine is not None:
                        # 使用新版PP-OCRv5优化引擎
                        self.new_ocr_engine = PPOCRv5Engine(
                            lang='ch',
                            use_gpu=self.use_gpu,
                            use_angle_cls=True,
                            det_limit_side_len=1280,
                            rec_batch_num=6,
                        )
                        self.logger.info(
                            '新OCR引擎初始化成功: PP-OCRv5优化引擎 (v2.0.0)'
                        )
                    elif (
                        self.ocr_engine_type == 'new_api'
                        or self.ocr_engine_type == 'ppocrv5'
                    ):
                        # 使用新版PDFOCR API（推荐方式）
                        # 构建参数字典，根据支持情况动态添加参数
                        pdfocr_params = {
                            'lang': 'ch',
                            'max_workers': 2,
                            'dpi': 300,
                            'max_side': 2048,
                        }

                        # 尝试添加GPU参数（如果支持的话）
                        try:
                            # 先尝试使用GPU参数创建
                            if self.use_gpu:
                                pdfocr_params['use_gpu'] = True
                            self.new_ocr_engine = PDFOCR(**pdfocr_params)
                        except (TypeError, ValueError) as e:
                            if 'use_gpu' in str(e):
                                # 如果use_gpu参数不支持，移除后重试
                                self.logger.warning(
                                    'PDFOCR不支持use_gpu参数，使用默认设备配置'
                                )
                                pdfocr_params.pop('use_gpu', None)
                                self.new_ocr_engine = PDFOCR(**pdfocr_params)
                            else:
                                raise

                        self.logger.info('新OCR引擎初始化成功: PDFOCR API (v2.0.0)')
                    else:
                        # 默认使用新版PDFOCR API
                        pdfocr_params = {
                            'lang': 'ch',
                            'max_workers': 2,
                            'dpi': 300,
                            'max_side': 2048,
                        }

                        # 尝试添加GPU参数（如果支持的话）
                        try:
                            if self.use_gpu:
                                pdfocr_params['use_gpu'] = True
                            self.new_ocr_engine = PDFOCR(**pdfocr_params)
                        except (TypeError, ValueError) as e:
                            if 'use_gpu' in str(e):
                                self.logger.warning(
                                    'PDFOCR不支持use_gpu参数，使用默认设备配置'
                                )
                                pdfocr_params.pop('use_gpu', None)
                                self.new_ocr_engine = PDFOCR(**pdfocr_params)
                            else:
                                raise

                        self.logger.info('新OCR引擎初始化成功: 默认PDFOCR API (v2.0.0)')
                else:
                    # 回退到旧版本引擎
                    if self.ocr_engine_type == 'ppocrv5':
                        engine_class = PPOCRv5Engine
                    elif self.ocr_engine_type == 'optimized':
                        engine_class = OptimizedEngine
                    elif self.ocr_engine_type == 'final32':
                        engine_class = Final32Engine
                    else:
                        engine_class = OCREngine

                    # 初始化引擎，全面启用GPU OCR
                    self.new_ocr_engine = engine_class(
                        lang='ch',  # 中文识别
                        use_gpu=self.use_gpu,  # 启用GPU加速
                    )
                    self.logger.info(
                        '新OCR引擎初始化成功: %s (旧版本)', engine_class.__name__
                    )

            except Exception as e:
                self.logger.error('新OCR引擎初始化失败: %s', e, exc_info=True)
                self.new_ocr_engine = None

        return self.new_ocr_engine

    def _extract_with_smart_engine(self, ocr_engine, use_cache=True) -> List[str]:
        """
        使用智能引擎处理PDF文件 (已验证成功的方式)
        """
        try:
            self.logger.info('使用智能引擎处理PDF文件 (已验证成功的方式)')

            # 使用PDF渲染器渲染PDF页面
            if render_pdf_to_images is None:
                self.logger.error('PDF渲染器不可用')
                return []

            # 渲染PDF页面
            self.logger.info('正在渲染PDF页面...')
            images = render_pdf_to_images(self.file_path, dpi=200)

            if not images:
                self.logger.warning('没有成功渲染任何页面')
                return []

            self.logger.info(f'成功渲染 {len(images)} 页')

            # 处理每一页
            pages_text = []
            for page_num, page_image in images:
                try:
                    self.logger.info(f'正在处理第 {page_num} 页...')

                    # OCR识别 (使用已验证成功的infer方法)
                    lines = ocr_engine.infer(page_image)

                    # 提取文本
                    page_text = '\n'.join(
                        [
                            line.text
                            for line in lines
                            if hasattr(line, 'text') and line.text.strip()
                        ]
                    )

                    pages_text.append(self._clean_text(page_text))

                    if page_text.strip():
                        self.logger.info(
                            f'第 {page_num} 页识别到 {len(lines)} 行文本, {len(page_text)} 字符'
                        )
                    else:
                        self.logger.warning(f'第 {page_num} 页未识别到文本')

                except Exception as e:
                    self.logger.error(f'处理第 {page_num} 页时出错: {e}')
                    pages_text.append('')

            # 保存到缓存
            if use_cache and self.cache_enabled:
                self._save_to_cache(pages_text)

            self.logger.info(f'智能引擎成功处理PDF文件，共 {len(pages_text)} 页')
            return pages_text

        except Exception as e:
            self.logger.error(f'智能引擎处理PDF文件失败: {e}', exc_info=True)
            return []

    def _extract_with_new_ocr_api(self, use_cache=True) -> List[str]:
        """
        使用新版OCR Pipeline API处理PDF文件
        优先使用已验证成功的智能引擎
        """
        if not SMART_OCR_AVAILABLE and not NEW_OCR_AVAILABLE:
            return []

        try:
            # 检查缓存
            if use_cache and self.cache_enabled:
                cached_result = self._load_from_cache()
                if cached_result:
                    self.logger.info('从缓存加载PDF文本（新OCR API）')
                    return cached_result

            self.logger.info('使用新版OCR Pipeline v2.0.0 API处理PDF文件')

            # 根据引擎类型选择处理方式
            ocr_engine = self._get_new_ocr_engine()
            if ocr_engine is None:
                return []

            # 优先使用智能引擎的渲染方式（已验证成功）
            if SMART_OCR_AVAILABLE and 'SmartOCREngine' in str(type(ocr_engine)):
                return self._extract_with_smart_engine(ocr_engine, use_cache)

            # 检查是否是PDFOCR实例（支持直接处理PDF）
            elif 'PDFOCR' in str(type(ocr_engine)):
                # 使用PDFOCR API直接处理整个PDF文件
                self.logger.info('使用PDFOCR API直接处理PDF文件')

                try:
                    # 直接提取PDF文本，返回按页分割的结果
                    result = ocr_engine.extract_detailed(self.file_path)

                    # 提取每页文本
                    pages_text = []
                    for page in result.pages:
                        pages_text.append(self._clean_text(page.full_text))

                    self.logger.info(
                        f'PDFOCR API成功处理PDF文件，共 {len(pages_text)} 页'
                    )

                except Exception as e:
                    self.logger.error(f'PDFOCR API处理失败: {e}，尝试简单提取')
                    # 回退到简单提取
                    try:
                        full_text = ocr_engine.extract_text(self.file_path)

                        # 按页分割文本
                        doc = fitz.open(self.file_path)
                        num_pages = len(doc)
                        doc.close()

                        if full_text:
                            lines = full_text.split('\n')
                            lines_per_page = max(1, len(lines) // num_pages)
                            pages_text = []

                            for i in range(num_pages):
                                start_idx = i * lines_per_page
                                end_idx = (
                                    start_idx + lines_per_page
                                    if i < num_pages - 1
                                    else len(lines)
                                )
                                page_text = '\n'.join(lines[start_idx:end_idx])
                                pages_text.append(self._clean_text(page_text))
                        else:
                            pages_text = [''] * num_pages
                    except Exception as e2:
                        self.logger.error(f'简单提取也失败: {e2}')
                        return []

            elif PPOCRv5Engine is not None and hasattr(ocr_engine, 'extract_text'):
                # 使用PP-OCRv5引擎逐页处理
                self.logger.info('使用PP-OCRv5引擎逐页处理')

                doc = fitz.open(self.file_path)
                pages_text = []

                for page_num in range(len(doc)):
                    try:
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap(
                            matrix=fitz.Matrix(2.0, 2.0)
                        )  # 2倍缩放提高质量
                        img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                            pix.height, pix.width, pix.n
                        )

                        # 处理图像格式
                        if pix.n == 4:
                            img_data = cv2.cvtColor(img_data, cv2.COLOR_RGBA2RGB)
                        elif pix.n == 3:
                            img_data = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

                        # 使用PP-OCRv5引擎处理
                        result = ocr_engine.extract_text(img_data)
                        if hasattr(result, 'full_text'):
                            text = result.full_text
                        else:
                            text = str(result)

                        pages_text.append(self._clean_text(text))
                        self.logger.info(f'PP-OCRv5引擎成功处理页面 {page_num + 1}')

                    except Exception as e:
                        self.logger.error(
                            f'PP-OCRv5引擎处理页面 {page_num + 1} 失败: {e}'
                        )
                        pages_text.append('')

                doc.close()
            else:
                self.logger.warning('无法识别OCR引擎类型，跳过新API处理')
                return []

            # 保存到缓存
            if use_cache and self.cache_enabled:
                self._save_to_cache(pages_text)

            self.logger.info(f'新OCR API成功处理PDF文件，共 {len(pages_text)} 页')
            return pages_text

        except Exception as e:
            self.logger.error(f'新OCR API处理PDF文件失败: {e}', exc_info=True)
            return []

    def _get_cache_key(self) -> str:
        """获取缓存键（基于路径+文件大小+修改时间，避免整文件读哈希带来的开销）"""
        try:
            st = os.stat(self.file_path)
            key = f'{self.file_path}|{st.st_size}|{int(st.st_mtime)}'
        except Exception:
            # 回退到路径作为键（极端情况下）
            key = self.file_path
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def _get_cache_path(self):
        """获取缓存文件路径"""
        if not self.cache_enabled:
            return None

        file_key = self._get_cache_key()
        cache_filename = f'{file_key}.json'
        return os.path.join(self.cache_dir, cache_filename)

    def _load_from_cache(self):
        """从缓存加载文本"""
        if not self.cache_enabled:
            return None

        cache_path = self._get_cache_path()
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    self.logger.info('从缓存加载PDF文本: %s', cache_path)
                    return cached_data.get('pages_text', [])
            except Exception as e:
                self.logger.warning('加载缓存失败: %s', e)
        return None

    def _load_from_temp_word(self):
        """从temp_word目录加载文本"""
        try:
            file_key = self._get_cache_key()
            temp_word_filename = f'{file_key}.txt'
            temp_word_path = os.path.join(self.temp_word_dir, temp_word_filename)

            if os.path.exists(temp_word_path):
                with open(temp_word_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
                # 按照页面分割文本（这里简单按换行符分割，实际可能需要更复杂的逻辑）
                pages_text = full_text.split('\n\n')  # 假设页面之间有两个换行符
                self.logger.info('从temp_word目录加载PDF文本: %s', temp_word_path)
                return pages_text
        except Exception as e:
            self.logger.warning('从temp_word目录加载文本失败: %s', e)
        return []  # 返回空列表而不是None，保持一致性

    def _save_to_cache(self, pages_text):
        """保存文本到缓存"""
        # 根据配置决定是否生成JSON缓存文件
        if not self.cache_enabled or not self.json_cache_enabled:
            # 即使不生成JSON缓存文件，也要保存文本到temp_word目录
            self._save_to_temp_word(pages_text)
            return

        cache_path = self._get_cache_path()
        if cache_path:
            try:
                cache_data = {
                    'file_path': self.file_path,
                    'file_hash': self._get_cache_key(),
                    'pages_count': len(pages_text),
                    'pages_text': pages_text,
                }
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info('保存PDF文本到缓存: %s', cache_path)
            except Exception as e:
                self.logger.warning('保存缓存失败: %s', e)

        # 同时保存文本到temp_word目录
        self._save_to_temp_word(pages_text)

    def _save_to_temp_word(self, pages_text):
        """保存文本到temp_word目录"""
        try:
            # 生成基于文件路径的唯一文件名
            file_key = self._get_cache_key()
            temp_word_filename = f'{file_key}.txt'
            temp_word_path = os.path.join(self.temp_word_dir, temp_word_filename)

            # 将所有页面文本连接并保存
            full_text = '\n'.join(pages_text)
            with open(temp_word_path, 'w', encoding='utf-8') as f:
                f.write(full_text)
            self.logger.info('保存PDF文本到temp_word目录: %s', temp_word_path)
        except Exception as e:
            self.logger.warning('保存文本到temp_word目录失败: %s', e)

    def set_stream_callback(self, callback: Callable[[int, str], None]):
        """设置流式处理回调函数"""
        self.stream_callback = callback

    def _try_decrypt_pdf(self, doc: fitz.Document) -> bool:
        """
        尝试解密PDF文档
        
        Args:
            doc: fitz.Document对象
            
        Returns:
            bool: 是否成功解密
        """
        try:
            # 检查文档是否加密
            if doc.is_encrypted:
                self.logger.info("检测到加密PDF文档")
                
                # 首先尝试空密码
                if doc.authenticate(""):
                    self.logger.info("使用空密码成功解密PDF")
                    return True
                
                # 如果空密码不行，尝试常见的默认密码
                common_passwords = ["", "123456", "password", "admin", "user"]
                for password in common_passwords:
                    if password and doc.authenticate(password):
                        self.logger.info(f"使用密码 '{password}' 成功解密PDF")
                        return True
                
                self.logger.warning("无法使用常见密码解密PDF文档")
                return False
            return True  # 文档未加密
        except Exception as e:
            self.logger.error(f"检查或解密PDF时出错: {e}")
            return False

    def _open_pdf_with_decryption(self, file_path: str) -> fitz.Document:
        """
        打开PDF文件并自动处理加密
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            fitz.Document: 打开的文档对象
            
        Raises:
            Exception: 如果无法打开或解密文档
        """
        try:
            # 打开PDF文档
            doc = fitz.open(file_path)
            
            # 尝试解密
            if not self._try_decrypt_pdf(doc):
                doc.close()
                raise Exception("无法解密PDF文档")
                
            return doc
        except Exception as e:
            self.logger.error(f"打开PDF文件时出错: {e}")
            raise

    def process_single_page(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个PDF页面

        Args:
            task: 任务字典，包含'page_num'键

        Returns:
            Dict[str, Any]: 包含页面信息和文本的字典
        """
        page_num = task['page_num']
        try:
            # 使用fitz打开PDF文件（支持加密PDF）
            doc = self._open_pdf_with_decryption(self.file_path)
            page = doc[page_num]
            text = page.get_text()
            doc.close()
            # 清理文本
            text = self._clean_text(text)
            return {
                'page': page_num + 1,  # 转换为1索引
                'text': text,
                'method': 'PyMuPDF',
            }
        except Exception as e:
            self.logger.warning(f'处理第 {page_num + 1} 页时出错: {e}')
            return {
                'page': page_num + 1,
                'text': '',
                'error': str(e),
                'method': 'PyMuPDF_failed',
            }

    def extract_text_per_page(self, use_cache=True) -> List[str]:
        """
        逐页提取PDF文本，优先使用缓存，然后尝试新版OCR API

        Args:
            use_cache: 是否使用缓存

        Returns:
            List[str]: 每页文本字符串列表（与后续处理保持一致）
        """
        if use_cache:
            cached_text = self._load_from_cache()
            if cached_text:
                self.logger.info('使用缓存的PDF文本')
                return cached_text

            # 如果缓存中没有，则尝试从temp_word目录加载
            temp_word_text = self._load_from_temp_word()
            if temp_word_text:
                self.logger.info('使用temp_word目录中的PDF文本')
                return temp_word_text

        if not os.path.exists(self.file_path):
            self.logger.error('PDF文件不存在: %s', self.file_path)
            return []

        # 优先尝试使用新版OCR API
        if NEW_OCR_AVAILABLE:
            self.logger.info('尝试使用新版OCR Pipeline v2.0.0...')
            new_api_result = self._extract_with_new_ocr_api(use_cache)
            if new_api_result:
                return new_api_result
            else:
                self.logger.warning('新版OCR API处理失败，回退到传统方法')

        try:
            self.logger.info('使用PyMuPDF提取文本...')
            all_pages_text = []
            self.failed_pages = []

            try:
                # 先探测总页数（支持加密PDF）
                with self._open_pdf_with_decryption(self.file_path) as pdf_probe:
                    total_pages = len(pdf_probe)

                # 使用并行处理
                max_workers = self.runtime_config.get(
                    'pdf_page_max_workers', os.cpu_count() or 1
                )
                timeout_sec = self.runtime_config.get('pdf_page_timeout_sec', 60)
                overall_timeout = max(
                    total_pages * 0.5,
                    self.runtime_config.get('pdf_overall_min_timeout_sec', 120),
                )

                # PyMuPDF/fitz 对象不是线程安全的，所以每个线程需要自己打开文件
                # 我们只传递页码 (0-indexed)
                tasks = [{'page_num': i} for i in range(total_pages)]

                results: List[Dict[str, Any]] = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_page = {
                        executor.submit(self.process_single_page, task): task
                        for task in tasks
                    }

                    try:
                        for future in as_completed(
                            future_to_page, timeout=overall_timeout
                        ):
                            page_info = future_to_page[future]
                            try:
                                result = future.result(timeout=timeout_sec)
                                results.append(result)

                                # 流式处理：如果有回调函数，则调用它
                                if self.stream_callback:
                                    page_num = result.get('page', 0)
                                    page_text = result.get('text', '')
                                    # 注意：这里我们传递的是页面数和文本内容，而不是调用不存在的方法
                                    try:
                                        # 对于单页处理，我们传递页面数和包含单个页面文本的列表
                                        self.stream_callback(page_num, page_text)
                                    except Exception as cb_error:
                                        self.logger.warning(
                                            '流式处理回调执行失败: %s', cb_error
                                        )
                            except Exception as exc:
                                self.logger.warning(
                                    '第 %d 页并行处理异常: %s',
                                    page_info['page_num'] + 1,
                                    exc,
                                )
                                results.append(
                                    {
                                        'page': page_info['page_num'] + 1,
                                        'text': '',
                                        'error': str(exc),
                                        'method': 'parallel_failed',
                                    }
                                )
                    except FuturesTimeoutError:
                        self.logger.warning(
                            '并行提取超过总超时限制，标记未完成页为超时'
                        )
                        # 标记所有未完成的为超时
                        for future, task in future_to_page.items():
                            if not future.done():
                                future.cancel()
                                results.append(
                                    {
                                        'page': task['page_num'] + 1,
                                        'text': '',
                                        'error': 'timeout',
                                        'method': 'parallel_timeout',
                                    }
                                )

                # 按页码排序并提取文本列表
                results_sorted = sorted(results, key=lambda x: x['page'])
                all_pages_text = [r.get('text', '') for r in results_sorted]

            except Exception as e:
                self.logger.error('使用PyMuPDF处理PDF时出错: %s', e)
                # 如果PyMuPDF失败，回退到PyPDF2
                pypdf2_texts = self._extract_with_pypdf2()
                all_pages_text = [text for text in pypdf2_texts]

            self._save_to_cache(all_pages_text)
            return all_pages_text

        except Exception as e:
            self.logger.error('提取PDF文本时发生未知错误: %s', e)
            return []

    def extract_text_with_ocr_when_needed(self) -> List[str]:
        """
        使用PyMuPDF提取文本，对无法提取的页面使用PaddleOCR处理
        这是针对投标文件的新处理方式
        """
        self.logger.info('使用PyMuPDF提取文本，对无法提取的页面使用OCR处理...')

        # 首先使用PyMuPDF提取文本
        pages_text = self.extract_text_per_page()

        # 检查哪些页面文本内容太少，需要OCR处理
        pages_to_ocr = []
        char_threshold = 30  # 文本字符数阈值
        for i, page_text in enumerate(pages_text):
            if len(page_text.strip()) < char_threshold:
                self.logger.info(
                    f'第 {i + 1} 页文本内容过少 (长度: {len(page_text.strip())})，标记为需要OCR处理'
                )
                pages_to_ocr.append(i + 1)  # 页码从1开始

            # 对需要OCR的页面进行OCR处理
            ocr_results = {}
            if pages_to_ocr:
                self.logger.info(f'对以下页面进行OCR处理: {pages_to_ocr}')
                # 优先使用新的OCR引擎（支持GPU加速）
                ocr_results = self._run_new_ocr_on_pages(pages_to_ocr)

            # 将OCR结果替换到原页面文本中
            for page_num, ocr_text in ocr_results.items():
                # 只有当OCR文本比原始文本更丰富时才替换
                original_text = pages_text[page_num - 1]
                if len(ocr_text.strip()) > len(original_text.strip()):
                    self.logger.info(f'使用OCR结果替换第 {page_num} 页的原始文本')
                    pages_text[page_num - 1] = ocr_text
                else:
                    self.logger.info(
                        f'第 {page_num} 页的OCR结果不如原始文本，保持原始文本'
                    )

        self._save_to_cache(pages_text)
        return pages_text

    def _run_paddle_ocr_on_pages(self, page_numbers: List[int]) -> Dict[int, str]:
        """
        使用PaddleOCR在指定页面执行OCR。
        """
        results = {}
        try:
            if self.paddle_processor is None:
                self.logger.info('初始化PaddleOCR处理器，GPU模式: %s', self.use_gpu)
                try:
                    self.paddle_processor = PPOCRPaddleProcessor(use_gpu=self.use_gpu)
                except Exception as e:
                    self.logger.error('PaddleOCR处理器初始化失败: %s', e)
                    return results

            # 使用fitz打开PDF文件
            doc = fitz.open(self.file_path)
            for page_num in page_numbers:
                try:
                    page = doc[page_num - 1]
                    # 增加分辨率以提高OCR准确性
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    pix = page.get_pixmap(matrix=mat)
                    # 转换为numpy数组（OpenCV图像格式）
                    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n
                    )
                    # 使用PaddleOCR处理，添加超时机制
                    import concurrent.futures
                    import threading

                    def ocr_with_timeout():
                        return self.paddle_processor.ocr_single_page(img_data)

                    # 为单个页面OCR设置5分钟超时
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(ocr_with_timeout)
                        try:
                            text = future.result(timeout=300)  # 5分钟超时
                            results[page_num] = self._clean_text(text)
                            self.logger.info(
                                'PaddleOCR成功处理页面 %d，文本长度: %d',
                                page_num,
                                len(text),
                            )
                        except concurrent.futures.TimeoutError:
                            self.logger.error(
                                'PaddleOCR处理页面 %d 超时（5分钟），跳过该页面',
                                page_num,
                            )
                            results[page_num] = ''
                            # 取消超时的任务
                            future.cancel()
                except Exception as page_exc:
                    self.logger.error(
                        '使用PaddleOCR处理页面 %d 时出错: %s',
                        page_num,
                        page_exc,
                        exc_info=True,
                    )
                    results[page_num] = ''
            doc.close()
        except Exception as e:
            self.logger.error('PaddleOCR处理过程中发生一般错误: %s', e, exc_info=True)
            for p_num in page_numbers:
                if p_num not in results:
                    results[p_num] = ''
        return results

    def _run_new_ocr_on_pages(self, page_numbers: List[int]) -> Dict[int, str]:
        """
        使用新的OCR引擎在指定页面执行OCR，支持GPU加速
        """
        results = {}
        try:
            # 获取新的OCR引擎实例
            ocr_engine = self._get_new_ocr_engine()
            if ocr_engine is None:
                self.logger.error('新OCR引擎不可用，无法处理页面')
                return results

            # 使用fitz打开PDF文件
            doc = fitz.open(self.file_path)
            for page_num in page_numbers:
                try:
                    page = doc[page_num - 1]
                    # 增加分辨率以提高OCR准确性
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    pix = page.get_pixmap(matrix=mat)
                    # 转换为numpy数组（BGR格式）
                    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n
                    )

                    # 如果是RGBA，转换为RGB
                    if pix.n == 4:
                        img_data = cv2.cvtColor(img_data, cv2.COLOR_RGBA2RGB)
                    elif pix.n == 3:
                        img_data = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

                    # 使用新OCR引擎处理，添加超时机制
                    import concurrent.futures

                    def new_ocr_with_timeout():
                        if NEW_OCR_AVAILABLE and hasattr(ocr_engine, 'extract_text'):
                            # 检查是否是PDFOCR实例（需要PDF文件路径）
                            if 'PDFOCR' in str(type(ocr_engine)):
                                # 使用新版本PDFOCR API处理，需要PDF文件路径
                                # 这里我们需要保存图像为临时PDF或使用页面提取
                                import tempfile
                                import fitz

                                # 创建临时PDF文件
                                with tempfile.NamedTemporaryFile(
                                    suffix='.pdf', delete=False
                                ) as temp_file:
                                    # 将图像转换为PDF
                                    temp_pdf = fitz.open()
                                    temp_page = temp_pdf.new_page(
                                        width=img_data.shape[1],
                                        height=img_data.shape[0],
                                    )

                                    # 将图像保存为临时文件然后插入PDF
                                    temp_img_path = temp_file.name + '.png'
                                    cv2.imwrite(temp_img_path, img_data)

                                    # 插入图像到PDF
                                    temp_page.insert_image(
                                        temp_page.rect, filename=temp_img_path
                                    )
                                    temp_pdf.save(temp_file.name)
                                    temp_pdf.close()

                                    try:
                                        # 使用PDFOCR API提取文本
                                        text = ocr_engine.extract_text(temp_file.name)
                                        return text
                                    finally:
                                        # 清理临时文件
                                        os.unlink(temp_file.name)
                                        if os.path.exists(temp_img_path):
                                            os.unlink(temp_img_path)
                            else:
                                # 使用新版本PP-OCRv5引擎处理图像
                                result = ocr_engine.extract_text(img_data)
                                if hasattr(result, 'full_text'):
                                    return result.full_text
                                else:
                                    return str(result)
                        else:
                            # 使用旧版本引擎的推理方法
                            ocr_lines = ocr_engine.infer(img_data)
                            # 提取文本
                            text_lines = []
                            for line in ocr_lines:
                                if hasattr(line, 'text') and line.text:
                                    text_lines.append(line.text.strip())
                            return '\n'.join(text_lines)

                    # 为单个页面OCR设置5分钟超时
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(new_ocr_with_timeout)
                        try:
                            text = future.result(timeout=300)  # 5分钟超时
                            results[page_num] = self._clean_text(text)
                            self.logger.info(
                                '新OCR引擎成功处理页面 %d，文本长度: %d',
                                page_num,
                                len(text),
                            )
                        except concurrent.futures.TimeoutError:
                            self.logger.error(
                                '新OCR引擎处理页面 %d 超时（5分钟），跳过该页面',
                                page_num,
                            )
                            results[page_num] = ''
                            # 取消超时的任务
                            future.cancel()
                except Exception as page_exc:
                    self.logger.error(
                        '使用新OCR引擎处理页面 %d 时出错: %s',
                        page_num,
                        page_exc,
                        exc_info=True,
                    )
                    results[page_num] = ''
            doc.close()
        except Exception as e:
            self.logger.error('新OCR引擎处理过程中发生一般错误: %s', e, exc_info=True)
            for p_num in page_numbers:
                if p_num not in results:
                    results[p_num] = ''
        return results

    def _run_rapid_ocr_on_pages(self, page_numbers: List[int]) -> Dict[int, str]:
        """
        使用RapidOCR在指定页面执行OCR（保留作为备用选项）
        """
        # 现在优先使用新的OCR引擎
        return self._run_new_ocr_on_pages(page_numbers)

    def process_pdf_full_text(self) -> List[str]:
        """
        全文本处理模式：全部读取文本后再处理
        首先尝试使用PyMuPDF读取，不能读取的页面改为采用PaddleOCR识别
        全部文本化后保存
        """
        self.logger.info('开始全文本处理模式...')

        if not os.path.exists(self.file_path):
            self.logger.error('PDF文件不存在: %s', self.file_path)
            return []

        # 首先尝试从缓存或temp_word目录加载
        cached_text = self._load_from_cache()
        if cached_text:
            self.logger.info('使用缓存的PDF文本')
            return cached_text

        temp_word_text = self._load_from_temp_word()
        if temp_word_text:
            self.logger.info('使用temp_word目录中的PDF文本')
            return temp_word_text

        try:
            # 使用PyMuPDF提取文本
            pages_text = self.extract_text_per_page(use_cache=False)

            # 检查哪些页面需要OCR处理
            pages_to_ocr = []
            char_threshold = 30  # 文本字符数阈值
            for i, page_text in enumerate(pages_text):
                if len(page_text.strip()) < char_threshold:
                    self.logger.info(
                        f'第 {i + 1} 页文本内容过少 (长度: {len(page_text.strip())})，标记为需要OCR处理'
                    )
                    pages_to_ocr.append(i + 1)  # 页码从1开始

            # 对需要OCR的页面进行OCR处理
            if pages_to_ocr:
                self.logger.info(f'对以下页面进行OCR处理: {pages_to_ocr}')
                # 优先使用新的OCR引擎（支持GPU加速）
                ocr_results = self._run_new_ocr_on_pages(pages_to_ocr)

                # 将OCR结果替换到原页面文本中
                for page_num, ocr_text in ocr_results.items():
                    # 只有当OCR文本比原始文本更丰富时才替换
                    original_text = pages_text[page_num - 1]
                    if len(ocr_text.strip()) > len(original_text.strip()):
                        self.logger.info(f'使用OCR结果替换第 {page_num} 页的原始文本')
                        pages_text[page_num - 1] = ocr_text
                    else:
                        self.logger.info(
                            f'第 {page_num} 页的OCR结果不如原始文本，保持原始文本'
                        )

            # 保存处理后的文本
            self._save_to_cache(pages_text)
            self._save_to_temp_word(pages_text)

            self.logger.info(f'PDF全文本处理完成，共处理 {len(pages_text)} 页')
            return pages_text

        except Exception as e:
            self.logger.error('全文本处理PDF时发生未知错误: %s', e)
            return []

    def stream_process_pdf(self, chunk_size: int = 3) -> List[str]:
        """
        流式处理PDF文件，边处理边返回文本块

        Args:
            chunk_size: 每次返回的页面块大小

        Returns:
            List[str]: 处理完成的所有页面文本
        """
        self.logger.info('开始流式处理PDF文件...')

        if not os.path.exists(self.file_path):
            self.logger.error('PDF文件不存在: %s', self.file_path)
            return []

        all_pages_text = []
        try:
            # 先探测总页数
            with fitz.open(self.file_path) as pdf_probe:
                total_pages = len(pdf_probe)
                # 记录总页数供外部查询进度
                try:
                    self.total_pages = total_pages  # 动态属性，供进度回显
                except Exception:
                    pass

            # 使用并行处理
            max_workers = self.runtime_config.get(
                'pdf_page_max_workers', os.cpu_count() or 1
            )
            timeout_sec = self.runtime_config.get('pdf_page_timeout_sec', 60)
            overall_timeout = max(
                total_pages * 0.5,
                self.runtime_config.get('pdf_overall_min_timeout_sec', 120),
            )

            # PyMuPDF/fitz 对象不是线程安全的，所以每个线程需要自己打开文件
            # 我们只传递页码 (0-indexed)
            tasks = [{'page_num': i} for i in range(total_pages)]

            results: List[Dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_page = {
                    executor.submit(self.process_single_page, task): task
                    for task in tasks
                }

                try:
                    for future in as_completed(future_to_page, timeout=overall_timeout):
                        page_info = future_to_page[future]
                        try:
                            result = future.result(timeout=timeout_sec)
                            results.append(result)

                            # 更新所有页面文本列表
                            page_index = result.get('page', 0) - 1  # 转换为0索引
                            if page_index >= len(all_pages_text):
                                # 扩展列表以容纳新页面
                                all_pages_text.extend(
                                    [''] * (page_index - len(all_pages_text) + 1)
                                )
                            all_pages_text[page_index] = result.get('text', '')

                            # 计算已处理的页面数
                            processed_pages = len([r for r in results if 'text' in r])

                            # 每处理完chunk_size页就触发一次回调
                            if (
                                processed_pages % chunk_size == 0
                                or processed_pages == total_pages
                            ):
                                self.logger.info(
                                    f'已处理 {processed_pages}/{total_pages} 页'
                                )
                                # 如果有流式处理回调，则调用
                                if self.stream_callback:
                                    # 将页面文本列表转换为单个字符串
                                    text_content = '\n'.join(
                                        all_pages_text[:processed_pages]
                                    )
                                    # 调用回调函数，传递已处理的页面数和文本内容
                                    try:
                                        self.stream_callback(
                                            processed_pages,
                                            text_content,
                                        )
                                    except Exception as cb_error:
                                        self.logger.warning(
                                            '流式处理回调执行失败: %s', cb_error
                                        )
                        except Exception as exc:
                            self.logger.warning(
                                '第 %d 页并行处理异常: %s',
                                page_info['page_num'] + 1,
                                exc,
                            )
                            results.append(
                                {
                                    'page': page_info['page_num'] + 1,
                                    'text': '',
                                    'error': str(exc),
                                    'method': 'parallel_failed',
                                }
                            )
                except FuturesTimeoutError:
                    self.logger.warning('并行提取超过总超时限制，标记未完成页为超时')
                    # 标记所有未完成的为超时
                    for future, task in future_to_page.items():
                        if not future.done():
                            future.cancel()
                            results.append(
                                {
                                    'page': task['page_num'] + 1,
                                    'text': '',
                                    'error': 'timeout',
                                    'method': 'parallel_timeout',
                                }
                            )

            # 按页码排序并提取文本列表
            results_sorted = sorted(results, key=lambda x: x['page'])
            all_pages_text = [r.get('text', '') for r in results_sorted]

        except Exception as e:
            self.logger.error('流式处理PDF时发生未知错误: %s', e)

        self._save_to_cache(all_pages_text)
        return all_pages_text
