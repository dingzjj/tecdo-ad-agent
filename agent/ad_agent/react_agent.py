# 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
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


class ReactAgentState(BaseModel):
    # 输入
    user_id: str = Field(description="用户id")
    overhead_information: dict = Field(
        default={}, description="额外信息,用于记录用户输入的模特图片，文档，文件")
    chat_history: list[BaseMessage] = Field(
        default=[], description="聊天历史,用于记录用户与agent的对话")


def add_file_not_in_dir_to_user_dir(user_id: str, original_file_path: str, content: str) -> str:
    """
    将original_file_path拷贝到user_id文件夹下，并记录文件名和文件内容到dir_info.txt中，返回一个相对路径
    """
    # 将original_file_path拷贝到user_id文件夹下
    relative_file_path = original_file_path.split("/")[-1]
    new_file_path = os.path.join(
        conf.get_path("user_data_dir"), user_id, relative_file_path)
    shutil.copy(original_file_path, new_file_path)
    # 将content写入dir_info.txt中
    with open(os.path.join(conf.get_path("user_data_dir"), user_id, "dir_info.txt"), "a") as f:
        f.write(f"文件名：{original_file_path.split("/")[-1]}，文件内容：{content}\n")
    # 返回一个相对路径
    return relative_file_path


def add_file_in_dir_to_user_dir(user_id: str, relative_file_path: str, content: str) -> str:
    """
    将relative_file_path记录到dir_info.txt中，记录文件名和文件内容
    """
    # 将original_file_path拷贝到user_id文件夹下
    with open(os.path.join(conf.get_path("user_data_dir"), user_id, "dir_info.txt"), "a") as f:
        f.write(f"文件名：{relative_file_path}，文件内容：{content}\n")
# 前提：所有文件都已经放到临时目录下


async def start_react_agent(state: ReactAgentState):
    # 创建用户文件夹
    os.makedirs(os.path.join(conf.get_path(
        "user_data_dir"), state.user_id), exist_ok=True)
    # 创建dir_info.txt(用于记录创建的文件信息)（每次往文件夹中添加文件时，dir_info.txt需要更新）
    # 将overhead_information中的文件拷贝过去
    for key, value in state.overhead_information.items():
        # value.split("/")[-1]为文件名
        new_file_path = add_file_not_in_dir_to_user_dir(
            state.user_id, value, "用户输入的文件")
        state.overhead_information[key] = new_file_path
    return {"overhead_information": state.overhead_information}


async def react_agent_invoke(state: ReactAgentState):
    result = start(
        state.user_id, state.chat_history, state.overhead_information)

    return result


async def end_react_agent(state: ReactAgentState):
    return state


def get_react_agent():
    graph = StateGraph(ReactAgentState)
    graph.add_node("start_react_agent", start_react_agent)
    graph.add_node("react_agent_invoke", react_agent_invoke)
    graph.add_node("end_react_agent", end_react_agent)

    graph.add_edge(START, "start_react_agent")
    graph.add_edge("start_react_agent", "react_agent_invoke")
    graph.add_edge("react_agent_invoke", "end_react_agent")
    graph.add_edge("end_react_agent", END)

    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


# 使用封装好的tools


def start(user_id, chat_history: list[BaseMessage], overhead_information: dict):
    agent_executor = create_react_agent(
        model=create_azure_llm(),
        tools=[
            check_user_data_dir,
            create_video,
            create_video_fragment,
            pre_review_material,
            get_user_data_dir_info
        ],
        prompt=REACT_AGENT_SYSTEM_PROMPT_cn.format(overhead_information=overhead_information, user_id=user_id))
    result = agent_executor.invoke({"messages": chat_history}, config={
        "configurable": {"thread_id": user_id}})
    return result

# 1.查看用户的文件夹


@tool
def get_user_data_dir_info(user_id):
    """
    获取用户的文件夹信息
    """
    with open(os.path.join(conf.get_path("user_data_dir"), user_id, "dir_info.txt"), "r") as f:
        return f.read()


@tool
def check_user_data_dir(user_id):
    """
    查看用户的文件夹,获取用户当前所拥有的文件
    """
    with open(os.path.join(conf.get_path("user_data_dir"), user_id, "dir_info.txt"), "r") as f:
        return f.read()

