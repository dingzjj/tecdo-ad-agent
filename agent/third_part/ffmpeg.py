from agent.third_part.font.font import get_font
import os
import subprocess
import json
import ffmpeg
from typing import Optional

from config import logger


def remove_watermark(input_video, output_video, logo_x, logo_y, logo_width, logo_height):
    # 构建FFmpeg命令
    command = [
        'ffmpeg',
        '-i', input_video,
        '-vf', f'delogo=x={
            logo_x}:y={
            logo_y}:w={
            logo_width}:h={
            logo_height}',
        output_video
    ]

    # 运行FFmpeg命令
    subprocess.run(command)


def merge_video_audio(
    video_file: str,
    audio_file: str,
    output_file: str,
    volume: float,
    audio_start: Optional[str] = None,  # 音频起始时间，格式如 "00:00:03.500"
    audio_duration: Optional[str] = None,  # 音频持续时间，格式如 "00:00:10.500"
    use_shortest: bool = False,
    audio_delay: float = 0,
):
    """
    将视频与音频合并，支持设置音量、控制输出长度、音频延迟、音频起始时间和持续时间。

    参数:
        video_file (str): 视频文件路径。
        audio_file (str): 音频文件路径。
        output_file (str): 输出视频文件路径。
        volume (float or None): 音量倍数，例如 3 表示提高 300% 音量。
        use_shortest (bool): 如果为 True，则输出以最短输入流为准。
        audio_delay (float): 音频延迟时间（秒），最多3位小数。
        audio_start (str): 音频起始时间，格式如 "00:00:03.500"，默认为None。
        audio_duration (str): 音频持续时间，格式如 "00:00:10.500"，默认为None。
    """
    # 输入流
    video_input = ffmpeg.input(video_file)

    # 构建音频输入，添加 -ss 和 -t 参数
    audio_input_args = {}
    if audio_start:
        audio_input_args["ss"] = audio_start
    if audio_duration:
        audio_input_args["t"] = audio_duration

    audio_input = ffmpeg.input(audio_file, **audio_input_args)

    # 视频流直接复制
    video = video_input.video

    # 音频流处理
    audio = audio_input.audio

    # 应用音频延迟（限制为3位小数）
    if audio_delay > 0:
        delay_seconds = round(audio_delay, 3)
        delay_ms = int(delay_seconds * 1000)  # 转换为整数毫秒
        audio = audio.filter_(
            "adelay", f"{delay_ms}|{delay_ms}"
        )  # 对立体声的两个通道都延迟

    # 音量调整
    if volume is not None:
        audio = audio.filter_("volume", volume)

    # 构建输出命令
    output_args = {"vcodec": "copy", "acodec": "aac", "strict": "experimental"}

    # 添加 shortest 参数（如果需要）
    if use_shortest:
        output_args["shortest"] = None

    # 创建输出对象
    output = ffmpeg.output(video, audio, output_file, **output_args)

    # 执行命令
    try:
        output.run(overwrite_output=True)
    except ffmpeg.Error as e:
        logger.error("❌ FFmpeg 错误:")
        logger.error("stdout:", e.stdout.decode() if e.stdout else None)
        logger.error("stderr:", e.stderr.decode() if e.stderr else None)
        raise e


def get_video_resolution(video_path: str) -> dict:
    """
    使用 ffprobe 获取指定视频文件的分辨率（宽度和高度）。

    该函数通过调用 ffprobe 命令行工具，提取视频流的第一段（索引为0）的 width 和 height 字段，
    并以字典形式返回。如果解析失败或视频路径无效，则返回 None。

    Parameters:
        video_path (str): 视频文件的完整路径或相对路径。

    Returns:
        dict or None: 包含视频分辨率信息的字典，格式为 {"width": int, "height": int}。
                      如果发生错误（如文件不存在、ffprobe 执行失败），则返回 None。
    """
    # 构建 ffprobe 命令
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        video_path,
    ]

    # 执行命令并获取输出
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        result.check_returncode()  # 检查命令是否成功执行

        # 解析 JSON 输出
        output = json.loads(result.stdout)
        width = output["streams"][0]["width"]
        height = output["streams"][0]["height"]

        # 返回字典对象
        return {"width": width, "height": height}

    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred: {e.stderr}")
        raise e


# 视频融合简单字幕


