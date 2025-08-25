from agent.ad_agent.art.agent_modules.prompt import EXECUTE_PLAN_SYSTEM_PROMPT_EN
from agent.ad_agent.art.agent_modules.prompt import CREATE_PLAN_PROMPT_EN
from agent.ad_agent.art.agent_modules.prompt import EXECUTE_PLAN_SYSTEM_PROMPT
from agent.ad_agent.art.agent_modules.pojo import InterruptInAdAgent
from langgraph.types import interrupt
from langchain_core.messages import AIMessage
from agent.utils import get_time_id
import os
from agent.third_part.moviepy_apply import concatenate_videos_from_urls
from config import conf
from agent.utils import is_video_file
from agent.ad_agent.art.plan_library import plan_library_manager
from agent.ad_agent.art.task_library import task_library_manager
from agent.ad_agent.art.agent_modules.prompt import CREATE_PLAN_PROMPT
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig
from typing import Optional
from agent.ad_agent.art.material_library import Material, material_librarys
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from agent.llm import create_azure_gpt5_llm
from langgraph.prebuilt import InjectedState
import asyncio
import json
from agent.third_part.multimodel_generation_model.kernel import model_factory
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import Field
from typing import Annotated
from agent.mini_agent import TranslatorAgent
from agent.ad_agent.art.agent_modules.prompt import CREATE_SCRIPT_PROMPT
from langchain_core.tools import tool
from agent.ad_agent.art.agent_modules.store import memory_saver


@tool(description="When creating video scripts, this tool must be used to create them.")
def create_script(require: Annotated[str, Field(description="Specific requirements for the script")],
                  config: RunnableConfig):
    """
    创建视频脚本,广告视频脚本,创作视频脚本时必须调用该工具来创建
    """
    llm = create_azure_gpt5_llm(name="create_script")
    response = llm.invoke([
        SystemMessage(
            content=CREATE_SCRIPT_PROMPT),
        HumanMessage(
            content=f"{require}")
    ])
    return response.content


@tool(description="Provide a description of the image and use the text-to-image model to create the image.")
def create_image_by_t2i(require: Annotated[str, Field(description="For the specific requirements of the picture, please provide the background, characters and actions within the picture.")],
                        config: RunnableConfig):
    """
    提供对图片的描述，使用text-to-image模型创建图片
    """
    # 一切在工具内的都为英文
    # 获取最大id
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to image")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(positive_prompt=require))
    # 输出的信息是生成 所用的提示词 + 图片地址(使用虚拟路径)
    # 将图片存到素材库中
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=require)
    return f"The image was successfully generated,{usage_feedback},the generated image id is {f'{material_id}'}"


@tool(description="Provide a description of the video and use the text-to-video model to create the video.")
def create_video_by_t2v(require: Annotated[str, Field(description="For the specific requirements of the video, please provide the background, characters and actions within the video.")],
                        config: RunnableConfig):
    """
    提供对视频的描述，使用text-to-video模型创建视频
    """
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to video")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(positive_prompt=require))
    # 输出的信息是生成 所用的提示词 + 视频地址(使用虚拟路径)
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=require)
    return f"The video was successfully generated,{usage_feedback},the generated video id is {f'{material_id}'}"


@tool(description="Specify the image ID to be used in the requirements to generate the video, or there is image upload in the additional information. Use the image-to-video model to create the video.")
def create_video_by_i2v(require: Annotated[str, Field(description="For the specific requirements of the video, please provide  characters and actions within the video.")],
                        image_id: Annotated[str, Field(description="The ID of the image in the material library, the format is {number} for example 1, and the format is #{number} for example #1 for user uploaded materials.")],
                        config: RunnableConfig) -> Command:
    """
    在需求中指定所用的图片id来生成视频，或者附加信息中有图片上传。使用image-to-video模型创建视频
    """
    # 一切在工具内的都为英文
    if image_id.startswith("image"):
        # 使用附加信息上的进行创作
        overhead_information = config["configurable"]["overhead_information"]
        image = overhead_information.get(image_id)
        if image is None:
            return f"图片{image_id}不存在"
        image_path = image["content"]
    else:
        # 使用素材库上的进行创作
        image: Optional[Material] = material_librarys[config["configurable"]["user_id"]
                                                      ].get_material_by_id(image_id)

        # 从overhead_information中取出指定ID对应的图片
        if image is None:
            return f"图片{image_id}不存在"
        image_path = image.material_path
    model_id = model_factory.choose_model_by_specific_function(
        require, "image to video")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(image_path=image_path, positive_prompt=require))
    # 将其保存到overhead_information中
    # 获取最大id
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=require)
    return f"Using image {image_id},{usage_feedback},the generated video id is {f'{material_id}'}"


