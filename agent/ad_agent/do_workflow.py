# Standard library imports
from agent.ad_agent.pojo import get_last_human_message
from agent.ad_agent.pojo import ad_agent_chat_message2chat_message
from agent.ad_agent.pojo import AdAgentChatMessage
from agent.utils import get_time_id
from agent.ad_agent.m2v_workflow import ainvoke_m2v_workflow
from MediaShield.process import process_media
from agent.utils import get_url_data
from agent.mini_agent import AnalyseImageAgent
from agent.ad_agent.m2v_workflow import VideoFragment
import json
import os
import shutil
import uuid
from typing import Any, List, Optional
# Third-party imports
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, Interrupt, interrupt
from pydantic import BaseModel, Field

# Local imports
from agent.ad_agent.exception import AIError, HumanError
from agent.ad_agent.plan_m2v_modify_agent import M2VAgent
from agent.ad_agent.m2v_workflow import (
    GenerateVideoState,
    GenerateVideoStateJSONEncoder,
    get_m2v_workflow,
)
from agent.mini_agent import Classifier
from agent.third_part.moviepy_apply import concatenate_videos_from_urls
from agent.third_part.i2v import i2v_strategy_chain
from agent.third_part.video_effects import VideoTransitionType, video_transitions
from agent.utils import create_dir, temp_dir
from config import conf

# Environment setup
# os.environ["LANGSMITH_API_KEY"] = "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"
# os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# # Project name for organizing LangSmith traces
# os.environ["LANGSMITH_PROJECT"] = "m2v_agent"

"""
通过建议，专门在原来的基础上进行更新
"""

# 用户能收到的错误信息e1与用户不能收到的错误信息e2，e1是用户的输入有问题，e2是llm生成出问题
start_hint = """支持预审素材，生成或修改视频,生成视频片段
(预审素材：提供素材，素材需要为视频)
(生成视频：提供商品名称，商品信息，模特图片)
(修改视频：旁边输入要修改的视频对应的ID，然后输入建议)
(生成视频片段：提供商品名称，商品信息，模特图片，模特动作or提示词)"""


class ADAgentState(BaseModel):
    user_id: str = Field(default="", description="用户id")
    workflow_id: str = Field(default="", description="工作流id")
    workflow_state: Optional[GenerateVideoState] = Field(
        default=None, description="工作流状态")
    chat_history: list[AdAgentChatMessage] = Field(
        default=[], description="聊天历史,用于记录用户与agent的对话")
    overhead_information: dict = Field(
        default={}, description="额外信息,用于记录用户输入的模特图片，文档，文件")
    # generate_fragment
    video_fragment_list: List[VideoFragment] = Field(
        default=[], description="视频片段list")
    # pre_review_material
    pre_review_material_result_list: List[str] = Field(
        default=[], description="素材预审结果list")
    # modify
    modified_workflow_state: Optional[GenerateVideoState] = Field(
        default=None, description="修改后的工作流状态")
    update_operations: list[dict] = Field(
        default=[], description="更新操作(用json表示)")
    error_info: Optional[Any] = Field(
        default=None, description="错误信息")
    # result
    return_result_number: int = Field(
        default=0, description="返回的结果数量")


# think-action react


async def route_generate_or_modify(state: ADAgentState, config):
    """
    路由生成或修改
    """
    # 根据用户的输入，判断是生成还是修改，使用llm分类器
    classifier = Classifier(
        categories=["生成,创建视频(不带音频字幕，数字人)", "生成，创建视频(带音频字幕，不带数字人)", "生成，创建视频(带音频字幕，带数字人)", "修改，编辑视频", "生成，创建视频片段", "素材预审", "其他"])
    category = classifier.classify(state.chat_history[-1].content)
    if category == "生成,创建视频(不带音频字幕，数字人)":
        return "generate_video"
    elif category == "生成，创建视频(带音频字幕，不带数字人)":
        return "generate_video_with_audio"
    elif category == "生成，创建视频(带音频字幕，带数字人)":
        return "generate_video_with_audio_and_digital_human"
    elif category == "修改，编辑视频":
        return "modify"
    elif category == "生成，创建视频片段":
        return "generate_fragment"
    elif category == "素材预审":
        return "pre_review_material"
    elif category == "其他":
        return "other"
    else:
        raise ValueError("未知操作")

# 生成，创建视频(带音频字幕，不带数字人)


