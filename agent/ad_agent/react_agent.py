# # 采用reAct框架 不断的调工具 - 直到得出结果（需要工具输出的src比较完善）
# import asyncio
# import json
# import os
# import uuid
# from typing import Annotated, Dict, List

# from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
# from langchain_core.tools import tool
# from langgraph.prebuilt import create_react_agent
# from pydantic import BaseModel, Field, root_validator
# from pydantic.v1 import tools

# from MediaShield.process import process_media
# from agent.ad_agent.prompt import (
#     AD_AGENT_HUMAN_PROMPT_cn,
#     AD_AGENT_SYSTEM_PROMPT_cn,
#     REACT_AGENT_SYSTEM_PROMPT_cn,
# )
# from agent.llm import create_azure_gpt5_llm
# from agent.ad_agent.art.material_library import MaterialLibrary, material_librarys
# from agent.mini_agent import (
#     GenerateVideoPromptAgent,
#     TranslatorAgent,
# )
# from agent.third_part.multimodel_generation_model.kernel import model_factory
# from agent.utils import (
#     is_image_file,
#     is_video_file,
# )
# from config import conf, logger

# # 设置环境变量
# os.environ["LANGSMITH_API_KEY"] = "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"
# os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# # Project name for organizing LangSmith traces
# os.environ["LANGSMITH_PROJECT"] = "react_agent"

# # 所有图片都在
# start_hint = "ad agent"


# # TODO 创作能力总结 -> 多图创作能力，多视频创作能力，文+图+视频混合创作能力
# # TODO 根据用户选择的图片生成商品lora model，并使用该lora model进行创作
# # TODO 提高agent使用素材库的能力 （所有未指定的生成都先查看素材库判断是否有合适的素材）
# # TODO 多跳能力优化
# # TODO 调用能力前弹出 （提示框）
# # TODO 单点能力 ->学到 组合能力 -> 多跳能力


# class AdAgentState(BaseModel):
#     # 输入
#     user_id: str = Field(description="用户id")
#     chat_history: list[BaseMessage] = Field(
#         default=[], description="聊天历史,用于记录用户与agent的对话")

#     """
#     广告agent
#     """

#     def __init__(self, user_id: str):
#         self.user_id = user_id
#         self.state = AdAgentState(user_id=user_id)

#     def invoke(self, message: str, overhead_information: dict = {}, chat_history: list[BaseMessage] = []):
#         """
#         调用agent
#         :param message: 消息
#         :param overhead_information: 额外信息,用于记录用户输入的图片，文档，文件
#         :return: 响应
#         """
#         # overhead_information_list = []
#         # for key, value in overhead_information.items():
#         #     overhead_information_list.append((key, value))

#         react_agent = create_react_agent(
#             # prompt=SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(
#             #     user_id=self.user_id, material_library=self.state.material_library.get_all_material_info())),
#             model=create_azure_gpt5_llm(),
#             tools=[get_material_from_link, get_material_in_web, upload_material, pre_review_material_in_material_library, pre_review_material_in_user_input, create_image_by_t2i, create_video_by_t2v,
#                    create_video_by_i2v_wo_assign, create_video_by_i2v_with_assign, create_image_by_i2i_wo_assign, create_image_by_i2i_with_assign]
#         )
#         # 在chat_history头部中添加SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(user_id=self.user_id))
#         chat_history.insert(0, SystemMessage(content=AD_AGENT_SYSTEM_PROMPT_cn.format(
#             user_id=self.user_id)))
#         chat_history.append(HumanMessage(
#             content=AD_AGENT_HUMAN_PROMPT_cn.format(question=message, overhead_information=overhead_information, user_id=self.user_id)))
#         result = react_agent.invoke({"messages": chat_history})
#         return result


# AdAgents: dict[str, AdAgent] = {}


# @tool
# def get_material_from_link(user_id: Annotated[str, Field(description="用户id")],
#                            link: Annotated[str, Field(description="链接")]):
#     """
#     根据链接获取素材
#     """
#     if user_id not in AdAgents:
#         raise ValueError(f"用户{user_id}不存在")
#     result = asyncio.run(
#         AdAgents[user_id].state.material_library.crawl_material_by_link(link))
#     if result:
#         return "素材获取成功，请在素材库中查看"
#     else:
#         return "素材获取失败，请检查链接是否有效"