@tool(description="Specify the image ID to be used in the requirements to generate the image, or there is image upload in the additional information. Use the image-to-image model to create the image.")
def create_image_by_i2i(require: Annotated[str, Field(description="For the specific requirements of the picture, please provide the background, characters and actions within the picture.")],
                        image_id: Annotated[str, Field(description="The ID of the image in the material library, the format is {number} for example 1, and the format is #{number} for example #1 for user uploaded materials.")],
                        config: RunnableConfig):
    """
    在需求中指定所用的图片id来生成图片，或者附加信息中有图片上传。使用image-to-image模型创建图片
    功能：1.生成某商品的多视角图片 2.对商品图片背景进行修改
    """
    # 一切在工具内的都为英文
    if image_id.startswith("image"):
        # 使用附加信息上的进行创作
        overhead_information = config["configurable"]["overhead_information"]
        image = overhead_information.get(image_id)
        if image is None:
            return f"图片{image_id}不存在"
        image_path = image["content"]
    else:
        # 使用素材库上的进行创作
        image: Optional[Material] = material_librarys[config["configurable"]["user_id"]
                                                      ].get_material_by_id(image_id)
        if image is None:
            return f"图片{image_id}不存在"
        image_path = image.material_path

    model_id = model_factory.choose_model_by_specific_function(
        require, "image to image")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(image_path=image_path, positive_prompt=require))

    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=require)
    return f"Using image {image_id},{usage_feedback},the generated image id is {f'{material_id}'}"


@tool(description="Merge multiple video fragments into a complete video.")
def merge_video(video_list: Annotated[list[str], Field(description="The list of video IDs, the format is {number} for example 1, and the format is #{number} for example #1 for user uploaded materials.")],
                config: RunnableConfig):
    """
    将多个视频片段拼接成一个完整的视频
    """
    real_video_list = []
    # 将视频列表中的视频拼接成一个完整的视频
    for video_id in video_list:
        video_path = material_librarys[config["configurable"]["user_id"]
                                       ].get_material_by_id(video_id).material_path
        if not is_video_file(video_path):
            return f"视频{video_id}不是视频文件"

        real_video_list.append(video_path)
    output_path = concatenate_videos_from_urls(
        real_video_list, os.path.join(conf.get_path("temp_dir"), f"{get_time_id()}.mp4"))
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=f"使用{video_list}拼接成的视频")
    # 将视频列表中的视频拼接成一个完整的视频
    return f"Successfully combining multiple video clips into a complete video,the generated video id is {material_id}"


class SeniorCreateAgentState(BaseModel):
    messages: list[BaseMessage]
    # 计划列表，包含着子任务，与子任务的执行结果 {"sub_task": "子任务", "result": "子任务的执行结果"}
    plan_list: list[dict] = []
    need_execute_plan_number: int = 0
    user_task: str = ""


def manager_context(state: SeniorCreateAgentState):
    # 对上下文进行过滤
    # 删除调用信息
    state.messages.pop()
    state.messages.pop()
    user_task = state.messages[-1].content
    return {"messages": state.messages, "user_task": user_task}


def get_tool_list_info():
    tool_list_info = {}
    tool_list_info[create_script.name] = create_script.args_schema.model_json_schema()[
        "description"]
    tool_list_info[create_image_by_t2i.name] = create_image_by_t2i.args_schema.model_json_schema()[
        "description"]
    tool_list_info[create_video_by_t2v.name] = create_video_by_t2v.args_schema.model_json_schema()[
        "description"]
    tool_list_info[create_video_by_i2v.name] = create_video_by_i2v.args_schema.model_json_schema()[
        "description"]
    tool_list_info[create_image_by_i2i.name] = create_image_by_i2i.args_schema.model_json_schema()[
        "description"]
    return str(tool_list_info)


