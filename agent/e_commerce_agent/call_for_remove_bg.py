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


# 支持的图像扩展名
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def get_workflow(filename):
    """加载工作流"""
    if os.path.exists(filename):
        with open(filename, "r") as f:
            prompt = json.load(f)
        return prompt
    else:
        raise FileNotFoundError(f"{filename} does not exist.")


def modify_workflow(workflow, new_image_path):
    """
    修改工作流中2号节点的image内容

    参数:
        workflow (dict): 工作流JSON数据
        new_image_path (str): 新的图片路径

    返回:
        dict: 修改后的工作流
    """

    # 修改2号节点的image内容
    if (
        "2" in workflow
        and "inputs" in workflow["2"]
        and "image" in workflow["2"]["inputs"]
    ):
        workflow["2"]["inputs"]["image"] = new_image_path

    return workflow


def post_job(server_address, client_id, prompt):
    try:
        resp = requests.post(
            f"http://{server_address}/prompt",
            headers={"Content-Type": "application/json"},
            json={"prompt": prompt, "clientId": client_id},
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


def get_images(server_address, prompt_id):
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


def save_node6_images(
    server_address, outputs, basename="output_node6", output_dir="./images"
):
    """
    下载6号节点的图片，不覆盖已有文件，自动命名。
    """
    os.makedirs(output_dir, exist_ok=True)
    if "6" in outputs:
        node_output = outputs["6"]
        images = node_output.get("images", [])
        for _, image_info in enumerate(images):
            params = {
                "filename": image_info["filename"],
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "temp"),
            }
            view_url = f"http://{server_address}/view"
            try:
                image_resp = requests.get(view_url, params=params)
                if image_resp.status_code != 200:
                    logger.error(f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                    logger.error(image_resp.text[:200])
                    continue

                image = Image.open(io.BytesIO(image_resp.content))

                # 自动判断扩展名
                ext = os.path.splitext(image_info["filename"])[-1].lower()
                if ext not in [".jpg", ".jpeg", ".png"]:
                    ext = ".jpg"

                # RGBA 转换（仅当保存为 JPG 时）
                if ext in [".jpg", ".jpeg"] and image.mode == "RGBA":
                    image = image.convert("RGB")

                # 自动生成唯一文件名
                # 使用 base_name + idx 命名，避免覆盖
                output_path = os.path.join(
                    output_dir, f"{basename}{ext}"
                )
                image.save(output_path)
            except Exception as e:
                logger.error(f"❌ 图片解码失败: {params}")
                logger.error("返回内容前200字符:", image_resp.content[:200])
                logger.error(e)
    else:
        logger.error("⚠️ 未找到6号节点的输出")


def process_image_dir(input_dir, output_dir, workflow_file, server_address, client_id):
    """
    批量处理输入目录中的所有图像

    参数:
        input_dir: 输入图片目录（绝对路径）
        output_dir: 输出图片目录
        workflow_file: 工作流 JSON 路径
        server_address: ComfyUI 地址
        client_id: UUID 客户端ID
    """
    # 检查目录
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"输入目录不存在: {input_dir}")

    workflow_template = get_workflow(workflow_file)

    # 遍历输入目录
    for fname in os.listdir(input_dir):
        fpath = os.path.join(input_dir, fname)
        if not os.path.isfile(fpath):
            continue

        ext = os.path.splitext(fname.lower())[1]
        if ext not in SUPPORTED_EXTENSIONS:
            logger.info(f"⏭️ 跳过非图像文件: {fname}")
            continue

        base_name = os.path.splitext(fname)[0]  # 获取不带扩展名的文件名

        try:
            rel_path = f"{input_dir}/{fname}"

            logger.info(f"\n🔄 处理图像: {fname}")

            # 每次都复制一份工作流（避免引用污染）
            workflow = json.loads(json.dumps(workflow_template))

            # 修改工作流
            modify_workflow(workflow, rel_path)

            # 提交任务
            prompt_id = post_job(server_address, client_id, workflow)

            # 获取输出
            outputs = get_images(server_address, prompt_id)

            # 保存结果
            save_node6_images(
                server_address, outputs, output_dir=output_dir, basename=base_name
            )

        except Exception as e:
            logger.error(f"❌ 处理 {fname} 时出错: {e}")
            continue
