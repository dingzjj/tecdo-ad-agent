import gradio as gr
from agent.ad_agent.m2v_workflow import generate_video_fragment_single_func
from agent.ad_agent.m2v_workflow import video_stitching_single_func
from config import conf
import asyncio
import os
from agent.utils import get_time_id
import time


def m2v_v2_generate(img, positive_prompt, negative_prompt, action_type):
    # 将文件存储到
    if not positive_prompt:
        positive_prompt = ""
    if not negative_prompt:
        negative_prompt = ""
    if not action_type:
        action_type = "model_show"

    # 初始化
    if not os.path.exists(img):
        return None
    while os.path.getsize(img) == 0:
        time.sleep(1)
    fragment_id = get_time_id()
    video_path = asyncio.run(generate_video_fragment_single_func(
        fragment_id, img, positive_prompt, negative_prompt, action_type, os.path.join(conf.get_path("user_data_dir"), "main", fragment_id))
    )
    return video_path


def m2v_v2_video_stitching(container_image_number, video_fragment1, video_fragment2, video_fragment3, video_fragment4, video_fragment5):
    video_fragment_list = [video_fragment1, video_fragment2,
                           video_fragment3, video_fragment4, video_fragment5]
    video_fragment_list = video_fragment_list[:container_image_number]
    video_id = get_time_id()

    video_fragment_list_new = []
    for video_fragment in video_fragment_list:
        # 确认每个片段的文件存在
        if video_fragment is None or video_fragment == "":
            continue
        if os.path.exists(video_fragment):
            video_fragment_list_new.append(video_fragment)
        while os.path.getsize(video_fragment) == 0:
            time.sleep(1)
    video_path = asyncio.run(video_stitching_single_func(
        os.path.join(conf.get_path("user_data_dir"), "main", video_id), video_fragment_list_new)
    )
    return gr.update(value=video_path)
