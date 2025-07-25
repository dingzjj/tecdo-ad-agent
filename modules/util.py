from langchain_core.messages import HumanMessage, AIMessage


def chatbot_to_chat_history(chatbot):
    chat_history = []
    for chat_message in chatbot:
        if chat_message["role"] == "user":
            chat_history.append(HumanMessage(content=chat_message["content"]))
        elif chat_message["role"] == "assistant":
            chat_history.append(AIMessage(content=chat_message["content"]))
    return chat_history
