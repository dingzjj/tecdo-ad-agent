from config import conf
from typing import List
import os
from google.genai.types import GenerateVideosConfig, Image
from agent.third_part.aliyunoss import share_file_in_oss
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

from typing import Optional


def create_azure_llm(name: Optional[str] = None) -> AzureChatOpenAI:
    # 配置 Azure OpenAI 客户端
    if name:
        return AzureChatOpenAI(
            name=name,
            api_key=conf.get("Azure_gpt.api_key"),  # API 密钥
            azure_endpoint=conf.get("Azure_gpt.azure_endpoint"),  # 替换为你的端点
            model=conf.get("Azure_gpt.model_name"),  # 选择模型
            deployment_name=conf.get("Azure_gpt.deployment_name"),  # 替换为你的部署名称
            api_version=conf.get("Azure_gpt.api_version"),  # API 版本
        )
    else:
        return AzureChatOpenAI(
            api_key=conf.get("Azure_gpt.api_key"),  # API 密钥
            azure_endpoint=conf.get("Azure_gpt.azure_endpoint"),  # 替换为你的端点
            model=conf.get("Azure_gpt.model_name"),  # 选择模型
            deployment_name=conf.get("Azure_gpt.deployment_name"),  # 替换为你的部署名称
            api_version=conf.get("Azure_gpt.api_version"),  # API 版本
        )


def create_azure_gpt5_llm(name: Optional[str] = None) -> AzureChatOpenAI:
    if name:
        return AzureChatOpenAI(
            name=name,
            api_key=conf.get("gpt5.api_key"),
            azure_endpoint=conf.get("gpt5.azure_endpoint"),
            model=conf.get("gpt5.model_name"),
            api_version=conf.get("gpt5.api_version")  # API 版本
        )
    else:
        return AzureChatOpenAI(
            api_key=conf.get("gpt5.api_key"),
            azure_endpoint=conf.get("gpt5.azure_endpoint"),
            model=conf.get("gpt5.model_name"),
            api_version=conf.get("gpt5.api_version")  # API 版本
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