tool_list_info = get_tool_list_info()


def generate_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    # llm生成计划
    llm = create_azure_gpt5_llm(name="generate_plan")
    require = state.messages[-1].content
    response = llm.invoke([
        SystemMessage(
            content=CREATE_PLAN_PROMPT_EN.format(
                tool_list=tool_list_info,
                expert_knowledge_prompt=plan_library_manager.get_prompt_from_plan_library(
                    "senior_create_agent"),
            )),
        HumanMessage(
            content=f"Requirement: {require}")
    ])
    # 将response.content转换为plan_list
    plan_list = json.loads(response.content)
    plan_list = plan_list["plan_list"]
    plan_list = [{"sub_task": plan, "result": None} for plan in plan_list]

    update_message = AIMessage(content=f"Task list: {plan_list}")
    interrupt(InterruptInAdAgent(
        type="interrupt_generate_plan", message_list=[update_message]))
    state.messages.append(update_message)
    # 中断返回
    return {"plan_list": plan_list, "messages": state.messages, "need_execute_plan_number": len(plan_list)}


def interrupt_generate_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    pass


def execute_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    # 执行计划
    # 逐一执行plan_list中的计划
    user_id = config["configurable"]["user_id"]
    now_execute_plan_number = len(
        state.plan_list) - state.need_execute_plan_number
    plan = state.plan_list[now_execute_plan_number]
    # TODO 增加保险措施避免工具错过
    execute_plan_agent = create_react_agent(
        name="senior_create_agent",
        model=create_azure_gpt5_llm(name="execute_plan"),
        tools=[create_script, create_image_by_t2i, create_video_by_t2v, merge_video,
               create_video_by_i2v, create_image_by_i2i],
        prompt=(
            EXECUTE_PLAN_SYSTEM_PROMPT_EN.format(
                task=state.user_task,
                plan_list=state.plan_list
            )
        )
    )
    response = execute_plan_agent.invoke(
        {"messages": [HumanMessage(content=f"The current task to be executed is: {plan["sub_task"]}")]})
    # 在这里查看最后是否非工具而没有调用
    # 将执行结果加入到plan_list中
    now_task_result: list[BaseMessage] = response["messages"]
    update_message_list = []
    for message in now_task_result:
        if message.content != "":
            update_message_list.append(AIMessage(content=message.content))
    interrupt(InterruptInAdAgent(
        type="interrupt_execute_plan", message_list=update_message_list))
    state.messages.extend(update_message_list)
    plan["result"] = response["messages"][-1].content
    return {"plan_list": state.plan_list, "messages": state.messages, "need_execute_plan_number": state.need_execute_plan_number - 1}


def interrupt_execute_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    pass


def if_return_execute_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    if state.need_execute_plan_number > 0:
        return True
    else:
        return False


senior_create_agent = StateGraph(SeniorCreateAgentState)
senior_create_agent.add_node("manager_context", manager_context)
senior_create_agent.add_node("generate_plan", generate_plan)
senior_create_agent.add_node("execute_plan", execute_plan)
senior_create_agent.add_node(
    "interrupt_generate_plan", interrupt_generate_plan)
senior_create_agent.add_node("interrupt_execute_plan", interrupt_execute_plan)


senior_create_agent.add_edge(START, "manager_context")
senior_create_agent.add_edge("manager_context", "generate_plan")
senior_create_agent.add_edge("generate_plan", "interrupt_generate_plan")
senior_create_agent.add_edge("interrupt_generate_plan", "execute_plan")
senior_create_agent.add_edge("execute_plan", "interrupt_execute_plan")
senior_create_agent.add_conditional_edges(
    "interrupt_execute_plan", if_return_execute_plan, {True: "execute_plan", False: END})

senior_create_agent.add_edge("execute_plan", END)

senior_create_agent = senior_create_agent.compile(checkpointer=memory_saver)


def return_senior_create_agent():
    return senior_create_agent
