from config import logger
import math
import json
import whisper
import os
import torch
from agent.third_part.ffmpeg import get_video_resolution

# 检查是否支持 CUDA
device = "cuda" if torch.cuda.is_available() else "cpu"

# 加载模型（可以改为 large、base、medium 等）
model = whisper.load_model("small", device=device)


def format_timestamp(seconds) -> str:
    """格式化时间戳为 SRT 格式"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def transcribe_audio_to_sentences(audio_path: str, output_dir: str = None) -> str:
    """
    将音频文件转录成句子级别的 SRT 字幕文件
    :param audio_path: 音频文件路径
    :param output_dir: 指定的输出目录（可选），默认为当前脚本目录下的 'whisper_output'
    :return: 生成的 .srt 文件路径
    """
    if output_dir is None:
        output_dir = "./whisper_output"
    os.makedirs(output_dir, exist_ok=True)

    result = model.transcribe(audio_path)

    # 使用原始文件名作为基础命名
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    srt_path = os.path.join(output_dir, f"{base_name}_sentence.srt")

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(result["segments"], start=1):
            start = segment["start"]
            end = segment["end"]
            text = segment["text"].strip()
            f.write(
                f"{i}\n{format_timestamp(
                    start)} --> {format_timestamp(end)}\n{text}\n\n"
            )
    return srt_path


def transcribe_audio_to_words(audio_path: str, output_dir: str) -> str:
    """
    将音频文件转录成单词级别的 SRT 字幕文件
    :param audio_path: 音频文件路径
    :param output_path: 生成的 .srt 文件的目录
    :return: 生成的 .srt 文件路径
    """

    result = model.transcribe(audio_path, word_timestamps=True)
    srt_path = os.path.join(output_dir, f"audio_words.srt")

    with open(srt_path, "w", encoding="utf-8") as f:
        word_index = 1
        current_sentence = []
        prev_was_sentence_end = True  # 初始为句子开头

        for segment in result["segments"]:
            words = segment.get("words", [])
            for word_obj in words:
                word = word_obj["word"].strip()
                start = word_obj["start"]
                end = word_obj["end"]

                # 处理标点符号：附加到前一个单词
                if word in [".", ",", "!", "?", ";", ":"] and current_sentence:
                    current_sentence[-1] += word
                    continue

                # 处理"I"作为"我"时的大写
                if word.lower() == "i" and len(word) == 1:
                    word = "I"

                # 处理句子首字母大写（包括独立的"I"）
                if prev_was_sentence_end or (
                    current_sentence and current_sentence[-1].endswith(
                        (".", "!", "?"))
                ):
                    word = word.capitalize()
                    prev_was_sentence_end = False

                # 写入SRT条目
                f.write(
                    f"{word_index}\n{format_timestamp(
                        start)} --> {format_timestamp(end)}\n{word}\n\n"
                )
                current_sentence.append(word)
                word_index += 1

                # 检测句子结束
                if word.endswith((".", "!", "?")):
                    prev_was_sentence_end = True
                    current_sentence = []

    return srt_path


def srt_to_json(srt_content: str) -> list:
    """
    将SRT格式的字幕内容转换为JSON格式

    参数:
        srt_content (str): SRT格式的字幕内容

    返回:
        list: 包含字幕信息的字典列表
    """
    subtitles = []
    # 将内容按空行分割成独立的字幕块
    srt_blocks = srt_content.strip().split("\n\n")

    for block in srt_blocks:
        # 将每个字幕块按行分割
        lines = block.strip().split("\n")

        if len(lines) >= 3:
            # 第一行是索引
            index = int(lines[0].strip())

            # 第二行是时间戳
            timestamp = lines[1].strip()

            # 剩余的行是字幕文本
            text = "\n".join(lines[2:]).strip()

            # 添加到字幕列表
            subtitles.append(
                {"index": index, "timestamp": timestamp, "text": text})

    return subtitles


def convert_srt_file(input_file: str, output_dir: str):
    """
    将SRT文件转换为JSON文件，并保存到指定目录

    参数:
        input_file (str): 输入的SRT文件路径
        output_dir (str): 输出的JSON文件存放目录
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        # 生成输出JSON文件路径
        output_file = os.path.join(output_dir, f"audio_words.json")

        # 读取SRT文件内容
        with open(input_file, "r", encoding="utf-8") as file:
            srt_content = file.read()

        # 转换为JSON格式
        subtitles = srt_to_json(srt_content)

        # 写入JSON文件
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(subtitles, file, ensure_ascii=False, indent=2)
        return output_file
    except Exception as e:
        logger.error(f"❌ 转换失败: {e}")
        raise e


