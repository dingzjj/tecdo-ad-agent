import time
from config import conf
import uuid
import shutil
from moviepy.editor import VideoFileClip
from agent.utils import judge_file_exist
from agent.utils import temp_dir
from config import logger
from moviepy.editor import VideoFileClip, concatenate_videoclips


def concatenate_videos_from_urls(video_urls, output_path):
    """
    将视频列表拼接成一个视频，并保存到output_path
    Args:
        video_urls: 视频列表(可以为本地pah，也可以为url)
        output_path: 输出视频路径
    Returns:
        str: 输出视频路径
    """
    if len(video_urls) == 0:
        raise Exception("视频列表为空")
    clips = []
    with temp_dir(dir_path=conf.get_path("temp_dir"), name=str(uuid.uuid4())) as temp_dir_path:
        for i, url in enumerate(video_urls):
            # 判断是否是本地文件，是本地文件的话，判断文件是否存在，如果是url则下载到本地的临时目录中
            downloaded = judge_file_exist(
                url, temp_dir_path, f"temp_video_{i}.mp4")
            if downloaded["exist"]:
                logger.info(f"merge video: {downloaded['path']}")
                clip = VideoFileClip(downloaded["path"])
                clips.append(clip)
            else:
                if downloaded["type"] == "url":
                    logger.error(f"下载失败: {url}")
                else:
                    logger.error(f"文件不存在: {url}")
        if len(clips) == 0:
            logger.error("未找到可用的视频文件。")
        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip.write_videofile(
            output_path, codec="libx264", audio_codec="aac")
        return output_path
