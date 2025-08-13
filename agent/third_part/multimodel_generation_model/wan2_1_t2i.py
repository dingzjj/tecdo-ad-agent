from agent.exception import Wan2_1_T2IError
import requests
import uuid
import json
import time
from PIL import Image
import io
import os
import random
from requests import RequestException
from typing import Optional
import asyncio

from agent.utils import get_time_id
from config import conf, logger


async def run_wan2_1_t2i(
    positive_prompt: str = "",
    negative_prompt: Optional[str] = "",
    batch_size: Optional[int] = 1,
    steps: Optional[int] = 8,
    width: int = 1280,
    height: int = 1280,
    denoise: Optional[float] = 1.0,
    cfg: Optional[float] = 1.0,
    output_dir: str = "./images",
):
    """
    运行 Wan2.1 文生写实图像生成模型

    Args:
        positive_prompt (str): 正面提示
        negative_prompt (str): 负面提示
        batch_size (int): 批量数量
        steps (int): 步数
        width (int): 输出的图像宽度
        height (int): 输出的图像高度
        denoise (float): K采样器的去噪参数
        cfg (float): K采样器的 CFG 参数
    """
    SERVER_ADDRESS = conf.get("comfyui.server_address")
    # 生成客户端唯一 ID
    CLIENT_ID = str(uuid.uuid4())
    WORKFILE_PATH = conf.get_path("comfyui.wan2_1_t2i_workflow_json_path")
    # 加载工作流
    workflow = get_workflow(WORKFILE_PATH)

    # 修改工作流
    new_workflow = modify_workflow(
        workflow,
        new_positive_prompt=positive_prompt,
        new_negative_prompt=negative_prompt,
        new_width=width,
        new_height=height,
        new_steps=steps,
        new_cfg=cfg,
        new_batch_size=batch_size,
        new_denoise=denoise,
    )

    # 运行
    prompt_id = post_job(SERVER_ADDRESS, CLIENT_ID, new_workflow)
    output_images = get_images(SERVER_ADDRESS, prompt_id)

    # 存储
    return save_images(SERVER_ADDRESS, output_images, output_dir)


def get_workflow(workflow_file: str) -> dict:
    """
    加载工作流文件

    Args:
        workflow_file (str): 工作流文件路径

    Returns:
        dict: 工作流内容
    """
    try:
        with open(workflow_file, "r") as f:
            content = json.load(f)
        return content
    except Exception as e:
        raise FileNotFoundError(f"❌ Couldn't found the file: {workflow_file}")


def modify_workflow(
    workflow: dict,
    new_positive_prompt: str = "",
    new_negative_prompt: Optional[str] = "",
    new_width: int = 1024,
    new_height: int = 1024,
    new_batch_size: Optional[int] = 1,
    new_steps: Optional[int] = 8,
    new_cfg: Optional[float] = 1.0,
    new_denoise: Optional[float] = 1.0,
) -> dict:
    """
    修改工作流内容

    Args:
        workflow (dict): 原始工作流
        new_positive_prompt (str): 新的正面提示，不为空时，会替换旧的正面提示
        new_negative_prompt (str, optional): 新的负面提示，不为空时，会替换旧的负面提示
        new_width (int): 生成图像宽度
        new_height (int): 生成图像高度
        new_batch_size (int): 批量生成数量
        new_steps (int): 降噪步骤
        new_cfg (float): 控制随机性和提示词服从性，值过高会导致质量下降
        new_denoise (float): 降噪强度，降低该值会保留原图的大部分内容

    Returns:
        dict: 修改后的工作流内容
    """

    # 修改正面提示
    if (
        "61" in workflow
        and "inputs" in workflow["61"]
        and "text" in workflow["61"]["inputs"]
    ):
        workflow["61"]["inputs"]["text"] = new_positive_prompt
    else:
        raise Wan2_1_T2IError("❌ 未找到61号节点")

    # 修改负面提示
    if (
        "4" in workflow
        and "inputs" in workflow["4"]
        and "text" in workflow["4"]["inputs"]
    ):
        workflow["4"]["inputs"]["text"] = new_negative_prompt
    else:
        raise Wan2_1_T2IError("❌ 未找到4号节点")

    # 修改生成质量
    if (
        "58" in workflow
        and "inputs" in workflow["58"]
        and "value" in workflow["58"]["inputs"]
    ):
        workflow["58"]["inputs"]["value"] = new_width
    else:
        raise Wan2_1_T2IError("❌ 未找到58号节点")

    if (
        "59" in workflow
        and "inputs" in workflow["59"]
        and "value" in workflow["59"]["inputs"]
    ):
        workflow["59"]["inputs"]["value"] = new_height
    else:
        raise Wan2_1_T2IError("❌ 未找到59号节点")

    # 修改 K采样器的内容
    # 修改34号节点的随机种子值
    if "34" in workflow and "inputs" in workflow["34"]:
        workflow["34"]["inputs"]["seed"] = random.randint(0, 2**64 - 1)

        workflow["34"]["inputs"]["steps"] = new_steps

        workflow["34"]["inputs"]["cfg"] = new_cfg

        workflow["34"]["inputs"]["denoise"] = new_denoise
    else:
        raise Wan2_1_T2IError("❌ 未找到34号节点")

    # 修改图像生成数量
    if "5" in workflow and "inputs" in workflow["5"]:
        workflow["5"]["inputs"]["batch_size"] = new_batch_size
    else:
        raise Wan2_1_T2IError("❌ 未找到5号节点")

    return workflow


