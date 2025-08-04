import time
from config import conf
import uuid
import shutil
from moviepy.editor import VideoFileClip
from pydub.utils import mediainfo
from agent.utils import judge_file_exist
from agent.utils import temp_dir
from config import logger
from moviepy.editor import VideoFileClip, concatenate_videoclips
import os
import requests
from agent.ad_agent.prompt import ANALYSE_IMAGE_RESPONSE_SCHEMA


def reconstruct_model_image_info(model_image_info: dict) -> str:
    return f"""{ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["connection"]["description"]}:{model_image_info["connection"]}
    {ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["composition"]["description"]}:{model_image_info["composition"]}
    {ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["Character posture"]["description"]}:{model_image_info["Character posture"]}
    """


def download_video(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        logger.error(f"下载失败: {url}")
        return None
    return filename


def get_audio_duration(file_path: str) -> float:
    # 获取音频文件的元数据
    audio_info = mediainfo(file_path)
    # 提取时长（以秒为单位）
    duration = float(audio_info['duration'])
    return duration


def copy_dir_to_dir(old_dir: str, new_dir: str):
    """
    将old_dir下的所有文件和文件夹复制到new_dir下
    old_dir和new_dir是总文件夹
    """
    shutil.copytree(old_dir, new_dir, dirs_exist_ok=True)


def validate_file_within_directory(base_directory: str, target_path: str) -> str:
    """
    检查给定的目标路径是否在指定的文件夹内。如果不在，则抛出异常。

    :param base_directory: 目标文件夹的根路径
    :param target_path: 要验证的目标文件路径
    :return: 如果目标路径在指定文件夹内，则返回该路径，否则抛出异常
    :raises ValueError: 如果目标路径超出了指定文件夹
    """
    # 规范化路径
    base_directory = os.path.abspath(base_directory)
    target_path = os.path.abspath(target_path)

    # 检查目标路径是否位于基准文件夹内
    if not target_path.startswith(base_directory):
        raise ValueError(f"目标路径 {target_path} 超出了指定文件夹 {base_directory} 的范围。")

    return target_path


def get_absolute_path_from_user_dir(user_id: str, file_path: str) -> str:
    """
    相对路径 -> 绝对路径
    file_path一般为相对路径
    """
    file_path = os.path.join(conf.get_path(
        "user_data_dir"), user_id, file_path)

    # 先判断分为是否超过
    if not validate_file_within_directory(conf.get_path("user_data_dir"), file_path):
        raise ValueError(f"文件路径 {file_path} 超出了指定文件夹 {
                         conf.get_path("user_data_dir")} 的范围。")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    return file_path
