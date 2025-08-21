from agent.ad_agent.pojo import gradio_chat_message_list2ad_agent_chat_message_list, AdAgentChatMessage
import asyncio
import os
import traceback
from langchain_core.messages import HumanMessage
# 第三方库导入
from langgraph.types import Command, Interrupt
# 本地模块导入
from config import conf, logger
from agent.ad_agent.do_workflow import do_workflow_app
from typing import List
import gradio as gr
import time
from modules.util import chatbot_to_chat_history
from langchain_core.messages import AIMessage

from pojo import user_id
from agent.ad_agent.pojo import gradio_chat_message_list2ad_agent_chat_message_list, AdAgentChatMessage
from agent.ad_agent.pojo import gradio_chat_message_list2chat_message_list

from agent.ad_agent.art.agent_modules.agent import AdAgent

from agent.ad_agent.art.material_library import material_librarys

AdAgents: dict[str, AdAgent] = {}


def send_message_to_art_ad_agent(user_id, user_input, chatbot, user_material_id):
    chat_history = gradio_chat_message_list2chat_message_list(chatbot)
    chat_history.pop(0)
    # 弹出最后一个元素，因为此时chatbot中最后一个元素为用户输入
    chat_history.pop(-1)
    question = user_input["text"]
    user_files = user_input["files"]

    overhead_information = {}
    for file_path in user_files:
        # 等待上传完毕再往后运行，即等到该文件的大小大于0
        while os.path.getsize(file_path) == 0:
            time.sleep(1)
        # 假如文件是png等等文件结尾的，则将其已img_{number}加入到overhead_information中
        if file_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
            overhead_information[f"#{user_material_id}"] = {
                "content": file_path,
                "description": f"用户上传的图片"
            }
            user_material_id += 1
        # 假如文件是pdf等等文件结尾的，则将其已pdf_{number}加入到overhead_information中
        elif file_path.endswith((".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xls", ".xlsx", ".json")):
            overhead_information[f"#{user_material_id}"] = {
                "content": file_path,
                "description": f"用户上传的文档"
            }
            user_material_id += 1
        elif file_path.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv")):
            overhead_information[f"#{user_material_id}"] = {
                "content": file_path,
                "description": f"用户上传的视频"
            }
            user_material_id += 1
        # 假如文件是其他文件结尾的，则将其已file_{number}加入到overhead_information中
        else:
            overhead_information[f"#{user_material_id}"] = {
                "content": file_path,
                "description": f"用户上传的其他文件"
            }
            user_material_id += 1

    if user_id not in AdAgents:
        AdAgents[user_id] = AdAgent(user_id)
    result = AdAgents[user_id].invoke(
        message=question, overhead_information=overhead_information)
    # 假如返回的是中断，则返回中断信息
    # 假如上次中断了，则这次视为对上次中断的恢复
    chatbot.append(gr.ChatMessage(
        role="assistant", content=result))
    return None, chatbot, material_librarys[user_id].return_material_list(), user_material_id


# def send_message_to_ad_agent(user_id, user_input, chatbot):
#     chat_history = gradio_chat_message_list2chat_message_list(chatbot)
#     chat_history.pop(0)
#     # 弹出最后一个元素，因为此时chatbot中最后一个元素为用户输入
#     chat_history.pop(-1)
#     question = user_input["text"]
#     user_files = user_input["files"]
#     img_number = 1
#     doc_number = 1
#     video_number = 1
#     other_number = 1
#     overhead_information = {}
#     for file_path in user_files:
#         # 等待上传完毕再往后运行，即等到该文件的大小大于0
#         while os.path.getsize(file_path) == 0:
#             time.sleep(1)
#         # 假如文件是png等等文件结尾的，则将其已img_{number}加入到overhead_information中
#         if file_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
#             overhead_information[f"#image_{img_number}"] = {
#                 "content": file_path,
#                 "description": f"用户上传的图片{img_number}"
#             }
#             img_number += 1
#         # 假如文件是pdf等等文件结尾的，则将其已pdf_{number}加入到overhead_information中
#         elif file_path.endswith((".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xls", ".xlsx", ".json")):
#             overhead_information[f"#doc_{doc_number}"] = {
#                 "content": file_path,
#                 "description": f"用户上传的文档{doc_number}"
#             }
#             doc_number += 1
#         elif file_path.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv")):
#             overhead_information[f"#video_{video_number}"] = {
#                 "content": file_path,
#                 "description": f"用户上传的视频{video_number}"
#             }
#             video_number += 1
#         # 假如文件是其他文件结尾的，则将其已file_{number}加入到overhead_information中
#         else:
#             overhead_information[f"#other_{other_number}"] = {
#                 "content": file_path,
#                 "description": f"用户上传的其他文件{other_number}"
#             }
#             other_number += 1

#     result = AdAgent(user_id).invoke(
#         message=question, overhead_information=overhead_information, chat_history=chat_history)

#     for file_path in user_files:
#         overhead_information[file_path] = file_path
#     chatbot.append(gr.ChatMessage(
#         role="assistant", content=result["messages"][-1].content))
#     return None, chatbot, AdAgent(user_id).state.material_library.return_material_list()


def send_message_to_do_workflow(user_input, chatbot, is_end):
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
