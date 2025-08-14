from agent.exception import SDXL_MV_AdapterError
from agent.utils import get_time_id
from config import logger
from config import conf
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
import subprocess
SERVER_IP = conf.get("comfyui.server_ip")
SERVER_USER = "root"
REMOTE_DIR = "/data/aigc/qws/ComfyUI/input_images/"  # 远程服务器存储图片地址
WORKFILE_PATH = conf.get_path(
    "comfyui.MVAdapter_workflow_json_path")  # 工作流文件路径
SERVER_ADDRESS = conf.get("comfyui.server_address")


async def run_sdxl_mv_adapter_i2i(
    image_path: str = "",
    positive_prompt: str = "",
    negative_prompt: Optional[str] = "",
    width: int = 768,
    height: int = 768,
    num_views: int = 4,
    steps: Optional[int] = 50,
    cfg: Optional[float] = 3.0,
    output_image_dir: str = "",
):
    """
    运行 sdxl 多视角生成模型
    Args:
        workflow (dict): 工作流内容
        new_positive_prompt (str): 新的正向提示词
        new_negative_prompt (Optional[str], optional): 新的负向提示词.
        new_width (int): 新的工作流输出图片宽度. Defaults to 1024.
        new_height (int): 新的工作流输出图片高度. Defaults to 1024.
        new_num_views (int): 新的生成视角的数量。 Defaults to 6.
        new_steps (int): 新的降噪步数。 Defaults to 25.
        new_cfg (int): 新的CFG值，控制随机性和提示词服从性，值过高会导致质量下降。 Defaults to 3.0.
        input_image_path (str): 输入图片的绝对路径
        output_image_dir (str): 输出图片的目录
    """
    # 生成客户端唯一 ID
    CLIENT_ID = str(uuid.uuid4())

    # 上传图片到服务器上：
    new_input_image_path = upload_image(image_path)

    # 加载工作流
    workflow = get_workflow(WORKFILE_PATH)

    # 修改工作流
    new_workflow = modify_workflow(
        workflow,
        new_positive_prompt=positive_prompt,
        new_negative_prompt=negative_prompt,
        new_width=width,
        new_height=height,
        new_num_views=num_views,
        new_steps=steps,
        new_cfg=cfg,
        new_image_path=new_input_image_path,
    )

    # 运行
    prompt_id = post_job(SERVER_ADDRESS, CLIENT_ID, new_workflow)
    output_images = get_images(SERVER_ADDRESS, prompt_id)

    # 存储
    return save_images(SERVER_ADDRESS, output_images, output_image_dir)


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
    new_width: int = 768,
    new_height: int = 768,
    new_num_views: int = 6,
    new_steps: Optional[int] = 50,
    new_cfg: Optional[float] = 3.0,
    new_image_path: str = "",
) -> dict:
    """
    根据用户的需求修改工作流中的内容
    Args:
        workflow (dict): 工作流内容
        new_positive_prompt (str): 新的正向提示词
        new_negative_prompt (Optional[str], optional): 新的负向提示词.
        new_width (int): 新的工作流输出图片宽度. Defaults to 1024.
        new_height (int): 新的工作流输出图片高度. Defaults to 1024.
        new_num_views (int): 新的生成视角的数量。 Defaults to 6.
        new_steps (int): 新的降噪步数。 Defaults to 25.
        new_cfg (int): 新的CFG值，控制随机性和提示词服从性，值过高会导致质量下降。 Defaults to 3.0.
        new_image_path (str): 新的图像路径
    Returns:
        dict: 新的工作流内容
    """
    # 修改提示词
    if (
        "6" in workflow
        and "inputs" in workflow["6"]
        and "prompt" in workflow["6"]["inputs"]
        and "negative_prompt" in workflow["6"]["inputs"]
    ):
        workflow["6"]["inputs"]["prompt"] = new_positive_prompt
        workflow["6"]["inputs"]["negative_prompt"] = new_negative_prompt
    else:
        raise ValueError("❌ 检测到6号节点不包含文本，无法修改。")

    # 修改生成图像长宽
    if (
        "8" in workflow
        and "inputs" in workflow["8"]
        and "width" in workflow["8"]["inputs"]
        and "height" in workflow["8"]["inputs"]
    ):
        workflow["8"]["inputs"]["width"] = new_width
        workflow["8"]["inputs"]["height"] = new_height
    else:
        raise ValueError("❌ 检测到8号节点不包含高宽比设置，无法修改。")

    # 修改视角数量
    if (
        "4" in workflow
        and "inputs" in workflow["4"]
        and "num_views" in workflow["4"]["inputs"]
    ):
        workflow["4"]["inputs"]["num_views"] = new_num_views
    else:
        raise ValueError("❌ 检测到4号节点不包含视角数量设置，无法修改。")

    # 修改采样器内容
    if (
        "6" in workflow
        and "inputs" in workflow["6"]
        and "seed" in workflow["6"]["inputs"]
        and "steps" in workflow["6"]["inputs"]
        and "cfg" in workflow["6"]["inputs"]
        and "num_views" in workflow["6"]["inputs"]
        and "width" in workflow["6"]["inputs"]
        and "height" in workflow["6"]["inputs"]
    ):
        # 修改随机种子
        new_seed = random.randint(0, 2**64 - 1)
        workflow["6"]["inputs"]["seed"] = new_seed
        workflow["6"]["inputs"]["steps"] = new_steps
        workflow["6"]["inputs"]["cfg"] = new_cfg
        workflow["6"]["inputs"]["num_views"] = new_num_views
        workflow["6"]["inputs"]["width"] = new_width
        workflow["6"]["inputs"]["height"] = new_height
        workflow["6"]["inputs"]["height"] = new_height
    else:
        raise ValueError("❌ 检测到6号节点不包含采样器设置，无法修改。")

    # 修改输入图片路径
    if (
        "7" in workflow
        and "inputs" in workflow["7"]
        and "image" in workflow["7"]["inputs"]
    ):
        workflow["7"]["inputs"]["image"] = new_image_path
    else:
        raise ValueError("❌ 检测到7号节点不包含输入图片路径设置，无法修改。")
    return workflow


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
        raise RuntimeError(f"❌ 获取失败: {e}")


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
        raise RuntimeError(f"❌ 提交失败: {e}")
    except KeyError:
        raise RuntimeError(f"❌ 返回数据有误: {resp.text}")
    except ValueError:
        raise RuntimeError(f"❌ 非合法 JSON: {resp.text}")


