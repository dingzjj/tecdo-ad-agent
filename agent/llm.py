import google.cloud.aiplatform_v1.types
from config import conf
from typing import Callable, List, Optional
import os
import matplotlib.pyplot as plt
from google.genai import types
from PIL import Image as PIL_Image
from google.genai.types import GenerateVideosConfig, Image
import uuid
from agent.third_part.aliyunoss import share_file_in_oss
import time
import asyncio
import httpx
from http import HTTPStatus
from dashscope import VideoSynthesis
from google import genai
from langchain_openai import AzureChatOpenAI
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
import vertexai
from config import conf, logger
from openai import OpenAI
from langchain.prompts import SystemMessagePromptTemplate, ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage


def create_azure_llm() -> AzureChatOpenAI:
    # 配置 Azure OpenAI 客户端
    return AzureChatOpenAI(
        api_key=conf.get("Azure_gpt.api_key"),  # API 密钥
        azure_endpoint=conf.get("Azure_gpt.azure_endpoint"),  # 替换为你的端点
        model=conf.get("Azure_gpt.model_name"),  # 选择模型
        deployment_name=conf.get("Azure_gpt.deployment_name"),  # 替换为你的部署名称
        api_version=conf.get("Azure_gpt.api_version"),  # API 版本
    )


def chat_with_openai_in_azure(system_prompt: str, prompt: str) -> str:
    llm = create_azure_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)
    return str(response.content)


class AzureChatOpenAIClient:
    def __init__(self):
        self.llm = create_azure_llm()
        # 这里的history用以llm发生错误时记录错误日志，便于重新生成
        self.history = []
        self.callback: bool = False

    def set_callback(self, user_input):
        self.callback = True
        self.history.append(HumanMessage(content=user_input))

    def chat_with_history(self, system_prompt: str, chat_history: list[BaseMessage]) -> str:
        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt)
        ]
        for message in chat_history:
            messages.append(message)

        for message in self.history:
            messages.append(message)

        response = self.llm.invoke(messages)
        response_content = str(response.content)
        self.history.append(AIMessage(content=response_content))
        return response_content


