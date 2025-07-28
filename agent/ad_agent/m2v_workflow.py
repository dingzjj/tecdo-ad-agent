from agent.utils import get_time_id
from agent.third_part.i2v import KELING_STRATEGY
from agent.mini_agent import AnalyseImageAgent
from agent.ad_agent.utils import copy_dir_to_dir
from enum import Enum
from agent.utils import create_dir
from agent.third_part.video_effects import video_transitions
from agent.third_part.video_effects import VideoTransitionType
import shutil
from agent.utils import get_video_duration
from agent.third_part.i2v import i2v_strategy_chain
from typing import List
import uuid
from agent.utils import get_url_data
from agent.utils import temp_dir
from langchain_core.runnables import RunnableConfig
from config import conf
from config import logger
import json
import os
import mimetypes
import asyncio
from agent.llm import get_gemini_multimodal_model
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
# v1表示纯视频
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "m2v_agent"


class VideoFragment(BaseModel):
    # 输入
    id: str = Field(default="", description="视频片段id")
    video_index: int = Field(description="视频索引,从1开始")
    model_image: str = Field(default="", description="模特图片")
    model_image_info: str = Field(default="", description="模特图片信息")
    action_type: str = Field(default="model_show",
                             description="视频类型(model_show, model_walk)")
    i2v_strategy: str = Field(default="keling", description="i2v策略")
    # 以下是可以改变的地方
    video_positive_prompt: str = Field(default="", description="视频正向prompt")
    video_negative_prompt: str = Field(default="", description="视频负向prompt")
    video_script: str = Field(default="", description="视频脚本")
    video_duration: float = Field(default=5.0, description="视频时长")
    # 以下都是结果(弄成相对路径)
    video_url_v1: str = Field(default="", description="视频path(in local)")

    def __str__(self):
        return f"视频片段id: {self.id}, 模特图片: {self.model_image}, 视频类型: {self.action_type}, i2v策略: {self.i2v_strategy}, 视频正向prompt: {self.video_positive_prompt}, 视频负向prompt: {self.video_negative_prompt}, 视频脚本: {self.video_script}, 视频时长: {self.video_duration}, 视频path(in local): {self.video_url_v1}"


class OutputVideo(BaseModel):
    # 使用相对路径
    video_url_v1: str = Field(default="", description="视频path(in local)")
    transition_effect: list[VideoTransitionType] = Field(
        default=[], description="转场效果")  # concatenate,dissolve


class GenerateVideoState(BaseModel):
    # 路径全部使用相对路径
    # 使用时已经创建了工作流目录
    id: str = Field(description="工作流id")
    product: str = Field(description="商品名称")
    product_info: str = Field(description="商品信息")
    model_images: list = Field(description="模特图片（带商品）")

    video_output_path: str = Field(description="视频输出path，即工作流目录")
    # 以下是用户输入
    video_positive_prompt: str = Field(default="", description="视频正向prompt")
    video_negative_prompt: str = Field(default="", description="视频负向prompt")
    video_fragment_duration: int = Field(default=5, description="视频片段时长")
    i2v_strategy: str = Field(default="keling", description="i2v策略")

    transition_effect: list[VideoTransitionType] = Field(
        default=[], description="转场效果")  # concatenate,dissolve

    # 以下是输出
    video_fragments: list[VideoFragment] = []
    output_video: OutputVideo = OutputVideo()

    def get_real_video_url_v1(self):
        # 拷贝的是假的只能临时调用
        return os.path.join(self.video_output_path, self.output_video.video_url_v1)

    def get_real_url(self, path: str):
        return os.path.join(self.video_output_path, path)

    def _copy(self, old_dir, new_dir: str, id: str):
        """
        拷贝：涉及文件的将文件相关的也拷贝到dir下
        Args:
            old_dir: 原来的目录路径(总文件夹)
            new_dir: 目标目录路径(总文件夹)
            id: 新的工作流id
        """
        import shutil
        import os
        new_state_dir = os.path.join(new_dir, id)
        # 确保目标目录存在
        os.makedirs(new_state_dir, exist_ok=True)

        # 创建新的状态对象(先进行深拷贝)
        new_state = self.model_copy(deep=True)
        new_state.id = id
        # 在将涉及文件的进行转移
        for video_fragment in new_state.video_fragments:
            # 创建文件夹
            os.makedirs(os.path.join(new_state_dir,
                        video_fragment.id), exist_ok=True)
            # 原来的路径
            old_video_url_v1 = os.path.join(
                old_dir, self.id, video_fragment.video_url_v1)
            # 新的路径
            new_video_url_v1 = os.path.join(
                new_state_dir, video_fragment.id, "video_url_v1.mp4")
            # 转移
            shutil.copy(old_video_url_v1, new_video_url_v1)
        return new_state


class GenerateVideoStateJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


async def route_start(state: GenerateVideoState, config):
    """
    路由
    """
    if state.video_positive_prompt == "":
        return "start_without_prompt"
    else:
        return "start_with_prompt"


async def start_without_prompt(state: GenerateVideoState, config):
    """
    没提供prompt,来生成视频片段
    """
    pass
    # 1.没有提供的全使用默认值来初始化
    if state.i2v_strategy == "":
        state.i2v_strategy = "keling"
    if state.video_fragment_duration == 0:
        state.video_fragment_duration = 5
    os.makedirs(os.path.join(state.video_output_path), exist_ok=True)

    # 将模特图片拷贝到文件夹下
    model_image_dir = []
    for i, model_image in enumerate(state.model_images):
        model_image_name = f"model_image_{i}.png"
        shutil.copy(model_image, os.path.join(
            state.video_output_path, model_image_name))
        model_image_dir.append(model_image_name)

    return {"i2v_strategy": state.i2v_strategy, "video_fragment_duration": state.video_fragment_duration, "model_images": model_image_dir}


async def start_with_prompt(state: GenerateVideoState, config):
    """
    提供prompt，来生成视频片段
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


async def generate_video_with_prompt(state: GenerateVideoState, config):
    """
    根据prompt来生成视频片段
    """
    # 1. 生成视频片段
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
    # 2.生成视频

    async def process_video_fragment(video_fragment: VideoFragment):
        """处理单个视频片段的异步函数"""
        real_image_path = state.get_real_url(video_fragment.model_image)
        video_url = await i2v_strategy_chain.execute_chain_with_prompt(
            img_path=real_image_path, positive_prompt=state.video_positive_prompt, negative_prompt=state.video_negative_prompt, duration=int(
                state.video_fragment_duration), i2v_strategy=video_fragment.i2v_strategy)
        video_data = get_url_data(video_url)
        video_fragment_path = os.path.join(
            video_fragment.id, "video_url_v1.mp4")
        with open(state.get_real_url(video_fragment_path), "wb") as f:
            f.write(video_data)
        video_fragment.video_url_v1 = video_fragment_path
        return video_fragment
    # 并发执行所有视频片段处理任务
    tasks = [process_video_fragment(video_fragment)
             for video_fragment in state.video_fragments]
    await asyncio.gather(*tasks)
    return {"video_fragments": state.video_fragments}


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
        目前是生成图片信息
    """
    # video_scripts = []
    # 对每个片段生成脚本

    for i, video_fragment in enumerate(state.video_fragments):
        real_image_path = state.get_real_url(video_fragment.model_image)
        video_fragment.model_image_info = AnalyseImageAgent().analyse_image(
            product=state.product, image_path=real_image_path)
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
        video_url_v1 = os.path.join(
            result_dir, video_fragment.id, "video_url_v1.mp4")
        # 直到video_number对应的文件不存在
        video_data = get_url_data(video_url)
        with open(video_url_v1, "wb") as f:
            f.write(video_data)
        video_fragment.video_url_v1 = os.path.join(
            video_fragment.id, "video_url_v1.mp4")
        # 获取视频时长
        video_duration = get_video_duration(video_url_v1)
        video_fragment.video_duration = int(video_duration)
        return video_fragment

    # 并发执行所有视频片段处理任务
    tasks = [process_video_fragment(video_fragment)
             for video_fragment in state.video_fragments]
    await asyncio.gather(*tasks)

    return {"video_fragments": state.video_fragments}


