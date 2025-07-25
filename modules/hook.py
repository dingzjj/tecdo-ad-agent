import asyncio
from config import conf
import uuid
from agent.ad_agent.m2v_workflow import ainvoke_m2v_workflow
import os

import gradio as gr

from agent.ad_agent.do_workflow import start_hint


def load_app(user_id):
    os.makedirs(os.path.join(
        conf.get("user_data_dir"), user_id), exist_ok=True)
    chatbot = [gr.ChatMessage(role="assistant", content=start_hint)]
    return chatbot


def user_input_func(user_input, chatbot):
    chatbot.append(gr.ChatMessage(role="user", content=user_input))
    return chatbot


def change_file(file_path, user_id):
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


async def m2v_v1_generate(user_id, positive_prompt, negative_prompt, img1_1, img1_2, img1_3, img1_4, img1_5, img2_1, img2_2, img2_3, img2_4, img2_5, img3_1, img3_2, img3_3, img3_4, img3_5):
    # video1
    img_dict = {
        "img1": [img1_1, img1_2, img1_3, img1_4, img1_5],
        "img2": [img2_1, img2_2, img2_3, img2_4, img2_5],
        "img3": [img3_1, img3_2, img3_3, img3_4, img3_5]
    }

    img1_list = [img for img in img_dict["img1"] if img is not None]
    img2_list = [img for img in img_dict["img2"] if img is not None]
    img3_list = [img for img in img_dict["img3"] if img is not None]
    print(img1_list)
    print(img2_list)
    print(img3_list)

    task_list = []
    workflow_ids = [None]*3
    video_output_path = os.path.join(conf.get_path("user_data_dir"), user_id)
    os.makedirs(video_output_path, exist_ok=True)
    video1 = None
    video2 = None
    video3 = None
    # 执行生成任务
    if len(img1_list) > 0:
        workflow_ids[0] = str(uuid.uuid4())
        task_list.append(ainvoke_m2v_workflow(user_id=f"{user_id}_{workflow_ids[0]}", id=workflow_ids[0], product="clothes", product_info="clothes",
                         model_images=img1_list, video_fragment_duration=5, video_output_path=os.path.join(video_output_path, workflow_ids[0]), positive_prompt=positive_prompt, negative_prompt=negative_prompt))
        video1 = os.path.join(
            video_output_path, workflow_ids[0], "video_url_v1.mp4")
    if len(img2_list) > 0:
        workflow_ids[1] = str(uuid.uuid4())
        task_list.append(ainvoke_m2v_workflow(user_id=f"{user_id}_{workflow_ids[0]}", id=workflow_ids[1], product="clothes", product_info="clothes",
                         model_images=img2_list, video_fragment_duration=5, video_output_path=os.path.join(video_output_path, workflow_ids[1]), positive_prompt=positive_prompt, negative_prompt=negative_prompt))
        video2 = os.path.join(
            video_output_path, workflow_ids[1], "video_url_v1.mp4")
    if len(img3_list) > 0:
        workflow_ids[2] = str(uuid.uuid4())
        task_list.append(ainvoke_m2v_workflow(user_id=f"{user_id}_{workflow_ids[0]}", id=workflow_ids[2], product="clothes", product_info="clothes",
                         model_images=img3_list, video_fragment_duration=5, video_output_path=os.path.join(video_output_path, workflow_ids[2]), positive_prompt=positive_prompt, negative_prompt=negative_prompt))
        video3 = os.path.join(
            video_output_path, workflow_ids[2], "video_url_v1.mp4")

    # 等待所有任务完成
    await asyncio.gather(*task_list)

    return video1, video2, video3


def m2v_v1_clear(video1, download1):
    print(video1)
    print(download1)
    return None, None


def m2v_v2_generate(group1_components, group2_components, group3_components):
    print(group1_components)
    print(group2_components)
    print(group3_components)


def m2v_v2_clear(video1, download1):
    print(video1)
    print(download1)
    return None, None


def ad_agent_send(user_input):
    print(user_input)
    return None, None
