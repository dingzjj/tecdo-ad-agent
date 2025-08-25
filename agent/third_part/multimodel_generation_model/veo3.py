from config import conf, logger
import httpx
import asyncio
import time
import uuid
from agent.third_part.aliyunoss import share_file_in_oss
from agent.exception import CreateVideoError
import os
import base64
import subprocess
import requests
from typing import Dict, Any, Literal
from agent.mini_agent import RephrasePromptAgent
from agent.exception import Veo3Error


class Veo3:
    def __init__(self, project_id: str = conf.get("veo3.project_id"), location_id: str = conf.get("veo3.location_id"),
                 output_dir: str = conf.get_path("veo3.output_dir"), model: str = conf.get("veo3.model_id")):
        """
        初始化视频生成器

        参数:
            project_id (str): Google Cloud项目ID
            location_id (str): 服务位置，默认为us-central1
            output_dir (str): 视频保存目录，默认为./output
            model (str): 模型ID，默认为veo-3.0-generate-preview
        """
        self.name: str = "veo3"
        self.project_id = project_id
        self.location_id = location_id
        self.model = model
        self.api_endpoint = f"{location_id}-aiplatform.googleapis.com"

        # 创建输出目录
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _image_to_base64(self, image_path: str) -> str:
        """
        将图片转换为Base64编码的字符串

        参数:
            image_path (str): 图片文件的路径

        返回:
            str: Base64编码的图片字符串
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_str = base64.b64encode(image_data).decode('utf-8')
            return base64_str

    def _get_access_token(self) -> str:
        """
        获取Google Cloud访问令牌

        返回:
            str: 访问令牌
        """
        try:
            result = subprocess.run(["gcloud", "auth", "print-access-token"],
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise Exception(f"获取访问令牌失败: {e}")

    def _submit_generation_task(self, request_payload: Dict[str, Any]) -> str:
        """
        提交视频生成任务

        参数:
            request_payload (dict): 请求载荷

        返回:
            str: 操作ID
        """
        access_token = self._get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        url = f"https://{self.api_endpoint}/v1/projects/{self.project_id}/locations/{
            self.location_id}/publishers/google/models/{self.model}:predictLongRunning"

        response = requests.post(url, headers=headers, json=request_payload)
        logger.info(f"提交响应: {response.status_code}")

        if response.status_code == 200:
            operation_name = response.json().get("name")
            logger.info(f"✅ 生成视频任务提交成功，操作ID: {operation_name}")
            return operation_name
        else:
            raise Exception(f"提交任务失败: {response.text}")

    def _fetch_result(self, operation_name: str) -> str:
        """
        获取生成结果

        参数:
            operation_name (str): 操作ID
        返回:
            str: 保存的视频文件路径
        """
        access_token = self._get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        fetch_url = f"https://{self.api_endpoint}/v1/projects/{self.project_id}/locations/{
            self.location_id}/publishers/google/models/{self.model}:fetchPredictOperation"
        payload = {"operationName": operation_name}

        while True:
            response = requests.post(fetch_url, headers=headers, json=payload)
            data = response.json()

            if "error" in data:
                raise Exception(f"视频生成失败: {data['error']}")
            elif "done" in data and data["done"]:
                logger.info("✅ 视频生成完成！")
                videos = data.get("response", {}).get("videos", [])
                if videos and "bytesBase64Encoded" in videos[0]:
                    video_base64 = videos[0]["bytesBase64Encoded"]
                    filename = f"video_{int(time.time())}.mp4"
                    filepath = os.path.join(self.output_dir, filename)

                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(video_base64))
                    logger.info(f"🎬 视频已保存为：{filepath}")
                    return filepath
                else:
                    raise Exception("未找到视频内容")
            else:
                logger.info("⏳ 正在处理中...")
                time.sleep(30)

    async def i2v(self, img_path: str, positive_prompt: str, negative_prompt: str, aspect_ratio: Literal["16:9", "9:16"] = "16:9", duration: Literal[8] = 8, resolution: Literal["1080p"] = "1080p", generate_audio=True, sample_count: int = 1, add_watermark: bool = False):
        """
        核心方法：生成视频

        参数:
            prompt (str): 文本提示词
            image_path (str, optional): 图片路径，如果提供则进行图片+文本生成视频
            aspect_ratio (str): 宽高比，默认16:9
            duration_seconds (str): 视频时长（秒），默认8秒
            resolution (str): 分辨率，默认1080p
            generate_audio (bool): 是否生成音频，默认True
            sample_count (int): 生成样本数量，默认1
            add_watermark (bool): 是否添加水印，默认False

        返回:
            str: 生成的视频文件路径
        """
        # 构建请求实例
        instance = {
            "prompt": positive_prompt
        }
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"图片文件不存在: {img_path}")
        pic_base64 = self._image_to_base64(img_path)
        # 从文件扩展名推断MIME类型
        ext = os.path.splitext(img_path)[1].lower()
        mime_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }
        mime_type = mime_type_map.get(ext, 'image/png')

        instance["image"] = {
            "bytesBase64Encoded": pic_base64,
            "mimeType": mime_type
        }
        # 构建请求载荷
        request_payload = {
            "endpoint": f"projects/{self.project_id}/locations/{self.location_id}/publishers/google/models/{self.model}",
            "instances": [instance],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": sample_count,
                "durationSeconds": duration,
                "personGeneration": "allow_all",
                "addWatermark": add_watermark,
                "includeRaiReason": True,
                "generateAudio": generate_audio,
                "resolution": resolution
            }
        }

        # 提交任务并获取结果(哪怕报错也不断重试，但最多重试3次)
        for _ in range(3):
            try:
                operation_name = self._submit_generation_task(request_payload)
                video_path = self._fetch_result(operation_name)
                logger.info(f"🎉 视频生成完成！文件路径: {video_path}")
                return video_path
            except Exception as e:
                logger.error(f"视频生成失败: {e}")
                if e["code"] == 3:
                    # 重构提示词
                    positive_prompt = RephrasePromptAgent().rephrase_prompt(
                        positive_prompt)
                    logger.info(f"重构提示词: {positive_prompt}")
        raise Veo3Error(f"视频生成失败")

    async def t2v(self, positive_prompt, negative_prompt, aspect_ratio: Literal["16:9", "9:16"] = "16:9", duration: Literal[8] = 8, resolution: Literal["1080p"] = "1080p", generate_audio=True, sample_count: int = 1, add_watermark: bool = False):
        """
        核心方法：生成视频

        参数:
            prompt (str): 文本提示词
            image_path (str, optional): 图片路径，如果提供则进行图片+文本生成视频
            aspect_ratio (str): 宽高比，默认16:9
            duration_seconds (str): 视频时长（秒），默认8秒
            resolution (str): 分辨率，默认1080p
            generate_audio (bool): 是否生成音频，默认True
            sample_count (int): 生成样本数量，默认1
            add_watermark (bool): 是否添加水印，默认False

        返回:
            str: 生成的视频文件路径
        """
        # 构建请求实例
        instance = {
            "prompt": positive_prompt
        }
        # 构建请求载荷
        request_payload = {
            "endpoint": f"projects/{self.project_id}/locations/{self.location_id}/publishers/google/models/{self.model}",
            "instances": [instance],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": sample_count,
                "durationSeconds": duration,
                "personGeneration": "allow_all",
                "addWatermark": add_watermark,
                "includeRaiReason": True,
                "generateAudio": generate_audio,
                "resolution": resolution
            }
        }

        # 提交任务并获取结果(哪怕报错也不断重试，但最多重试3次)
        for i in range(3):
            try:
                operation_name = self._submit_generation_task(request_payload)
                video_path = self._fetch_result(operation_name)
                logger.info(f"🎉 视频生成完成！文件路径: {video_path}")
                return video_path
            except Exception as e:
                logger.error(f"视频生成失败: {e}")
                if e["code"] == 3:
                    # 重构提示词
                    positive_prompt = RephrasePromptAgent().rephrase_prompt(
                        positive_prompt)
        raise Veo3Error(f"视频生成失败")