# 2.创建视频


@tool
def create_video(user_id, product: str, product_info: str, video_fragment_duration: int, images_relative_path: list[str]):
    """
    创建视频
    Args:
        product(str): 商品名称，输入可为空字符串，为空则使用默认值
        product_info(str): 商品信息，输入可为空字符串，为空则使用默认值
        video_fragment_duration(int): 视频片段时长，输入可为0，为0则使用默认值
        images(list[str]): 模特图片路径列表
    Returns:
        str: 视频创建结果
    """
    if product == "":
        product = "clothes"
    if product_info == "":
        product_info = "clothes"
    if video_fragment_duration == 0:
        video_fragment_duration = 5

    video_id = str(uuid.uuid4())
    video_relative_path = os.path.join(video_id, 'video_url_v1.mp4')
    # video_absolute_path = get_absolute_path_from_user_dir(
    #     user_id, video_relative_path)
    # 验证images对应的文件是否存在
    images_absolute_path = []
    for index, image in enumerate(images_relative_path):
        if not os.path.exists(get_absolute_path_from_user_dir(user_id, image)):
            return f"模特图片不存在: {image}"
        if not image.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
            return f"模特图片格式错误: {image}"
        images_absolute_path.append(
            get_absolute_path_from_user_dir(user_id, image))
    video_id = str(uuid.uuid4())

    with create_dir(os.path.join(conf.get_path("user_data_dir"), user_id), name=video_id) as result_dir:
        m2v_workflow = get_m2v_workflow()
        configuration: RunnableConfig = {"configurable": {
            "thread_id": "1", "result_dir": result_dir}}
        # 此处temp_dir是工作流对应的文件夹
        # 从这里return的是dict
        result: GenerateVideoState = asyncio.run(m2v_workflow.ainvoke({"id": video_id, "product": product, "product_info": product_info, "model_images": images_absolute_path,
                                                                       "video_fragment_duration": video_fragment_duration, "video_output_path": os.path.join(conf.get_path("m2v_workflow_result_dir"), user_id)},
                                                                      config=configuration))
        add_file_in_dir_to_user_dir(user_id, video_relative_path, f"""根据product={product},product_info={
                                    product_info},video_fragment_duration={video_fragment_duration},images={images_relative_path}创建的视频""")
        return f"视频创建成功，创建的视频位于 {video_relative_path}"
    # 3.创建视频片段


