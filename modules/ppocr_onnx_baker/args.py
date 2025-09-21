import argparse

def get_args():
    parser = argparse.ArgumentParser()
    
    # --- Detection model parameters ---
    parser.add_argument("--det_model_dir", type=str, default="./models/ppocr/ch_PP-OCRv5_det_infer.onnx")
    parser.add_argument("--det_limit_side_len", type=int, default=960)
    parser.add_argument("--det_thresh", type=float, default=0.3)
    parser.add_argument("--det_box_thresh", type=float, default=0.6)
    parser.add_argument("--det_unclip_ratio", type=float, default=1.5)
    parser.add_argument("--use_dilation", type=bool, default=False)
    parser.add_argument("--det_db_score_mode", type=str, default="slow")

    # --- Recognition model parameters ---
    parser.add_argument("--rec_model_dir", type=str, default="./models/ppocr/ch_PP-OCRv5_rec_infer.onnx")
    parser.add_argument("--rec_image_shape", type=str, default="3, 48, 320") # C, H, W
    parser.add_argument("--rec_batch_num", type=int, default=6)
    parser.add_argument("--rec_char_dict_path", type=str, default="./models/ppocr/ppocr_keys_v1.txt")
    
    # --- Preprocessing ---
    parser.add_argument(
        '--det_pre_operators',
        default='[{"DetResizeForTest": {}}, {"NormalizeImage": {"std": [0.229, 0.224, 0.225], "mean": [0.485, 0.456, 0.406], "scale": "1./255.", "order": "hwc"}}, {"ToCHWImage": null}, {"KeepKeys": {"keep_keys": ["image", "shape"]}}]'
    )
    
    # --- Postprocessing ---
    parser.add_argument(
        '--det_postprocess',
        default='{"name": "DBPostProcess", "thresh": 0.3, "box_thresh": 0.6, "max_candidates": 1000, "unclip_ratio": 1.5, "use_dilation": false, "score_mode": "slow"}'
    )

    args = parser.parse_args([])
    
    # Manually parse string args into python objects
    args.rec_image_shape = [int(v) for v in args.rec_image_shape.split(",")]
    args.det_pre_operators = eval(args.det_pre_operators)
    args.det_postprocess = eval(args.det_postprocess)
    
    return args
