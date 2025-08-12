# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
from config import logger
from langchain_core.messages import SystemMessage
from agent.utils import is_image_file
from agent.third_part.multimodal_generation_model import model_factory
from pydantic import BaseModel, Field, root_validator
from agent.ad_agent.prompt import AD_AGENT_SYSTEM_PROMPT_cn
from langchain_core.messages import HumanMessage
from agent.ad_agent.prompt import AD_AGENT_HUMAN_PROMPT_cn
from agent.material_library import Material
from agent.material_library import MaterialLibrary
from agent.utils import get_time_id
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from agent.ad_agent.prompt import REACT_AGENT_SYSTEM_PROMPT_cn
from agent.llm import create_azure_llm
from agent.mini_agent import AnalyseImageAgent
from agent.ad_agent.m2v_workflow import VideoFragment
from agent.utils import get_url_data
from agent.third_part.i2v import i2v_strategy_chain
import uuid
from MediaShield.process import process_media
from agent.ad_agent.utils import get_absolute_path_from_user_dir
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import os
import asyncio

# first 创建用户文件夹
from pydantic import BaseModel
from pydantic import Field
from langchain_core.messages import BaseMessage
from config import conf

from agent.ad_agent.m2v_workflow import get_m2v_workflow
from agent.ad_agent.m2v_workflow import GenerateVideoState
from langchain_core.runnables import RunnableConfig
from agent.utils import create_dir
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "react_agent"

# 所有图片都在
start_hint = "ad agent"


class AdAgentState(BaseModel):
    # 输入
    user_id: str = Field(description="用户id")
    chat_history: list[BaseMessage] = Field(
        default=[], description="聊天历史,用于记录用户与agent的对话")
    chat_and_tool_history: list[BaseMessage] = Field(
        default=[], description="聊天和工具调用历史,用于记录用户与agent的对话和工具调用")
    material_library: MaterialLibrary = Field(
        default=None, description="素材库")

    @root_validator(pre=True)
    def set_material_library(cls, values):
        user_id = values.get('user_id')
        if user_id:
            material_library_dir = os.path.join(
                conf.get_path("material_library_dir"), user_id)
            os.makedirs(material_library_dir, exist_ok=True)
            values['material_library'] = MaterialLibrary(
                material_library_dir=material_library_dir)
        return values

# TODO 创作能力总结 -> 多图创作能力，多视频创作能力，文+图+视频混合创作能力
# TODO 根据用户选择的图片生成商品lora model，并使用该lora model进行创作
# TODO 多跳能力优化


