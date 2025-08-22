# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
from agent.ad_agent.art.agent_modules.pojo import InterruptInAdAgent
from typing import Literal
from agent.mini_agent import MaterialAnalyserAgent
from agent.mini_agent import TranslatorAgent
from agent.mini_agent import AnalyseMaterialAgent
from langchain_core.messages import AIMessage
from pandas.core.series import doc
from pydantic import BaseModel, Field
from agent.ad_agent.art.agent_modules.senior_create_agent import return_senior_create_agent
from agent.ad_agent.art.agent_modules.material_agent import return_material_agent
from agent.ad_agent.art.agent_modules.junior_create_agent import return_junior_create_agent
from agent.llm import create_azure_llm
from langgraph.graph import END
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, Interrupt
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
from agent.ad_agent.art.material_library import MaterialLibrary
from config import conf, logger
import asyncio
from agent.ad_agent.art.agent_modules.store import memory_saver

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
# TODO 单点能力 ->学到 组合能力 -> 多跳能力
# TODO 确认询问机制
# TODO 提示词压缩技术
# TODO 任务库扩充方法

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


@tool(description="将任务交给高级创作代理")
def transfer_to_senior_create_agent(
    state: Annotated[MessagesState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    tool_message = {
        "role": "tool",
        "content": f"成功将任务交给高级创作代理",
        "name": "transfer_to_senior_create_agent",
        "tool_call_id": tool_call_id,
    }
    return Command(
        goto="senior_create_agent",
        update={**state, "messages": state["messages"] + [tool_message]},
        graph=Command.PARENT,
    )


@tool(description="将任务交给素材管理代理")
def transfer_to_material_agent(
    state: Annotated[MessagesState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    tool_message = {
        "role": "tool",
        "content": f"成功将任务交给素材管理代理",
        "name": "transfer_to_material_agent",
        "tool_call_id": tool_call_id,
    }
    return Command(
        goto="material_agent",
        update={**state, "messages": state["messages"] + [tool_message]},
        graph=Command.PARENT,
    )


@tool(description="将任务交给低级创作代理")
def transfer_to_junior_create_agent(
    state: Annotated[MessagesState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    tool_message = {
        "role": "tool",
        "content": f"成功将任务交给低级创作代理",
        "name": "transfer_to_junior_create_agent",
        "tool_call_id": tool_call_id,
    }
    return Command(
        goto="junior_create_agent",
        update={**state, "messages": state["messages"] + [tool_message]},
        graph=Command.PARENT,
    )


def add_messages(old_messages: list[BaseMessage], new_messages: list[BaseMessage]) -> list[BaseMessage]:
    return old_messages + new_messages


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
        # TODO supervisor不能吃到工具调用信息，只需要接收到（在Sub agent 到supervisor之间添加个消息过滤）
        # TODO sub agent也不用接收到全部消息，过滤部分信息
        supervisor_agent = create_react_agent(
            model=create_azure_llm(),
            tools=[transfer_to_senior_create_agent,
                   transfer_to_material_agent, transfer_to_junior_create_agent],
            prompt=(
                "您是一名主管，负责管理一名代理人员：\n"
                "- 一名高级创作代理人员。将广告，宣传短片等大型创作任务分配给该代理人员\n"
                "- 一名素材管理代理。对需使用的素材进行搜索，上传，预审等任务分配给该代理人员但用户没有特别明确针对于素材搜索，上传，预审需求时，不要分配给该代理人员\n"
                "- 一名低级创作代理人员。将简单的创作任务分配给该代理人员，例如单个图片，单个视频创作任务，即不涉及多张图片，多段视频的创作任务\n"
                "每次只安排一名代理人员工作，不要同时呼叫多个代理人员。\n"
                "您自己不要做任何工作"
                "输出结果时，不要输出任何其他内容，只输出结果，不要出现代理人员相关信息"
            ),
            name="supervisor")
        supervisor = (
            StateGraph(MessagesState)
            # NOTE: `destinations` is only needed for visualization and doesn't affect runtime behavior
            .add_node(supervisor_agent, destinations=("senior_create_agent", "material_agent", "junior_create_agent", END))
            .add_node("senior_create_agent", return_senior_create_agent())
            .add_node("material_agent", return_material_agent(self.user_id))
            .add_node("junior_create_agent", return_junior_create_agent(self.user_id))
            .add_edge(START, "supervisor")
            # always return back to the supervisor
            .add_edge("senior_create_agent", "supervisor")
            .add_edge("material_agent", "supervisor")
            .add_edge("junior_create_agent", "supervisor")
            .compile(checkpointer=memory_saver)
        )
        self.supervisor = supervisor

    def stream(self, message: str, overhead_information: dict = {}):
        result = []
        """
        调用agent
        :param message: 消息
        :param overhead_information: {"id": {"content": "图片1路径", "description": "图片1描述"}, "id": {"content": "视频1路径", "description": "视频1描述"}} 额外信息,用于记录用户输入的图片，文档，文件
        :return: 响应
        """
        # 假如有图片，视频上传，先对素材进行分析

        upload_material_id_list = []
        # 将overhead_information中的图片上传到素材库中
        for upload_material_id, upload_material_info in overhead_information.items():
            upload_material_path = upload_material_info["content"]
            analysis_result = asyncio.run(MaterialAnalyserAgent().analyse_material(
                material_path=upload_material_path, source="local"))
            analysis_result = TranslatorAgent().translate(
                from_lang="English", to_lang="Chinese", text=analysis_result)
            self.material_library.append_material_with_analysis(
                material_path=upload_material_path, title=upload_material_info["description"], description=analysis_result, analysis_result=analysis_result, id=upload_material_id)
            overhead_information[upload_material_id]["content"] = analysis_result
            upload_material_id_list.append(upload_material_id)
        # task library
        if len(upload_material_id_list) > 0:
            self.agent_chat_history.append(HumanMessage(
                content=f"{message}\n上传的素材如下：{overhead_information}"))
        else:
            self.agent_chat_history.append(HumanMessage(
                content=f"{message}"))

        # supervisor and sub-agent
        # supervisor
        # Define the multi-agent supervisor graph

        sub_agent_list = ["senior_create_agent",
                          "material_agent", "junior_create_agent"]

        # Create state with material library and user_id
        state = AdAgentState(
            messages=self.agent_chat_history)
        agent_config = {"configurable": {
            "thread_id": self.user_id, "overhead_information": overhead_information, "user_id": self.user_id}}
        while True:
            if self.is_interrupted:
                # 中断
                for chunk in self.supervisor.stream(Command(resume=message), config=agent_config, stream_mode="messages"):
                    # 将chunk中有用的信息加入到agent_chat_history中
                    llm_token, metadata = chunk
                    # print("---------------llm_token-----------------")
                    # print(llm_token)
                    # print("---------------metadata-----------------")
                    # print(metadata)
                    # print("--------------------------------")
                    if metadata["langgraph_node"] in sub_agent_list:
                        # 从node_value中提取有用信息
                        self.agent_chat_history.append(llm_token)

            else:
                # 非中断
                # 在生成计划时中断返回，在1.任务列表，2、每个子任务 +子任务的执行结果 3.总结果
                for chunk in self.supervisor.stream(state, config=agent_config, stream_mode="messages"):
                    # 将chunk中有用的信息加入到agent_chat_history中
                    llm_token, metadata = chunk
                    # print("---------------llm_token-----------------")
                    # print(llm_token)
                    # print("---------------metadata-----------------")
                    # print(metadata)
                    # print("--------------------------------")
                    if metadata["langgraph_node"] in sub_agent_list:
                        # 从node_value中提取有用信息
                        self.agent_chat_history.append(llm_token)
            with open("/data/dzj/ad_agent/agent/ad_agent/art/agent_modules/agent_chat_history.txt", "w") as f:
                # 每个元素换行输出
                for message in self.agent_chat_history:
                    f.write(str(message)+"\n")
            snapshot = self.supervisor.get_state(agent_config)
            if isinstance(snapshot.interrupts[-1], Interrupt):
                interrupt_message: InterruptInAdAgent = snapshot.interrupts[-1].value
                if interrupt_message.type == "tool_call":
                    self.is_interrupted = True
                    return interrupt_message.message_list
                else:
                    message = interrupt_message.type
                    self.is_interrupted = True
                    yield interrupt_message.message_list
            elif isinstance(snapshot.values["messages"][-1], AIMessage):
                self.is_interrupted = False
                return snapshot.values["messages"][-1].content