# @tool
# def upload_material(user_id: Annotated[str, Field(description="用户id")],
#                     overhead_information: Annotated[str, Field(description="""额外信息,用于记录用户输入的图片，文档，文件,json格式,例如：{"image_1": "/data/dzj/ad_agent/temp/phone/phone.jpg", "image_2": "/data/dzj/ad_agent/temp/phone/phone.jpg"}""")]):
#     """
#     上传素材
#     """
#     overhead_information = json.loads(overhead_information)
#     if user_id not in AdAgents:
#         raise ValueError(f"用户{user_id}不存在")
#     for key, value in overhead_information.items():
#         if key.startswith("image_"):
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v1(
#                 title="用户上传的图片", description="用户上传的图片", sub_material_path=value)
#         elif key.startswith("video_"):
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v1(
#                 title="用户上传的视频", description="用户上传的视频", sub_material_path=value)
#     return "素材上传成功"


# @tool
# def get_material_in_web(user_id: Annotated[str, Field(description="用户id")],
#                         keyword: Annotated[str, Field(description="关键词")]):
#     """
#     根据关键词在网上获取素材
#     """
#     # 一切在工具内的都为英文
#     keyword = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=keyword)
#     if user_id not in AdAgents:
#         raise ValueError(f"用户{user_id}不存在")
#     asyncio.run(
#         AdAgents[user_id].state.material_library.crawl_material_in_web(keyword))
#     return "素材爬取成功,请在素材库中查看"


# @tool
# def pre_review_material_in_material_library(user_id: Annotated[str, Field(description="用户id")],
#                                             material_id: Annotated[str, Field(description="素材id,素材id的格式为{number}_{number}，例如1_1")]):
#     """
#     预审素材,预审素材库中的素材，
#     """
#     if user_id not in AdAgents:
#         raise ValueError(f"用户{user_id}不存在")
#     material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#         material_id)
#     if material_path is None:
#         return f"素材{material_id}不存在"
#     if not (is_image_file(material_path) or is_video_file(material_path)):
#         return f"素材{material_id}不是图片或视频"
#     result = process_media(
#         media_file=material_path,
#         MEDIASHIELD_GEMINI_API_KEY=conf.get(
#             "MEDIASHIELD_GEMINI_API_KEY"),
#         MEDIASHIELD_GPT_API_KEY=conf.get("MEDIASHIELD_GPT_API_KEY"),
#         similarity_threshold=0.4,
#         text_input=None,
#         screenshot=None
#     )
#     return result


# @tool
# def pre_review_material_in_user_input(overhead_information: Annotated[str, Field(description="""额外信息,用于记录用户输入的图片，文档，文件,json格式,例如：{"image_1": "/data/dzj/ad_agent/temp/phone/phone.jpg", "image_2": "/data/dzj/ad_agent/temp/phone/phone.jpg"}""")]):
#     """
#     预审素材，预审用户输入的图片，文档，文件
#     """
#     pre_review_material_result_list = []
#     overhead_information = json.loads(overhead_information)
#     for key, value in overhead_information.items():
#         if key.startswith("video_") or key.startswith("image_"):
#             # 对图片进行预审
#             video_path = value
#             text_input = None
#             screenshot = ""
#             result = process_media(
#                 media_file=video_path,
#                 gemini_api_key=conf.get("mediashield.gemini_api_key"),
#                 gpt_api_key=conf.get("mediashield.gpt_api_key"),
#                 similarity_threshold=0.4,
#                 text_input=text_input,
#                 screenshot=screenshot
#             )
#             result = result["message"]
#             pre_review_material_result_list.append(result)
#     pre_review_material_content = ""
#     for index, pre_review_material_result in enumerate(pre_review_material_result_list):
#         pre_review_material_content += f"""素材{index + 1}
#             的预审结果为{pre_review_material_result}"""

#     return pre_review_material_content


# # 用户给定图片or没有给定图片
# @tool
# def create_image_by_t2i(user_id: Annotated[str, Field(description="用户id")],
#                         require: Annotated[str, Field(description="需求，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")]):
#     """
#     使用text-to-image模型创建图片
#     """
#     if user_id not in AdAgents:
#         raise ValueError(f"用户{user_id}不存在")
#     # 一切在工具内的都为英文
#     require = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=require)
#     # 在素材库中选择合适的素材
#     material_id_list = AdAgents[user_id].state.material_library.select_appropriate_material(
#         require)
#     if len(material_id_list) == 0:
#         model_id = model_factory.choose_model_by_specific_function(
#             require, "text to image")
#         model = model_factory.get_model_by_id(model_id)
#         output_path = asyncio.run(model.generate(positive_prompt=require))
#         # 将生成的素材放入素材库
#         AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#             title=require, description=require, sub_material_path=output_path)
#         return "图片生成成功,请在素材库中查看"
#     else:
#         bigger_than_one = False
#         model_id = model_factory.choose_model_by_specific_function(
#             require, "image to image")
#         model = model_factory.get_model_by_id(model_id)
#         for material_id in material_id_list:
#             material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#                 material_id)
#             if material_path is None:
#                 continue
#             if not os.path.exists(material_path):
#                 continue
#             if not is_image_file(material_path):
#                 continue
#             bigger_than_one = True
#             # 图片 + 需求 -> 生成图片prompt
#             GenerateVideoPromptAgent().generate_video_prompt(
#                 require=require, material_path=material_path)
#             output_path = asyncio.run(model.generate(
#                 positive_prompt=require, image_path=material_path))
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=require, description=require, sub_material_path=output_path)
#         if not bigger_than_one:
#             output_path = asyncio.run(model.generate(positive_prompt=require))
#             # 将生成的素材放入素材库
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=require, description=require, sub_material_path=output_path)
#         return "图片生成成功,请在素材库中查看"


