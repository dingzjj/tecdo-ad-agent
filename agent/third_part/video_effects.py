from config import conf
from agent.utils import temp_dir
import os
import shutil
import uuid
from agent.third_part.moviepy_apply import concatenate_videos_from_urls
from moviepy.editor import VideoFileClip, CompositeVideoClip, concatenate_videoclips
from enum import Enum


class VideoTransitionType(Enum):
    DISSOLVE = "dissolve"
    CONCATENATE = "concatenate"


def video_transitions(video_1_path, video_2_path, output_path, type: VideoTransitionType):
    match type:
        case VideoTransitionType.DISSOLVE:
            return video_transitions_with_dissolve(video_1_path, video_2_path, output_path)
        case VideoTransitionType.CONCATENATE:
            return video_transitions_with_concatenate(video_1_path, video_2_path, output_path)
        case _:
            raise ValueError(f"Invalid transition type: {type}")


def video_transitions_with_concatenate(video_1_path, video_2_path, output_path):
    """
    视频转场效果,使用 concatenate
    """
    video_list = [video_1_path, video_2_path]
    return concatenate_videos_from_urls(
        video_list, output_path=output_path)


def video_transitions_with_dissolve(video_1_path, video_2_path, output_path, transition_duration: float = 0.5, split_count: int = 20):
    """
    视频转场效果,使用 dissolve, 支持动态设置转场时长和分割片段数量。
    """
    # 加载视频
    clip_1 = VideoFileClip(video_1_path)
    clip_2 = VideoFileClip(video_2_path)

    # 获取视频时长
    duration_video1 = clip_1.duration
    duration_video2 = clip_2.duration

    # 第一部分：纯 1.mp4
    part1 = clip_1.subclip(0, duration_video1 - transition_duration)

    # 第三部分：纯 2.mp4
    part3 = clip_2.subclip(transition_duration, duration_video2)

    # 第二部分：1.mp4和2.mp4的叠加部分
    part2_1 = clip_1.subclip(
        duration_video1 - transition_duration, duration_video1)
    part2_2 = clip_2.subclip(0, transition_duration)

    # 根据分割数量，动态生成更细粒度的转场片段
    def split_part(part, count, part_name):
        """ 将视频片段 `part` 分割成 `count` 个小片段，并返回这些小片段 """
        segment_duration = transition_duration / count
        segments = []
        for i in range(count):
            start_time = i * segment_duration
            end_time = start_time + segment_duration
            segment = part.subclip(start_time, end_time)
            segments.append(segment)
        return segments

    part2_1_segments = split_part(part2_1, split_count, "part2_1")
    part2_2_segments = split_part(part2_2, split_count, "part2_2")

    # 生成叠化效果：为每一段设置不同的透明度
    def apply_fade_in_effect(part1_segments, part2_segments, split_count):
        """ 根据透明度为每个分段应用叠化效果 """
        fade_opacities = [0.95, 0.85, 0.75, 0.65,
                          0.55, 0.45, 0.35, 0.25, 0.15, 0.05]
        # 将1分成split_count段,每段设置不同的透明度
        fade_opacities = [round(1 - i/split_count, 3)
                          for i in range(split_count)]
        composite_segments = []
        for i in range(len(part1_segments)):
            # 叠加每对片段（前片段设置透明度）
            composite = CompositeVideoClip(
                [part2_segments[i], part1_segments[i].set_opacity(fade_opacities[i])])
            composite_segments.append(composite)
        return composite_segments

    # 应用叠化效果
    part2_composite = apply_fade_in_effect(
        part2_1_segments, part2_2_segments, split_count)

    # 拼接视频片段
    video1 = concatenate_videoclips(part2_composite)
    video2 = concatenate_videoclips([part1, video1, part3])

    # 输出视频
    video2.write_videofile(output_path, codec="libx264", audio_codec="aac")

    return video2


def video_stitching(video_output_path: str, video_fragment_list: list[str], video_transition_type: VideoTransitionType = VideoTransitionType.CONCATENATE):
    os.makedirs(video_output_path, exist_ok=True)
    # 其中的video_fragment_list是视频片段的绝对路径列表
    if len(video_fragment_list) == 0:
        return None
    if len(video_fragment_list) == 1:
        return video_fragment_list[0]
    print(video_fragment_list)
    with temp_dir(dir_path=conf.get_path("temp_dir"), name=str(uuid.uuid4())) as temp_concatenate_dir:
        now_concatenate_index = 0
        while len(video_fragment_list) > 1:
            output_path = os.path.join(
                temp_concatenate_dir, f"concat_{now_concatenate_index}_{now_concatenate_index+1}.mp4")

            video_transitions(
                video_fragment_list[0], video_fragment_list[1], output_path, video_transition_type)
            video_fragment_list.pop(1)
            video_fragment_list[0] = output_path
            now_concatenate_index += 1

        video_url_v1 = os.path.join(video_output_path, "video_url_v1.mp4")
        # 将now_batch_video_list中的唯一一个文件copy到
        shutil.copy(video_fragment_list[-1], video_url_v1)
    return video_url_v1
