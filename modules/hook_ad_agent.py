import asyncio
import os
import traceback
from langchain_core.messages import HumanMessage
# 第三方库导入
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt
from agent.ad_agent.m2v_workflow import GenerateVideoState
# 本地模块导入
from config import conf, logger
from agent.ad_agent.do_workflow import do_workflow_app
from typing import List
from agent.ad_agent.m2v_workflow import VideoFragment
import gradio as gr
import time
from modules.util import chatbot_to_chat_history
from langchain_core.messages import AIMessage

from pojo import user_id
from agent.ad_agent.pojo import gradio_chat_message_list2ad_agent_chat_message_list, AdAgentChatMessage


def send_message_to_ad_agent(user_input, chatbot, is_end):
    # 此处的chatbot是已经包含用户输入的chatbot
    user_question = user_input["text"]
    upload_files: list[str] = user_input["files"]
    overhead_information = {}
    img_number = 1
    doc_number = 1
    video_number = 1
    other_number = 1
    for file_path in upload_files:
        # 等待上传完毕再往后运行，即等到该文件的大小大于0
        while os.path.getsize(file_path) == 0:
            time.sleep(1)
        # 假如文件是png等等文件结尾的，则将其已img_{number}加入到overhead_information中
        if file_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
            overhead_information[f"img_{img_number}"] = file_path
            img_number += 1
        # 假如文件是pdf等等文件结尾的，则将其已pdf_{number}加入到overhead_information中
        elif file_path.endswith((".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xls", ".xlsx", ".json")):
            overhead_information[f"doc_{doc_number}"] = file_path
            doc_number += 1
        elif file_path.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv")):
            overhead_information[f"video_{video_number}"] = file_path
            video_number += 1
        # 假如文件是其他文件结尾的，则将其已file_{number}加入到overhead_information中
        else:
            overhead_information[f"other_{other_number}"] = file_path
            other_number += 1

    chat_history = gradio_chat_message_list2ad_agent_chat_message_list(chatbot)
    # 弹出两个start_hint
    chat_history.pop(0)
    chat_history.pop(0)
    configuration = {"configurable": {"thread_id": user_id}}
    try:
        if is_end:
            # 判断本轮对话是否结束
            # 如果结束则为开始新的一轮
            result = asyncio.run(do_workflow_app.ainvoke(
                {"chat_history": chat_history,
                 "overhead_information": overhead_information}, config=configuration, stream_mode="values"))
            if "__interrupts__" in result:
                interrupt_info_is_end_true: Interrupt = result["__interrupts__"][-1]
                hint = interrupt_info_is_end_true.value
                # 返回中断信息
                chatbot.append(gr.ChatMessage(role="assistant", content=hint))
                is_end = False
            else:
                result_number = result["return_result_number"]
                # 将result["chat_history"]的后result_number个元素添加到chatbot中
                for i in range(result_number, 0, -1):
                    chatbot.append(result["chat_history"]
                                   [-i].to_gradio_chat_message())
                is_end = True
        else:
            # 如果没有结束则视为对之前信息的补充
            # 调用agent
            result = asyncio.run(do_workflow_app.ainvoke(
                Command(update={"suggestion": user_question}), config=configuration, stream_mode="values"))
            if "__interrupts__" in result:
                interrupt_info_is_end_false: Interrupt = result["__interrupts__"][-1]
                hint = interrupt_info_is_end_false.value
                # 返回中断信息
                chatbot.append(gr.ChatMessage(role="assistant", content=hint))
                is_end = False
            else:
                # 获取修改后的视频的路径
                result_number = result["return_result_number"]
                # 将result["chat_history"]的后result_number个元素添加到chatbot中
                for i in range(result_number, 0, -1):
                    chatbot.append(result["chat_history"]
                                   [-i].to_gradio_chat_message())
                is_end = True
        return "", chatbot, is_end
    except Exception as e:
        logger.error(f"Error in chat_with_ad_agent: {e}")
        logger.error(traceback.format_exc())  # 打印完整的调用堆栈
        return "", chatbot, is_end