# @tool
# def create_video_by_t2v(user_id: Annotated[str, Field(description="用户id")],
#                         require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")]):
#     """
#     使用text-to-video模型创建视频
#     """

#     # 一切在工具内的都为英文
#     require = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=require)

#     # 在素材库中选择合适的素材
#     material_id_list = AdAgents[user_id].state.material_library.select_appropriate_material(
#         require)
#     if len(material_id_list) == 0:
#         model_id = model_factory.choose_model_by_specific_function(
#             require, "text to video")
#         model = model_factory.get_model_by_id(model_id)
#         output_path = asyncio.run(model.generate(positive_prompt=require))
#         AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#             title=require, description=require, sub_material_path=output_path)
#         return "视频生成成功,请在素材库中查看"
#     else:
#         bigger_than_one = False
#         model_id = model_factory.choose_model_by_specific_function(
#             require, "image to video")
#         model = model_factory.get_model_by_id(model_id)
#         for material_id in material_id_list:
#             material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#                 material_id)
#             if material_path is None:
#                 continue
#             if not is_image_file(material_path):
#                 continue
#             video_prompt = GenerateVideoPromptAgent().generate_video_prompt(
#                 require=require, material_path=material_path)
#             output_path = asyncio.run(model.generate(
#                 positive_prompt=video_prompt, image_path=material_path))
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=require, description=require, sub_material_path=output_path)
#         if not bigger_than_one:
#             model_id = model_factory.choose_model_by_specific_function(
#                 require, "text to video")
#             model = model_factory.get_model_by_id(model_id)
#             output_path = asyncio.run(model.generate(positive_prompt=require))
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=require, description=require, sub_material_path=output_path)

#         return f"根据素材{material_id_list}生成视频,请在素材库中查看"


# @tool
# def create_video_by_i2v_wo_assign(user_id: Annotated[str, Field(description="用户id")],
#                                   require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
#                                   overhead_information: Annotated[str, Field(description="""额外信息,用于记录用户输入的图片，文档，文件,json格式,例如：{"image_1": "/data/dzj/ad_agent/temp/phone/phone.jpg", "image_2": "/data/dzj/ad_agent/temp/phone/phone.jpg"}""")]):
#     """
#     用户没有指定图片或者用户希望根据其在附加输入中输入的图片来生成视频，使用image-to-video模型创建视频
#     """
#     # 一切在工具内的都为英文
#     require = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=require)

