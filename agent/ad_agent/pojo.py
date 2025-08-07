from typing import Literal
from pydantic import BaseModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

import gradio as gr


class AdAgentChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    type: Literal["text", "image", "video", "audio", "document"]
    content: str = ""
    file_path: str = ""

    def to_gradio_chat_message(self):
        if self.type == "text":
            return gr.ChatMessage(role=self.role, content=self.content)
        elif self.type == "image":
            return gr.ChatMessage(role=self.role, content=gr.Image(value=self.file_path, height=100))
        elif self.type == "video":
            return gr.ChatMessage(role=self.role, content=gr.Video(value=self.file_path, height=100))


def gradio_chat_message2ad_agent_chat_message(gradio_chat_message: gr.ChatMessage):
    # 核心：数据类型
    content = gradio_chat_message["content"]
    if isinstance(content, str):
        return AdAgentChatMessage(role=gradio_chat_message["role"], type="text", content=content, file_path="")
    elif isinstance(content, gr.Image):
        return AdAgentChatMessage(role=gradio_chat_message["role"], type="image", content="", file_path=content.value['path'])
    elif isinstance(content, gr.Video):
        return AdAgentChatMessage(role=gradio_chat_message["role"], type="video", content="", file_path=content.value["video"]['path'])
    else:
        return AdAgentChatMessage(role=gradio_chat_message["role"], type="text", content=str(content), file_path="")


def gradio_chat_message_list2ad_agent_chat_message_list(gradio_chat_message_list: list[gr.ChatMessage]):
    ad_agent_chat_message_list = []
    for gradio_chat_message in gradio_chat_message_list:
        ad_agent_chat_message_list.append(
            gradio_chat_message2ad_agent_chat_message(gradio_chat_message))
    return ad_agent_chat_message_list


def ad_agent_chat_message2chat_message(ad_agent_chat_message_list: list[AdAgentChatMessage]):
    chat_message_list = []
    for ad_agent_chat_message in ad_agent_chat_message_list:
        if ad_agent_chat_message.type == "text":
            if ad_agent_chat_message.role == "user":
                chat_message_list.append(HumanMessage(
                    content=ad_agent_chat_message.content))
            else:
                chat_message_list.append(
                    AIMessage(content=ad_agent_chat_message.content))


def get_last_human_message(chat_message_list: list[AdAgentChatMessage]):
    if len(chat_message_list) == 0:
        return ""
    chat_message = chat_message_list[-1]
    if chat_message.role == "user":
        return chat_message.content
    else:
        return ""
