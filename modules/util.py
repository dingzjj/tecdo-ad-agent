"""
工具模块
提供聊天历史转换、国际化、HTML文件读取等功能
"""

import os
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage

from agent.ad_agent.pojo import AdAgentChatMessage
from config import modules_path


def chatbot_to_chat_history(chatbot: List[dict]) -> List[AdAgentChatMessage]:
    """
    将Gradio聊天机器人格式转换为广告代理聊天历史格式

    Args:
        chatbot: Gradio聊天机器人消息列表

    Returns:
        广告代理聊天消息列表
    """
    chat_history = []

    for chat_message in chatbot:
        role = chat_message.get("role", "")
        content = chat_message.get("content", "")

        if role == "user":
            chat_history.append(
                AdAgentChatMessage(role="user", type="text", content=content)
            )
        elif role == "assistant":
            chat_history.append(
                AdAgentChatMessage(
                    role="assistant", type="text", content=content)
            )

    return chat_history


def i18n(text: str) -> str:
    """
    国际化函数（目前直接返回原文）

    Args:
        text: 需要国际化的文本

    Returns:
        国际化后的文本
    """
    return text


def get_html(filename: str) -> str:
    """
    读取HTML文件内容

    Args:
        filename: HTML文件名

    Returns:
        HTML文件内容，如果文件不存在则返回空字符串
    """
    if not filename:
        return ""

    path = os.path.join(modules_path, "web_assets", "html", filename)

    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                return file.read()
    except (IOError, OSError) as e:
        print(f"读取HTML文件 {filename} 时发生错误: {e}")

    return ""


def get_history_names() -> List[str]:
    """
    获取历史记录名称列表

    Returns:
        历史记录名称列表（目前返回空列表）
    """
    return []


def get_first_history_name() -> str:
    """
    获取第一个历史记录名称

    Returns:
        第一个历史记录名称（目前返回空字符串）
    """
    return ""
