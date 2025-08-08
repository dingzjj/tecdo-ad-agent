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


def get_workflow(filename):
    """加载工作流"""
    if os.path.exists(filename):
        print(f"🔍 Loading prompt: {filename}")
        with open(filename, "r") as f:
            prompt = json.load(f)
        return prompt
    else:
        raise FileNotFoundError(f"{filename} does not exist.")


def modify_workflow(
    workflow,
    new_views=6,
    new_positive_text="",
    new_negative_text="",
    new_image_path="",
    new_width=1024,
    new_height=1024,
):
    """
    修改工作流中 6号中视角个数、正面提示、负面提示、图片生成大小，7号节点中的图片路径，以及 8号节点中的图片生成大小

    参数:
        workflow (dict): 工作流JSON数据
        new_views (int): 新的视角个数
        new_positive_text (str): 新的正面提示文本
        new_negetive_text (str): 新的负面提示文本
        new_image_path (str): 新的图片路径
        new_width (int): 新的宽度
        new_height (int): 新的高度

    返回:
        dict: 修改后的工作流
    """

    # 修改6号节点的inputs内容
    if "6" in workflow and "inputs" in workflow["6"]:
        workflow["6"]["inputs"]["num_views"] = new_views
        workflow["6"]["inputs"]["prompt"] = new_positive_text
        workflow["6"]["inputs"]["negative_prompt"] = new_negative_text
        workflow["6"]["inputs"]["width"] = new_width
        workflow["6"]["inputs"]["height"] = new_height
        workflow["6"]["inputs"]["seed"] = random.randint(0, 2**64 - 1)
    # 修改7号节点的image内容
    if (
        "7" in workflow
        and "inputs" in workflow["7"]
        and "image" in workflow["7"]["inputs"]
    ):
        if new_image_path:
            workflow["7"]["inputs"]["image"] = new_image_path
            print(f"✅ 已将7号节点的图像路径修改为: {new_image_path}")
        else:
            raise ValueError(f"图像路径不能为空.")

    # 修改8号节点的输出图片大小
    if "8" in workflow and "inputs" in workflow["8"]:
        workflow["8"]["inputs"]["width"] = new_width
        workflow["8"]["inputs"]["height"] = new_height

    return workflow


def post_job(server_address, client_id, prompt):
    print("📤 提交任务中...")
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
    print("⏳ 等待执行完成...")
    try:
        while True:
            history_resp = requests.get(
                f"http://{server_address}/history/{prompt_id}")
            if history_resp.status_code == 200:
                history_data = history_resp.json()
                if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                    break
                time.sleep(1)

        # print(json.dumps(history_data, indent=2))
        outputs = history_data[prompt_id]["outputs"]
        return outputs
    except RequestException as e:
        raise RuntimeError(f"❌ 获取失败: {e}")


def save_node11_images(server_address, outputs, output_dir):
    """
    只下载11号预览图像节点的图片。

    参数:
        server_address (str): 服务器地址
        outputs (dict): 从get_images获取的输出数据
    """
    os.makedirs("./images", exist_ok=True)
    # 只处理11号节点
    if "11" in outputs:
        node_output = outputs["11"]
        images = node_output.get("images", [])
        for idx, image_info in enumerate(images):
            params = {
                "filename": image_info["filename"],
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "temp"),
            }
            view_url = f"http://{server_address}/view"
            try:
                image_resp = requests.get(view_url, params=params)
                if image_resp.status_code != 200:
                    print(f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                    print(image_resp.text[:200])
                    continue

                image = Image.open(io.BytesIO(image_resp.content))
                output_path = os.path.join(output_dir, f"output_{idx}.jpg")
                image.save(output_path)

            except Exception as e:
                print(f"❌ 图片解码失败: {params}")
                print("返回内容前200字符:", image_resp.content[:200])
                print(e)
    else:
        print("⚠️ 未找到11号节点的输出")


def call_for_MVAdapter(positive_prompt: str, negative_prompt: str, image_path: str, output_dir: str):
    """
    调用MVAdapter
    """
    server_address = conf.get_path("comfyui_server_address")
    client_id = str(uuid.uuid4())  # generate client_id
    workflow_file = conf.get_path("MVAdapter_workflow_json_path")
    prompt = get_workflow(workflow_file)
    prompt = modify_workflow(
        prompt,
        new_positive_text=positive_prompt,
        new_negative_text=negative_prompt,
        new_image_path=image_path,
        new_views=4,
        new_width=768,
        new_height=768
    )

    # 运行
    prompt_id = post_job(server_address, client_id, prompt)
    outputs = get_images(server_address, prompt_id)

    # 保存图片
    save_node11_images(server_address, outputs, output_dir)
