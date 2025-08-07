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
        print(f"🔍 Loading prompt: {filename}")
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
        print(f"✅ 已将2号节点的image内容修改为: {new_image_path}")

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
        print(f"✅ 提交成功，prompt_id: {prompt_id}")
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


def get_unique_filename(base_dir, base_name, ext):
    """
    生成一个不重复的文件名，例如：output_node6_0.jpg、output_node6_1.jpg...
    """
    idx = 0
    while True:
        filename = f"{base_name}_{idx}{ext}"
        full_path = os.path.join(base_dir, filename)
        if not os.path.exists(full_path):
            return full_path
        idx += 1


def save_node6_images(server_address, outputs):
    """
    下载6号节点的图片，不覆盖已有文件，自动命名。
    """
    base_dir = "./images"
    os.makedirs(base_dir, exist_ok=True)
    print("🔻 开始下载6号节点的图片...")

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
                    print(f"⚠️ 图片请求失败: 状态码 {image_resp.status_code}")
                    print(image_resp.text[:200])
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
                output_path = get_unique_filename(
                    base_dir, "output_node6", ext)
                image.save(output_path)
                print(f"💾 已保存图片: {output_path}")
            except Exception as e:
                print(f"❌ 图片解码失败: {params}")
                print("返回内容前200字符:", image_resp.content[:200])
                print(e)
    else:
        print("⚠️ 未找到6号节点的输出")


def process_image_dir(input_dir, workflow_file, server_address, client_id):
    """
    批量处理输入目录中的所有图像

    参数:
        input_dir: 输入图片目录（绝对路径）
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

        try:
            rel_path = f"{input_dir}/{fname}"

            # 每次都复制一份工作流（避免引用污染）
            workflow = json.loads(json.dumps(workflow_template))

            # 修改工作流
            modify_workflow(workflow, rel_path)

            # 提交任务
            prompt_id = post_job(server_address, client_id, workflow)

            # 获取输出
            outputs = get_images(server_address, prompt_id)

            # 保存结果
            save_node6_images(server_address, outputs)

        except Exception as e:
            print(f"❌ 处理 {fname} 时出错: {e}")
            continue


if __name__ == "__main__":
    # 配置服务器信息
    server_address = "127.0.0.1:6009"
    client_id = str(uuid.uuid4())  # generate client_id

    # 加载工作流
    workflow_file = conf.get_path("remove_bg_workflow_json_path")

    """如果需要对其他节点的信息进行修改，
    可以先研究工作流 JSON 文件中的节点信息（或者打开 ComfyUI 查看每个节点中的属性值设置），
    再根据 modify_workflow 内容来模仿修改"""
    # 图片要用绝对路径
    input_dir = "/data/dzj/dataset/product1/images768_768"
    process_image_dir(input_dir, workflow_file, server_address, client_id)