#     input_image_list = []
#     # 判断其中是否有image_开头
#     overhead_information = json.loads(overhead_information)
#     for key, value in overhead_information.items():
#         if key.startswith("image_"):
#             # 使用image-to-video模型创建视频
#             input_image_list.append(value)
#     if len(input_image_list) == 0:
#         # 在素材库中选择合适的素材
#         material_id_list = AdAgents[user_id].state.material_library.select_appropriate_material(
#             require)
#         if len(material_id_list) == 0:
#             return "没有找到合适的素材,请调用get_material_in_web来获取素材"
#         for material_id in material_id_list:
#             material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#                 material_id)
#             if material_path is None:
#                 return f"素材{material_id}不存在"
#             if not is_image_file(material_path):
#                 return f"素材{material_id}不是图片"
#             video_prompt = GenerateVideoPromptAgent().generate_video_prompt(
#                 require=require, material_path=material_path)
#             model_id = model_factory.choose_model_by_specific_function(
#                 require, "image to video")
#             model = model_factory.get_model_by_id(model_id)
#             output_path = asyncio.run(model.generate(
#                 image_path=material_path, positive_prompt=video_prompt))
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=require, description=require, sub_material_path=output_path)
#         return "视频生成成功,请在素材库中查看"
#     else:
#         # 使用以上图片 + 需求 来创建视频
#         model_id = model_factory.choose_model_by_specific_function(
#             require, "image to video")
#         model = model_factory.get_model_by_id(model_id)
#         for input_image in input_image_list:
#             video_prompt = GenerateVideoPromptAgent().generate_video_prompt(
#                 require=require, material_path=input_image)
#             output_path = asyncio.run(model.generate(
#                 image_path=input_image, positive_prompt=video_prompt))
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=require, description=require, sub_material_path=output_path)

#         return "视频生成成功,请在素材库中查看"


# @tool
# def create_video_by_i2v_with_assign(user_id: Annotated[str, Field(description="用户id")],
#                                     require: Annotated[str, Field(description="需求，具体需求，例如对视频的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
#                                     material_id: Annotated[str, Field(description="素材id,素材id的格式为{number}_{number}，例如1_1")]):
#     """
#     用户指定了使用素材库中的图片来生成视频，使用image-to-video模型创建视频
#     """
#     # 一切在工具内的都为英文
#     require = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=require)

#     # 从素材库中获取素材
#     material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#         material_id)
#     if material_path is None:
#         return f"素材{material_id}不存在"
#     # 使用以上图片 + 需求 来创建视频
#     # 确保该素材是图片,通过后缀进行判断
#     if not is_image_file(material_path):
#         return f"素材{material_id}不是图片"
#     logger.info(f"material_path: {material_path} use i2v to create video")
#     model_id = model_factory.choose_model_by_specific_function(
#         require, "image to video")
#     model = model_factory.get_model_by_id(model_id)
#     video_prompt = GenerateVideoPromptAgent().generate_video_prompt(
#         require=require, material_path=material_path)
#     output_path = asyncio.run(model.generate(
#         image_path=material_path, positive_prompt=video_prompt))
#     AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#         title=require, description=require, sub_material_path=output_path)
#     return "视频生成成功,请在素材库中查看"