def save_images(server_address: str, outputs: dict, output_dir: str = "./images"):
    """
    下载11号节点的图片，支持自定义输出目录和文件名前缀，
    Args:
        server_address (str): 服务器地址
        outputs (dict): 从 get_images 获取的输出数据
        output_dir (str): 输出图片的目录
    """
    os.makedirs(output_dir, exist_ok=True)
    if "11" not in outputs:
        raise SDXL_MV_AdapterError("11号节点无图像数据")
    node_output = outputs["11"]
    images = node_output.get("images", [])
    if not images:
        raise SDXL_MV_AdapterError("11号节点无图像数据")
    # 下载图片
    image_list = []
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
                logger.error(f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                logger.error(image_resp.text[:200])
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
            output_path = os.path.join(output_dir, f"{get_time_id()}{ext}")
            # 保存图片
            image.save(output_path)
            image_list.append(output_path)
        except Exception as e:
            logger.error(f"❌ 图片解码失败: {params}")
            logger.error("返回内容前200字符:", image_resp.content[:200])
            logger.error(e)
    return image_list


def upload_image(local_input_image_path: str = "") -> str:
    """
    上传本地图片到指定服务器上
    Args:
        local_input_image_path(str): 本地图片文件存储的绝对路径

    Returns:
        str: 图片存放路径
    """
    if not os.path.isfile(local_input_image_path):
        raise FileNotFoundError(f"本地图片不存在: {local_input_image_path}")

    # 获取图片名称
    image_name = os.path.basename(os.path.normpath(local_input_image_path))

    try:
        cmd = [
            "scp",
            "-i",
            "/root/.ssh/id_rsa",
            "-r",
            local_input_image_path,
            f"{SERVER_USER}@{SERVER_IP}:{REMOTE_DIR}",
        ]
        subprocess.run(cmd, check=True)

        # 返回远程目录完整路径
        remote_full_path = os.path.join(REMOTE_DIR, image_name)
        return remote_full_path
    except Exception as e:
        raise RuntimeError(f"❌ 上传失败: {e}")


if __name__ == "__main__":
    # 信息配置
    positive_prompt = """3d style"""  # 正面提示词
    negative_prompt = (
        """watermark, ugly, deformed, noisy, blurry, low contrast"""  # 负面提示词
    )
    width, height = 1024, 1024  # 图像宽高
    input_image_path = "/data/qws/Call_for_ComfyUI/input_images/5838f0a4-7e70-4b7f-bf44-cece5981852d.png"  # 输入本地图片存储的绝对路径
    output_image_dir = "./images"  # 输出文件夹
    num_views = 4  # 生成视角数量

    # 可选填参数
    steps = 50  # 降噪步数
    cfg = 3.0  # CFG 值，控制随机性和提示词服从性，值过高会导致质量下降

    asyncio.run(
        run_sdxl_mv_adapter_i2i(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_views=num_views,
            steps=steps,
            cfg=cfg,
            input_image_path=input_image_path,
            output_image_dir=output_image_dir,
        )
    )