def time_string_to_seconds(time_str: str) -> float:
    """
    将时间字符串转换为秒数。

    支持的时间格式包括：
        - "HH:MM:SS,mmm"
        - "MM:SS,mmm"
        - "SS.mmm"

    Args:
        time_str (str): 时间字符串，例如 "00:01:23.45" 或 "123.45"

    Returns:
        float: 对应的秒数
    """
    if not time_str:
        return 0.0
    time_str = time_str.replace(",", ".")
    parts = time_str.split(":")
    if len(parts) == 1:
        # 只有秒数
        return float(parts[0])
    elif len(parts) == 2:
        # 分和秒
        return float(parts[0]) * 60 + float(parts[1])
    else:
        # 时、分、秒
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


def format_time(sec: float) -> str:
    """
    将秒数格式化为 ASS 字幕支持的时间格式 H:MM:SS.cs（百分之一秒）

    示例输出：`0:13:45.30`

    Args:
        sec (float): 秒数

    Returns:
        str: 格式化后的时间字符串
    """
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - math.floor(sec)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def calculate_resolution_dependent_config(config: dict) -> dict:
    """
    动态计算基于视频高度的配置值（如字体大小、边距等）

    根据 config 中的百分比参数动态计算实际像素值，并设置最小限制。

    Args:
        config (dict): 包含基础配置参数的字典，需包含以下字段：
            - videoHeight (int): 视频高度
            - baseFontSizePercent (float): 基础字体大小占视频高度的百分比
            - highlightFontSizePercent (float): 高亮字体大小占视频高度的百分比
            - marginVPercent (float): 垂直边距占视频高度的百分比

    Returns:
        dict: 更新后的配置字典，新增以下字段：
            - fontSize (int)
            - highlightFontSize (int)
            - marginV (int)
    """
    config["fontSize"] = max(
        12, round(config["videoHeight"] *
                  (config["baseFontSizePercent"] / 100))
    )
    config["highlightFontSize"] = max(
        14, round(config["videoHeight"] *
                  (config["highlightFontSizePercent"] / 100))
    )
    config["marginV"] = max(
        10, round(config["videoHeight"] * (config["marginVPercent"] / 100))
    )
    return config


