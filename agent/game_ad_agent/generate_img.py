import cv2
import numpy as np
from config import logger
import os
import io
import requests
from agent.third_part.comfyui import post_job, get_images
from agent.third_part.comfyui import modify_workflow
from agent.third_part.comfyui import get_workflow
import uuid
from config import conf
import mimetypes
from sqlalchemy import desc
from agent.llm import get_gemini_multimodal_model
from vertexai.generative_models import Part
import asyncio
import json
from moviepy.editor import VideoFileClip
import math
from agent.game_ad_agent.prompt import ANALYSE_VIDEO_SYSTEM_PROMPT_en, ANALYSE_VIDEO_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en


def get_video_duration(video_path):
    try:
        with VideoFileClip(video_path) as clip:
            duration = clip.duration
        return duration
    except Exception as e:
        print(f"❌ 读取视频失败: {e}")
        return None


def generate_image_prompt(video_path, description, orientation):
    duration = get_video_duration(video_path)
    prompt_count = max(1, math.floor(duration / 8))
    with open(video_path, "rb") as file:
        video_data = file.read()
    mime_type, _ = mimetypes.guess_type(video_path)
    if mime_type is None:
        mime_type = "video/mp4"
    system_prompt = ANALYSE_VIDEO_SYSTEM_PROMPT_en.format(count=prompt_count*2)
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=system_prompt,
        response_schema=ANALYSE_VIDEO_RESPONSE_SCHEMA
    )
    response = gemini_generative_model.generate_content([
        ANALYSE_IMAGE_HUMAN_PROMPT_en.format(
            description=description, orientation=orientation),
        Part.from_data(video_data, mime_type=mime_type)
    ])
    content = response.candidates[0].content.parts[0].text
    content_json = json.loads(content)
    prompt_list = content_json.get("prompt", [])
    return prompt_list

# def generate_image_v1(image_prompt):
#     """模拟生成图片，其实是从/data/dzj/ad_agent/user_dir/20250804111203/image_v1中逐一读取图片"""
#     image_v1_dir = "/data/dzj/ad_agent/user_dir/20250804111203/image_v1"
#     image_v1_list = os.listdir(image_v1_dir)
#     for image_v1_path in image_v1_list:
#         image_v1 = cv2.imread(image_v1_path)
#         yield image_v1


def generate_image_v1(image_prompt):
    """
    生成文生图的图片 by WAN
    输出图片的cv格式
    """
    comfyui_server_address = conf.get("comfyui_server_address")
    client_id = str(uuid.uuid4())  # generate client_id
    prompt = get_workflow(conf.get_path("WAN_generate_img_workflow_file"))
    prompt = modify_workflow(prompt, image_prompt)
    # 运行
    prompt_id = post_job(comfyui_server_address, client_id, prompt)
    outputs = get_images(comfyui_server_address, prompt_id)
    # 只处理28号节点

    if "63" in outputs:
        node_output = outputs["63"]
        images = node_output.get("images", [])
        for idx, image_info in enumerate(images):
            params = {
                "filename": image_info["filename"],
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "temp"),
            }
            view_url = f"http://{comfyui_server_address}/view"
            try:
                image_resp = requests.get(view_url, params=params)
                if image_resp.status_code != 200:
                    logger.error(f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                    logger.error(image_resp.text[:200])
                    continue
                # 将图片的image_resp.content转换为cv格式
                # 将 image_resp.content 转换为 BytesIO 对象
                image_bytes = io.BytesIO(image_resp.content)

                # 从 BytesIO 对象读取图像并转换为 NumPy 数组
                image_np = np.frombuffer(image_bytes.read(), dtype=np.uint8)

                # 使用 cv2.imdecode 将 NumPy 数组解码为 OpenCV 格式的图像
                # cv2.IMREAD_COLOR 表示彩色图像
                image_cv = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
                return image_cv
            except Exception as e:
                logger.error(f"❌ 图片解码失败: {params}")
                logger.error("返回内容前200字符:", image_resp.content[:200])
                logger.error(e)
    else:
        logger.error("⚠️ 未找到63号节点的输出")
    raise Exception("未找到63号节点的输出")

# async def main():
#     video_path = "./input_file/Mahjong_Match.mp4"
#     description = """
#     This is a relaxing game perfect for playing during short breaks: a simple mahjong tile-matching puzzle. Players need to tap two identical mahjong tiles to eliminate them and clear the entire board. The game has a gentle pace, a clean interface, and calming music.
#     """
#     prompt = await generate_video_prompt(video_path, description)
#     print(prompt)

# if __name__ == "__main__":
#     asyncio.run(main())
