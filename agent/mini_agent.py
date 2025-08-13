
from agent.llm import create_azure_gpt5_llm
import re
from agent.llm import create_azure_llm
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Literal
from agent.utils import get_time_id
from config import conf
import requests
import os
from agent.llm import get_gemini_multimodal_model
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from agent.ad_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en
import mimetypes
from agent.ad_agent.prompt import SELLING_POINTS_CLASSIFIER_SYSTEM_PROMPT_en, SELLING_POINTS_CLASSIFIER_HUMAN_PROMPT_en
from agent.ad_agent.prompt import CLASSIFIER_SYSTEM_PROMPT_en, CLASSIFIER_HUMAN_PROMPT_en
from agent.third_part.prompt import ACTION_TYPES_CLASSIFIER_SYSTEM_PROMPT_en, ACTION_TYPES_CLASSIFIER_HUMAN_PROMPT_en
from agent.llm import chat_with_openai_in_azure
from config import logger
import json
import uuid


class SellingPointsClassifier:
    def __init__(self, categories: list[str]):
        # category_id,category_name
        self.categories = [{"category_id": str(uuid.uuid4()), "category_name": category}
                           for category in categories]

        self.system_prompt = SELLING_POINTS_CLASSIFIER_SYSTEM_PROMPT_en
        self.human_prompt = SELLING_POINTS_CLASSIFIER_HUMAN_PROMPT_en

    def classify(self, input_text: str) -> str:
        while True:
            response = chat_with_openai_in_azure(
                self.system_prompt, self.human_prompt.format(input_text=input_text, categories=self.categories))
            try:
                content = json.loads(response)
                print(content)
                category_id = content["category_id"]
                # 直到能解析出category_id为止
                for category in self.categories:
                    if category["category_id"] == category_id:
                        return category["category_name"]
            except Exception as e:
                logger.error(e)


class ActionTypesClassifier:
    def __init__(self, categories: list[str]):
        # category_id,category_name
        self.categories = [{"category_id": str(uuid.uuid4()), "category_name": category}
                           for category in categories]

        self.system_prompt = ACTION_TYPES_CLASSIFIER_SYSTEM_PROMPT_en
        self.human_prompt = ACTION_TYPES_CLASSIFIER_HUMAN_PROMPT_en

    def classify(self, input_text: str) -> str:
        while True:
            response = chat_with_openai_in_azure(
                self.system_prompt, self.human_prompt.format(input_text=input_text, categories=self.categories))
            try:
                content = json.loads(response)
                print(content)
                category_id = content["category_id"]
                # 直到能解析出category_id为止
                for category in self.categories:
                    if category["category_id"] == category_id:
                        return category["category_name"]
            except Exception as e:
                logger.error(e)


class Classifier:
    """
    分类器，将输入的文本分类为多个类别中的一个
    """

    def __init__(self, categories: list[str]):
        # category_id,category_name
        self.categories = [{"category_id": str(uuid.uuid4()), "category_name": category}
                           for category in categories]

        self.system_prompt = CLASSIFIER_SYSTEM_PROMPT_en
        self.human_prompt = CLASSIFIER_HUMAN_PROMPT_en

    def classify(self, input_text: str) -> str:
        while True:
            response = chat_with_openai_in_azure(
                self.system_prompt, self.human_prompt.format(input_text=input_text, categories=self.categories))
            try:
                content = json.loads(response)
                print(content)
                category_id = content["category_id"]
                # 直到能解析出category_id为止
                for category in self.categories:
                    if category["category_id"] == category_id:
                        return category["category_name"]
            except Exception as e:
                logger.error(e)


