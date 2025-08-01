# 1.将游戏画面分为竖屏和横屏
# 2.为其添加手机边框
# 3.使用yolo11m-seg.pt or yolo11m.pt 进行物体检测
# 4.
from agent.exception import ComfyUIError
import io
from PIL import Image
import time
import uuid
import requests
from agent.utils import get_time_id, temp_dir
import os
import json
from config import conf
from agent.game_ad_agent.deal_img import merge_img
from config import logger
import torch
from agent.game_ad_agent.data.phone.phone_data import get_phone_data
import numpy as np
import cv2
# 第一个维度为高，第二个维度为宽

from agent.game_ad_agent.phone_detect_predict_img import predict_img_return_with_max_conf


def detect_phone(background_img):
    """
    检测背景图中的手机
    """
    return predict_img_return_with_max_conf(background_img)


def judge_phone_orientation(game_img) -> bool:
    """
    判断手机是竖屏还是横屏
    返回值为True表示竖屏，False表示横屏
    """
    return game_img.shape[0] > game_img.shape[1]


def inpaint_background(background_img, phone_and_game_img):
    workflow_json_path = conf.get_path("inpaint_workflow_json_path")
    if not os.path.exists(workflow_json_path):
        raise FileNotFoundError(f"workflow_json_path: {
                                workflow_json_path} not found")
    with open(workflow_json_path, "r") as f:
        workflow = json.load(f)
    new_text = "place it in hand.改变手势，手紧紧拿着握住手机"
    # 将background_img和phone_and_game_img保存在temp目录下
    with temp_dir(conf.get_path("temp_dir"), get_time_id()) as temp_dir_path:
        # 修改27号节点的image路径
        new_image_base_path = os.path.join(temp_dir_path, "background_img.png")
        cv2.imwrite(new_image_base_path, background_img)
        new_add_image_path = os.path.join(
            temp_dir_path, "phone_and_game_img.png")
        cv2.imwrite(new_add_image_path, phone_and_game_img)

        if (
            "27" in workflow
            and "inputs" in workflow["27"]
            and "image" in workflow["27"]["inputs"]
        ):
            workflow["27"]["inputs"]["image"] = new_image_base_path

        # 修改31号节点的image路径（如果存在）
        if (
            "31" in workflow
            and "inputs" in workflow["31"]
            and "image" in workflow["31"]["inputs"]
        ):
            workflow["31"]["inputs"]["image"] = new_add_image_path

        # 修改29号节点的text内容
        if (
            "29" in workflow
            and "inputs" in workflow["29"]
            and "text" in workflow["29"]["inputs"]
        ):
            workflow["29"]["inputs"]["text"] = new_text

        client_id = str(uuid.uuid4())
        resp = requests.post(
            f"http://{conf.get("comfyui_server_address")}/prompt",
            headers={"Content-Type": "application/json"},
            json={"prompt": workflow, "clientId": client_id},
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        while True:
            history_resp = requests.get(
                f"http://{conf.get("comfyui_server_address")}/history/{prompt_id}")
            history_data = history_resp.json()
            if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                break
            time.sleep(5)

        # print(json.dumps(history_data, indent=2))
        outputs = history_data[prompt_id]["outputs"]
        # 只处理28号节点
        if "28" in outputs:
            node_output = outputs["28"]
            images = node_output.get("images", [])
            for idx, image_info in enumerate(images):
                params = {
                    "filename": image_info["filename"],
                    "subfolder": image_info.get("subfolder", ""),
                    "type": image_info.get("type", "temp"),
                }
                view_url = f"http://{conf.get("comfyui_server_address")}/view"
                try:
                    image_resp = requests.get(view_url, params=params)
                    if image_resp.status_code != 200:
                        logger.error(
                            f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                        logger.error(image_resp.text[:200])
                        raise ComfyUIError(
                            f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                    image = Image.open(io.BytesIO(image_resp.content))
                    # 将其变成cv2
                    image = cv2.imdecode(np.frombuffer(
                        image_resp.content, np.uint8), cv2.IMREAD_COLOR)
                    return image
                except Exception as e:
                    logger.error(f"❌ 图片解码失败: {params}")
                    logger.error("返回内容前200字符:", image_resp.content[:200])
                    logger.error(e)
                    raise ComfyUIError(f"❌ 图片解码失败: {params}")
        else:
            logger.error("⚠️ 未找到28号节点的输出")
            raise ComfyUIError("⚠️ 未找到28号节点的输出")


def chartlet_phone_and_game(game_img, background_img):
    """
    游戏画面和手机画面融合，并且到指定background_img的指定位置

    in_phone 表示里面 phone表示手机框,real_phone表示手机框在背景图中的四个点
    """

    # 对游戏页面进行伸缩
    game_points = [[0, 0], [0, game_img.shape[0]],
                   [game_img.shape[1], game_img.shape[0]], [game_img.shape[1], 0]]

    if game_img.shape[0] > background_img.shape[0] or game_img.shape[1] > background_img.shape[1]:
        scale = min(background_img.shape[0] / game_img.shape[0],
                    background_img.shape[1] / game_img.shape[1])
        # 计算缩放后的size
        game_resized_size = (
            int(game_img.shape[0] * scale), int(game_img.shape[1] * scale))
        # 缩放
        game_resized_img = cv2.resize(game_img, game_resized_size)
        game_points = [
            [game_points[0][0] * scale, game_points[0][1] * scale],
            [game_points[1][0] * scale, game_points[1][1] * scale],
            [game_points[2][0] * scale, game_points[2][1] * scale],
            [game_points[3][0] * scale, game_points[3][1] * scale]
        ]
    else:
        game_resized_img = game_img
        game_resized_size = game_img.shape[:2]
    add_buttom = background_img.shape[0] - game_resized_size[0]
    add_right = background_img.shape[1] - game_resized_size[1]

    # 空白填充
    game_resized_img = cv2.copyMakeBorder(game_resized_img, 0, add_buttom, 0, add_right,
                                          cv2.BORDER_CONSTANT, value=(255, 255, 255))

    game_resized_size = game_resized_img.shape[:2]
    # 1.检测背景图中的手机
    # phone_boxes是一个矩形
    phone_boxes = detect_phone(background_img)

    # 获取手机边框的四个点
    real_phone_points = phone_boxes.xyxy.to(torch.int).reshape(-1, 2).tolist()

    # 判断边框为竖屏还是横屏
    real_phone_width = real_phone_points[1][0] - real_phone_points[0][0]
    real_phone_height = real_phone_points[1][1] - real_phone_points[0][1]
    # 左上，左下，右下，右上
    real_phone_points = [real_phone_points[0], [real_phone_points[0][0], real_phone_points[1][1]],
                         real_phone_points[1], [real_phone_points[1][0], real_phone_points[0][1]]]
    is_phone_of_background_vertical = real_phone_height > real_phone_width
    # 2.判断游戏画面是竖屏还是横屏
    is_game_vertical = judge_phone_orientation(game_img)
    if is_game_vertical != is_phone_of_background_vertical:
        logger.error("游戏画面和背景图中的手机边框方向不一致")
    # 3.为游戏画面添加手机边框(手机边框+游戏画面)
    # 创建一个白布放置【手机+游戏画面】
    # 确定手机边框在背景图片中的四个点[即phone_boxes]

    # 确定游戏画面在背景图片中的四个点【得经过两次透视变换】
    # 1.将游戏画面进行透视变换到白布上（游戏画面进行扩展）
    # 先确定四个点
    # 先判断边框是否大于视频的大小

    # 虚假的手机
    most_appropriate_phone = get_phone_data(
        game_img.shape[1], game_img.shape[0])

    in_phone_points: list = most_appropriate_phone["points"]
    phone_img = cv2.imread(most_appropriate_phone["img_path"])
    phone_width = phone_img.shape[1]
    phone_height = phone_img.shape[0]
    phone_points = [[0, 0], [0, phone_height], [
        phone_width, phone_height], [phone_width, 0]]

    if phone_img.shape[0] > background_img.shape[0] or phone_img.shape[1] > background_img.shape[1]:
        scale = min(background_img.shape[0] / phone_img.shape[0],
                    background_img.shape[1] / phone_img.shape[1])
        # 计算缩放后的size
        phone_resized_size = (
            int(phone_img.shape[0] * scale), int(phone_img.shape[1] * scale))
        # 缩放
        phone_resized_img = cv2.resize(phone_img, phone_resized_size)
        phone_points = [
            [phone_points[0][0] * scale, phone_points[0][1] * scale],
            [phone_points[1][0] * scale, phone_points[1][1] * scale],
            [phone_points[2][0] * scale, phone_points[2][1] * scale],
            [phone_points[3][0] * scale, phone_points[3][1] * scale]
        ]
    else:
        phone_resized_img = phone_img
        phone_resized_size = phone_img.shape[:2]
    add_buttom = background_img.shape[0] - phone_resized_size[0]
    add_right = background_img.shape[1] - phone_resized_size[1]

    # 空白填充
    phone_resized_img = cv2.copyMakeBorder(phone_resized_img, 0, add_buttom, 0, add_right,
                                           cv2.BORDER_CONSTANT, value=(255, 255, 255))
    phone_resized_size = phone_resized_img.shape[:2]

    # phone_resized_img and game_resized_img no problem

    M2 = cv2.getPerspectiveTransform(np.float32(
        phone_points), np.float32(real_phone_points))
    src_points = np.array(in_phone_points, dtype=np.float32).reshape(-1, 1, 2)
    real_phone_points = cv2.perspectiveTransform(src_points, M2)
    real_phone_points = real_phone_points.reshape(-1, 2).tolist()
    M_FOR_GAME = cv2.getPerspectiveTransform(
        np.float32(game_points), np.float32(real_phone_points))
    # 先游戏迁移过去
    M_FOR_PHONE = M2
    final_game_img = cv2.warpPerspective(
        game_resized_img, M_FOR_GAME, (game_resized_size[1], game_resized_size[0]), borderValue=(255, 255, 255))
    final_phone_img = cv2.warpPerspective(
        phone_resized_img, M_FOR_PHONE, (phone_resized_size[1], phone_resized_size[0]), borderValue=(255, 255, 255))

    lower_white = np.array([200, 200, 200])  # 白色区域的下界
    upper_white = np.array([255, 255, 255])  # 白色区域的上界

    # 创建掩码，白色区域为0，非白色区域为1
    mask = cv2.inRange(final_phone_img, lower_white, upper_white)

    # 反转掩码，将非白色部分为1，白色部分为0
    mask_inv = cv2.bitwise_not(mask)

    # 2. 将掩码应用到 final_phone_img 和 final_game_img 上
    # 仅保留 final_phone_img 中非白色部分
    final_phone_img_no_white = cv2.bitwise_and(
        final_phone_img, final_phone_img, mask=mask_inv)

    # 将 final_game_img 中的背景区域保留（即白色区域）
    final_game_img_no_white = cv2.bitwise_and(
        final_game_img, final_game_img, mask=mask)

    # 3. 合并 final_game_img 和 final_phone_img
    final_phone_and_game_img = cv2.add(
        final_game_img_no_white, final_phone_img_no_white)

    return inpaint_background(background_img, final_phone_and_game_img)


def get_video_first_frame(cap):
    """
    获取视频的第一帧
    """
    ret, frame = cap.read()
    return frame


def chartlet_video_to_video(main_cap, overlay_cap, chartlet_address, output_video_path):
    """
    必须要保证overlay_cap的总帧数大于main_cap的总帧数
    将overlay_cap的视频叠加到main_cap的视频上
    main_cap与overlay_cap都需要为cv2.VideoCapture对象
    chartlet_address为chartlet的地址
    chartlet_address为xyxy的格式
    """
    # 获取主视频的宽高信息
    # 获取主视频和覆盖视频的帧率
    fps = main_cap.get(cv2.CAP_PROP_FPS)

    # 获取主视频的宽高信息
    frame_width = int(main_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(main_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 创建视频写入对象，用于保存合成视频
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 视频编码格式
    out = cv2.VideoWriter(output_video_path, fourcc, fps,
                          (frame_width, frame_height))
    # 提取 chartlet_address 的坐标
    x1, y1, x2, y2 = chartlet_address  # 左上角(x1, y1)，右下角(x2, y2)

    # 在 overlay_cap 中读取帧

    while main_cap.isOpened() and overlay_cap.isOpened():
        ret_main, main_frame = main_cap.read()
        ret_overlay, overlay_frame = overlay_cap.read()

        if not ret_main or not ret_overlay:
            break

        # 确保 overlay_frame 和目标区域大小匹配
        overlay_resized = cv2.resize(overlay_frame, (x2 - x1, y2 - y1))

        # 将 overlay_frame 放置在 main_frame 的指定区域
        main_frame_with_overlay = main_frame.copy()

        # 确保不会越界
        main_frame_with_overlay[y1:y2, x1:x2] = overlay_resized

        # 写入合成后的帧到输出视频
        out.write(main_frame_with_overlay)


def invoke_game_ad_workflow(game_video_input, game_cover_input):
    # 1.llm生成文生图的prompt与脚本

    # 2.使用文生图prompt来生成图片

    # 3.对图片进行手机内容替换

    # 4.使用脚本+图片进行视频生成

    # 5.返回视频路径
    output_video_path = ""
    return output_video_path
