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


@tool
def create_script(require: Annotated[str, Field(description="需求，具体需求，例如对脚本的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                  state: Annotated[dict, InjectedState]):
    """
    创建广告视频脚本
    """
    llm = create_azure_gpt5_llm()
    response = llm.invoke([
        SystemMessage(
            content=CREATE_SCRIPT_PROMPT),
        HumanMessage(
            content=f"{require}")
    ])
    return response.content


@tool
def create_image_by_t2i(require: Annotated[str, Field(description="需求，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        state: Annotated[dict, InjectedState]):
    """
    提供对图片的描述，使用text-to-image模型创建图片
    """
    # 一切在工具内的都为英文
    require = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=require)
    overhead_information = state["overhead_information"]
    # 获取最大id
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to image")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(positive_prompt=require))
    # 输出的信息是生成 所用的提示词 + 图片地址(使用虚拟路径)
    max_id = max(int(key.split("_")[1]) for key in overhead_information.keys())
    return Command(
        update={
            "overhead_information": {
                f"#image_{max_id + 1}": {
                    "content": output_path,
                    "description": f"使用提示词{require}生成图片"
                }
            },
            "message": [ToolMessage(
                content=f"生成图片成功,所用的提示词为{usage_feedback},生成的图片id为{f'#image_{max_id + 1}'}")
            ]
        }
    )


@tool
def create_video_by_t2v(require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        state: Annotated[dict, InjectedState]):
    """
    提供对视频的描述，使用text-to-video模型创建视频
    """

    # 一切在工具内的都为英文
    require = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=require)
    overhead_information = state["overhead_information"]
    model_id = model_factory.choose_model_by_specific_function(
        require, "text to video")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback, output_path = asyncio.run(
        model.generate(positive_prompt=require))
    # 输出的信息是生成 所用的提示词 + 视频地址(使用虚拟路径)
    max_id = max(int(key.split("_")[1]) for key in overhead_information.keys())
    return Command(
        update={
            "overhead_information": {
                f"#video_{max_id + 1}": {
                    "content": output_path,
                    "description": f"使用提示词{require}生成视频"
                }
            },
            "message": [ToolMessage(
                content=f"生成图片成功,所用的提示词为{usage_feedback},生成的图片id为{f'#image_{max_id + 1}'}")
            ]
        }
    )


@tool
def create_video_by_i2v(require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        image_id: Annotated[str, Field(description="图片id，例如：#image_1")],
                        state: Annotated[dict, InjectedState]) -> Command:
    """
    在需求中指定所用的图片id，使用image-to-video模型创建视频
    """
    # 一切在工具内的都为英文
    require = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=require)

    overhead_information = state["overhead_information"]
    # 从overhead_information中取出指定ID对应的图片
    image = overhead_information.get(image_id)
    if image is None:
        return f"图片{image_id}不存在"
    model_id = model_factory.choose_model_by_specific_function(
        require, "image to video")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback = f"使用图片{image_id}生成视频,所用的提示词为{require}"
    output_path = asyncio.run(
        model.generate(image_path=image["content"], positive_prompt=require))

    # 将其保存到overhead_information中
    # 获取最大id
    max_id = max(int(key.split("_")[1]) for key in overhead_information.keys())
    return Command(
        update={
            "overhead_information": {
                f"#video_{max_id + 1}": {
                    "content": output_path,
                    "description": f"使用图片{image_id}生成视频,所用的提示词为{require}"
                }
            },
            "message": [ToolMessage(
                content=f"生成视频成功,所用的提示词为{usage_feedback},生成的视频id为{f'#video_{max_id + 1}'}")
            ]
        }
    )


@tool
def create_image_by_i2i(positive_prompt: Annotated[str, Field(description="正向提示词，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
                        image_id: Annotated[str, Field(description="图片id，例如：#image_1")],
                        state: Annotated[dict, InjectedState]):
    """
    在需求中指定所用的图片id，使用image-to-image模型创建图片
    功能：1.生成某商品的多视角图片 2.对商品图片背景进行修改
    """
    # 一切在工具内的都为英文
    positive_prompt = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=positive_prompt)

    overhead_information = state["overhead_information"]
    # 从overhead_information中取出指定ID对应的图片
    image = overhead_information.get(image_id)
    if image is None:
        return f"图片{image_id}不存在"
    model_id = model_factory.choose_model_by_specific_function(
        positive_prompt, "image to image")
    model = model_factory.get_model_by_id(model_id)
    usage_feedback = f"使用图片{image_id}生成图片,所用的提示词为{positive_prompt}"

    output_path = asyncio.run(
        model.generate(image_path=image["content"], positive_prompt=positive_prompt))

    # 将其保存到overhead_information中
    # 获取最大id
    max_id = max(int(key.split("_")[1]) for key in overhead_information.keys())
    return Command(
        update={
            "overhead_information": {
                f"#image_{max_id + 1}": {
                    "content": output_path,
                    "description": f"使用图片{image_id}生成图片,所用的提示词为{positive_prompt}"
                }
            },
            "message": [ToolMessage(
                content=f"生成图片成功,所用的提示词为{usage_feedback},生成的图片id为{f'#image_{max_id + 1}'}")
            ]
        }
    )


creation_agent = create_react_agent(
    model=create_azure_gpt5_llm(),
    tools=[create_image_by_t2i, create_video_by_t2v,
           create_video_by_i2v, create_image_by_i2i, create_script],
    prompt=(
        "你是一个创作agent,你负责根据用户的需求生成图片或视频或脚本"
    ),
)
