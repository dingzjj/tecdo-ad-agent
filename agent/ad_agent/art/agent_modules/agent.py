# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
from agent.mini_agent import AnalyseMaterialAgent
from langchain_core.messages import AIMessage
from pandas.core.series import doc
from pydantic import BaseModel
from agent.ad_agent.art.agent_modules.material_agent import get_material_from_link, upload_material, get_material_in_web, pre_review_material_in_material_library, pre_review_material_in_user_input
from agent.ad_agent.art.agent_modules.high_level_create_agent import create_image_by_t2i, create_video_by_t2v, create_video_by_i2v, create_image_by_i2i, create_script
from agent.llm import create_azure_llm
from langgraph.graph import END
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId
from typing import Annotated
from agent.ad_agent.art.material_library import material_librarys
from langchain_core.messages import convert_to_messages
from langgraph_supervisor import create_supervisor
from agent.ad_agent.art.task_library import task_library_manager
import os
from langchain_core.messages import BaseMessage, HumanMessage
from agent.llm import create_azure_gpt5_llm
from langgraph.checkpoint.memory import MemorySaver
from agent.ad_agent.art.material_library import MaterialLibrary
from config import conf, logger
import asyncio

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
# TODO 确认询问机制

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


memory_saver = MemorySaver()


class AdAgentState(BaseModel):
    messages: list[BaseMessage]


class AdAgent:
    """
    广告agent(素材库版)
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.material_library = MaterialLibrary(
            material_library_dir=os.path.join(conf.get_path("material_library_dir"), user_id))
        material_librarys[user_id] = self.material_library
        self.agent_chat_history: list[BaseMessage] = []
        self.is_interrupted = False

    def invoke(self, message: str, overhead_information: dict = {}):
        """
        调用agent
        :param message: 消息
        :param overhead_information: {"id": {"content": "图片1路径", "description": "图片1描述"}, "id": {"content": "视频1路径", "description": "视频1描述"}} 额外信息,用于记录用户输入的图片，文档，文件
        :return: 响应
        """
        # TODO 假如有图片，视频上传，先对素材进行分析

        new_overhead_information = {}
        upload_material_id_list = []
        # 将overhead_information中的图片上传到素材库中
        for upload_material_id, upload_material_info in overhead_information.items():
            upload_material_path = upload_material_info["content"]
            description = asyncio.run(AnalyseMaterialAgent().analyse_material(
                material_path=upload_material_path, source="local"))
            self.material_library.append_material_without_analysis(
                material_path=upload_material_path, title=upload_material_info["description"], description=description, id=upload_material_id)
            new_overhead_information[upload_material_id] = description
            upload_material_id_list.append(upload_material_id)

        # task library
        expert_knowledge_prompt = task_library_manager.task_retrieval(message)
        if len(upload_material_id_list) > 0:
            self.agent_chat_history.append(HumanMessage(
                content=f"{message}，用户上传的素材如下：{overhead_information}"))
        else:
            self.agent_chat_history.append(HumanMessage(
                content=f"{message}"))
        upload_message = AIMessage(
            content=f"用户上传的素材：{upload_material_id_list}已经上传到素材库中")
        self.agent_chat_history.append(upload_message)

        # supervisor and sub-agent
        # supervisor
        # Define the multi-agent supervisor graph

        high_level_create_agent = create_react_agent(
            name="Senior_Creative_Agent",
            model=create_azure_gpt5_llm(),
            tools=[create_image_by_t2i, create_video_by_t2v,
                   create_video_by_i2v, create_image_by_i2i, create_script],
            prompt=(
                "你是一名高级创作代理人员。可以完成广告，宣传短片等大型创作任务。可以参考以下任务:\n" + expert_knowledge_prompt
            ),
        )

        low_level_create_agent = create_react_agent(
            name="Low_Level_Creative_Agent",
            model=create_azure_gpt5_llm(),
            tools=[create_image_by_t2i, create_video_by_t2v,
                   create_video_by_i2v, create_image_by_i2i],
            prompt=(
                "你是一名低级创作代理人员。可以完成单个图片，单个视频创作任务"
            ),
        )
        material_agent = create_react_agent(
            name="Material_Management_Agent",
            model=create_azure_gpt5_llm(),
            tools=[get_material_from_link, upload_material, get_material_in_web,
                   pre_review_material_in_material_library, pre_review_material_in_user_input],
            prompt=(
                "你是一个素材管理代理,你负责根据用户的需求管理素材,例如根据用户的需求从网上获取素材，上传素材，预审素材等"
            ),
        )

        supervisor = create_supervisor(
            model=create_azure_gpt5_llm(),
            agents=[high_level_create_agent,
                    material_agent, low_level_create_agent],
            prompt=(
                "您是一名主管，负责管理一名代理人员：\n"
                "- 一名高级创作代理人员。将广告，宣传短片等大型创作任务分配给该代理人员\n"
                "- 一名高级素材代理人员。对需使用的素材进行搜索，上传，预审等任务分配给该代理人员\n"
                "- 一名低级创作代理人员。将单个图片，单个视频创作任务分配给该代理人员\n"
                "每次只安排一名代理人员工作，不要同时呼叫多个代理人员。\n"
                "您自己不要做任何工作"
            ),
            output_mode="last_message"
        ).compile(checkpointer=memory_saver, name="ad agent")

        # Create state with material library and user_id
        while True:
            state = AdAgentState(
                messages=self.agent_chat_history)
            agent_config = {"configurable": {
                "thread_id": self.user_id, "overhead_information": overhead_information, "user_id": self.user_id}}

            for chunk in supervisor.stream(state, config=agent_config, stream_mode="updates"):
                # 将chunk中有用的信息加入到agent_chat_history中
                print(chunk)
                # 非中断

                # 中断
            patterns = ["transfer_to_senior_creative_agent",
                        "transfer_to_material_agent", "transfer_to_low_level_create_agent"]
            for pattern in patterns:
                if pattern in chunk["supervisor"]["messages"][-1].content:
                    continue

            return chunk["supervisor"]["messages"][-1].content
