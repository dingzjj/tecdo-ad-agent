from ultralytics import YOLO
from config import conf
model_v1 = YOLO(conf.get_path(
    "yolo11m_detect_phone_model_path_v1"), task="detect")
model_v2 = YOLO(conf.get_path(
    "yolo11m_detect_phone_model_path_v2"), task="detect")


def predict_img_return_with_max_conf(img, conf_threshold=0.7):
    """
    只返回置信度最高的结果
    conf_threshold: 置信度阈值
    返回: (mask_xy, binary_mask)
    """
    results = model_v1.predict(source=img, conf=conf_threshold,
                               show_labels=False, show_conf=False, task="detect")
    if len(results[0].boxes.xyxy) > 0:
        return results[0].boxes
    else:
        results = model_v2.predict(source=img, conf=conf_threshold,
                                   show_labels=False, show_conf=False, task="detect")
    if len(results[0].boxes.xyxy) > 0:
        return results[0].boxes
    else:
        raise Exception("No phone detected")