async def evaluate_video_fragments(state: GenerateVideoState, config):
    """
    评估视频片段
    """
    # 1.评估点1：Motion Smoothness
    pass


async def add_transition_effect(state: GenerateVideoState, config):
    """
    添加转场效果,两两之间确定转场效果
    目前默认使用dissolve(叠化)
    """
    transition_effect = []
    for i in range(len(state.video_fragments)-1):
        transition_effect.append(VideoTransitionType.DISSOLVE)
    state.output_video.transition_effect = transition_effect
    return {"transition_effect": transition_effect, "output_video": state.output_video}


async def video_stitching(state: GenerateVideoState, config):
    """
    视频拼接,添加转场效果
    在temp_dir下创建一个文件夹，用于存储拼接后的临时视频，之后将这个文件夹删除
    """
    result_dir = state.video_output_path
    # 根据特效来进行合并
    with temp_dir(dir_path=conf.get_path("temp_dir"), name=str(uuid.uuid4())) as temp_concatenate_dir:
        now_batch_video_list: list = [None]*len(state.video_fragments)
        now_video_effect_index = 0

        for i, video_fragment in enumerate(state.video_fragments):
            # 根据index来添加到list中的指定为止
            now_batch_video_list[video_fragment.video_index -
                                 1] = os.path.join(result_dir, video_fragment.video_url_v1)

        while len(now_batch_video_list) > 1:
            output_path = os.path.join(
                temp_concatenate_dir, f"concat_{now_video_effect_index}_{now_video_effect_index+1}.mp4")
            if now_video_effect_index >= len(state.output_video.transition_effect):
                now_video_effect = VideoTransitionType.CONCATENATE
            else:
                now_video_effect = state.output_video.transition_effect[now_video_effect_index]

            video_transitions(
                now_batch_video_list[0], now_batch_video_list[1], output_path, now_video_effect)
            now_batch_video_list.pop(1)
            now_batch_video_list[0] = output_path
            now_video_effect_index += 1

        video_url_v1 = os.path.join(result_dir, "video_url_v1.mp4")
        # 将now_batch_video_list中的唯一一个文件copy到
        shutil.copy(now_batch_video_list[-1], video_url_v1)
        # 状态更新
        state.output_video.video_url_v1 = "video_url_v1.mp4"
        state.output_video.transition_effect = state.transition_effect
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

WORKFLOW_NODES = {
    "generate_video_fragments": generate_video_fragments,
    "generate_video_script": generate_video_script,
    "generate_video": generate_video,
    "add_transition_effect": add_transition_effect,
    "video_stitching": video_stitching,
    "add_background_music": add_background_music,
    "save_state": save_state,
    "start_without_prompt": start_without_prompt,
    "start_with_prompt": start_with_prompt,
    "generate_video_with_prompt": generate_video_with_prompt,
}


def get_m2v_workflow():
    """
    获取应用
    """
    graph = StateGraph(GenerateVideoState)

    # 添加所有节点
    for node_name, node_method in WORKFLOW_NODES.items():
        graph.add_node(node_name, node_method)

    # 添加边

    graph.add_conditional_edges(START, route_start, {
        "start_without_prompt": "start_without_prompt",
        "start_with_prompt": "start_without_prompt"
    })

    # 有提示词部分
    graph.add_edge("start_with_prompt", "generate_video_with_prompt")
    graph.add_edge("generate_video_with_prompt", "add_transition_effect")
    graph.add_edge("add_transition_effect", "video_stitching")
    graph.add_edge("video_stitching", "add_background_music")
    graph.add_edge("add_background_music", "save_state")
    graph.add_edge("save_state", END)

    # 没提示词部分
    graph.add_edge("start_without_prompt", "generate_video_fragments")
    graph.add_edge("generate_video_fragments", "generate_video_script")
    graph.add_edge("generate_video_script", "generate_video")
    graph.add_edge("generate_video", "add_transition_effect")
    graph.add_edge("add_transition_effect", "video_stitching")
    graph.add_edge("video_stitching", "add_background_music")
    graph.add_edge("add_background_music", "save_state")
    graph.add_edge("save_state", END)
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def ainvoke_m2v_workflow(user_id: str, id: str, product: str, product_info: str, model_images: list, video_fragment_duration: int, video_output_path: str, positive_prompt: str, negative_prompt: str) -> GenerateVideoState:
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
    graph = get_m2v_workflow()
    configuration: RunnableConfig = {"configurable": {
        "thread_id": f"{user_id}_{id}"}}
    # result_dir就是工作流目录
    result: GenerateVideoState = await graph.ainvoke({"id": id, "product": product, "product_info": product_info, "model_images": model_images,
                                                      "video_fragment_duration": video_fragment_duration, "video_output_path": video_output_path, "video_positive_prompt": positive_prompt, "video_negative_prompt": negative_prompt},
                                                     config=configuration)
    result: GenerateVideoState = GenerateVideoState.model_validate(result)
    return result


