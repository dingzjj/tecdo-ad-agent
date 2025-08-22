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


@tool(description="创作脚本时必须调用该工具来创建视频脚本,广告视频脚本")
def create_script(require: Annotated[str, Field(description="需求，具体需求，例如对脚本的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                  config: RunnableConfig):
    """
    创建视频脚本,广告视频脚本
    """
    llm = create_azure_gpt5_llm()
    response = llm.invoke([
        SystemMessage(
            content=CREATE_SCRIPT_PROMPT),
        HumanMessage(
            content=f"{require}")
    ])
    return response.content


@tool(description="提供对图片的描述，使用text-to-image模型创建图片")
def create_image_by_t2i(require: Annotated[str, Field(description="需求，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        config: RunnableConfig):
    """
    提供对图片的描述，使用text-to-image模型创建图片
    """
    # 一切在工具内的都为英文
    require = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=require)
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
    return f"生成图片成功,{usage_feedback},生成的图片id为{f'{material_id}'}"


@tool(description="提供对视频的描述，使用text-to-video模型创建视频")
def create_video_by_t2v(require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        config: RunnableConfig):
    """
    提供对视频的描述，使用text-to-video模型创建视频
    """

    # 一切在工具内的都为英文
    require = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=require)
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to video")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(positive_prompt=require))
    # 输出的信息是生成 所用的提示词 + 视频地址(使用虚拟路径)
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=require)
    return f"生成视频成功,{usage_feedback},生成的视频id为{f'{material_id}'}"


@tool(description="在需求中指定所用的图片id来生成视频，或者附加信息中有图片上传。使用image-to-video模型创建视频")
def create_video_by_i2v(require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        image_id: Annotated[str, Field(description="图片id，素材库中的素材id的格式为{number}例如1，用户上传的素材id的格式为#{number}例如#1")],
                        config: RunnableConfig) -> Command:
    """
    在需求中指定所用的图片id来生成视频，或者附加信息中有图片上传。使用image-to-video模型创建视频
    """
    # 一切在工具内的都为英文
    require = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=require)

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
    return f"使用图片{image_id},{usage_feedback},生成的视频id为{f'{material_id}'}"


@tool(description="在需求中指定所用的图片id来生成图片，或者附加信息中有图片上传。使用image-to-image模型创建图片")
def create_image_by_i2i(positive_prompt: Annotated[str, Field(description="正向提示词，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        image_id: Annotated[str, Field(description="图片id，素材库中的素材id的格式为{number}例如1，用户上传的素材id的格式为#{number}例如#1")],
                        config: RunnableConfig):
    """
    在需求中指定所用的图片id来生成图片，或者附加信息中有图片上传。使用image-to-image模型创建图片
    功能：1.生成某商品的多视角图片 2.对商品图片背景进行修改
    """
    # 一切在工具内的都为英文
    positive_prompt = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=positive_prompt)
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
        positive_prompt, "image to image")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(image_path=image_path, positive_prompt=positive_prompt))

    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=positive_prompt)
    return f"使用图片{image_id},{usage_feedback},生成的图片id为{f'{material_id}'}"


@tool(description="将多个视频片段拼接成一个完整的视频")
def merge_video(video_list: Annotated[list[str], Field(description="视频列表，视频id的格式为{number}例如1，用户上传的素材id的格式为#{number}例如#1")],
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
        real_video_list, conf.get_path("temp_dir"))
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=f"使用{video_list}拼接成的视频")
    # 将视频列表中的视频拼接成一个完整的视频
    return f"将多个视频片段拼接成一个完整的视频成功,生成的视频id为{material_id}"


class SeniorCreateAgentState(BaseModel):
    messages: list[BaseMessage]
    # 计划列表，包含着子任务，与子任务的执行结果 {"sub_task": "子任务", "result": "子任务的执行结果"}
    plan_list: list[dict] = []


def manager_context(state: SeniorCreateAgentState):
    # 对上下文进行过滤
    print(state.messages)
    # 删除调用信息
    state.messages.pop()
    state.messages.pop()
    return {"messages": state.messages}


def get_tool_list_info():
    tool_list_info = {}
    tool_list_info[create_script.name] = create_script.args_schema.model_json_schema()
    tool_list_info[create_image_by_t2i.name] = create_image_by_t2i.args_schema.model_json_schema()
    tool_list_info[create_video_by_t2v.name] = create_video_by_t2v.args_schema.model_json_schema()
    tool_list_info[create_video_by_i2v.name] = create_video_by_i2v.args_schema.model_json_schema()
    tool_list_info[create_image_by_i2i.name] = create_image_by_i2i.args_schema.model_json_schema()
    return str(tool_list_info)


tool_list_info = get_tool_list_info()


def generate_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    # llm生成计划
    llm = create_azure_gpt5_llm(name="generate_plan")
    require = state.messages[-1].content
    response = llm.invoke([
        SystemMessage(
            content=CREATE_PLAN_PROMPT.format(
                tool_list=tool_list_info,
                expert_knowledge_prompt=plan_library_manager.get_prompt_from_plan_library(
                    "senior_create_agent"),
            )),
        HumanMessage(
            content=f"需求：{require}")
    ])
    # 将response.content转换为plan_list
    plan_list = json.loads(response.content)
    plan_list = plan_list["plan_list"]
    plan_list = [{"sub_task": plan, "result": None} for plan in plan_list]
    return {"plan_list": plan_list}

# TODO: 需要将执行结果加入到plan_list中


def execute_plan(state: SeniorCreateAgentState, config: RunnableConfig):
    # 执行计划
    # 逐一执行plan_list中的计划
    user_id = config["configurable"]["user_id"]
    for plan in state.plan_list:
        execute_plan_agent = create_react_agent(
            name="senior_create_agent",
            model=create_azure_gpt5_llm(name="execute_plan"),
            tools=[create_image_by_t2i, create_video_by_t2v, merge_video,
                   create_video_by_i2v, create_image_by_i2i, create_script],
            prompt=(
                f"""你是一名高级创作代理人员。可以通过调用工具来完成广告，宣传短片等大型创作任务。所有操作尽可能使用工具来完成。输出要尽可能详细，把工具输出结果也写入到输出中。
                任务列表如下，里面包含子任务，子任务的执行结果：
                {state.plan_list}
                """
            )
        )
        response = execute_plan_agent.invoke(
            {"messages": [HumanMessage(content=f"当前要执行的任务是：{plan["sub_task"]}")]})
        # 将执行结果加入到plan_list中
        plan["result"] = response["messages"][-1].content
    return {"plan_list": state.plan_list}


senior_create_agent = StateGraph(SeniorCreateAgentState)
senior_create_agent.add_node("manager_context", manager_context)
senior_create_agent.add_node("generate_plan", generate_plan)
senior_create_agent.add_node("execute_plan", execute_plan)
senior_create_agent.add_edge(START, "manager_context")
senior_create_agent.add_edge("manager_context", "generate_plan")
senior_create_agent.add_edge("generate_plan", "execute_plan")
senior_create_agent.add_edge("execute_plan", END)
senior_create_agent = senior_create_agent.compile(checkpointer=memory_saver)


def return_senior_create_agent():
    return senior_create_agent
