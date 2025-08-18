# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
import asyncio
import json
import os
import uuid
from typing import Annotated, Dict, List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, root_validator
from pydantic.v1 import tools

from MediaShield.process import process_media
from agent.ad_agent.prompt import (
    AD_AGENT_HUMAN_PROMPT_cn,
    AD_AGENT_SYSTEM_PROMPT_cn,
    REACT_AGENT_SYSTEM_PROMPT_cn,
)
from agent.llm import create_azure_gpt5_llm
from agent.material_library import MaterialLibrary
from agent.mini_agent import (
    GenerateVideoPromptAgent,
    TranslatorAgent,
)
from agent.third_part.multimodel_generation_model.kernel import model_factory
from agent.utils import (
    is_image_file,
    is_video_file,
)
from config import conf, logger

# 设置环境变量
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "react_agent"

# 所有图片都在
start_hint = "ad agent"


# TODO 创作能力总结 -> 多图创作能力，多视频创作能力，文+图+视频混合创作能力
# TODO 根据用户选择的图片生成商品lora model，并使用该lora model进行创作
# TODO 提高agent使用素材库的能力 （所有未指定的生成都先查看素材库判断是否有合适的素材）
# TODO 多跳能力优化
# TODO 调用能力前弹出 （提示框）
# TODO 单点能力 ->学到 组合能力 -> 多跳能力


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
        # overhead_information_list = []
        # for key, value in overhead_information.items():
        #     overhead_information_list.append((key, value))

        # task library

        # tool library

        # supervisor

        react_agent = create_react_agent(
            # prompt=SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(
            #     user_id=self.user_id, material_library=self.state.material_library.get_all_material_info())),
            model=create_azure_gpt5_llm(),
            tools=[get_material_from_link, get_material_in_web, upload_material, pre_review_material_in_material_library, pre_review_material_in_user_input, create_image_by_t2i, create_video_by_t2v,
                   create_video_by_i2v_wo_assign, create_video_by_i2v_with_assign, create_image_by_i2i_wo_assign, create_image_by_i2i_with_assign]
        )
        # 在chat_history头部中添加SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(user_id=self.user_id))
        chat_history.insert(0, SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(
            user_id=self.user_id)))
        chat_history.append(HumanMessage(
            content=AD_AGENT_HUMAN_PROMPT_cn.format(question=message, overhead_information=overhead_information, user_id=self.user_id)))
        result = react_agent.invoke({"messages": chat_history})
        return result


AdAgents: dict[str, AdAgent] = {}