# @tool
# def create_image_by_i2i_wo_assign(user_id: Annotated[str, Field(description="用户id")],
#                                   positive_prompt: Annotated[str, Field(description="正向提示词，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
#                                   overhead_information: Annotated[str, Field(description="""额外信息,用于记录用户输入的图片，文档，文件,json格式,例如：{"image_1": "/data/dzj/ad_agent/temp/phone/phone.jpg", "image_2": "/data/dzj/ad_agent/temp/phone/phone.jpg"}""")]):
#     """
#     用户没有指定图片或者用户希望根据其在附加输入中输入的图片来生成图片，使用image-to-image模型创建图片
#     功能：1.生成某商品的多视角图片 2.对商品图片背景进行修改
#     """
#     # 一切在工具内的都为英文
#     positive_prompt = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=positive_prompt)
#     input_image_list = []
#     # 判断其中是否有image_开头
#     overhead_information = json.loads(overhead_information)
#     for key, value in overhead_information.items():
#         if key.startswith("image_"):
#             # 使用image-to-video模型创建视频
#             input_image_list.append(value)
#     if len(input_image_list) == 0:
#         # 在素材库中选择合适的素材
#         material_id_list = AdAgents[user_id].state.material_library.select_appropriate_material(
#             positive_prompt)
#         if len(material_id_list) == 0:
#             return "没有找到合适的素材,请调用create_image_by_t2i来生成图片"
#         for material_id in material_id_list:
#             material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#                 material_id)
#             if material_path is None:
#                 return f"素材{material_id}不存在"
#             if not is_image_file(material_path):
#                 return f"素材{material_id}不是图片"
#             model_id = model_factory.choose_model_by_specific_function(
#                 positive_prompt, "image to image")
#             model = model_factory.get_model_by_id(model_id)
#             output_path_list = asyncio.run(model.generate(
#                 image_path=material_path, positive_prompt=positive_prompt, negative_prompt=""))
#             if isinstance(output_path_list, str):
#                 output_path_list = [output_path_list]
#             AdAgents[user_id].state.material_library.insert_material_with_sub_material_list_to_v2(
#                 title=positive_prompt, description=positive_prompt, sub_material_path_list=output_path_list)
#         return "图片生成成功,请在素材库中查看"
#     else:
#         # 使用以上图片 + 需求 来创建图片
#         model_id = model_factory.choose_model_by_specific_function(
#             positive_prompt, "image to image")
#         model = model_factory.get_model_by_id(model_id)
#         for input_image in input_image_list:
#             output_path = asyncio.run(model.generate(
#                 image_path=input_image, positive_prompt=positive_prompt, negative_prompt=""))
#             AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#                 title=positive_prompt, description=positive_prompt, sub_material_path=output_path)

#         return "视频生成成功,请在素材库中查看"


# @tool
# def create_image_by_i2i_with_assign(user_id: Annotated[str, Field(description="用户id")],
#                                     positive_prompt: Annotated[str, Field(description="正向提示词，具体需求，例如对图片的具体要求，例如：一个穿着白色连衣裙的女孩在海边跳舞")],
#                                     negative_prompt: Annotated[str, Field(description="负向提示词，例如：不要有文字")],
#                                     material_id: Annotated[str, Field(description="素材id,素材id的格式为{number}_{number}，例如1_1")]):
#     """
#     用户指定了使用素材库中的图片来生成图片，使用image-to-image模型创建图片
#     功能：1.生成某商品的多视角图片 2.对商品图片背景进行修改
#     """
#     # 一切在工具内的都为英文
#     positive_prompt = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=positive_prompt)
#     negative_prompt = TranslatorAgent().translate(
#         from_lang="Chinese", to_lang="English", text=negative_prompt)

#     material_path = AdAgents[user_id].state.material_library.get_material_by_id(
#         material_id)
#     if material_path is None:
#         return f"素材{material_id}不存在"
#     # 使用以上图片 + 需求 来创建视频
#     # 确保该素材是图片,通过后缀进行判断
#     if not is_image_file(material_path):
#         return f"素材{material_id}不是图片"
#     model_id = model_factory.choose_model_by_specific_function(
#         positive_prompt, "image to image")
#     model = model_factory.get_model_by_id(model_id)
#     output_path = asyncio.run(model.generate(
#         image_path=material_path, positive_prompt=positive_prompt, negative_prompt=negative_prompt))
#     AdAgents[user_id].state.material_library.insert_material_with_one_sub_material_to_v2(
#         title=positive_prompt, description=positive_prompt, sub_material_path=output_path)
#     return "视频生成成功,请在素材库中查看"
