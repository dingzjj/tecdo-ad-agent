from config import modules_path
import os
from langchain_core.messages import HumanMessage, AIMessage


def chatbot_to_chat_history(chatbot):
    chat_history = []
    for chat_message in chatbot:
        if chat_message["role"] == "user":
            chat_history.append(HumanMessage(content=chat_message["content"]))
        elif chat_message["role"] == "assistant":
            chat_history.append(AIMessage(content=chat_message["content"]))
    return chat_history


def i18n(text):
    return text


def get_html(filename):
    path = os.path.join(modules_path, "web_assets", "html", filename)
    if os.path.exists(path):
        with open(path, encoding="utf8") as file:
            return file.read()
    return ""


def get_history_names():
    return []


def get_first_history_name():
    return ""
