from agent.ad_agent.utils import concatenate_videos_from_urls
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
