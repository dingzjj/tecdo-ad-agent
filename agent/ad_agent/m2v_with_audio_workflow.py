from langchain_core.runnables import RunnableConfig
import asyncio
from agent.third_part.video_effects import VideoTransitionType
from enum import Enum
from agent.utils import create_dir
import shutil
from agent.utils import get_video_duration
from agent.third_part.i2v import i2v_strategy_chain
from typing import List
from agent.utils import add_subtitles_with_ffmpeg_and_openai_whisper
import uuid
from agent.third_part.ffmpeg import merge_video_audio
from agent.ad_agent.utils import get_audio_duration
from agent.third_part.elevenlabs import text_to_speech_with_elevenlabs
from agent.utils import get_url_data
from agent.ad_agent.prompt import CREATE_AUDIO_TEXT_SYSTEM_PROMPT_en, CREATE_AUDIO_TEXT_HUMAN_PROMPT_en
from agent.third_part.moviepy_apply import concatenate_videos_from_urls
from config import conf
from config import logger
import json
import os
import mimetypes
from agent.llm import get_gemini_multimodal_model
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from agent.ad_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en
# v1表示纯视频，v2表示视频+音频，v3表示视频+字幕+音频,v4添加背景音乐
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "m2v_agent"


class VideoFragment(BaseModel):
    # 输入
    id: str = Field(default="", description="视频片段id")
    video_index: int = Field(description="视频索引")
    model_image: str = Field(default="", description="模特图片")
    model_image_info: str = Field(default="", description="模特图片信息")
    action_type: str = Field(default="model_show",
                             description="视频类型(model_show, model_walk)")
    i2v_strategy: str = Field(default="keling", description="i2v策略")

    # 以下是可以改变的地方
    video_positive_prompt: str = Field(default="", description="视频正向prompt")
    video_negative_prompt: str = Field(default="", description="视频负向prompt")
    video_script: str = Field(default="", description="视频脚本(即音频文案)")
    video_duration: float = Field(default=5.0, description="视频时长")
    # 以下都是结果
    audio_url: str = Field(default="", description="音频path(in local)")
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")

    def __str__(self):
        return f"视频片段id: {self.id}, 模特图片: {self.model_image}, 视频类型: {self.action_type}, i2v策略: {self.i2v_strategy}, 视频正向prompt: {self.video_positive_prompt}, 视频负向prompt: {self.video_negative_prompt}, 视频脚本: {self.video_script}, 视频时长: {self.video_duration}, 视频path(in local): {self.video_url_v3}"


class OutputVideo(BaseModel):
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")
    subtitle_text: dict = Field(default={}, description="字幕文案")


class GenerateVideoState(BaseModel):
    # 以下是输入
    id: str = Field(description="工作流id")
    product: str = Field(description="商品名称")
    product_info: str = Field(description="商品信息")
    model_images: list = Field(description="模特图片（带商品）")
    i2v_strategy: str = Field(default="keling", description="i2v策略")
    video_output_path: str = Field(description="视频输出path")
    video_fragment_duration: int = Field(default=5, description="视频片段时长")
    transition_effect: list[VideoTransitionType] = Field(
        default=[], description="转场效果")  # concatenate,dissolve
    resolution: dict = Field(
        default={}, description="视频分辨率")
    # 中间状态
    is_audio_too_long: bool = False
    # 以下是输出
    video_fragments: list[VideoFragment] = []
    output_video: OutputVideo = OutputVideo()

    def get_real_video_url_v1(self):
        return os.path.join(self.video_output_path, self.output_video.video_url_v1)

    def get_real_video_url_v2(self):
        return os.path.join(self.video_output_path, self.output_video.video_url_v2)

    def get_real_video_url_v3(self):
        return os.path.join(self.video_output_path,  self.output_video.video_url_v3)

    def get_real_url(self, path: str):
        return os.path.join(self.video_output_path, path)


class GenerateVideoStateJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


async def start(state: GenerateVideoState, config):
    """
    将模特图片拷贝到文件夹下
    """
    os.makedirs(os.path.join(state.video_output_path), exist_ok=True)

    # 将模特图片拷贝到文件夹下
    model_image_dir = []
    for i, model_image in enumerate(state.model_images):
        model_image_name = f"model_image_{i}.png"
        shutil.copy(model_image, os.path.join(
            state.video_output_path, model_image_name))
        model_image_dir.append(model_image_name)
    return {"model_images": model_image_dir}