async def other(state: ADAgentState, config):
    """
    其他
    """
    state.chat_history.append(AdAgentChatMessage(
        role="assistant", type="text", content="未知操作，请选择一个agent支持的操作"))
    return {"chat_history": state.chat_history, "return_result_number": 1}


async def start_generate_video_with_audio(state: ADAgentState, config):
    """
    开始生成视频(带音频字幕，不带数字人)
    """

    pass


async def generate_video_with_audio(state: ADAgentState, config):
    pass


async def end_generate_video_with_audio(state: ADAgentState, config):
    pass


# 生成，创建视频(带音频字幕，带数字人)
async def start_generate_video_with_audio_and_digital_human(state: ADAgentState, config):
    """
    开始生成视频(带音频字幕，带数字人)
    """
    pass


async def generate_video_with_audio_and_digital_human(state: ADAgentState, config):
    pass


async def end_generate_video_with_audio_and_digital_human(state: ADAgentState, config):
    pass


# 素材预审
async def start_pre_review_material(state: ADAgentState, config):
    """
    素材预审
    """
    pass


async def pre_review_material(state: ADAgentState, config):
    """
    素材预审
    """
    pre_review_material_result_list = []
    for key, value in state.overhead_information.items():
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
    # 对视频进行预审
    return {"pre_review_material_result_list": pre_review_material_result_list}


#  generate_video

async def end_pre_review_material(state: ADAgentState, config):
    """
    结束素材预审
    """
    pre_review_material_content = ""
    for index, pre_review_material_result in enumerate(state.pre_review_material_result_list):
        pre_review_material_content += f"""素材{index + 1}
            的预审结果为{pre_review_material_result}"""

    state.chat_history.append(AdAgentChatMessage(
        role="assistant", type="text", content=pre_review_material_content))
    return {"chat_history": state.chat_history, "return_result_number": 1}


async def start_generate_video(state: ADAgentState, config):
    """
    开始生成
    """
    # 附加信息中的图片信息必定作为模特图片
    video_output_path = conf.get_path("m2v_workflow_result_dir")
    # llm从用户输入中提取商品名称、商品信息、模特图片、视频片段时长，没有则使用默认值(字符串),将其放入workflow_state中
    workflow_state = GenerateVideoState(id=get_time_id(
    ), product="", product_info="", model_images=[], video_output_path=video_output_path)
    m2v_agent = M2VAgent()
    m2v_agent.set_workflow_state(workflow_state)
    await m2v_agent.extract_generate_video_information(
        state.chat_history, state.overhead_information)
    return {"workflow_state": workflow_state}


async def gv_ainvoke_m2v_workflow(state: ADAgentState, config):
    """
    调用m2v_workflow
    """
    workflow_state = state.workflow_state
    if workflow_state is None:
        raise ValueError("workflow_state is None")
    # 调用工作流前的状态初始化
    product = workflow_state.product
    product_info = workflow_state.product_info
    model_images = workflow_state.model_images
    video_fragment_duration = workflow_state.video_fragment_duration
    video_output_path = workflow_state.video_output_path
    id = workflow_state.id
    video_positive_prompt = workflow_state.video_positive_prompt
    video_negative_prompt = workflow_state.video_negative_prompt
    workflow_dir = os.path.join(video_output_path, id)

    os.makedirs(workflow_dir, exist_ok=True)
    result: GenerateVideoState = await ainvoke_m2v_workflow(user_id=state.user_id, id=id, product=product, product_info=product_info,
                                                            model_images=model_images, video_fragment_duration=video_fragment_duration, video_output_path=workflow_dir, positive_prompt=video_positive_prompt, negative_prompt=video_negative_prompt)
    state.workflow_state = result
    return {"workflow_state": state.workflow_state}


async def end_generate_video(state: ADAgentState, config):
    """
    结束生成
    """
    video_content = ""
    for index, video_fragment in enumerate(state.workflow_state.video_fragments):
        video_content += f"""片段{index + 1}：{video_fragment.action_type}
            ，模特序号为{int(index/2)+1},视频时长为{video_fragment.video_duration}秒\n"""
    state.chat_history.append(
        AdAgentChatMessage(role="assistant", type="text", content=f"""视频生成完成,使用的生成策略是{state.workflow_state.i2v_strategy}，视频内容：{video_content}"""))
    state.chat_history.append(AdAgentChatMessage(role="user", type="video", content="", file_path=os.path.join(
        state.workflow_state.video_output_path, state.workflow_state.id, "video_url_v1.mp4")))
    return {"chat_history": state.chat_history, "return_result_number": 2}

