import asyncio
from agent.utils import get_time_id
from config import conf
import uuid
from agent.ad_agent.m2v_workflow import ainvoke_m2v_workflow
import os

import gradio as gr

from agent.ad_agent.do_workflow import start_hint

from pojo import user_id
import cv2
from PIL import Image


def load_app():
    os.makedirs(os.path.join(
        conf.get("user_data_dir"), user_id), exist_ok=True)
    # chatbot = [gr.ChatMessage(role="assistant", content=start_hint)]


# 先为chatbot添加用户输入


def user_input_func(user_input, chatbot):
    chatbot.append(gr.ChatMessage(role="user", content=user_input))
    return chatbot


def change_file(file_path):
    if file_path is None:
        return None, None
    video_display = None
    image_display = None
    filename, file_extension = os.path.splitext(file_path)
    if file_extension == ".mp4":
        video_display = file_path
    elif file_extension == ".jpg" or file_extension == ".png":
        image_display = file_path
    return video_display, image_display


async def m2v_v1_generate(positive_prompt, negative_prompt, img1_1, img1_2, img1_3, img1_4, img1_5, img2_1, img2_2, img2_3, img2_4, img2_5, img3_1, img3_2, img3_3, img3_4, img3_5):
    # video1
    img_dict = {
        "img1": [img1_1, img1_2, img1_3, img1_4, img1_5],
        "img2": [img2_1, img2_2, img2_3, img2_4, img2_5],
        "img3": [img3_1, img3_2, img3_3, img3_4, img3_5]
    }

    img1_list = [img for img in img_dict["img1"] if img is not None]
    img2_list = [img for img in img_dict["img2"] if img is not None]
    img3_list = [img for img in img_dict["img3"] if img is not None]
    task_list = []
    workflow_ids = [None]*3
    video_output_path = os.path.join(conf.get_path("user_data_dir"), user_id)
    os.makedirs(video_output_path, exist_ok=True)
    video1 = None
    video2 = None
    video3 = None
    # 执行生成任务
    if len(img1_list) > 0:
        workflow_ids[0] = get_time_id()
        task_list.append(ainvoke_m2v_workflow(user_id=f"{user_id}_{workflow_ids[0]}", id=workflow_ids[0], product="clothes", product_info="clothes",
                         model_images=img1_list, video_fragment_duration=5, video_output_path=os.path.join(video_output_path, workflow_ids[0]), positive_prompt=positive_prompt, negative_prompt=negative_prompt))
        video1 = os.path.join(
            video_output_path, workflow_ids[0], "video_url_v1.mp4")
    if len(img2_list) > 0:
        workflow_ids[1] = get_time_id()
        task_list.append(ainvoke_m2v_workflow(user_id=f"{user_id}_{workflow_ids[0]}", id=workflow_ids[1], product="clothes", product_info="clothes",
                         model_images=img2_list, video_fragment_duration=5, video_output_path=os.path.join(video_output_path, workflow_ids[1]), positive_prompt=positive_prompt, negative_prompt=negative_prompt))
        video2 = os.path.join(
            video_output_path, workflow_ids[1], "video_url_v1.mp4")
    if len(img3_list) > 0:
        workflow_ids[2] = get_time_id()
        task_list.append(ainvoke_m2v_workflow(user_id=f"{user_id}_{workflow_ids[0]}", id=workflow_ids[2], product="clothes", product_info="clothes",
                         model_images=img3_list, video_fragment_duration=5, video_output_path=os.path.join(video_output_path, workflow_ids[2]), positive_prompt=positive_prompt, negative_prompt=negative_prompt))
        video3 = os.path.join(
            video_output_path, workflow_ids[2], "video_url_v1.mp4")

    # 等待所有任务完成
    await asyncio.gather(*task_list)

    return video1, video2, video3


def m2v_v1_clear(group_number, group_img_container_number):
    output = [None]*(group_number*group_img_container_number)
    return tuple(output)


def m2v_v2_clear():
    return tuple([None]*5*5)


max_image_container_number = 5
min_image_container_number = 0


def m2v_v2_add_image_btn_click(image_container_number):
    m2v_v2_container_add_btn_state = gr.update(interactive=True)
    # 增加之后一定能删除
    m2v_v2_container_remove_btn_state = gr.update(interactive=True)
    if image_container_number < max_image_container_number:
        image_container_number += 1
    if image_container_number == max_image_container_number:
        m2v_v2_container_add_btn_state = gr.update(interactive=False)

    visiable_container = [gr.update(visible=True)
                          for _ in range(image_container_number)]
    invisiable_container = [gr.update(visible=False) for _ in range(
        max_image_container_number-image_container_number)]
    return image_container_number, *visiable_container, *invisiable_container, m2v_v2_container_add_btn_state, m2v_v2_container_remove_btn_state


def m2v_v2_remove_image_btn_click(image_container_number):
    # 删除之后一定能增加
    m2v_v2_container_add_btn_state = gr.update(interactive=True)
    m2v_v2_container_remove_btn_state = gr.update(interactive=True)
    if image_container_number > min_image_container_number:
        image_container_number -= 1
    if image_container_number == min_image_container_number:
        m2v_v2_container_remove_btn_state = gr.update(interactive=False)
    visiable_container = [gr.update(visible=True)
                          for _ in range(image_container_number)]
    invisiable_container = [gr.update(visible=False) for _ in range(
        max_image_container_number-image_container_number)]
    return image_container_number, *visiable_container, *invisiable_container, m2v_v2_container_add_btn_state, m2v_v2_container_remove_btn_state
