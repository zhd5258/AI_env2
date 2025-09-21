import cv2
import numpy as np
import operator
from PIL import Image

class DetResizeForTest(object):
    def __init__(self, **kwargs):
        super(DetResizeForTest, self).__init__()
        self.resize_long = 960

    def __call__(self, data):
        img = data['image']
        src_h, src_w, _ = img.shape

        ratio = self.resize_long / max(src_h, src_w)
        resize_h = int(src_h * ratio)
        resize_w = int(src_w * ratio)
        
        # Ensure dimensions are divisible by 32
        resize_h = max(int(round(resize_h / 32) * 32), 32)
        resize_w = max(int(round(resize_w / 32) * 32), 32)

        img = cv2.resize(img, (resize_w, resize_h))
        data['image'] = img
        data['shape'] = np.array([src_h, src_w, ratio, ratio])
        return data

class NormalizeImage(object):
    def __init__(self, scale=None, mean=None, std=None, order='chw', **kwargs):
        if isinstance(scale, str):
            scale = eval(scale)
        self.scale = np.float32(scale if scale is not None else 1.0 / 255.0)
        mean = mean if mean is not None else [0.485, 0.456, 0.406]
        std = std if std is not None else [0.229, 0.224, 0.225]
        
        shape = (3, 1, 1) if order == 'chw' else (1, 1, 3)
        self.mean = np.array(mean).reshape(shape).astype('float32')
        self.std = np.array(std).reshape(shape).astype('float32')

    def __call__(self, data):
        img = data['image']
        img = (img.astype('float32') * self.scale - self.mean) / self.std
        data['image'] = img
        return data

class ToCHWImage(object):
    def __init__(self, **kwargs):
        pass

    def __call__(self, data):
        img = data['image']
        data['image'] = img.transpose((2, 0, 1))
        return data

class KeepKeys(object):
    def __init__(self, keep_keys, **kwargs):
        self.keep_keys = keep_keys

    def __call__(self, data):
        return {key: data[key] for key in self.keep_keys}

def create_operators(op_param_list):
    """
    Create a list of operators based on the parameters.
    """
    ops = []
    for op_param in op_param_list:
        op_name = list(op_param)[0]
        param = {} if op_param[op_name] is None else op_param[op_name]
        
        if op_name == 'DetResizeForTest':
            op = DetResizeForTest(**param)
        elif op_name == 'NormalizeImage':
            op = NormalizeImage(**param)
        elif op_name == 'ToCHWImage':
            op = ToCHWImage(**param)
        elif op_name == 'KeepKeys':
            op = KeepKeys(**param)
        else:
            raise ValueError(f"Unknown operator: {op_name}")
        ops.append(op)
    return ops