def create_ass_style_line(config: dict) -> str:
    """
    构建 ASS 字幕样式行（Style 行），用于 .ass 文件中的 [V4+ Styles] 部分

    Args:
        config (dict): 包含样式相关配置的字典，必须包含以下字段：
            - fontName (str): 字体名称
            - fontSize (int): 字号
            - fontColor (str): 主颜色（十六进制 RGB）
            - outlineColor (str): 描边颜色（十六进制 RGB）
            - backgroundColor (str): 背景颜色（十六进制 RGB）
            - bold (int): 是否加粗（0 或 1）
            - italic (int): 是否斜体（0 或 1）
            - underline (int): 是否下划线（0 或 1）
            - strikeout (int): 是否删除线（0 或 1）
            - scaleX (int): 水平缩放（百分比）
            - scaleY (int): 垂直缩放（百分比）
            - spacing (int): 字间距
            - angle (int): 字体角度
            - borderStyle (int): 边框样式
            - outline (int): 描边宽度
            - shadow (int): 阴影深度
            - alignment (int): 对齐方式
            - marginL (int): 左侧边距
            - marginR (int): 右侧边距
            - marginV (int): 底部边距
            - encoding (str): 编码方式

    Returns:
        str: 样式定义行（Style line）
    """
    style_line = (
        f"Style: Default,"
        f"{config['fontName']},"  # Fontname
        f"{config['fontSize']},"  # Fontsize
        f"&H{config['fontColor']}&,"  # PrimaryColour
        f"&H{config['outlineColor']}&,"  # SecondaryColour
        f"&H{config['outlineColor']}&,"  # OutlineColour
        f"&H{config['backgroundColor']}&,"  # BackColour
        f"{config['bold']},"  # Bold
        f"{config['italic']},"  # Italic
        f"{config['underline']},"  # Underline
        f"{config['strikeout']},"  # StrikeOut
        f"{config['scaleX']},"  # ScaleX
        f"{config['scaleY']},"  # ScaleY
        f"{config['spacing']},"  # Spacing
        f"{config['angle']},"  # Angle
        f"{config['borderStyle']},"  # BorderStyle
        f"{config['outline']},"  # Outline
        f"{config['shadow']},"  # Shadow
        f"{config['alignment']},"  # Alignment
        f"{config['marginL']},"  # MarginL
        f"{config['marginR']},"  # MarginR
        f"{config['marginV']},"  # MarginV
        "1"  # Encoding
    )
    return style_line


def create_subtitle_text(
    word_group: list | dict, highlight_index: int, config: dict
) -> str:
    """
    创建带高亮效果的字幕文本，用于一个单词组中突出当前播放的单词

    Args:
        word_group (list of dict): 当前单词组，包含多个单词对象
        highlight_index (int): 需要高亮的单词索引
        config (dict): 包含以下字段：
            - highlightFontSize (int): 高亮时使用的字体大小
            - highlightColor (str): 高亮颜色（十六进制）

    Returns:
        str: 格式化的字幕文本
    """
    result = []
    for i, word in enumerate(word_group):
        if i == highlight_index:
            result.append(
                f"{{\\fs{config['highlightFontSize']}\\c&H{
                    config['highlightColor']}&}}"
                f"{word['word'].strip()}{{\\r}}"
            )
        else:
            result.append(word["word"].strip())
    return " ".join(result)


def create_sentence_aware_groups(
    words: list | dict, words_per_group: int = 3
) -> list[list[dict]]:
    """
    按句子边界或最大单词数量对单词进行分组

    如果遇到句尾标点（如 . ! ?），则强制结束当前组。

    Args:
        words (list of dict): 单词列表，每个元素包含 'word' 和 'start'/'end'
        words_per_group (int): 每组最多包含多少个单词

    Returns:
        list of list of dict: 分组后的单词列表
    """
    groups = []
    current_group = []

    for word in words:
        if not word.get("word"):
            continue
        current_group.append(word)

        is_end_of_sentence = any(word["word"].endswith(p)
                                 for p in [".", "!", "?"])
        is_max_words = len(current_group) >= words_per_group

        if is_max_words or is_end_of_sentence:
            groups.append(current_group)
            current_group = []

    if current_group:
        groups.append(current_group)

    return groups


