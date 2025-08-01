from agent.game_ad_agent.phone_segment_predict_img import convert_mask_to_binary
from agent.game_ad_agent.phone_segment_predict_img import predict_img
import cv2
import numpy as np
# chartlet_img_with_mask -> chartlet -> perspective_transform_img_to_img


def perspective_transform_img_to_img(src_img, srcPoints: list, dst_img, dstPoints: list):
    """
    将原图的srcPoints映射到dst_img的dstPoints

    srcPoints与dstPoints需要按照如下顺序：
    左上,右上,右下,左下

    1.先将src_img的size -> dst_img的size [扩充]

    2.将[扩充]后的src_img的srcPoints映射到src_img的dstPoints

    3.图片融合
    """

    # 获取src_img的size
    src_img_size = src_img.shape[:2]

    # 获取dst_img的size
    dst_img_size = dst_img.shape[:2]
    if src_img_size[0] > dst_img_size[0] or src_img_size[1] > dst_img_size[1]:
        # 计算缩放比例
        scale = min(dst_img_size[0] / src_img_size[0],
                    dst_img_size[1] / src_img_size[1])
        # 计算缩放后的size
        resized_size = (
            int(src_img_size[0] * scale), int(src_img_size[1] * scale))
        # 缩放
        resized_img = cv2.resize(src_img, resized_size)

        # srcPoints也会进行缩放
        srcPoints = [
            [srcPoints[0][0] * scale, srcPoints[0][1] * scale],
            [srcPoints[1][0] * scale, srcPoints[1][1] * scale],
            [srcPoints[2][0] * scale, srcPoints[2][1] * scale],
            [srcPoints[3][0] * scale, srcPoints[3][1] * scale]
        ]
    else:
        resized_img = src_img
        resized_size = src_img_size
    # 进行扩充,只是空白填充
    add_buttom = dst_img_size[0] - resized_size[0]
    add_right = dst_img_size[1] - resized_size[1]
    # 空白填充
    resized_img = cv2.copyMakeBorder(resized_img, 0, add_buttom, 0, add_right,
                                     cv2.BORDER_CONSTANT, value=(255, 255, 255))
    # cv2.drawContours(resized_img, [np.array(srcPoints)], -1, (0, 0, 255), 2)
    # cv2.imwrite("/data/dzj/yolov8-segment/result/perspective_transform_img_to_img_resized.jpg",
    #             resized_img)

    # 方法一：进行透视变换(像素低的情况效果不行)
    pts1 = np.float32(srcPoints)
    pts2 = np.float32(dstPoints)
    M = cv2.getPerspectiveTransform(pts1, pts2)
    output_img = cv2.warpPerspective(
        resized_img, M, (dst_img_size[1], dst_img_size[0]), borderValue=(255, 255, 255))
    cv2.imwrite("/data/dzj/yolov8-segment/result/perspective_transform_img_to_img_output.jpg",
                output_img)
    # 进行融合
    # 创建掩码，将源图像的非空白部分叠加到目标图像
    # 方法二：使用缩小，旋转操作来实现

    mask = np.zeros_like(output_img)
    for i in range(output_img.shape[0]):
        for j in range(output_img.shape[1]):
            if np.any(output_img[i, j] != [255, 255, 255]):  # 判断是否为空白区域
                mask[i, j] = output_img[i, j]  # 记录非空白区域

    # 将源图像的有效区域叠加到目标图像
    dst_img_with_overlay = dst_img.copy()
    for i in range(dst_img.shape[0]):
        for j in range(dst_img.shape[1]):
            if np.any(mask[i, j] != [0, 0, 0]):  # 判断是否为有效区域
                dst_img_with_overlay[i, j] = mask[i, j]
    # 插入后对dstPoints线段区域进行羽化

    # 保存最终合成图像

    return dst_img_with_overlay


def get_left_top_point(dstPoints: list):
    sorted_pts = sorted(dstPoints, key=lambda p: (p[0], p[1]))

    # 排序后第一个点是最左侧的点
    leftmost_point = sorted_pts[0]

    # 找出 X 最小的点中的 Y 最小的点即为左上角
    left_top = min([point for point in sorted_pts if point[0]
                   == leftmost_point[0]], key=lambda p: p[1])

    return left_top