class AdAgent:
    """
    广告agent
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state = AdAgentState(user_id=user_id)

    def invoke(self, message: str, overhead_information: dict = {}, chat_history: list[BaseMessage] = []):
        """
        调用agent
        :param message: 消息
        :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
        :return: 响应
        """

        react_agent = create_react_agent(
            prompt=SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(
                user_id=self.user_id, material_library=self.state.material_library.get_all_material_info())),
            model=create_azure_llm(),
            tools=[get_material_from_link, get_material_in_web, upload_material, pre_review_material, create_image_by_t2i, create_video_by_t2v,
                   create_video_by_i2v_wo_assign, create_video_by_i2v_with_assign, create_image_by_i2i_wo_assign, create_image_by_i2i_with_assign]
        )
        NOW_EPOCH_CHAT_HISTORY = chat_history.copy()
        NOW_EPOCH_CHAT_HISTORY.append(HumanMessage(
            content=AD_AGENT_HUMAN_PROMPT_cn.format(question=message, overhead_information=overhead_information, user_id=self.user_id)))
        result = react_agent.invoke({"messages": NOW_EPOCH_CHAT_HISTORY})
        return result


AdAgents: dict[str, AdAgent] = {}


@tool
def get_material_from_link(user_id: str, link: str):
    """
    根据链接获取素材
    :param link: 链接
    :return: 素材
    """
    if user_id not in AdAgents:
        raise ValueError(f"用户{user_id}不存在")
    result = asyncio.run(
        AdAgents[user_id].state.material_library.crawl_material_by_link(link))
    if result:
        return "素材获取成功，请在素材库中查看"
    else:
        return "素材获取失败，请检查链接是否有效"


@tool
def upload_material(user_id: str, overhead_information: dict):
    """
    上传素材
    :param user_id: 用户id
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    :return: 素材
    """
    if user_id not in AdAgents:
        raise ValueError(f"用户{user_id}不存在")
    for key, value in overhead_information.items():
        if key.startswith("image_"):
            AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v1(
                title="用户上传的图片", description="用户上传的图片", sub_material_path=value)
        elif key.startswith("video_"):
            AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v1(
                title="用户上传的视频", description="用户上传的视频", sub_material_path=value)
    return "素材上传成功"


@tool
def get_material_in_web(user_id: str, keyword: str):
    """
    根据关键词获取素材
    :param user_id: 用户id
    :param keyword: 关键词
    """
    if user_id not in AdAgents:
        raise ValueError(f"用户{user_id}不存在")
    AdAgents[user_id].state.material_library.crawl_material_in_web(keyword)
    return "素材爬取成功,请在素材库中查看"


@tool
def pre_review_material(overhead_information: dict):
    """
    预审素材
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    """
    pre_review_material_result_list = []
    for key, value in overhead_information.items():
        if key.startswith("video_") or key.startswith("img_"):
            # 对图片进行预审
            video_path = value
            text_input = None
            screenshot = ""
            result = process_media(
                media_file=video_path,
                MEDIASHIELD_GEMINI_API_KEY=conf.get(
                    "MEDIASHIELD_GEMINI_API_KEY"),
                MEDIASHIELD_GPT_API_KEY=conf.get("MEDIASHIELD_GPT_API_KEY"),
                similarity_threshold=0.4,
                text_input=text_input,
                screenshot=screenshot
            )
            result = result["message"]
            pre_review_material_result_list.append(result)
    pre_review_material_content = ""
    for index, pre_review_material_result in enumerate(pre_review_material_result_list):
        pre_review_material_content += f"""素材{index + 1}
            的预审结果为{pre_review_material_result}"""
    return pre_review_material_content


# 用户给定图片or没有给定图片
@tool
def create_image_by_t2i(user_id: str, require: str):
    """
    使用text-to-image模型创建图片
    :param user_id: 用户id
    :param require: 需求，具体需求，例如对图片的具体要求，例如："一个穿着白色连衣裙的女孩在海边跳舞"
    """
    if user_id not in AdAgents:
        raise ValueError(f"用户{user_id}不存在")
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to image")
    model = model_factory.get_model_by_id(model_id)
    output_path = asyncio.run(model.generate(positive_prompt=require))
    # 将生成的素材放入素材库
    AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
        title=require, description=require, sub_material_path=output_path)
    return "图片生成成功,请在素材库中查看"


@tool
def create_video_by_t2v(user_id: str, require: str):
    """
    使用text-to-video模型创建视频
    :param user_id: 用户id
    :param require: 需求，具体需求，例如对视频的具体要求，例如："一个穿着白色连衣裙的女孩在海边跳舞"
    """
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to video")
    model = model_factory.get_model_by_id(model_id)
    output_path = asyncio.run(model.generate(positive_prompt=require))
    AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
        title=require, description=require, sub_material_path=output_path)
    return "视频生成成功,请在素材库中查看"


@tool
def create_video_by_i2v_wo_assign(user_id: str, require: str, overhead_information: dict):
    """
    用户没有指定图片或者用户希望根据其在附加输入中输入的图片来生成视频，使用image-to-video模型创建视频
    :param user_id: 用户id
    :param require: 需求，具体需求，例如对视频的具体要求，例如："一个穿着白色连衣裙的女孩在海边跳舞"
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    """
    input_image_list = []
    # 判断其中是否有image_开头
    for key, value in overhead_information.items():
        if key.startswith("image_"):
            # 使用image-to-video模型创建视频
            input_image_list.append(value)
    if len(input_image_list) == 0:
        # 在素材库中选择合适的素材
        material_id_list = AdAgents[user_id].state.material_library.select_appropriate_material(
            require)
        if len(material_id_list) == 0:
            return "没有找到合适的素材,请调用get_material_in_web来获取素材"
        for material_id in material_id_list:
            material_path = AdAgents[user_id].state.material_library.get_material_by_id(
                material_id)
            if material_path is None:
                return f"素材{material_id}不存在"
            if not is_image_file(material_path):
                return f"素材{material_id}不是图片"
            model_id = model_factory.choose_model_by_specific_function(
                require, "image to video")
            model = model_factory.get_model_by_id(model_id)
            output_path = asyncio.run(model.generate(
                image_path=material_path, positive_prompt=require))
            AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
                title=require, description=require, sub_material_path=output_path)
        return "视频生成成功,请在素材库中查看"
    else:
        # 使用以上图片 + 需求 来创建视频
        model_id = model_factory.choose_model_by_specific_function(
            require, "image to video")
        model = model_factory.get_model_by_id(model_id)
        for input_image in input_image_list:
            output_path = asyncio.run(model.generate(
                image_path=input_image, positive_prompt=require))
            AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
                title=require, description=require, sub_material_path=output_path)

        return "视频生成成功,请在素材库中查看"


@tool
def create_video_by_i2v_with_assign(user_id: str, require: str, material_id: str):
    """
    用户指定了使用素材库中的图片来生成视频，使用image-to-video模型创建视频
    :param user_id: 用户id
    :param require: 需求，具体需求，例如对视频的具体要求，例如："一个穿着白色连衣裙的女孩在海边跳舞"
    :param material_id: 素材id,素材id的格式为"{number}_{number}"，例如"1_1"
    """
    # 从素材库中获取素材
    material_path = AdAgents[user_id].state.material_library.get_material_by_id(
        material_id)
    if material_path is None:
        return f"素材{material_id}不存在"
    # 使用以上图片 + 需求 来创建视频
    # 确保该素材是图片,通过后缀进行判断
    if not is_image_file(material_path):
        return f"素材{material_id}不是图片"
    logger.info(f"material_path: {material_path} use i2v to create video")
    model_id = model_factory.choose_model_by_specific_function(
        require, "image to video")
    model = model_factory.get_model_by_id(model_id)
    output_path = asyncio.run(model.generate(
        image_path=material_path, positive_prompt=require))
    AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
        title=require, description=require, sub_material_path=output_path)
    return "视频生成成功,请在素材库中查看"


@tool
def create_image_by_i2i_wo_assign(user_id: str, positive_prompt: str, negative_prompt: str, overhead_information: dict):
    """
    用户没有指定图片或者用户希望根据其在附加输入中输入的图片来生成图片，使用image-to-image模型创建图片
    :param user_id: 用户id
    :param positive_prompt: 正向提示词，具体需求，例如对图片的具体要求，例如："一个穿着白色连衣裙的女孩在海边跳舞"
    :param negative_prompt: 负向提示词，例如："不要有文字"
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    """
    input_image_list = []
    # 判断其中是否有image_开头
    for key, value in overhead_information.items():
        if key.startswith("image_"):
            # 使用image-to-video模型创建视频
            input_image_list.append(value)
    if len(input_image_list) == 0:
        # 在素材库中选择合适的素材
        material_id_list = AdAgents[user_id].state.material_library.select_appropriate_material(
            positive_prompt)
        if len(material_id_list) == 0:
            return "没有找到合适的素材,请调用get_material_in_web来获取素材"
        for material_id in material_id_list:
            material_path = AdAgents[user_id].state.material_library.get_material_by_id(
                material_id)
            if material_path is None:
                return f"素材{material_id}不存在"
            if not is_image_file(material_path):
                return f"素材{material_id}不是图片"
            model_id = model_factory.choose_model_by_specific_function(
                positive_prompt, "image to image")
            model = model_factory.get_model_by_id(model_id)
            output_path = asyncio.run(model.generate(
                image_path=material_path, positive_prompt=positive_prompt, negative_prompt=negative_prompt))
            AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
                title=positive_prompt, description=positive_prompt, sub_material_path=output_path)
        return "图片生成成功,请在素材库中查看"
    else:
        # 使用以上图片 + 需求 来创建图片
        model_id = model_factory.choose_model_by_specific_function(
            positive_prompt, "image to image")
        model = model_factory.get_model_by_id(model_id)
        for input_image in input_image_list:
            output_path = asyncio.run(model.generate(
                image_path=input_image, positive_prompt=positive_prompt, negative_prompt=negative_prompt))
            AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
                title=positive_prompt, description=positive_prompt, sub_material_path=output_path)

        return "视频生成成功,请在素材库中查看"


@tool
def create_image_by_i2i_with_assign(user_id: str, positive_prompt: str, negative_prompt: str, material_id: str):
    """
    用户指定了图片，使用image-to-image模型创建图片
    :param user_id: 用户id
    :param positive_prompt: 正向提示词，具体需求，例如对图片的具体要求，例如："一个穿着白色连衣裙的女孩在海边跳舞"
    :param negative_prompt: 负向提示词，例如："不要有文字"
    :param material_id: 素材id,素材id的格式为"{number}_{number}"，例如"1_1"
    """
    material_path = AdAgents[user_id].state.material_library.get_material_by_id(
        material_id)
    if material_path is None:
        return f"素材{material_id}不存在"
    # 使用以上图片 + 需求 来创建视频
    # 确保该素材是图片,通过后缀进行判断
    if not is_image_file(material_path):
        return f"素材{material_id}不是图片"
    model_id = model_factory.choose_model_by_specific_function(
        positive_prompt, "image to image")
    model = model_factory.get_model_by_id(model_id)
    output_path = asyncio.run(model.generate(
        image_path=material_path, positive_prompt=positive_prompt, negative_prompt=negative_prompt))
    AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
        title=positive_prompt, description=positive_prompt, sub_material_path=output_path)
    return "视频生成成功,请在素材库中查看"