@tool
def create_video_fragment(user_id, img_path: str, product: str, product_info: str, video_fragment_duration: int, action_type: str, prompt: str, negative_prompt: str, i2v_strategy: str, bgm: str):
    """
    创建视频片段
    Args:
        img_path(str): 图片路径
        product(str): 商品名称，输入可为空字符串，为空则使用默认值
        product_info(str): 商品信息，输入可为空字符串，为空则使用默认值
        video_fragment_duration(str): 视频片段时长，输入可为空字符串，为空则使用默认值
        action_type(str): 动作类型，输入可为空字符串，为空则使用默认值
        prompt(str): 提示词（一般为多个词语，连着的用逗号隔开），输入可为空字符串，为空则使用默认值
        negative_prompt(str): 负向提示词（一般为多个词语，连着的用逗号隔开），输入可为空字符串，为空则使用默认值
        i2v_strategy(str): 图片转视频策略,例如keling,veo3，输入可为空字符串，为空则使用默认值
        bgm(str): 背景音乐，输入可为空字符串，为空则使用默认值
    Returns:
        str: 视频片段创建结果
    """
    if product == "":
        product = "clothes"
    if product_info == "":
        product_info = "clothes"
    if video_fragment_duration == 0:
        video_fragment_duration = 5.0
    if i2v_strategy == "":
        i2v_strategy = "keling"
    if action_type == "":
        action_type = "model_show"
    if prompt == "":
        prompt = "模特展示商品"
    if negative_prompt == "":
        negative_prompt = "模特展示商品"
    img_absolute_path = get_absolute_path_from_user_dir(
        user_id, img_path)
    if not os.path.exists(img_absolute_path):
        return f"图片不存在: {img_absolute_path}"
    if not img_absolute_path.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
        return f"图片格式错误: {img_absolute_path}"

    fragment_id = str(uuid.uuid4())
    fragment_relative_path = os.path.join(fragment_id, "video_url_v1.mp4")
    fragment_path = get_absolute_path_from_user_dir(
        user_id, os.path.join(fragment_id, "video_url_v1.mp4"))
    if prompt != "":
        # 有提供提示词,使用提示词来生成视频片段
        video_url = asyncio.run(i2v_strategy_chain.execute_chain_with_prompt(img_path=img_absolute_path, video_positive_prompt=prompt,
                                                                             video_negative_prompt=negative_prompt, duration=video_fragment_duration, i2v_strategy=i2v_strategy,
                                                                             resolution={}))
        video_data = get_url_data(video_url)
        with open(fragment_path, "wb") as f:
            f.write(video_data)
        video_fragment = VideoFragment(id=fragment_id, video_index=1, model_image=img_path,
                                       video_type=action_type, video_duration=video_fragment_duration, video_positive_prompt=prompt, video_negative_prompt=negative_prompt, video_url_v1="video_url_v1.mp4")
    elif action_type != "":
        # 没有提供提示词，根据type来生成
        # 对图片进行分析，获取模特图片信息
        model_image_info = AnalyseImageAgent().analyse_image(
            product=product, image_path=img_absolute_path)
        video_positive_prompt, video_negative_prompt, video_url = asyncio.run(i2v_strategy_chain.execute_chain(product=product, product_info=product_info,
                                                                                                               img_path=img_path, img_info=model_image_info,
                                                                                                               video_type=action_type, duration=video_fragment_duration,
                                                                                                               i2v_strategy=i2v_strategy, resolution={}))
        # 将视频url保存到video_fragment中
        video_data = get_url_data(video_url)
        with open(fragment_path, "wb") as f:
            f.write(video_data)
        video_fragment = VideoFragment(id=fragment_id, video_index=1, model_image=img_path,
                                       video_type=action_type, video_duration=video_fragment_duration, video_positive_prompt=video_positive_prompt, video_negative_prompt=video_negative_prompt, video_url_v1="video_url_v1.mp4")
    else:
        # 都没有提供，使用默认值
        action_type = "model_show"
        model_image_info = AnalyseImageAgent().analyse_image(
            product=product, image_path=img_path)
        video_positive_prompt, video_negative_prompt, video_url = asyncio.run(i2v_strategy_chain.execute_chain(product=product, product_info=product_info, img_path=img_absolute_path,
                                                                                                               img_info=model_image_info, video_type=action_type, duration=video_fragment_duration, i2v_strategy=i2v_strategy, resolution={}))
        # 将视频url保存到video_fragment中
        video_data = get_url_data(video_url)
        with open(fragment_path, "wb") as f:
            f.write(video_data)
        video_fragment = VideoFragment(id=fragment_id, video_index=1, model_image=img_path,
                                       video_type=action_type, video_duration=video_fragment_duration,
                                       video_positive_prompt=video_positive_prompt, video_negative_prompt=video_negative_prompt,
                                       video_url_v1=fragment_relative_path)

    return str(video_fragment)

# 4.预审


@ tool
def pre_review_material(user_id, material_path: str):
    """
    预审素材（素材可以是图片或视频），判断素材是否符合要求
    Args:
        material_path(str): 素材路径,一般为相对路径
    Returns:
        str: 素材预审结果
    """
    try:
        material_path = get_absolute_path_from_user_dir(
            user_id, material_path)
        text_input = None
        screenshot = ""
        result = process_media(
            media_file=material_path,
            MEDIASHIELD_GEMINI_API_KEY=conf.get(
                "MEDIASHIELD_GEMINI_API_KEY"),
            MEDIASHIELD_GPT_API_KEY=conf.get("MEDIASHIELD_GPT_API_KEY"),
            similarity_threshold=0.4,
            text_input=text_input,
            screenshot=screenshot
        )
        result = result["message"]
        return result["message"]
    except Exception as e:
        return f"预审素材失败: {e}"

    # 5。修改视频


def invoke_react_agent(user_id: str, chat_history: list[BaseMessage], overhead_information: dict, configurable: RunnableConfig):
    app = get_react_agent()
    result = asyncio.run(app.ainvoke(
        {"user_id": user_id, "chat_history": chat_history, "overhead_information": overhead_information}, config=configurable))
    return result
