# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
from click.decorators import pass_meta_key
from agent.ad_agent.prompt import AD_AGENT_SYSTEM_PROMPT_cn
from langchain_core.tools.base import ArgsSchema, BaseTool
from langchain_core.messages import HumanMessage
from agent.ad_agent.prompt import AD_AGENT_HUMAN_PROMPT_cn
from agent.e_commerce_agent.material_library import Material
from agent.e_commerce_agent.material_library import MaterialLibrary
from agent.utils import get_time_id
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph import StateGraph
from agent.ad_agent.prompt import REACT_AGENT_SYSTEM_PROMPT_cn
from agent.llm import create_azure_llm
from langchain_openai import ChatOpenAI
from agent.llm import get_gemini_multimodal_model
from agent.mini_agent import AnalyseImageAgent
from agent.ad_agent.m2v_workflow import VideoFragment
from agent.utils import get_url_data
from agent.third_part.i2v import i2v_strategy_chain
import uuid
from MediaShield.process import process_media
from agent.ad_agent.utils import get_absolute_path_from_user_dir
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import shutil
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
        default=MaterialLibrary(), description="素材库")


AdAgents = {}


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
            prompt=AD_AGENT_SYSTEM_PROMPT_cn.format(user_id=self.user_id),
            model=create_azure_llm(),
            tools=[get_material_in_web]
        )
        NOW_EPOCH_CHAT_HISTORY = chat_history.copy()
        NOW_EPOCH_CHAT_HISTORY.append(HumanMessage(
            content=AD_AGENT_HUMAN_PROMPT_cn.format(question=message, overhead_information=overhead_information, user_id=self.user_id)))
        result = react_agent.invoke({"messages": NOW_EPOCH_CHAT_HISTORY})
        return result


@tool
def get_material_from_link(self, link: str):
    """
    根据链接获取素材https://blog.csdn.net/Alex_StarSky/article/details/136574438
    :param link: 链接
    :return: 素材
    """
    pass


@tool
def upload_material(self, overhead_information: dict = {}):
    """
    上传素材
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    :return: 素材
    """
    for key, value in overhead_information.items():
        if key.startswith("image_"):
            material_id = self.state.material_library.get_id()
            material = Material(id=material_id, title="用户上传的图片",
                                description="用户上传的图片", img_content_list=[(value, "用户上传的图片")])
            self.state.material_library.append_material(material)
        elif key.startswith("video_"):
            material_id = self.state.material_library.get_id()
            material = Material(id=material_id, title="用户上传的视频",
                                description="用户上传的视频", img_content_list=[(value, "用户上传的视频")])
            self.state.material_library.append_material(material)
    return "素材上传成功"


@tool()
def get_material_in_web(user_id: str, keyword: str):
    """
    根据关键词获取素材
    :param user_id: 用户id
    :param keyword: 关键词
    """
    if user_id not in AdAgents:
        raise ValueError(f"用户{user_id}不存在")
    AdAgents[user_id].state.material_library.crawl_material(keyword)
    return "素材爬取成功,请在素材库中查看"


@tool
def pre_review_material(self, overhead_information: dict = {}):
    """
    预审素材
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    :return: 素材
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


# 用户给定图片or没有给定
@tool
def create_video_by_t2v(user_id: str, require: str):
    """
    使用text-to-video模型创建视频
    :param user_id: 用户id
    :param require: 需求
    """
    pass


@tool
def create_video_by_i2v_wo_assign(user_id: str, require: str, overhead_information: dict = {}):
    """
    用户没有指定图片或者用户希望根据其输入的图片来生成视频，使用image-to-video模型创建视频
    :param user_id: 用户id
    :param require: 需求
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
        pass
    else:
        # 使用以上图片 + 需求 来创建视频
        pass


@tool
def create_video_by_i2v_with_assign(user_id: str, require: str, overhead_information: dict = {}):
    """
    用户指定了图片，使用image-to-video模型创建视频
    :param user_id: 用户id
    :param require: 需求
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    """
    pass


@tool
def create_image_by_t2i(user_id: str, require: str):
    """
    使用text-to-image模型创建图片
    :param user_id: 用户id
    :param require: 需求
    """
    pass


@tool
def create_image_by_i2i_wo_assign(user_id: str, require: str, overhead_information: dict = {}):
    """
    用户没有指定图片或者用户希望根据其输入的图片来生成图片，使用image-to-image模型创建图片
    :param user_id: 用户id
    :param require: 需求
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    """
    pass


@tool
def create_image_by_i2i_with_assign(user_id: str, require: str, overhead_information: dict = {}):
    """
    用户指定了图片，使用image-to-image模型创建图片
    :param user_id: 用户id
    :param require: 需求
    :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
    """
    pass