#  generate_fragment


async def start_generate_fragment(state: ADAgentState, config):
    """
    开始生成片段
    """
    pass


async def generate_fragment(state: ADAgentState, config):
    """
    生成片段
    根据模特图片，是否提供提示词，视频类型，视频时长，生成视频片段
    """
    # 获取以上信息
    video_output_path = conf.get_path("m2v_workflow_result_dir")
    model_images = [value for key, value in state.overhead_information.items(
    ) if key.startswith("img_")]
    m2v_agent = M2VAgent()
    m2v_agent.set_workflow_state(state.workflow_state)
    content: dict = await m2v_agent.extract_generate_fragment_information(
        state.chat_history)
    product = content["product"]
    product_info = content["product_info"]
    video_fragment_duration = content["video_fragment_duration"]
    action_type = content["action_type"]
    prompt = content["prompt"]
    negative_prompt = content["negative_prompt"]
    i2v_strategy = content["i2v_strategy"]
    for model_image in model_images:
        fragment_id = get_time_id()
        # action_type: str = Field(default="model_show",
        #                         description="视频类型(model_show, model_walk)")
        # # 以下是可以改变的地方
        # video_positive_prompt: str = Field(default="", description="视频正向prompt")
        # video_negative_prompt: str = Field(default="", description="视频负向prompt")
        # 创建dir for video_fragment
        with create_dir(video_output_path, name=fragment_id) as result_dir:
            video_fragment = None
            if prompt != "":
                # 有提供提示词,使用提示词来生成视频片段
                video_url = await i2v_strategy_chain.execute_chain_with_prompt(img_path=model_image, video_positive_prompt=prompt, video_negative_prompt=negative_prompt, duration=video_fragment_duration, i2v_strategy=i2v_strategy, resolution={})
                video_data = get_url_data(video_url)
                with open(os.path.join(result_dir, "video_url_v1.mp4"), "wb") as f:
                    f.write(video_data)
                video_fragment = VideoFragment(id=fragment_id, video_index=1, model_image=model_image,
                                               action_type=action_type, video_duration=video_fragment_duration, video_positive_prompt=prompt, video_negative_prompt=negative_prompt, video_url_v1="video_url_v1.mp4")
            elif action_type != "":
                # 没有提供提示词，根据type来生成
                # 对图片进行分析，获取模特图片信息
                model_image_info = AnalyseImageAgent().analyse_image(
                    product=product, image_path=model_image)
                video_positive_prompt, video_negative_prompt, video_url = await i2v_strategy_chain.execute_chain(product=product, product_info=product_info,
                                                                                                                 img_path=model_image, img_info=model_image_info, action_type=action_type, duration=video_fragment_duration, i2v_strategy=i2v_strategy)
                # 将视频url保存到video_fragment中
                video_data = get_url_data(video_url)
                with open(os.path.join(result_dir, "video_url_v1.mp4"), "wb") as f:
                    f.write(video_data)
                video_fragment = VideoFragment(id=fragment_id, video_index=1, model_image=model_image,
                                               action_type=action_type, video_duration=video_fragment_duration, video_positive_prompt=video_positive_prompt, video_negative_prompt=video_negative_prompt, video_url_v1="video_url_v1.mp4")
            else:
                # 都没有提供，使用默认值
                action_type = "model_show"
                model_image_info = AnalyseImageAgent().analyse_image(
                    product=product, image_path=model_image)
                video_positive_prompt, video_negative_prompt, video_url = await i2v_strategy_chain.execute_chain(product=product, product_info=product_info,
                                                                                                                 img_path=model_image, img_info=model_image_info, action_type=action_type, duration=video_fragment_duration, i2v_strategy=i2v_strategy)
                # 将视频url保存到video_fragment中
                video_data = get_url_data(video_url)
                with open(os.path.join(result_dir, "video_url_v1.mp4"), "wb") as f:
                    f.write(video_data)
                video_fragment = VideoFragment(id=fragment_id, video_index=1, model_image=model_image,
                                               action_type=action_type, video_duration=video_fragment_duration, video_positive_prompt=video_positive_prompt, video_negative_prompt=video_negative_prompt, video_url_v1="video_url_v1.mp4")

            if video_fragment is not None:
                video_fragment.i2v_strategy = i2v_strategy
                state.video_fragment_list.append(video_fragment)
    return {"video_fragment_list": state.video_fragment_list}


