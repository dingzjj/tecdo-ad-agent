# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
from langchain_core.messages import convert_to_messages
from agent.ad_agent.art.agent_modules.create_agent import creation_agent
from langgraph_supervisor import create_supervisor
from agent.ad_agent.art.task_library import task_library_manager
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
    overhead_information: dict = Field(
        default={}, description="素材库，用于记录用户输入和中途生成的图片，视频")


def pretty_print_message(message, indent=False):
    pretty_message = message.pretty_repr(html=True)
    if not indent:
        print(pretty_message)
        return

    indented = "\n".join("\t" + c for c in pretty_message.split("\n"))
    print(indented)


def pretty_print_messages(update, last_message=False):
    is_subgraph = False
    if isinstance(update, tuple):
        ns, update = update
        # skip parent graph updates in the printouts
        if len(ns) == 0:
            return

        graph_id = ns[-1].split(":")[0]
        print(f"Update from subgraph {graph_id}:")
        print("\n")
        is_subgraph = True

    for node_name, node_update in update.items():
        update_label = f"Update from node {node_name}:"
        if is_subgraph:
            update_label = "\t" + update_label

        print(update_label)
        print("\n")

        messages = convert_to_messages(node_update["messages"])
        if last_message:
            messages = messages[-1:]

        for m in messages:
            pretty_print_message(m, indent=is_subgraph)
        print("\n")


class AdAgent:
    """
    广告agent
    无素材库的概念，只会基于用户输入的图片，文档，文件进行创作
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state = AdAgentState(user_id=user_id)

    def invoke(self, message: str, overhead_information: dict = {}, chat_history: list[BaseMessage] = []):
        """
        调用agent
        :param message: 消息
        :param overhead_information: {"#image_1": {"content": "图片1路径", "description": "图片1描述"}, "#video_1": {"content": "视频1路径", "description": "视频1描述"}} 额外信息,用于记录用户输入的图片，文档，文件 
        :return: 响应
        """

        # task library
        expert_knowledge_prompt = task_library_manager.task_retrieval(message)

        # supervisor and sub-agent

        # supervisor
        supervisor = create_supervisor(
            model=create_azure_gpt5_llm(),
            agents=[creation_agent],
            prompt=(
                "您是一名主管，负责管理一名代理人员：\n"
                "- 一名创作代理人员。将创作相关任务分配给该代理人员\n"
                "每次只安排一名代理人员工作，不要同时呼叫多个代理人员。\n"
                "您自己不要做任何工作。你可以参考以下任务:\n" + expert_knowledge_prompt
            ),
            output_mode="full_history",
        ).compile()
        chat_history.insert(0, HumanMessage(content=message))
        for chunk in supervisor.stream(
                {
                    "message": chat_history,
                    "overhead_information": overhead_information
                }):
            pretty_print_messages(chunk, last_message=True)