async def generate_video_fragments(state: GenerateVideoState, config):
    """
    初始化视频片段
    """
    result_dir = state.video_output_path
    auto_id = 1
    for i, model_image in enumerate(state.model_images):
        video_fragment = VideoFragment(id=str(auto_id), video_index=auto_id,
                                       model_image=model_image, video_duration=state.video_fragment_duration,
                                       action_type="model_show", i2v_strategy=state.i2v_strategy)
        auto_id += 1
        # 创建视频片段目录
        os.makedirs(os.path.join(result_dir, video_fragment.id), exist_ok=True)
        state.video_fragments.append(video_fragment)

        video_fragment = VideoFragment(id=str(auto_id), video_index=auto_id,
                                       model_image=model_image, video_duration=state.video_fragment_duration,
                                       action_type="model_walk", i2v_strategy=state.i2v_strategy)
        auto_id += 1
        # 创建视频片段目录
        os.makedirs(os.path.join(
            result_dir, video_fragment.id), exist_ok=True)
        state.video_fragments.append(video_fragment)
    return {"video_fragments": state.video_fragments}


async def generate_video_script(state: GenerateVideoState, config):
    """
        使用gemini flash 对图片进行分析 + 商品信息  生成 展示商品的prompts (两步法)
    """
    # video_scripts = []
    # 对每个片段生成脚本

    for i, video_fragment in enumerate(state.video_fragments):
        real_image_path = state.get_real_url(video_fragment.model_image)

        with open(real_image_path, "rb") as file:
            image_data = file.read()

        # 根据文件后缀获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(real_image_path)
        if mime_type is None:
            # 如果无法猜测，默认为 image/jpeg
            mime_type = "image/jpeg"

        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
            response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=state.product),
                Part.from_data(image_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        model_image_info = content["pictorial information"]
        video_fragment.model_image_info = model_image_info
        # video_script = chat_with_gemini_in_vertexai(CREATE_VIDEO_PROMPT_SYSTEM_PROMPT_en.format(duration=state.video_duration, video_content_limit=CREATE_VIDEO_PROMPT_LIMIT_ABOUT_MOVEMENT_en),
        #  CREATE_VIDEO_PROMPT_HUMAN_PROMPT_en.format( model_image_info=reconstruct_model_image_info(model_image_info), product=state.product, duration=state.video_duration))

    return {"video_fragments": state.video_fragments}


async def generate_video(state: GenerateVideoState, config):
    """
    根据脚本与图片生成视频
    """
    result_dir = state.video_output_path

    async def process_video_fragment(video_fragment: VideoFragment):
        """处理单个视频片段的异步函数"""
        real_image_path = state.get_real_url(video_fragment.model_image)
        video_positive_prompt, video_negative_prompt, video_url = await i2v_strategy_chain.execute_chain(
            product=state.product, product_info=state.product_info, img_path=real_image_path,
            img_info=video_fragment.model_image_info, duration=int(
                state.video_fragment_duration),
            resolution={}, action_type=video_fragment.action_type, i2v_strategy=state.i2v_strategy)
        video_fragment.video_positive_prompt = video_positive_prompt
        video_fragment.video_negative_prompt = video_negative_prompt
        #  假如当前有文件则跳过
        video_url_v1 = os.path.join(video_fragment.id, "video_url_v1.mp4")
        # 直到video_number对应的文件不存在
        video_data = get_url_data(video_url)
        with open(os.path.join(result_dir, video_url_v1), "wb") as f:
            f.write(video_data)
        video_fragment.video_url_v1 = video_url_v1
        # 获取视频时长
        video_duration = get_video_duration(
            state.get_real_url(video_url_v1))
        video_fragment.video_duration = int(video_duration)
        return video_fragment

    # 并发执行所有视频片段处理任务
    tasks = [process_video_fragment(video_fragment)
             for video_fragment in state.video_fragments]
    await asyncio.gather(*tasks)

    return {"video_fragments": state.video_fragments}


async def generate_audio_text(state: GenerateVideoState, config):
    """
    根据商品信息，模特图片（图片信息），视频时长，语速(限制字数)，生成 字幕文案 + 音频，此处需要根据音频效果对文案进行不断调整
    """
    # 每个片段一段话（视频时长确定）

    # 假如添加开头数字人视频
    CREATE_AUDIO_TEXT_RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {},
        "required": []
    }
    fragment_info = ""
    if state.is_audio_too_long:
        word_min_count = int((state.video_fragment_duration-2)*2)
        word_max_count = int((state.video_fragment_duration-2)*3)  # 6-9
    else:
        word_min_count = int((state.video_fragment_duration-2)*3)
        word_max_count = int((state.video_fragment_duration-2)*4)  # 9-12
    state.is_audio_too_long = False

    for i, video_fragment in enumerate(state.video_fragments):
        fragment_info += f"( fragment{i}:{video_fragment.model_image_info})\n"
        CREATE_AUDIO_TEXT_RESPONSE_SCHEMA["properties"][f"fragment{i}"] = {
            "type": "string", "description": f"The video script for the {i}th segment"}
        CREATE_AUDIO_TEXT_RESPONSE_SCHEMA["required"].append(
            f"fragment{i}")
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=CREATE_AUDIO_TEXT_SYSTEM_PROMPT_en.format(
            word_min_count=word_min_count, word_max_count=word_max_count),
        response_schema=CREATE_AUDIO_TEXT_RESPONSE_SCHEMA)

    response = gemini_generative_model.generate_content(
        [
            CREATE_AUDIO_TEXT_HUMAN_PROMPT_en.format(
                product=state.product, fragment_info=fragment_info),
        ]
    )
    content = json.loads(response.candidates[0].content.parts[0].text)
    state.output_video.subtitle_text = content
    for i, video_fragment in enumerate(state.video_fragments):
        if video_fragment.video_index == 0:
            video_fragment.video_script = content["begin"]
        else:
            video_fragment.video_script = content[f"fragment{i}"]
    return {"video_fragments": state.video_fragments, "output_video": state.output_video,
            "is_audio_too_long": state.is_audio_too_long}