def generate_ass_file(json_data: list[dict], output_path: str, config: dict) -> str:
    """
    主函数：根据 JSON 数据生成 `.ass` 字幕文件

    输入是包含单词及时间戳的 JSON 数据，输出为符合 ASS 格式的字幕文件。

    Args:
        json_data (list of dict): 字幕数据列表，格式如下：
            [
                {"text": "Hello", "timestamp": "0 --> 1.5"},
                ...
            ]
        output_path (str): 输出的 `.ass` 文件路径
        config (dict): 包含字幕样式和行为控制的配置字典

    Returns:
        str: 生成的 `.ass` 文件路径
    """

    # 计算依赖分辨率的配置
    config = calculate_resolution_dependent_config(config)

    # 解析字幕数据
    all_words = [
        {
            "word": item["text"],
            "start": time_string_to_seconds(item["timestamp"].split(" --> ")[0]),
            "end": time_string_to_seconds(item["timestamp"].split(" --> ")[1]),
        }
        for item in json_data
    ]

    # 构建 ASS 文件内容
    ass_content = "[Script Info]\n"
    ass_content += "Title: Word Timestamp Subtitles\n"
    ass_content += "ScriptType: v4.00+\n"
    ass_content += f"PlayResX: {config['videoWidth']}\n"
    ass_content += f"PlayResY: {config['videoHeight']}\n\n"

    ass_content += "[V4+ Styles]\n"
    ass_content += "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    ass_content += "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
    ass_content += "Alignment, MarginL, MarginR, MarginV, Encoding\n"
    ass_content += create_ass_style_line(config) + "\n\n"

    ass_content += "[Events]\n"
    ass_content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

    # 按每组最多 `wordsToShow` 单词进行分组
    word_groups = create_sentence_aware_groups(
        all_words, config["wordsToShow"])

    # 生成每个单词对应的字幕条目
    dialogue_lines = []

    for group_index, group in enumerate(word_groups):
        for word_index, word in enumerate(group):
            start = word["start"]
            end = word["end"]
            subtitle_text = create_subtitle_text(group, word_index, config)

            dialogue_lines.append(
                {
                    "start": start,
                    "end": end,
                    "formattedStart": format_time(start),
                    "formattedEnd": format_time(end),
                    "text": subtitle_text,
                }
            )

    # 填补同一组内字幕间的空隙
    for i in range(len(dialogue_lines) - 1):
        curr = dialogue_lines[i]
        next_line = dialogue_lines[i + 1]
        if (
            next_line["start"] - curr["end"] > 0
            and next_line["start"] - curr["end"] <= config["maxGapTimeMs"] / 1000
        ):
            curr["end"] = next_line["start"]
            curr["formattedEnd"] = format_time(curr["end"])

    # 写入 Events 部分
    for line in dialogue_lines:
        ass_content += f"Dialogue: 0,{line['formattedStart']},{
            line['formattedEnd']},Default,,0,0,0,,{line['text']}\n"

    # 保存到文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"✅ 已成功生成 ASS 字幕文件：{output_path}")
    return output_path


def generate_ass_with_default_config(video_path: str, subtitle_data_path: str, output_dir: str):
    """
    根据视频分辨率，生成默认的ASS字幕文件
    Args:
        video_path: 视频文件路径
        subtitle_data_path: 字幕数据文件路径(.json)
        output_dir: 输出的ASS字幕文件路径的文件夹
    Returns:
        str: 生成的ASS字幕文件路径
    """
    resolution = get_video_resolution(video_path)
    config = {
        "wordsToShow": 3,
        "fontName": "Arial",
        "baseFontSizePercent": 4.5,
        "fontColor": "FFFFFF",
        "outlineColor": "000000",
        "backgroundColor": "000000",
        "highlightFontSizePercent": 6.0,
        "highlightColor": "00FFFF",
        "bold": 0,
        "italic": 0,
        "underline": 0,
        "strikeout": 0,
        "scaleX": 100,
        "scaleY": 100,
        "spacing": 0,
        "angle": 0,
        "borderStyle": 1,
        "outline": 2,
        "shadow": 1,
        "alignment": 2,
        "marginL": 10,
        "marginR": 10,
        "marginVPercent": 4.5,
        "videoWidth": resolution["width"],
        "videoHeight": resolution["height"],
        "maxGapTimeMs": 2000,
        "outputFileName": "word_timestamps.ass",
    }

    # 加载 JSON 字幕数据
    with open(subtitle_data_path, "r", encoding="utf-8") as f:
        subtitle_data = json.load(f)
    output_path = os.path.join(output_dir, f"audio_words.ass")
    generate_ass_file(subtitle_data, output_path, config)
    return output_path