async def end_generate_fragment(state: ADAgentState, config):
    """
    结束生成片段
    """
    video_output_path = conf.get_path("m2v_workflow_result_dir")
    for index, video_fragment in enumerate(state.video_fragment_list):
        fragment_content = f"""片段{index + 1}生成完成,使用的生成策略是keling，视频内容：{video_fragment.action_type}，模特序号为{int(index/2)+1},视频时长为{video_fragment.video_duration}秒,
            使用的正面提示词为({video_fragment.video_positive_prompt}),使用的负面提示词为({video_fragment.video_negative_prompt})\n"""
        state.chat_history.append(AdAgentChatMessage(
            role="assistant", type="text", content=fragment_content))
        state.return_result_number += 1
        video_url = os.path.join(
            video_output_path, video_fragment.id, "video_url_v1.mp4")
        state.chat_history.append(AdAgentChatMessage(
            role="assistant", type="video", content="", file_path=video_url))
        state.return_result_number += 1
    return {"chat_history": state.chat_history, "return_result_number": state.return_result_number}


async def gf_ainvoke_m2v_workflow(state: ADAgentState, config):
    """
    调用m2v_workflow
    """
    workflow_state = state.workflow_state
    if workflow_state is None:
        raise ValueError("workflow_state is None")


async def start_modify(state: ADAgentState, config):
    """
    开始修改,判断是否缺少某些条件
    """

    # 通过用户的对话来判断需要进行修改的workflow_state
    pass


async def m_load_state(state: ADAgentState, config):
    # state.json在temp_dir/id/state.json
    m2v_workflow_result_dir_path = config["configurable"]["result_dir"]
    m2v_workflow_dir = os.path.join(
        m2v_workflow_result_dir_path, state.workflow_id)
    state_path = os.path.join(m2v_workflow_dir, "state.json")
    with open(state_path, "r") as f:
        state.workflow_state = GenerateVideoState.model_validate_json(f.read())
    if state.workflow_state is None:
        raise ValueError("workflow_state is None")
    return {"workflow_state": state.workflow_state}

# 用户输入建议，agent针对建议+当前状态 -> 更新操作(多个更新操作list[str]) -> 更新状态


async def m_generate_operations(state: ADAgentState, config):
    """
    生成更新操作
    """
    # 初始化
    if state.workflow_state is None:
        raise ValueError("workflow_state is None")

    # 创建新的 m2v_agent 实例
    m2v_agent = M2VAgent()

    if state.error_info is None:
        m2v_agent.set_workflow_state(state.workflow_state)

        update_operations = await m2v_agent.generate_update_operations(
            chat_history=ad_agent_chat_message2chat_message(state.chat_history))
        return {"update_operations": update_operations}
    elif isinstance(state.error_info, AIError):
        # 根据执行时错误信息重新生成suggestion与当前执行状态update_operations
        update_operations = await m2v_agent.regenerate_update_operations(
            get_last_human_message(state.chat_history), state.error_info.message, state.update_operations)
        return {"update_operations": update_operations}


async def m_execute_operations(state: ADAgentState, config):
    # 在执行前创建一个虚拟的workflow_state
    """
    执行更新操作
    在更新操作之前，创建复制版，之后所有的操作都基于这个复制版
    """
    # 初始化
    # 数据校验
    result_dir = config["configurable"]["result_dir"]
    if state.workflow_state is None:
        raise ValueError("workflow_state is None")
    update_operations = state.update_operations
    # 创建虚拟环境
    modified_workflow_id = str(uuid.uuid4())
    virtual_workflow_state = state.workflow_state._copy(
        result_dir, result_dir, modified_workflow_id)

    # 创建新的 m2v_agent 实例
    m2v_agent = M2VAgent()
    m2v_agent.set_workflow_state(virtual_workflow_state)

    try:
        workflow_state = await m2v_agent.invoke(update_operations)
        return {"workflow_state": workflow_state, "error_info": None, "modified_workflow_id": modified_workflow_id, "modified_workflow_state": virtual_workflow_state}
    except HumanError as e:
        # 调用失败时返回错误信息，用户收到错误信息后需要重新提供建议
        # 根据update_operations执行情况与humanerror生成新的suggestion
        return {"error_info": e}
    except AIError as e:
        # 根据异常让llm进行修正
        return {"error_info": e}


