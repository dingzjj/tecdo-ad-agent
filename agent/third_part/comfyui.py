from agent.utils import logger
import requests
import uuid
import json
import time
from PIL import Image
import io
import os


def get_workflow(filename):
    """加载工作流"""
    if os.path.exists(filename):
        with open(filename, "r") as f:
            prompt = json.load(f)
        return prompt
    else:
        raise FileNotFoundError(f"{filename} does not exist.")


def modify_workflow(workflow, new_text):
    """
    修改工作流中61号节点的text内容。

    参数:
        workflow (dict): 工作流JSON数据
        new_text (str): 新的text内容

    返回:
        dict: 修改后的工作流
    """

    # 修改61号节点的text内容
    if (
        "61" in workflow
        and "inputs" in workflow["61"]
        and "text" in workflow["61"]["inputs"]
    ):
        workflow["61"]["inputs"]["text"] = new_text
    return workflow


def post_job(server_address, client_id, prompt):
    logger.info("📤 提交任务中...")
    resp = requests.post(
        f"http://{server_address}/prompt",
        headers={"Content-Type": "application/json"},
        json={"prompt": prompt, "clientId": client_id},
    )
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]
    return prompt_id


def get_images(server_address, prompt_id):
    logger.info("⏳ 等待执行完成...")
    while True:
        history_resp = requests.get(
            f"http://{server_address}/history/{prompt_id}")
        history_data = history_resp.json()
        if prompt_id in history_data and "outputs" in history_data[prompt_id]:
            break
        time.sleep(1)

    # print(json.dumps(history_data, indent=2))
    outputs = history_data[prompt_id]["outputs"]
    return outputs
