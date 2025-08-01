from agent.utils import get_time_id
import cv2
from PIL import Image
from config import conf
import os
import gradio as gr


def game_ad_submit(game_video_input, game_cover_input):
    # 检查输入文件是否存在
    if not game_video_input or not os.path.exists(game_video_input):
        raise ValueError(f"视频文件不存在: {game_video_input}")

    # 获得game_video_input视频的宽高
    cap = cv2.VideoCapture(game_video_input)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {game_video_input}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    # 确保temp目录存在
    temp_dir = conf.get_path("temp_dir")

    # 生成视频
    # 返回实际的视频文件路径

    output_video_path = ""
    return output_video_path, width, height


def get_game_ad_video_mid_state(game_ad_video_mid_output):
    print(f"game_ad_video_mid_output: {game_ad_video_mid_output}")
    """
    获得中间状态
    """
    # 处理Gradio组件传递的参数
    # game_ad_video_mid_output 可能是元组 (image_path, annotations) 或者直接是路径
    if isinstance(game_ad_video_mid_output, tuple):
        video_path = game_ad_video_mid_output[0]  # 取第一个元素作为路径
    else:
        video_path = game_ad_video_mid_output

    # 检查输入文件是否存在
    if not video_path or not os.path.exists(video_path):
        raise ValueError(f"视频文件不存在: {video_path}")

    # 取出视频的第一张作为图片
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {video_path}")

    ret, frame = cap.read()
    cap.release()

    # 检查是否成功读取帧
    if not ret or frame is None:
        raise ValueError(f"无法从视频中读取帧: {video_path}")

    # 确保temp目录存在
    temp_dir = conf.get_path("temp_dir")
    os.makedirs(temp_dir, exist_ok=True)

    img_name = str(get_time_id()) + ".png"
    img_path = os.path.join(temp_dir, img_name)

    # 保存图片
    success = cv2.imwrite(img_path, frame)
    if not success:
        raise ValueError(f"无法保存图片到: {img_path}")

    # 获取图片的宽高
    height, width = frame.shape[:2]
    # 返回图片路径，x，y，width
    print(f"img_path: {img_path}")
    return img_path, gr.update(maximum=width), gr.update(maximum=height), gr.update(maximum=width)


def update_game_ad_video_mid_state(x_slider, y_slider, width_slider, game_ad_agent_mid_video_first_image, game_video_input, game_video_input_width, game_video_input_height):
    """
    更新中间状态
    """
    if x_slider > 0 and y_slider > 0 and width_slider > 0:
        if game_video_input_width == 0 or game_video_input_height == 0:
            # 通过game_video_input获得宽高
            cap = cv2.VideoCapture(game_video_input)
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {game_video_input}")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            game_video_input_width = width
            game_video_input_height = height
        x1 = x_slider
        y1 = y_slider
        x2 = int(x1 + width_slider)
        y2 = int(y1 + width_slider *
                 (game_video_input_height/game_video_input_width))
        return (game_ad_agent_mid_video_first_image, [((x1, y1, x2, y2), "")])
    else:
        return (game_ad_agent_mid_video_first_image, [])


def generate_game_ad_final_video(game_video_input, game_cover_input, game_ad_agent_mid_video, x_slider, y_slider, width_slider):
    """
    生成最终视频
    """
    pass
