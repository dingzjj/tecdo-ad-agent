"""
核心钩子模块
提供应用加载、用户输入处理、文件管理和视频生成等功能
"""

import asyncio
import os
from typing import List, Tuple, Optional, Dict, Any
import gradio as gr

from agent.utils import get_time_id
from agent.ad_agent.m2v_workflow import ainvoke_m2v_workflow
from agent.ad_agent.do_workflow import start_hint
from config import conf
from pojo import user_id

# 常量定义
MAX_IMAGE_CONTAINER_NUMBER = 5
MIN_IMAGE_CONTAINER_NUMBER = 0
DEFAULT_VIDEO_FRAGMENT_DURATION = 5
DEFAULT_PRODUCT = "clothes"
DEFAULT_PRODUCT_INFO = "clothes"
DEFAULT_VIDEO_FILENAME = "video_url_v1.mp4"

# 文件类型映射
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv")


def load_app(user_id: str) -> Tuple[str, List[gr.ChatMessage]]:
    """
    加载应用并初始化聊天界面

    Args:
        user_id: 用户ID

    Returns:
        用户ID和初始化的聊天历史
    """
    # 生成新的用户ID
    new_user_id = get_time_id()

    # 创建用户数据目录
    user_data_path = os.path.join(conf.get("user_data_dir"), new_user_id)
    os.makedirs(user_data_path, exist_ok=True)

    # 初始化聊天历史
    chatbot = []

    # 添加欢迎图片
    welcome_image_path = "/data/dzj/ad_agent/agent/ad_agent/data/tecdo.jpg"
    if os.path.exists(welcome_image_path):
        chatbot.append(
            gr.ChatMessage(role="assistant", content=gr.Image(
                value=welcome_image_path))
        )

    # 添加开始提示
    chatbot.append(
        gr.ChatMessage(role="assistant", content=start_hint)
    )

    return new_user_id, chatbot


def user_input_func(
    user_input: Dict[str, Any],
    chatbot: List[gr.ChatMessage]
) -> List[gr.ChatMessage]:
    """
    处理用户输入，将文件和文本添加到聊天历史

    Args:
        user_input: 用户输入，包含文本和文件
        chatbot: 当前聊天历史

    Returns:
        更新后的聊天历史
    """
    user_question = user_input.get("text", "")
    upload_files = user_input.get("files", [])

    # 处理上传的文件
    for file_path in upload_files:
        if not file_path:
            continue

        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in IMAGE_EXTENSIONS:
            chatbot.append(
                gr.ChatMessage(role="user", content=gr.Image(value=file_path))
            )
        elif file_ext in VIDEO_EXTENSIONS:
            chatbot.append(
                gr.ChatMessage(role="user", content=gr.Video(value=file_path))
            )
        else:
            chatbot.append(
                gr.ChatMessage(role="user", content=file_path)
            )

    # 添加用户文本
    if user_question:
        chatbot.append(
            gr.ChatMessage(role="user", content=user_question)
        )

    return chatbot