def chartlet(src_img, dst_img, dstPoints: list):
    # 获取src_img的边缘四个点
    # shape中，第一个是height，第二个是width
    src_img_size = src_img.shape[:2]
    # src_img_size -> 高*宽
    # 1.确定dstPoints左上角的点
    left_top_point = get_left_top_point(dstPoints)
    # 2.确定左上角的点在dstPoints中的索引
    left_top_index = dstPoints.index(left_top_point)

    srcPoints = [[0, 0], [0, src_img_size[0]],
                 [src_img_size[1], src_img_size[0]], [src_img_size[1], 0]]
    # 根据left_top_index确定dstPoints的顺序
    index = 0
    while (index < left_top_index):
        # 3.根据dstPoints的顺序确定srcPoints的顺序
        # 根据左上角的点与逆时针操作确定srcPoints的顺
        # 将dstPoints的四个点映射到srcPoints的四个点,并且保证顺序一致，
        last_element = srcPoints.pop()  # 移除并获取最后一个元素
        srcPoints.insert(0, last_element)  # 将其插入到列表的最前面
        index += 1
    return perspective_transform_img_to_img(
        src_img, srcPoints, dst_img, dstPoints)


def chartlet_img_with_mask(src_img, dst_img, segment_result, scale_factor=0.9):
    """输入输出的都是cv2处理的结果"""

    for i, mask in enumerate(segment_result.xy):
        # 检查掩码是否为空或无效
        if mask is None or len(mask) == 0:
            print("跳过空掩码")
            continue

        # 确保掩码是闭合的
        if not cv2.arcLength(mask, True) > 0:
            print("跳过无效轮廓")
            continue

        approx = []
        epsilon = 0.01 * cv2.arcLength(mask, True)
        max_iterations = 100  # 防止无限循环
        iteration = 0

        while len(approx) != 4 and iteration < max_iterations:
            approx = cv2.approxPolyDP(mask, epsilon, True)
            if len(approx) > 4:
                epsilon *= 1.1
            elif len(approx) < 4:
                epsilon *= 0.9
            iteration += 1

        # 检查是否成功找到4个点的轮廓
        if len(approx) == 4:
            # 处理approx形状 (4, 1, 2)，approx即为凸点坐标
            dstPoints = approx.reshape(-1, 2).astype(np.int32).tolist()
            if scale_factor != 1.0:
                # dstPoints向内收缩10%
                # 计算中心点
                cx, cy = np.mean(dstPoints, axis=0)
                # 新顶点坐标
                new_points = []

                for point in dstPoints:
                    x, y = point
                    new_x = cx + (x - cx) * scale_factor
                    new_y = cy + (y - cy) * scale_factor
                    new_points.append([new_x, new_y])
                dstPoints = new_points
            return chartlet(src_img, dst_img, dstPoints)
        else:
            # TODO 处理无法找到4个点的轮廓
            print(f"无法找到4个点的轮廓，当前点数: {len(approx)}")


def merge_img(up_img, buttom_img, white_tolerance=30):
    """
    将 up_img 和 buttom_img 进行融合。两张图片的 size 必须相同。

    参数：
    - up_img: 顶部图片
    - buttom_img: 底部图片
    - white_tolerance: 白色容差范围，控制白色的定义（0-255）
    - dilation_kernel_size: 膨胀操作的内核大小，控制扩展的程度
    """

    # 将图片转换为 NumPy 数组，方便处理
    buttom_img_copy = buttom_img.copy()

    # 计算白色的容差，允许颜色接近白色的像素也认为是白色
    lower_white = np.array(
        [255 - white_tolerance, 255 - white_tolerance, 255 - white_tolerance])
    upper_white = np.array([255, 255, 255])

    # 生成白色区域的掩码
    white_mask = np.all((up_img >= lower_white) &
                        (up_img <= upper_white), axis=-1)

    # 将上层图片的非白色区域替换到底层图片
    for i in range(up_img.shape[0]):
        for j in range(up_img.shape[1]):
            if white_mask[i, j]:  # 如果白色区域经过膨胀
                buttom_img_copy[i, j] = up_img[i, j]

    return buttom_img_copy


if __name__ == "__main__":
    output_path = "/data/dzj/yolov8-segment/result/output_img.jpg"
    src_img_path = "/data/dzj/yolov8-segment/data/phone1.jpg"
    dst_img_path = "/data/dzj/yolov8-segment/data/text.png"
    segment_result = predict_img(dst_img_path)
    src_img = cv2.imread(src_img_path)
    dst_img = cv2.imread(dst_img_path)
    chartlet_img_with_mask(src_img, dst_img, segment_result, scale_factor=1.1)