async def generate_video_fragment_single_func(fragment_id, img_path, positive_prompt, negative_prompt, action_type, video_output_path):
    """
    生成单个视频
    video_output_path: 视频输出dir(就是生成视频的目录)
    """
    os.makedirs(video_output_path, exist_ok=True)
    # 将img_path拷贝到video_output_path
    img_new_path = "model_image.png"
    real_img_new_path = os.path.join(video_output_path, img_new_path)
    shutil.copy(img_path, real_img_new_path)
    video_fragment = VideoFragment(id=fragment_id, video_index=1,
                                   model_image=img_new_path, video_duration=5,
                                   action_type="model_show", i2v_strategy=KELING_STRATEGY)

    video_url_v1 = os.path.join(video_output_path, "video_url_v1.mp4")
    video_fragment.video_url_v1 = "video_url_v1.mp4"
    # 调用m2v_workflow工作流
    if positive_prompt != "":
        video_fragment.video_positive_prompt = positive_prompt
        video_fragment.video_negative_prompt = negative_prompt
        video_url = await i2v_strategy_chain.execute_chain_with_prompt(
            img_path=real_img_new_path, positive_prompt=positive_prompt, negative_prompt=negative_prompt, duration=int(5), i2v_strategy=KELING_STRATEGY)
        video_data = get_url_data(video_url)

        with open(os.path.join(video_output_path, "video_url_v1.mp4"), "wb") as f:
            f.write(video_data)

    else:
        if action_type == "":
            action_type = "model_show"
        video_fragment.action_type = action_type
        model_image_info = AnalyseImageAgent().analyse_image(
            product="clothes", image_path=real_img_new_path)
        video_positive_prompt, video_negative_prompt, video_url = await i2v_strategy_chain.execute_chain(
            product="clothes", product_info="clothes", img_path=real_img_new_path,
            img_info=model_image_info, duration=5, action_type=action_type)
        video_data = get_url_data(video_url)
        with open(os.path.join(video_output_path, "video_url_v1.mp4"), "wb") as f:
            f.write(video_data)
        video_fragment.video_positive_prompt = video_positive_prompt
        video_fragment.video_negative_prompt = video_negative_prompt

    # 将状态进行保存
    with open(os.path.join(video_output_path, "state.json"), "w") as f:
        json.dump(video_fragment.model_dump(), f, cls=json.JSONEncoder)
    return video_url_v1
    # 保存state.json


async def video_stitching_single_func(video_output_path: str, video_fragment_list: list[str]):
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
            now_video_effect = VideoTransitionType.DISSOLVE

            video_transitions(
                video_fragment_list[0], video_fragment_list[1], output_path, now_video_effect)
            video_fragment_list.pop(1)
            video_fragment_list[0] = output_path
            now_concatenate_index += 1

        video_url_v1 = os.path.join(video_output_path, "video_url_v1.mp4")
        # 将now_batch_video_list中的唯一一个文件copy到
        shutil.copy(video_fragment_list[-1], video_url_v1)
    return video_url_v1