def change_file(file_path: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    根据文件类型返回相应的显示组件

    Args:
        file_path: 文件路径

    Returns:
        视频显示路径和图片显示路径的元组
    """
    if not file_path:
        return None, None

    video_display = None
    image_display = None

    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext == ".mp4":
        video_display = file_path
    elif file_ext in (".jpg", ".png"):
        image_display = file_path

    return video_display, image_display


async def m2v_v1_generate(
    positive_prompt: str,
    negative_prompt: str,
    img1_1: Optional[str], img1_2: Optional[str], img1_3: Optional[str],
    img1_4: Optional[str], img1_5: Optional[str],
    img2_1: Optional[str], img2_2: Optional[str], img2_3: Optional[str],
    img2_4: Optional[str], img2_5: Optional[str],
    img3_1: Optional[str], img3_2: Optional[str], img3_3: Optional[str],
    img3_4: Optional[str], img3_5: Optional[str]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    从多组图片生成视频（v1版本）

    Args:
        positive_prompt: 正向提示词
        negative_prompt: 负向提示词
        img1_1-img1_5: 第一组图片
        img2_1-img2_5: 第二组图片
        img3_1-img3_5: 第三组图片

    Returns:
        三个生成的视频路径
    """
    # 组织图片数据
    img_dict = {
        "img1": [img1_1, img1_2, img1_3, img1_4, img1_5],
        "img2": [img2_1, img2_2, img2_3, img2_4, img2_5],
        "img3": [img3_1, img3_2, img3_3, img3_4, img3_5]
    }

    # 过滤有效的图片
    img1_list = [img for img in img_dict["img1"] if img is not None]
    img2_list = [img for img in img_dict["img2"] if img is not None]
    img3_list = [img for img in img_dict["img3"] if img is not None]

    # 准备任务列表
    task_list = []
    workflow_ids = [None] * 3
    video_output_path = os.path.join(conf.get_path("user_data_dir"), user_id)
    os.makedirs(video_output_path, exist_ok=True)

    # 初始化视频路径
    video1 = None
    video2 = None
    video3 = None

    # 执行生成任务
    if img1_list:
        workflow_ids[0] = get_time_id()
        task_list.append(
            _create_video_generation_task(
                workflow_ids[0], img1_list, positive_prompt, negative_prompt, video_output_path
            )
        )
        video1 = os.path.join(
            video_output_path, workflow_ids[0], DEFAULT_VIDEO_FILENAME)

    if img2_list:
        workflow_ids[1] = get_time_id()
        task_list.append(
            _create_video_generation_task(
                workflow_ids[1], img2_list, positive_prompt, negative_prompt, video_output_path
            )
        )
        video2 = os.path.join(
            video_output_path, workflow_ids[1], DEFAULT_VIDEO_FILENAME)

    if img3_list:
        workflow_ids[2] = get_time_id()
        task_list.append(
            _create_video_generation_task(
                workflow_ids[2], img3_list, positive_prompt, negative_prompt, video_output_path
            )
        )
        video3 = os.path.join(
            video_output_path, workflow_ids[2], DEFAULT_VIDEO_FILENAME)

    # 等待所有任务完成
    if task_list:
        await asyncio.gather(*task_list)

    return video1, video2, video3


def _create_video_generation_task(
    workflow_id: str,
    model_images: List[str],
    positive_prompt: str,
    negative_prompt: str,
    video_output_path: str
) -> Any:
    """
    创建视频生成任务

    Args:
        workflow_id: 工作流ID
        model_images: 模型图片列表
        positive_prompt: 正向提示词
        negative_prompt: 负向提示词
        video_output_path: 视频输出路径

    Returns:
        异步任务对象
    """
    return ainvoke_m2v_workflow(
        user_id=f"{user_id}_{workflow_id}",
        id=workflow_id,
        product=DEFAULT_PRODUCT,
        product_info=DEFAULT_PRODUCT_INFO,
        model_images=model_images,
        video_fragment_duration=DEFAULT_VIDEO_FRAGMENT_DURATION,
        video_output_path=os.path.join(video_output_path, workflow_id),
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt
    )


def m2v_v1_clear(
    group_number: int,
    group_img_container_number: int
) -> Tuple[None, ...]:
    """
    清空v1版本的图片容器

    Args:
        group_number: 组数
        group_img_container_number: 每组图片数量

    Returns:
        包含None值的元组
    """
    output_size = group_number * group_img_container_number
    return tuple([None] * output_size)


def m2v_v2_clear() -> Tuple[None, ...]:
    """
    清空v2版本的图片容器

    Returns:
        包含None值的元组
    """
    return tuple([None] * (MAX_IMAGE_CONTAINER_NUMBER * MAX_IMAGE_CONTAINER_NUMBER))


def m2v_v2_add_image_btn_click(image_container_number: int) -> Tuple[int, ...]:
    """
    添加图片按钮点击事件

    Args:
        image_container_number: 当前图片容器数量

    Returns:
        更新后的状态元组
    """
    # 更新按钮状态
    add_btn_state = gr.update(interactive=True)
    remove_btn_state = gr.update(interactive=True)

    # 增加容器数量
    if image_container_number < MAX_IMAGE_CONTAINER_NUMBER:
        image_container_number += 1

    # 如果达到最大值，禁用添加按钮
    if image_container_number == MAX_IMAGE_CONTAINER_NUMBER:
        add_btn_state = gr.update(interactive=False)

    # 生成可见性更新列表
    visible_containers = [
        gr.update(visible=True) for _ in range(image_container_number)
    ]
    invisible_containers = [
        gr.update(visible=False) for _ in range(
            MAX_IMAGE_CONTAINER_NUMBER - image_container_number
        )
    ]

    return (
        image_container_number,
        *visible_containers,
        *invisible_containers,
        add_btn_state,
        remove_btn_state
    )


def m2v_v2_remove_image_btn_click(image_container_number: int) -> Tuple[int, ...]:
    """
    删除图片按钮点击事件

    Args:
        image_container_number: 当前图片容器数量

    Returns:
        更新后的状态元组
    """
    # 更新按钮状态
    add_btn_state = gr.update(interactive=True)
    remove_btn_state = gr.update(interactive=True)

    # 减少容器数量
    if image_container_number > MIN_IMAGE_CONTAINER_NUMBER:
        image_container_number -= 1

    # 如果达到最小值，禁用删除按钮
    if image_container_number == MIN_IMAGE_CONTAINER_NUMBER:
        remove_btn_state = gr.update(interactive=False)

    # 生成可见性更新列表
    visible_containers = [
        gr.update(visible=True) for _ in range(image_container_number)
    ]
    invisible_containers = [
        gr.update(visible=False) for _ in range(
            MAX_IMAGE_CONTAINER_NUMBER - image_container_number
        )
    ]

    return (
        image_container_number,
        *visible_containers,
        *invisible_containers,
        add_btn_state,
        remove_btn_state
    )
