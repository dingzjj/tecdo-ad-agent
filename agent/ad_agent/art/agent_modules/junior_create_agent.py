from langgraph.prebuilt import create_react_agent
from agent.llm import create_azure_gpt5_llm
from typing import Optional
from agent.ad_agent.art.material_library import Material, material_librarys
from langchain_core.messages import ToolMessage
from langgraph.types import Command
import asyncio
import json
from agent.third_part.multimodel_generation_model.kernel import model_factory
from pydantic import Field
from typing import Annotated
from agent.mini_agent import TranslatorAgent
from agent.ad_agent.art.agent_modules.prompt import CREATE_SCRIPT_PROMPT
from langchain_core.tools import tool

# 低级创作代理人员 可以完成单个图片，单个视频创作任务，但每次创作任务都弹出提示框，询问是否需要继续创作
# 提示1:图片与需求不符， 提示2:图片风格

from langgraph.types import Command, interrupt
from langchain_core.runnables import Runnable, RunnableConfig
from agent.ad_agent.art.agent_modules.pojo import InterruptInAdAgent

from langchain_core.messages import AIMessage


@tool(description="Provide a description of the image and use the text-to-image model to create the image.")
def create_image_by_t2i(require: Annotated[str, Field(description="For the specific requirements of the picture, please provide the background, characters and actions within the picture.")],
                        config: RunnableConfig):
    """
    提供对图片的描述，使用text-to-image模型创建图片
    """
    # 中文
    # 根据已有模型询问风格来补充需求

    more_require = interrupt(InterruptInAdAgent(
        type="tool_call", message_list=[AIMessage(content=model_factory.return_supply_require(require, "text to image"))]))
    require = require + f"and {more_require}"

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
    return f"{usage_feedback},the generated image id is {f'{material_id}'}"


@tool(description="Provide a description of the video and use the text-to-video model to create the video.")
def create_video_by_t2v(require: Annotated[str, Field(description="For the specific requirements of the video, please provide the background, characters and actions within the video.")],
                        config: RunnableConfig):
    """
    提供对视频的描述，使用text-to-video模型创建视频
    """
    more_require = interrupt(InterruptInAdAgent(
        type="tool_call", message_list=[AIMessage(content=model_factory.return_supply_require(require, "text to video"))]))
    require = require + f"and {more_require}"

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
    more_require = interrupt(InterruptInAdAgent(
        type="tool_call", message_list=[AIMessage(content=model_factory.return_supply_require(require, "image to video"))]))
    require = require + f"and {more_require}"

    if image_id.startswith("image"):
        # 使用附加信息上的进行创作
        overhead_information = config["configurable"]["overhead_information"]
        image = overhead_information.get(image_id)
        if image is None:
            return f"Image {image_id} does not exist."
        image_path = image["content"]
    else:
        # 使用素材库上的进行创作
        image: Optional[Material] = material_librarys[config["configurable"]["user_id"]
                                                      ].get_material_by_id(image_id)

        # 从overhead_information中取出指定ID对应的图片
        if image is None:
            return f"Image {image_id} does not exist."
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
    more_require = interrupt(InterruptInAdAgent(
        type="tool_call", message_list=[AIMessage(content=model_factory.return_supply_require(require, "image to image"))]))
    require = require + f",{more_require}"

    if image_id.startswith("image"):
        # 使用附加信息上的进行创作
        overhead_information = config["configurable"]["overhead_information"]
        image = overhead_information.get(image_id)
        if image is None:
            return f"Image {image_id} does not exist."
        image_path = image["content"]
    else:
        # 使用素材库上的进行创作
        image: Optional[Material] = material_librarys[config["configurable"]["user_id"]
                                                      ].get_material_by_id(image_id)

        # 从overhead_information中取出指定ID对应的图片
        if image is None:
            return f"Image {image_id} does not exist."
        image_path = image.material_path

    model_id = model_factory.choose_model_by_specific_function(
        require, "image to image")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(image_path=image_path, positive_prompt=require))
    # 将其保存到overhead_information中
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=require)
    return f"Using image {image_id},{usage_feedback},the generated image id is {f'{material_id}'}"


def return_junior_create_agent():
    return create_react_agent(
        name="junior_create_agent",
        model=create_azure_gpt5_llm(),
        tools=[create_image_by_t2i, create_video_by_t2v,
               create_video_by_i2v, create_image_by_i2i],
        prompt=(
            "You are a junior creative agent. You can complete single image and single video creation tasks."
        ),
    )
