from agent.utils import get_time_id
from agent.exception import QwenT2IError
from config import logger
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
from config import conf
from agent.mini_agent import GenerateImagePromptAgent


async def run_qwen_t2i(
    positive_prompt: str = "",
    negative_prompt: Optional[str] = "",
    output_dir: str = "./images",
    generate_mode: str = "custom",
    width: int = 1024,
    height: int = 768,
    batch_size: Optional[int] = 1,
    steps: Optional[int] = 25,
    cfg: Optional[float] = 3.0,
    shift: Optional[float] = 3.10,
    is_optimize_prompt_words: bool = False
):
    """
    运行 Qwen 图像生成模型

    Args:
        positive_prompt (str): 正面提示词
        negative_prompt (str): 负面提示词（可选）
        output_dir (str): 输出文件夹
        generate_mode (str): 图像生成模式
        width (int): 图像宽度（可选，默认值为 1024）
        height (int): 图像高度（可选，默认值为 768）
        batch_size (int): 批处理大小（可选，默认值为 1）
        steps (int): 生成步数（可选，默认值为 25）
        cfg (float): CFG 值（可选，默认值为 8.0）
        shift (float): 平移值（可选，默认值为 1.0）

    Tips:
        generate_mode 比例值参考："1:1", "3:4", "5:8", "9:16", "9:21", "4:3", "3:2", "16:9", "21:9"
        若 generate_mode = "custom"，则 width 和 height 必填
    """

    if is_optimize_prompt_words:
        positive_prompt = GenerateImagePromptAgent().generate_image_prompt(
            positive_prompt)

    SERVER_ADDRESS = conf.get("comfyui.server_address")
    # 生成客户端唯一 ID
    CLIENT_ID = str(uuid.uuid4())
    WORKFILE_PATH = conf.get_path("comfyui.qwen_t2i_workflow_json_path")
    # 加载工作流
    workflow = get_workflow(WORKFILE_PATH)

    # 修改工作流
    new_workflow = modify_workflow(
        workflow,
        new_positive_prompt=positive_prompt,
        new_negative_prompt=negative_prompt,
        new_generate_image_mode=generate_mode,
        new_width=width,
        new_height=height,
        new_steps=steps,
        new_cfg=cfg,
        new_batch_size=batch_size,
        new_shift=shift,
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
    new_generate_image_mode: str = "custom",
    new_batch_size: Optional[int] = 1,
    new_steps: Optional[int] = 25,
    new_cfg: Optional[float] = 3.0,
    new_shift: Optional[float] = 3.10,
) -> dict:
    """
    根据用户的需求修改工作流中的内容

    Args:
        workflow (dict): 工作流内容
        new_positive_prompt (str): 新的正向提示词
        new_negative_prompt (Optional[str], optional): 新的负向提示词.
        new_width (int): 新的工作流输出图片宽度. Defaults to 1024.
        new_height (int): 新的工作流输出图片高度. Defaults to 1024.
        new_generate_image_mode (str): 选择图像生成模式。可以选择 "custom" 自定义图像大小 或者 确定的图像比例值。 Defaults to "custom".
            比例值参考："1:1", "3:4", "5:8", "9:16", "9:21", "4:3", "3:2", "16:9", "21:9"
        new_batch_size (int): 新的生成图片的数量。 Defaults to 1.
        new_steps (int): 新的降噪步数。 Defaults to 25.
        new_cfg (int): 新的CFG值，控制随机性和提示词服从性，值过高会导致质量下降。 Defaults to 3.0.
        new_shift (float): 新的Shift值。 Defaults to 3.10.

    Returns:
        dict: 新的工作流内容
    """
    # 比例值映射
    ASPECT_RATIO_MAP = {
        "1:1": "1:1 square 1024x1024",
        "3:4": "3:4 portrait 896x1152",
        "5:8": "5:8 portrait 832x1216",
        "9:16": "9:16 portrait 768x1344",
        "9:21": "9:21 portrait 640x1536",
        "4:3": "4:3 landscape 1152x896",
        "3:2": "3:2 landscape 1216x832",
        "16:9": "16:9 landscape 1344x768",
        "21:9": "21:9 landscape 1536x640",
    }

    # 模式选择
    if new_generate_image_mode in ASPECT_RATIO_MAP:
        resolved_aspect_ratio = ASPECT_RATIO_MAP[new_generate_image_mode]
    elif new_generate_image_mode == "custom":
        resolved_aspect_ratio = "custom"
    else:
        raise ValueError(
            f"❌ 不支持的图像生成模式: {new_generate_image_mode}\n"
            f"支持的值: {list(ASPECT_RATIO_MAP.keys())} \n 或 'custom'"
        )

    # 修改提示词
    if (
        "6" in workflow
        and "inputs" in workflow["6"]
        and "text" in workflow["6"]["inputs"]
    ):
        workflow["6"]["inputs"]["text"] = new_positive_prompt
    else:
        raise ValueError("❌ 检测到6号节点不包含文本，无法修改。")

    if (
        "7" in workflow
        and "inputs" in workflow["7"]
        and "text" in workflow["7"]["inputs"]
    ):
        workflow["7"]["inputs"]["text"] = new_negative_prompt
    else:
        raise ValueError("❌ 检测到7号节点不包含文本，无法修改。")

    # 修改生成图像生成模式
    if "72" in workflow and "inputs" in workflow["72"]:
        workflow["72"]["inputs"]["batch_size"] = new_batch_size

        workflow["72"]["inputs"]["aspect_ratio"] = resolved_aspect_ratio

        if resolved_aspect_ratio == "custom":
            workflow["72"]["inputs"]["width"] = new_width
            workflow["72"]["inputs"]["height"] = new_height
        else:
            logger.info(f"✅ 已将72号节点的高宽比设置为: {resolved_aspect_ratio}")
    else:
        raise ValueError("❌ 检测到72号节点不包含高宽比设置，无法修改。")

    # 修改采样器内容
    if (
        "3" in workflow
        and "inputs" in workflow["3"]
        and "seed" in workflow["3"]["inputs"]
    ):
        # 修改随机种子
        new_seed = random.randint(0, 2**64 - 1)
        workflow["3"]["inputs"]["seed"] = new_seed

        workflow["3"]["inputs"]["steps"] = new_steps

        workflow["3"]["inputs"]["cfg"] = new_cfg
    else:
        raise ValueError("❌ 检测到3号节点不包含采样器设置，无法修改。")

    # 修改移位值
    if "66" in workflow and "inputs" in workflow["66"]:
        workflow["66"]["inputs"]["shift"] = new_shift
    else:
        raise ValueError("❌ 检测到66号节点不包含shift设置，无法修改。")

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
    下载74号节点的图片，支持自定义输出目录和文件名前缀，

    Args:
        server_address (str): 服务器地址
        outputs (dict): 从 get_images 获取的输出数据
        output_dir (str): 输出图片的目录
    """
    os.makedirs(output_dir, exist_ok=True)

    if "74" not in outputs:
        raise QwenT2IError("❌ 74号节点无图像数据")

    node_output = outputs["74"]
    images = node_output.get("images", [])
    if not images:
        raise QwenT2IError("❌ 74号节点无图像数据")

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
            raise QwenT2IError(f"❌ 图片解码失败: {params}")


if __name__ == "__main__":
    # 信息配置
    positive_prompt = """春秋战国时期，孔子和他的弟子们齐聚学堂上，弟子们席地而坐，桌上都摆着竹卷，孔子手拿戒尺，讲书论经。
    """  # 正面提示词
    negative_prompt = """"""  # 负面提示词
    output_dir = "./images"  # 输出文件夹
    generate_mode = (
        "custom"  # 生成模式其他选项： (1:1|3:4|5:8|9:16|9:21|4:3|3:2|16:9|21:9)
    )
    width, height = 1024, 768  # 图像宽高
    # 可选填信息
    batch_size = 1  # 生成图像数量 (1-5)
    steps = 20  # 降噪步数
    cfg = 3.0  # CFG 值，控制随机性和提示词服从性，值过高会导致质量下降
    shift = 3.10  # 移位值（1-5）

    asyncio.run(
        run_qwen_t2i(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            output_dir=output_dir,
            generate_mode=generate_mode,
            width=width,
            height=height,
            steps=steps,
            batch_size=batch_size,
            cfg=cfg,
            shift=shift,
        )
    )