async def generate_audio(state: GenerateVideoState, config):
    """
    根据字幕文案，生成音频
    """
    try:
        result_dir = state.video_output_path
        for i, video_fragment in enumerate(state.video_fragments):
            audio_file_path = os.path.join(video_fragment.id, "audio.mp3")

            video_url_v2 = os.path.join(video_fragment.id, "video_url_v2.mp4")
            audio_speed = 1.0

            text_to_speech_with_elevenlabs(
                conf.get("elevenlabs_api_key"), video_fragment.video_script, state.get_real_url(audio_file_path), "Laura", audio_speed)
            video_fragment.audio_url = audio_file_path
            # 音频时长必须小于视频时长，否则重新生成字幕文案
            audio_duration = get_audio_duration(
                state.get_real_url(audio_file_path))
            while audio_duration > video_fragment.video_duration:
                # 音频时长必须小于视频时长，否则重新生成字幕文案
                # 方法一：调口音速度
                # 方法二：调字幕 TODO 口音速度在0.7-1.2之间，1.2之后超过则需要重新生成字幕文案
                audio_speed += 0.05
                if audio_speed > 1.2:
                    state.is_audio_too_long = True
                    break
                text_to_speech_with_elevenlabs(conf.get(
                    "elevenlabs_api_key"), video_fragment.video_script, state.get_real_url(audio_file_path), "Laura", audio_speed)
                audio_duration = get_audio_duration(
                    state.get_real_url(audio_file_path))

            merge_video_audio(state.get_real_url(video_fragment.video_url_v1), state.get_real_url(audio_file_path),
                              state.get_real_url(video_url_v2), 1, None, None)
            video_fragment.video_url_v2 = video_url_v2
        return {"video_fragments": state.video_fragments, "is_audio_too_long": state.is_audio_too_long}
    except Exception as e:
        # 采取方案二：调字幕 TODO
        logger.error(f"生成音频失败: {e}")
        raise e


async def route_if_audio_too_long(state: GenerateVideoState, config):
    """
    如果音频时长超过了视频时长，则重新生成文案
    """
    return state.is_audio_too_long


async def add_subtitles(state: GenerateVideoState, config):
    """
    为每个视频片段添加字幕
    """
    result_dir = state.video_output_path
    for video_fragment in state.video_fragments:
        video_url_v3 = os.path.join(video_fragment.id, "video_url_v3.mp4")
        output_dir = os.path.join(result_dir, video_fragment.id)
        add_subtitles_with_ffmpeg_and_openai_whisper(
            state.get_real_url(video_fragment.audio_url), state.get_real_url(video_fragment.video_url_v2), output_dir, state.get_real_url(video_url_v3), "Montserrat-Italic-VariableFont_wght")
        video_fragment.video_url_v3 = video_url_v3
    return {"video_fragments": state.video_fragments}


