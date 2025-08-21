from agent.llm import create_azure_gpt5_llm
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from pydantic import Field
from typing import Annotated
from agent.mini_agent import TranslatorAgent
import asyncio
import json
from MediaShield.process import process_media
from agent.utils import is_image_file, is_video_file
from config import conf
from langgraph.prebuilt import InjectedState
from agent.ad_agent.art.material_library import material_librarys
from langchain_core.runnables import Runnable, RunnableConfig


@tool
def get_material_from_link(link: Annotated[str, Field(description="链接")],
                           config: RunnableConfig):
    """
    根据链接获取素材
    """
    user_id = config["configurable"]["user_id"]
    result = asyncio.run(
        material_librarys[user_id].crawl_material_by_link(link))
    if result:
        return "素材获取成功，请在素材库中查看"
    else:
        return "素材获取失败，请检查链接是否有效"


@tool
def upload_material(config: RunnableConfig):
    """
    上传素材,将用户上传的图片，文档，文件，上传到素材库中
    """
    user_id = config["configurable"]["user_id"]
    overhead_information = config["configurable"]["overhead_information"]
    for key, value in overhead_information.items():
        material_path = value["content"]
        # 根据后缀判断素材类型
        if material_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
            material_librarys[user_id].append_material_without_analysis(
                material_path=material_path, title="用户上传的图片")
        # 假如文件是pdf等等文件结尾的，则将其已pdf_{number}加入到overhead_information中
        elif material_path.endswith((".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xls", ".xlsx", ".json")):
            material_librarys[user_id].append_material_without_analysis(
                material_path=material_path, title="用户上传的文档")
        elif material_path.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv")):
            material_librarys[user_id].append_material_without_analysis(
                material_path=material_path, title="用户上传的视频")
        # 假如文件是其他文件结尾的，则将其已file_{number}加入到overhead_information中
        else:
            material_librarys[user_id].append_material_without_analysis(
                material_path=material_path, title="用户上传的其他文件")

    return "素材上传成功"


@tool
def get_material_in_web(keyword: Annotated[str, Field(description="关键词")],
                        config: RunnableConfig):
    """
    根据关键词在网上获取素材
    """
    # 一切在工具内的都为英文
    keyword = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=keyword)
    user_id = config["configurable"]["user_id"]
    asyncio.run(
        material_librarys[user_id].crawl_material_in_web(keyword))
    return "素材爬取成功,请在素材库中查看"


@tool
def pre_review_material_in_material_library(material_id: Annotated[str, Field(description="需要预审的素材id,素材库中的素材id的格式为{number}例如1，用户上传的素材id的格式为#{number}例如#1")],
                                            config: RunnableConfig):
    """
    预审素材,预审素材库中的素材，
    """
    user_id = config["configurable"]["user_id"]
    material_path = material_librarys[user_id].get_material_by_id(
        material_id)
    if material_path is None:
        return f"素材{material_id}不存在"
    if not (is_image_file(material_path) or is_video_file(material_path)):
        return f"素材{material_id}不是图片或视频"
    result = process_media(
        media_file=material_path,
        MEDIASHIELD_GEMINI_API_KEY=conf.get(
            "MEDIASHIELD_GEMINI_API_KEY"),
        MEDIASHIELD_GPT_API_KEY=conf.get("MEDIASHIELD_GPT_API_KEY"),
        similarity_threshold=0.4,
        text_input=None,
        screenshot=None
    )
    return result


@tool
def get_material_in_material_library(require: Annotated[str, Field(description="需求，具体需求，例如对素材的具体要求，例如：蓝牙耳机")],
                                     config: RunnableConfig):
    """
    根据需求从素材库中获取相关的素材
    """
    user_id = config["configurable"]["user_id"]
    result = material_librarys[user_id].select_appropriate_material(require)
    return result


@tool
def pre_review_material_in_user_input(material_id_list: Annotated[list[str], Field(description="需要进行预审的素材id列表,素材库中的素材id的格式为{number}例如1，用户上传的素材id的格式为#{number}例如#1")],
                                      config: RunnableConfig):
    """
    预审素材，既可以预审用户输入的图片，文档，文件,也可以对素材库中的素材进行预审，一般来说用户有进行图片上传并且提出预审需求时会对用户上传的图片进行预审
    """
    user_id = config["configurable"]["user_id"]
    overhead_information = config["configurable"]["overhead_information"]
    result = "预审结果如下：\n"
    if len(material_id_list) > 0:
        for material_id in material_id_list:
            if material_id.startswith("image_"):
                material = overhead_information[material_id]
                if material is None:
                    result += f"您上传的图片{material_id.split('_')[1]}不存在\n"
                else:
                    pre_review_result = process_media(
                        media_file=material["content"],
                        MEDIASHIELD_GEMINI_API_KEY=conf.get(
                            "MEDIASHIELD_GEMINI_API_KEY"),
                        MEDIASHIELD_GPT_API_KEY=conf.get(
                            "MEDIASHIELD_GPT_API_KEY"),
                        similarity_threshold=0.4,
                        text_input=None,
                        screenshot=None
                    )
                    result += f"您上传的图片{material_id.split('_')[1]}预审成功,预审结果为{
                        pre_review_result}\n"
            elif material_id.startswith("video_"):
                material = overhead_information[material_id]
                if material is None:
                    result += f"您上传的视频{material_id.split('_')[1]}不存在\n"
                else:
                    pre_review_result = process_media(
                        media_file=material["content"],
                        MEDIASHIELD_GEMINI_API_KEY=conf.get(
                            "MEDIASHIELD_GEMINI_API_KEY"),
                        MEDIASHIELD_GPT_API_KEY=conf.get(
                            "MEDIASHIELD_GPT_API_KEY"),
                        similarity_threshold=0.4,
                        text_input=None,
                        screenshot=None
                    )
                    result += f"您上传的视频{material_id.split('_')[1]}预审成功,预审结果为{
                        pre_review_result}\n"
            else:
                material = material_librarys[user_id].get_material_by_id(
                    material_id)
                if material is None:
                    result += f"素材{material_id}不存在\n"
                else:
                    pre_review_result = process_media(
                        media_file=material.material_path,
                        MEDIASHIELD_GEMINI_API_KEY=conf.get(
                            "MEDIASHIELD_GEMINI_API_KEY"),
                        MEDIASHIELD_GPT_API_KEY=conf.get(
                            "MEDIASHIELD_GPT_API_KEY"),
                        similarity_threshold=0.4,
                        text_input=None,
                        screenshot=None
                    )
                    result += f"素材库中的素材{material_id}预审成功,预审结果为{pre_review_result}\n"

    return result


def return_material_agent(user_id: str):
    return  create_react_agent(
            name="material_agent",
            model=create_azure_gpt5_llm(),
            tools=[get_material_from_link, upload_material, get_material_in_web,
                   pre_review_material_in_material_library, pre_review_material_in_user_input],
            prompt=(
                "你是一个素材管理代理,你负责根据用户的需求管理素材,例如根据用户的需求从网上获取素材，上传素材，预审素材等"
            ),
        )