class AnalyseImageAgent:
    """
    分析图片(人+商品)，返回图片信息
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    def analyse_image(self, product: str, image_path: str, source: Literal["web", "local"], language: Literal["cn", "en"]) -> str:

        match self.model:
            case "gemini-2.5-flash":
                return self.analyse_image_with_gemini_2_5_flash(product, image_path, source)
            case _:
                raise ValueError(f"Unsupported model: {self.model}")

    def analyse_image_with_gemini_2_5_flash(self, product: str, image_path: str, source: Literal["web", "local"]) -> str:

        if source == "web":
            response = requests.get(image_path)
            image_data = response.content
        elif source == "local":
            with open(image_path, "rb") as file:
                image_data = file.read()

        # 根据文件后缀获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            # 如果无法猜测，默认为 image/jpeg
            mime_type = "image/jpeg"

        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
            response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=product),
                Part.from_data(image_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        return content["pictorial information"]


class AnalyseMaterialAgent:

    async def analyse_material(self, product: str, material_path: str, source: Literal["web", "local"]) -> str:

        if source == "web":
            response = requests.get(material_path)
            material_data = response.content
        elif source == "local":
            with open(material_path, "rb") as file:
                material_data = file.read()

        mime_type, _ = mimetypes.guess_type(material_path)
        if mime_type is None:
            # 如果无法猜测，默认为 image/jpeg
            mime_type = "image/jpeg"

        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
            response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=product),
                Part.from_data(material_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        return content["pictorial information"]


class TranslatorAgent:
    def __init__(self):
        self.model = "gpt-4o-mini"

    def translate(self, from_lang: str, to_lang: str, text: str) -> str:
        llm = create_azure_llm()
        response = llm.invoke([
            SystemMessage(content=f"You are a translator. You are given a text in {from_lang} and you need to translate it to {
                          to_lang}.Generally, the contents within "" or “” do not need to be translated."),
            HumanMessage(
                content=f"""{text}""")
        ])
        # 将有""或“”的内容替换回来
        result = response.content
        # 正则表达式匹配双引号或中文引号中的内容
        pattern = r'["“”](.*?)["”]'
        # 替换 B 中双引号或中文引号中的内容为 A
        result = re.sub(pattern, lambda m: text, result)

        return result


GENERATE_VIDEO_PROMPT_SYSTEM_PROMPT_zh = """
# Role：视频脚本生成专家

## Background：用户需要生成的短视频内容通常时长在5-10秒以内，涉及快速、有效的表达和展现，因此需要简洁且吸引人的脚本来吸引观众注意力。

## Attention：在短时间内传达清晰的信息是关键，要考虑内容的吸引性和简洁性，使观众能在最短时间内了解视频主题。

## Profile：
- Author: prompt-optimizer
- Description: 专注于短视频脚本的生成，使内容生动、有趣并能快速传达主题。

### Skills:
- 熟悉短视频传播特性和观众心理
- 擅长简洁、精练的文案创作
- 具备创意思维，能提出独特的视觉呈现
- 了解各种视频类型及其风格
- 能迅速把握主题并提炼核心信息

## Goals:
- 生成一段简短且富有吸引力的脚本
- 快速传达视频的主题和信息
- 保证脚本内容符合观众的兴趣和需求
- 提供与视频制作团队有效沟通的概述
- 激发观众的好奇心，引导其观看视频

## Constrains:
- 脚本长度需控制在一段话内，避免冗长
- 内容必须适合视频时长（5-10秒）
- 注意语言的简洁性与口语化，易于观众理解
- 脚本需符合视频所属领域的风格与调性
- 避免使用专业术语，以免造成理解障碍

## Workflow:
1. 明确视频主题和目标受众
2. 整理与主题相关的关键信息
3. 进行头脑风暴，生成不同的表达方式
4. 根据用户的需求和图片内容编写出最简练、富有吸引力的脚本

