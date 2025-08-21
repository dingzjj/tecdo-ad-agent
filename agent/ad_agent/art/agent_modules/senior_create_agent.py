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


@tool(description="创建视频脚本,广告视频脚本")
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

    # 将其保存到overhead_information中
    user_id = config["configurable"]["user_id"]
    material_id = material_librarys[user_id].append_material_without_analysis(
        material_path=output_path, title=positive_prompt)
    return f"使用图片{image_id},{usage_feedback},生成的图片id为{f'{material_id}'}"


def return_senior_create_agent(user_id: str, expert_knowledge_prompt: str):
    return create_react_agent(
        name="senior_create_agent",
        model=create_azure_gpt5_llm(),
        tools=[create_image_by_t2i, create_video_by_t2v,
               create_video_by_i2v, create_image_by_i2i, create_script],
        prompt=(
            f"""你是一名高级创作代理人员。可以完成广告，宣传短片等大型创作任务。\n目前拥有的素材信息为{
                material_librarys[user_id].get_all_material_info()}\n可以参考以下任务:\n {expert_knowledge_prompt}"""
        ),
    )
