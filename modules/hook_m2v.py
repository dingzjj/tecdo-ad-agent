"""
图片到视频生成模块 (v2版本)
提供单个图片生成视频和视频拼接功能
"""

import asyncio
import os
import time
from typing import List, Optional, Union
import gradio as gr

from agent.ad_agent.m2v_workflow import (
    generate_video_fragment_single_func,
    video_stitching_single_func
)
from agent.utils import get_time_id
from config import conf


def m2v_v2_generate(
    img: str,
    positive_prompt: str,
    negative_prompt: str,
    action_type: str
) -> Optional[str]:
    """
    从单张图片生成视频片段

    Args:
        img: 输入图片路径
        positive_prompt: 正向提示词
        negative_prompt: 负向提示词
        action_type: 动作类型

    Returns:
        生成的视频路径，失败时返回None
    """
    # 参数验证和默认值设置
    positive_prompt = positive_prompt or ""
    negative_prompt = negative_prompt or ""
    action_type = action_type or "model_show"

    # 检查输入文件
    if not img or not os.path.exists(img):
        return None

    # 等待文件完全写入
    _wait_for_file_ready(img)

    # 生成视频片段
    try:
        fragment_id = get_time_id()
        video_output_path = os.path.join(
            conf.get_path("user_data_dir"),
            "main",
            fragment_id
        )

        video_path = asyncio.run(
            generate_video_fragment_single_func(
                fragment_id,
                img,
                positive_prompt,
                negative_prompt,
                action_type,
                video_output_path
            )
        )
        return video_path
    except Exception as e:
        print(f"生成视频片段时发生错误: {e}")
        return None


def m2v_v2_video_stitching(
    container_image_number: int,
    video_fragment1: Optional[str],
    video_fragment2: Optional[str],
    video_fragment3: Optional[str],
    video_fragment4: Optional[str],
    video_fragment5: Optional[str]
) -> gr.update:
    """
    拼接多个视频片段

    Args:
        container_image_number: 图片容器数量
        video_fragment1-5: 视频片段路径

    Returns:
        Gradio更新对象，包含拼接后的视频路径
    """
    # 收集所有视频片段
    video_fragments = [
        video_fragment1, video_fragment2, video_fragment3,
        video_fragment4, video_fragment5
    ]

    # 根据容器数量截取片段
    video_fragments = video_fragments[:container_image_number]

    # 过滤有效的视频片段
    valid_fragments = _filter_valid_video_fragments(video_fragments)

    if not valid_fragments:
        return gr.update(value=None)

    try:
        # 生成拼接视频
        video_id = get_time_id()
        output_path = os.path.join(
            conf.get_path("user_data_dir"),
            "main",
            video_id
        )

        video_path = asyncio.run(
            video_stitching_single_func(output_path, valid_fragments)
        )
        return gr.update(value=video_path)
    except Exception as e:
        print(f"视频拼接时发生错误: {e}")
        return gr.update(value=None)


def _wait_for_file_ready(file_path: str, timeout: int = 30) -> None:
    """
    等待文件准备就绪（文件大小稳定）

    Args:
        file_path: 文件路径
        timeout: 超时时间（秒）
    """
    start_time = time.time()
    last_size = -1

    while time.time() - start_time < timeout:
        if os.path.exists(file_path):
            current_size = os.path.getsize(file_path)
            if current_size > 0 and current_size == last_size:
                return
            last_size = current_size
        time.sleep(1)

    raise TimeoutError(f"等待文件 {file_path} 准备就绪超时")


def _filter_valid_video_fragments(
    video_fragments: List[Optional[str]]
) -> List[str]:
    """
    过滤有效的视频片段

    Args:
        video_fragments: 视频片段路径列表

    Returns:
        有效的视频片段路径列表
    """
    valid_fragments = []

    for fragment in video_fragments:
        if not fragment or fragment == "":
            continue

        if os.path.exists(fragment):
            # 等待文件准备就绪
            try:
                _wait_for_file_ready(fragment)
                valid_fragments.append(fragment)
            except TimeoutError:
                print(f"视频片段 {fragment} 准备超时，跳过")
                continue

    return valid_fragments