## OutputFormat:
- 输出内容需为一段简洁、流畅的话语
- 字数控制在30-50字左右
"""

GENERATE_VIDEO_PROMPT_HUMAN_PROMPT_zh = """
根据需求和图片内容编写出最简练、富有吸引力的脚本
需求：{require}
"""
GENERATE_VIDEO_PROMPT_HUMAN_PROMPT_en = """
Generate a concise and attractive script based on the user's requirements and the content of the pictures.
Requirement: {require}
"""

GENERATE_VIDEO_PROMPT_SYSTEM_PROMPT_en = """
# Role: Video Script Generation Expert 
## Background: The short video content that users need to create usually lasts within 5 to 10 seconds. It requires rapid and effective expression and presentation, so a concise and attractive script is necessary to capture the audience's attention. 
Attention: It is crucial to convey clear information within a short period of time. Consider the attractiveness and conciseness of the content to enable the audience to grasp the main theme of the video in the shortest possible time. 
## Profile: - Author: prompt-optimizer
- Description: Focuses on generating short video scripts to make the content lively, engaging and capable of quickly conveying the theme. 
### Skills:
- Familiar with the characteristics of short video dissemination and the psychology of the audience
- Skilled in creating concise and elegant copywriting
- Possessing creative thinking, able to propose unique visual presentations
- Understanding of various video types and their styles
- Capable of quickly grasping the theme and extracting the core information 
## Goals:
- Generate a brief and attractive script
- Quickly convey the theme and information of the video
- Ensure the script content meets the interests and needs of the audience
- Provide an overview for effective communication with the video production team
- Stimulate the audience's curiosity and guide them to watch the video 
## Constrains:
- The script length should be limited to a single paragraph to avoid being too lengthy.
- The content must be suitable for the duration of the video (5-10 seconds).
- Pay attention to the brevity and colloquialism of the language, making it easy for the audience to understand.
- The script should conform to the style and tone of the video's subject matter.
- Avoid using technical terms to prevent comprehension difficulties. 
## Workflow:
1. Clearly define the video's theme and target audience.
2. Organize the key information related to the theme.
3. Conduct brainstorming to generate various expressions.
4. Based on the user's requirements and the content of the pictures, write the most concise and attractive script.
## OutputFormat:
The output content should be a concise and fluent statement. The translation should be natural and follow English expression habits. Please provide the final translation without any additional text.
"""


GENERATE_VIDEO_PROMPT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "video_prompt": {
            "type": "STRING",
            "description": "video prompt(the script of the video)"
        }
    },
    "required": ["video_prompt"]
}


class GenerateImagePromptAgent:
    def __init__(self):
        self.model = "gpt-5"

    def generate_image_prompt(self, require: str) -> str:
        llm = create_azure_gpt5_llm()
        response = llm.invoke([
            SystemMessage(
                content=f"""你是一个文生图模型提示词优化专家，你的任务是根据用户的需求，生成一个文生图模型可以理解的提示词，即转化为对场景的描述。例如：用户需求是：生成一个带有"钛动"耳机的图片，你生成的提示词是：刻有"钛动"字样的耳机"""),
            HumanMessage(
                content=f"{require}")
        ])
        return response.content


class GenerateVideoPromptAgent:
    def __init__(self):
        self.model = "gemini-2.5-flash"

    def generate_video_prompt(self, require: str, material_path: str, source: Literal["web", "local"] = "local") -> str:
        # 图片 + 需求 -> 生成视频prompt
        # 使用gemini2.5-flash模型生成视频prompt

        if source == "web":
            response = requests.get(material_path)
            material_data = response.content
        elif source == "local":
            with open(material_path, "rb") as file:
                material_data = file.read()

        mime_type, _ = mimetypes.guess_type(material_path)
        if mime_type is None:
            # 如果无法猜测，默认为 image/jpeg
            mime_type = "image/jpeg"
        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=GENERATE_VIDEO_PROMPT_SYSTEM_PROMPT_en.format(
                require=require, material_path=material_path), response_schema=GENERATE_VIDEO_PROMPT_SCHEMA)
        response = gemini_generative_model.generate_content(
            [
                GENERATE_VIDEO_PROMPT_HUMAN_PROMPT_en.format(require=require),
                Part.from_data(material_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        return content["video_prompt"]