def chat_once(llm, system_prompt: str, prompt: str) -> str:
    """
    单次对话
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    response = llm.invoke(messages)
    return str(response.content)


def chat_with_openai_in_azure_with_template(system_prompt_template: str, **kwargs) -> str:
    # 创建聊天提示模板
    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt_template),
    ])

    llm = create_azure_llm()
    chain = chat_prompt | llm
    response = chain.invoke(kwargs)
    return str(response.content)


def chat_with_gemini_in_vertexai(system_prompt: str, prompt: str) -> str:
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get_file_path('gemini_conf'))
    vertexai.init(project='ca-biz-vypngh-y97n', credentials=credentials)
    multimodal_model = GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config=GenerationConfig(
            temperature=0.1)
    )
    # Query the model
    try:
        response = multimodal_model.generate_content(
            [
                prompt
            ]
        )
        return response.text
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return ""


def translate_with_gemini_in_vertexai(context: str) -> str:
    system_prompt = "你是一个专业的中文翻译员，请只提供翻译后的中文内容，避免添加任何其他解释或信息。"
    prompt = f"请将以下内容翻译成中文：{context}"
    try:
        gemini_result = chat_with_gemini_in_vertexai(system_prompt, prompt)
        return gemini_result
    except Exception as e:
        return context


def generate_embedding_with_openai(text: str) -> list[float]:
    query_vectors = [
        vec.embedding
        for vec in OpenAI(api_key=conf.get('openai_api_key'), base_url=conf.get('openai_api_base')).embeddings.create(input=text, model=conf.get('openai_embedding_model')).data]
    return query_vectors[0]


def get_gemini_multimodal_model(system_prompt: str, response_schema: dict):
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get("gemini_conf"))
    vertexai.init(project='ca-biz-vypngh-y97n', credentials=credentials)

    # Load the model
    multimodal_model = GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config=GenerationConfig(
            temperature=0.1, response_mime_type="application/json", response_schema=response_schema)
    )
    return multimodal_model


# Create Gemini create image model client
def create_gemini_create_image_model_client():
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get("gemini_conf"),
        scopes=[conf.get("gemini_scopes")],
    )

    client = genai.Client(
        vertexai=True,
        project=conf.get("gemini_project"),
        location=conf.get("gemini_location"),
        credentials=credentials,
    )
    return client


# dashscope sdk >= 1.23.4

def i2v_with_tongyi(img_url, prompt, resolution, duration, prompt_extend=True):
    def get_video_url(img_url):
        if img_url.startswith("http"):
            return img_url
        else:
            return "file://" + img_url
    """
    通过通义的i2v模型生成视频
    img_url: 图片url
    prompt: 提示词
    resolution: 分辨率
    prompt_extend: 是否扩展提示词

    img_url:使用http:.... or 使用本地文件路径
    # 使用本地文件路径（file://+文件路径）
    # 使用绝对路径
    # img_url = "file://" + "/path/to/your/img.png"    # Linux/macOS
    # img_url = "file://" + "C:/path/to/your/img.png"  # Windows
    # 或使用相对路径
    # img_url = "file://" + "./img.png"                # 以实际路径为准

    return 返回的是远程url，需要下载
    """
    # call sync api, will return the result
    rsp = VideoSynthesis.call(api_key=conf.get("tongyi_api_key"),
                              model='wanx2.1-i2v-turbo',
                              prompt=prompt,
                              # negative_prompt='',  # 可选，负面提示词
                              # template='flying',# 模板，包括squish（解压捏捏）、flying（魔法悬浮）、carousel（时光木马）
                              img_url=get_video_url(img_url),
                              parameters={
                                  "resolution": resolution,
                                  "duration": duration,  # 视频时长wanx2.1-i2v-turbo：可选值为3、4或5;wanx2.1-i2v-plus：仅支持5秒
                                  "prompt_extend": prompt_extend
    }
    )
    if rsp.status_code == HTTPStatus.OK:
        result = rsp.output.video_url
        return result
    else:
        logger.error('Failed, status_code: %s, code: %s, message: %s' %
                     (rsp.status_code, rsp.code, rsp.message))


# def get_gemini_response_with_web_search(system_prompt: str, input: str, model: str) -> str:
#     # 设置GOOGLE_API_KEY为conf.get("gemini_config.private_key")
#     os.environ["GOOGLE_API_KEY"] = conf.get("gemini_config.private_key")
#    # Configure the client
#     #    `vertexai=True,project="your-project-id", location="us-central1"`
#     credentials = service_account.Credentials.from_service_account_file(
#         filename=conf.get_file_path('gemini_conf'))
#     vertexai.init(project='ca-biz-vypngh-y97n', credentials=credentials)
#     client = genai.Client(vertexai=True, credentials=credentials)

#     # Define the grounding tool
#     grounding_tool = types.Tool(
#         google_search=types.GoogleSearch()
#     )

#     # Configure generation settings
#     config = types.GenerateContentConfig(
#         tools=[grounding_tool]
#     )

#     # Make the request
#     response = client.models.generate_content(
#         model=model,
#         contents=input,
#         config=config,
#     )
#     return response

def get_gpt_response_with_web_search():
    client = OpenAI(api_key=conf.get("openai_api_key"),
                    base_url=conf.get("openai_api_base"))

    response = client.responses.create(
        model="gpt-4o-search-preview",
        tools=[{"type": "web_search_preview"}],
        input="我要关于拖鞋的视频的具体链接"
    )

    return response


def get_gpt5_response(query: str):
    client = OpenAI(api_key=conf.get("gpt5.api_key"),
                    base_url=conf.get("gpt5.base_url"))

    response = client.responses.create(
        model=conf.get("gpt5.model_name"),
        input=query
    )
    return response