async def supply_information(state: ADAgentState, config):
    """
    人机交互：补充信息
    """
    # 初始化
    assert isinstance(state.error_info, HumanError)
    hint = f"{state.error_info.message},请补充信息"
    # 根据错误信息向用户提出建议，让用户重新输入建议
    user_input = interrupt(hint)
    state.chat_history.append(AdAgentChatMessage(
        role="user", type="text", content=user_input, file_path=""))
    # 返回用户输入
    return {"chat_history": state.chat_history}


def route_error_info(state: ADAgentState, config):
    """
    路由错误信息
    """
    error_info = state.error_info
    if error_info is None:
        return "none_error"
    elif isinstance(error_info, HumanError):
        return "human_error"
    elif isinstance(error_info, AIError):
        return "ai_error"
    else:
        raise ValueError("error_info is not HumanError or AIError")


# 对视频进行评估


async def m_evaluate_video_fragments(state: ADAgentState, config):
    """
    评估视频片段
    """
    # 1.评估点1：Motion Smoothness
    pass

# 对视频进行重新拼接


async def m_video_stitching(state: ADAgentState, config):
    """
    视频拼接,添加转场效果
    在temp_dir下创建一个文件夹，用于存储拼接后的临时视频，之后将这个文件夹删除
    """
    workflow_state = state.modified_workflow_state
    if workflow_state is None:
        raise ValueError("workflow_state is None")
    # 根据特效来进行合并
    with temp_dir(dir_path=conf.get_path("temp_dir"), name=str(uuid.uuid4())) as temp_concatenate_dir:
        now_batch_video_list: list = [None]*len(workflow_state.video_fragments)
        now_video_effect_index = 0

        for i, video_fragment in enumerate(workflow_state.video_fragments):
            # 根据index来添加到list中的指定为止
            now_batch_video_list[video_fragment.video_index -
                                 1] = os.path.join(config["configurable"]["result_dir"], workflow_state.id, video_fragment.video_url_v1)

        while len(now_batch_video_list) > 1:
            output_path = os.path.join(
                temp_concatenate_dir, f"concat_{now_video_effect_index}_{now_video_effect_index+1}.mp4")
            if now_video_effect_index >= len(workflow_state.output_video.transition_effect):
                now_video_effect = VideoTransitionType.CONCATENATE
            else:
                now_video_effect = workflow_state.output_video.transition_effect[
                    now_video_effect_index]

            video_transitions(
                now_batch_video_list[0], now_batch_video_list[1], output_path, now_video_effect)
            now_batch_video_list.pop(1)
            now_batch_video_list[0] = output_path
            now_video_effect_index += 1

        video_url_v1 = os.path.join(
            config["configurable"]["result_dir"], workflow_state.id, "video_url_v1.mp4")
        # 将now_batch_video_list中的唯一一个文件copy到
        shutil.copy(now_batch_video_list[-1], video_url_v1)
        # 状态更新
        workflow_state.output_video.video_url_v1 = "video_url_v1.mp4"
        workflow_state.output_video.transition_effect = workflow_state.transition_effect
        workflow_state.output_video.bgm = workflow_state.bgm
    return {"workflow_state": workflow_state}


async def m_save_state(state: ADAgentState, config):
    """
    保存状态,认为没有问题时则将modified_workflow_state拷贝回workflow_state中
    """
    if state.modified_workflow_state is None:
        # 没有进行任何修改
        pass
    else:
        result_dir = config["configurable"]["result_dir"]
        state.workflow_state = state.modified_workflow_state
        with open(os.path.join(result_dir, state.modified_workflow_state.id, "state.json"), "w") as f:
            json.dump(state.workflow_state.model_dump(),
                      f, cls=GenerateVideoStateJSONEncoder)


async def end_modify(state: ADAgentState, config):
    """
    结束修改
    """
    state.chat_history.append(AdAgentChatMessage(
        role="assistant", type="text", content="视频修改完成,修改后的视频id为" + state.workflow_state.id))
    state.return_result_number += 1
    state.chat_history.append(AdAgentChatMessage(
        role="assistant", type="video", content="", file_path=os.path.join(
            config["configurable"]["result_dir"], state.workflow_state.id, "video_url_v1.mp4")))
    state.return_result_number += 1
    return {"chat_history": state.chat_history, "return_result_number": state.return_result_number}


