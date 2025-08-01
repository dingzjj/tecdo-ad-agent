from ultralytics import YOLO
import numpy as np
import cv2
from config import conf
# Load a model
# pretrained YOLO11n model
model = YOLO(conf.get_path("yolo11m_segment_phone_model_path"))

# Run batched inference on a list of images
# return a list of Results objects


def predict_img(img, conf_threshold=0.8):
    """
    只返回置信度最高的结果
    conf_threshold: 置信度阈值
    返回: (mask_xy, binary_mask)
    """
    results = model.predict(
        source=img, conf=conf_threshold, show_labels=False, show_conf=False)
    result = results[0]

    # 检查是否有检测结果
    if result.masks is None:
        return None, None
    mask_result = result.masks
    # # 获取置信度最高的结果
    # mask_data = mask_result.data  # 获取mask数据 - ndarray
    # orig_shape = mask_result.orig_shape  # 获取原始图像尺寸
    # mask_xy = mask_result.xy

    # binary_mask = convert_mask_to_binary(mask_result, orig_shape)

    return mask_result


def convert_mask_to_binary(masks) -> np.ndarray:
    """
    将YOLO返回的mask数据转换为二值图

    Args:
        mask_data: YOLO返回的mask数据 
        orig_shape: 原始图像尺寸 (H, W)

    Returns:
        binary_mask: 二值图 
    """

    # 有值的点为1，无值的点为0
    orig_shape = masks.orig_shape
    # 先创建一个与原始图像尺寸相同的二值图
    for idx, mask in enumerate(masks):
        if mask.data.dim() == 3 and (mask.data.size(0) == 1 or mask.data.size(2) == 1):
            maskdata = mask.data.squeeze()  # 这会移除大小为1的维度
        # 缩放掩码到目标图像的尺寸
        resized_mask = cv2.resize(maskdata.cpu().numpy(
        ), (orig_shape[1], orig_shape[0]), interpolation=cv2.INTER_NEAREST)
        # 获取掩码中非零点的坐标
        y_indices, x_indices = np.where(resized_mask > 0)
        # 选择或生成颜色
        # color = [255, 255, 255]
        # ratio = 0.3  # 设置了透明度
        # 在空白图像中绘制掩码
        binary_mask = np.zeros(orig_shape, dtype=np.uint8)
        for y, x in zip(y_indices, x_indices):
            binary_mask[y, x] = 255
    return binary_mask


def save_binary_mask(binary_mask: np.ndarray, output_path: str):
    """
    保存二值图到文件

    Args:
        binary_mask: 二值图数组
        output_path: 输出文件路径
    """
    cv2.imwrite(output_path, binary_mask)


# 使用示例
if __name__ == "__main__":
    # # 测试函数
    pass