def burn_subtitles_to_video_default(
    input_video_file: str, subtitle_file: str, output_video_dir: str
) -> str:
    """
    将 `.srt` 字幕渲染进视频画面，并输出到指定目录。

    使用 `subtitles={subtitle_file}` 滤镜方式将字幕烧录进视频。
    输出视频格式为 MP4，音频流直接复制，不重新编码。

    Parameters:
        input_video_file (str): 原始视频文件的完整路径。
        subtitle_file (str): `.srt` 字幕文件的完整路径。
        output_video_dir (str): 输出视频文件的保存目录。

    Returns:
        str: 渲染后的带字幕视频文件的完整路径。
    """
    if not os.path.exists(input_video_file):
        raise FileNotFoundError(f"找不到视频文件：{input_video_file}")
    if not os.path.exists(subtitle_file):
        raise FileNotFoundError(f"找不到字幕文件：{subtitle_file}")

    # 获取基础名称并构造输出路径
    base_name = os.path.splitext(os.path.basename(input_video_file))[0]
    output_video_file = os.path.join(output_video_dir, f"{base_name}_srt.mp4")
    os.makedirs(output_video_dir, exist_ok=True)

    try:
        (
            ffmpeg.input(input_video_file)
            .output(
                output_video_file,
                vf=f"subtitles={subtitle_file}",
                vcodec="libx264",
                acodec="copy",
            )
            .run(overwrite_output=True)
        )
        return output_video_file
    except ffmpeg.Error as e:
        logger.error("❌ FFmpeg 错误:")
        logger.error("stdout:", e.stdout.decode() if e.stdout else None)
        logger.error("stderr:", e.stderr.decode() if e.stderr else None)
        raise

# 视频融合个性化字幕


def burn_subtitles_to_video_individuation(
    input_video_file, subtitle_file, output_video_path, font_name
):
    """
    将自定义字体样式的 `.ass` 字幕渲染进视频画面，并输出到指定目录。

    使用 `subtitles={subtitle_file}:fontsdir={fonts_dir}:force_style='FontName={font_name}'` 滤镜方式渲染字幕。
    输出视频格式为 MP4，音频流直接复制，不重新编码。

    Parameters:
        input_video_file (str): 原始视频文件的完整路径。
        subtitle_file (str): `.ass` 字幕文件的完整路径。
        output_video_dir (str): 输出视频文件的保存目录。
        fonts_dir (str): 存放字体文件的目录路径。
        font_name (str): 使用的字体文件名（如 Caprasimo-Regular.ttf）。

    Returns:
        str: 渲染后的带字幕视频文件的完整路径。
    """
    if not os.path.exists(input_video_file):
        raise FileNotFoundError(f"找不到视频文件：{input_video_file}")
    if not os.path.exists(subtitle_file):
        raise FileNotFoundError(f"找不到字幕文件：{subtitle_file}")
    font_info = get_font(font_name)
    fonts_dir = font_info["font-dir"]
    font_name = font_info["font-name"]
    try:
        (
            ffmpeg.input(input_video_file)
            .output(
                output_video_path,
                vf=f"subtitles={subtitle_file}:fontsdir={
                    fonts_dir}:force_style='FontName={font_name}'",
                vcodec="libx264",
                acodec="copy",
            )
            .run(overwrite_output=True)
        )
        return output_video_path
    except ffmpeg.Error as e:
        logger.error("❌ FFmpeg 错误:")
        logger.error("stdout:", e.stdout.decode() if e.stdout else None)
        logger.error("stderr:", e.stderr.decode() if e.stderr else None)
        raise e


def extract_audio(video_file: str, output_audio_path: str, audio_type: str = "mp3") -> str:
    """
    从指定视频文件中提取音频，并保存为 .wav 格式到指定输出目录。

    视频文件名中的扩展名会被去掉，并替换为 `.wav` 作为音频输出文件名。
    示例：输入 `video.mp4`，输出 `video.wav`。

    Parameters:
        video_file (str): 视频文件的完整路径（支持常见格式如 mp4、avi 等）。
        output_audio_path (str): 音频文件要保存的目标路径。

    Returns:
        str: 提取后的音频文件的完整路径（WAV 格式）
    """
    try:
        # 使用 ffmpeg 提取音频并转为 WAV 格式
        (
            ffmpeg.input(video_file)
            .output(output_audio_path, format=audio_type)
            .run(overwrite_output=True)
        )

        return output_audio_path

    except ffmpeg.Error as e:
        logger.error("❌ FFmpeg 错误:", e.stderr.decode()
                     if e.stderr else "无详细错误信息")
        raise e