async def evaluate_video_fragments(state: GenerateVideoState, config):
    """
    评估视频片段
    """
    # 1.评估点1：Motion Smoothness
    pass


async def video_stitching(state: GenerateVideoState, config):
    """
    视频拼接
    """
    result_dir = state.video_output_path
    video_v1_list = []
    video_v2_list = []
    video_v3_list = []
    for video_fragment in state.video_fragments:
        video_v1_list.append(state.get_real_url(video_fragment.video_url_v1))
        video_v2_list.append(state.get_real_url(video_fragment.video_url_v2))
        video_v3_list.append(state.get_real_url(video_fragment.video_url_v3))
    video_url_v1 = "video_url_v1.mp4"
    video_url_v2 = "video_url_v2.mp4"
    video_url_v3 = "video_url_v3.mp4"
    state.output_video.video_url_v1 = concatenate_videos_from_urls(
        video_v1_list, output_path=state.get_real_url(video_url_v1))
    state.output_video.video_url_v2 = concatenate_videos_from_urls(
        video_v2_list, output_path=state.get_real_url(video_url_v2))
    state.output_video.video_url_v3 = concatenate_videos_from_urls(
        video_v3_list, output_path=state.get_real_url(video_url_v3))
    return {"output_video": state.output_video}


async def add_background_music(state: GenerateVideoState, config):
    """
    添加背景音乐
    """
    pass


async def save_state(state: GenerateVideoState, config):
    """
    保存状态
    """
    result_dir = state.video_output_path
    with open(os.path.join(result_dir, "state.json"), "w") as f:
        json.dump(state.model_dump(), f, cls=GenerateVideoStateJSONEncoder)

# 工作流节点配置
WORKFLOW_NODES = {
    "start": start,
    "generate_video_fragments": generate_video_fragments,
    "generate_video_script": generate_video_script,
    "generate_video": generate_video,
    "generate_audio_text": generate_audio_text,
    "generate_audio": generate_audio,
    "add_subtitles": add_subtitles,
    "evaluate_video_fragments": evaluate_video_fragments,
    "video_stitching": video_stitching,
    "add_background_music": add_background_music,
    "save_state": save_state
}


def get_m2v_with_audio_workflow():
    """
    获取应用
    """
    graph = StateGraph(GenerateVideoState)

    # 添加所有节点
    for node_name, node_method in WORKFLOW_NODES.items():
        graph.add_node(node_name, node_method)

    # 添加边
    graph.add_edge(START, "start")
    graph.add_edge("start", "generate_video_fragments")
    graph.add_edge("generate_video_fragments", "generate_video_script")
    graph.add_edge("generate_video_script", "generate_video")
    graph.add_edge("generate_video", "generate_audio_text")
    graph.add_edge("generate_audio_text",
                   "generate_audio")
    graph.add_conditional_edges(
        "generate_audio", route_if_audio_too_long, {
            True: "generate_audio_text",
            False: "add_subtitles"
        })
    graph.add_edge("add_subtitles", "evaluate_video_fragments")
    graph.add_edge("evaluate_video_fragments", "video_stitching")
    graph.add_edge("video_stitching", "add_background_music")
    graph.add_edge("add_background_music", "save_state")
    graph.add_edge("save_state", END)

    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def ainvoke_m2v_with_audio_workflow(user_id: str, id: str, product: str, product_info: str, model_images: list[str], video_fragment_duration: int, video_output_path: str):
    """
    调用m2v_workflow工作流
    Args:
        product: 商品名称
        product_info: 商品信息
        model_images: 模特图片
        video_fragment_duration: 视频片段时长
        video_output_path: 视频输出dir(就是工作流目录)
    """

    os.makedirs(video_output_path, exist_ok=True)
    app = get_m2v_with_audio_workflow()
    configuration: RunnableConfig = {"configurable": {
        "thread_id": f"{user_id}_{id}"}}
    # result_dir就是工作流目录
    result: GenerateVideoState = await app.ainvoke({"id": id, "product": product, "product_info": product_info, "model_images": model_images,
                                                    "video_fragment_duration": video_fragment_duration, "video_output_path": video_output_path},
                                                   config=configuration)
    result: GenerateVideoState = GenerateVideoState.model_validate(result)

    return result