def get_do_workflow_app():
    """
    获取app
    """
    graph = StateGraph(ADAgentState)
    # 生成视频
    graph.add_node("other", other)
    graph.add_node("start_generate_video_with_audio",
                   start_generate_video_with_audio)
    graph.add_node("start_generate_video_with_audio_and_digital_human",
                   start_generate_video_with_audio_and_digital_human)
    graph.add_node("start_generate_video", start_generate_video)
    graph.add_node("gv_ainvoke_m2v_workflow", gv_ainvoke_m2v_workflow)
    graph.add_node("start_modify", start_modify)
    graph.add_node("m_load_state", m_load_state)
    graph.add_node("m_generate_operations", m_generate_operations)
    graph.add_node("m_execute_operations", m_execute_operations)
    graph.add_node("supply_information", supply_information)
    graph.add_node("m_video_stitching", m_video_stitching)
    graph.add_node("m_evaluate_video_fragments", m_evaluate_video_fragments)
    graph.add_node("m_save_state", m_save_state)
    graph.add_node("end_modify", end_modify)
    graph.add_node("end_generate_video", end_generate_video)
    graph.add_node("end_generate_fragment", end_generate_fragment)
    graph.add_node("gf_ainvoke_m2v_workflow", gf_ainvoke_m2v_workflow)
    # 生成片段
    graph.add_node("start_generate_fragment", start_generate_fragment)
    graph.add_node("generate_fragment", generate_fragment)
    # 素材预审
    graph.add_node("start_pre_review_material", start_pre_review_material)
    graph.add_node("pre_review_material", pre_review_material)
    graph.add_node("end_pre_review_material", end_pre_review_material)

    graph.add_conditional_edges(START, route_generate_or_modify, {
        "generate_video": "start_generate_video",
        "generate_video_with_audio": "start_generate_video_with_audio",
        "generate_video_with_audio_and_digital_human": "start_generate_video_with_audio_and_digital_human",
        "modify": "start_modify",
        "generate_fragment": "start_generate_fragment",
        "pre_review_material": "start_pre_review_material",
        "other": "other"
    })
    # 素材预审
    graph.add_edge("start_pre_review_material", "pre_review_material")
    graph.add_edge("pre_review_material", "end_pre_review_material")
    graph.add_edge("end_pre_review_material", END)

    # 生成视频
    graph.add_edge("start_generate_video", "gv_ainvoke_m2v_workflow")
    graph.add_edge("gv_ainvoke_m2v_workflow", "end_generate_video")
    graph.add_edge("end_generate_video", END)

    # 生成片段
    graph.add_edge("start_generate_fragment", "generate_fragment")
    graph.add_edge("generate_fragment", "end_generate_fragment")
    graph.add_edge("end_generate_video", END)

    # 修改视频
    graph.add_edge("start_modify", "m_load_state")
    graph.add_edge("m_load_state", "m_generate_operations")
    graph.add_edge("m_generate_operations", "m_execute_operations")
    graph.add_conditional_edges("m_execute_operations", route_error_info, {
        "none_error": "m_evaluate_video_fragments",
        "human_error": "supply_information",
        "ai_error": "m_execute_operations"
    })
    graph.add_edge("m_evaluate_video_fragments", "m_video_stitching")
    graph.add_edge("m_video_stitching", "m_save_state")
    graph.add_edge("m_save_state", "end_modify")
    graph.add_edge("end_modify", END)

    # 其他
    graph.add_edge("other", END)
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


do_workflow_app = get_do_workflow_app()


async def ainvoke_m2v_agent(user_id: str, workflow_id: str, chat_history: List[BaseMessage], overhead_information: dict):
    """
    调用m2v_agent

    """
    app = get_do_workflow_app()
    configuration: RunnableConfig = {"configurable": {
        "thread_id": user_id}}
    result = await app.ainvoke({"workflow_id": workflow_id, "chat_history": chat_history,
                                "overhead_information": overhead_information}, config=configuration,
                               stream_mode="values")
    snapshot = app.get_state(config=configuration)
    while snapshot.next:
        # 中断事件
        if "__interrupts__" in result:
            interrupt_info: Interrupt = result["__interrupts__"][-1]
            hint = interrupt_info.value
            suggestion = input(hint)
            result = await app.ainvoke(
                Command(update={"suggestion": suggestion}), config=configuration)
    return result