def post_job(server_address: str, client_id: str, workflow: dict) -> dict:
    """
    提交工作流任务

    Args:
        server_address (str): 服务地址
        client_id (str): 用户ID
        workflow (dict): 工作流

    Returns:
        dict: 工作流任务 ID
    """

    try:
        resp = requests.post(
            f"http://{server_address}/prompt",
            headers={"Content-Type": "application/json"},
            json={"prompt": workflow, "clientId": client_id},
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]
        return prompt_id
    except RequestException as e:
        raise Wan2_1_T2IError(f"❌ 提交失败: {e}")
    except KeyError:
        raise Wan2_1_T2IError(f"❌ 返回数据有误: {resp.text}")
    except ValueError:
        raise Wan2_1_T2IError(f"❌ 非合法 JSON: {resp.text}")


def get_images(server_address: str, prompt_id: str) -> str:
    """
    从 ComfyUI 中获取当前任务生成的图片信息

    Args:
        server_address (str): ComfyUI 服务器地址
        prompt_id (str): 当前任务生成的图片对应的工作流 ID

    Returns:
        str: 生成的图片路径
    """
    try:
        while True:
            history_resp = requests.get(
                f"http://{server_address}/history/{prompt_id}")
            if history_resp.status_code == 200:
                history_data = history_resp.json()
                if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                    break
                time.sleep(1)

        outputs = history_data[prompt_id]["outputs"]
        return outputs
    except RequestException as e:
        raise Wan2_1_T2IError(f"❌ 获取失败: {e}")


def save_images(server_address: str, outputs: dict, output_dir: str = "./images"):
    """
    下载63号节点的图片，支持自定义输出目录和文件名前缀，

    Args:
        server_address (str): 服务器地址
        outputs (dict): 从 get_images 获取的输出数据
        output_dir (str): 输出图片的目录
    """
    os.makedirs(output_dir, exist_ok=True)

    if "63" not in outputs:
        raise Wan2_1_T2IError("❌ 未找到63号节点")

    node_output = outputs["63"]
    images = node_output.get("images", [])
    if not images:
        raise Wan2_1_T2IError("❌ 63号节点无图像数据")

    # 下载图片
    for image_info in images:
        params = {
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "temp"),
        }
        view_url = f"http://{server_address}/view"

        try:
            image_resp = requests.get(view_url, params=params, timeout=10)
            if image_resp.status_code != 200:
                continue

            image = Image.open(io.BytesIO(image_resp.content))

            # 推断扩展名
            ext = os.path.splitext(image_info["filename"])[1].lower()
            if ext not in [".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"]:
                ext = ".jpg"

            # 处理 RGBA → RGB（JPG 不支持透明通道）
            if ext in [".jpg", ".jpeg"] and image.mode == "RGBA":
                image = image.convert("RGB")

            # 生成随机文件名并检查是否存在
            while True:
                random_filename = f"{get_time_id()}{ext}"
                output_path = os.path.join(output_dir, random_filename)
                if not os.path.exists(output_path):
                    break  # 找到一个唯一的文件名，退出循环

            # 保存图片
            image.save(output_path)
            logger.info(f"💾 已保存图片: {output_path}")
            return output_path
        except Exception as e:
            raise Wan2_1_T2IError(f"❌ 图片解码失败: {params}")


if __name__ == "__main__":
    # 信息配置
    positive_prompt = """
    春秋战国时期，孔子和他的弟子们齐聚学堂上，弟子们席地而坐，桌上都摆着竹卷，孔子手拿戒尺，讲书论经。
    """  # 正面提示词
    negative_prompt = """"""  # 负面提示词
    output_dir = "./images"  # 输出文件夹
    width, height = 1024, 1024  # 图像宽高

    # 可选填参数
    batch_size = 1  # 生成图像数量 (1-5)
    steps = 8  # 降噪步数
    denoise = 1.0  # 降噪强度，降低该值会保留原图的大部分内容
    cfg = 1.0  # CFG

    # 运行
    asyncio.run(
        run_wan2_1_t2i(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            batch_size=batch_size,
            steps=steps,
            width=width,
            height=height,
            denoise=denoise,
            cfg=cfg,
            output_dir=output_dir,
        )
    )
