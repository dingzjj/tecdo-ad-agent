from ultralytics import YOLO
from config import conf
model = YOLO(conf.get_path("yolo11m_detect_phone_model_path"))


def predict_img_return_with_max_conf(img, conf_threshold=0.8):
    """
    只返回置信度最高的结果
    conf_threshold: 置信度阈值
    返回: (mask_xy, binary_mask)
    """
    results = model.predict(source=img, conf=conf_threshold,
                            show_labels=False, show_conf=False)
    return results[0].boxes
