      
from agent.third_part.prompt import ANALYSE_IMAGE_VEO3_PROMPT_MODEL_SHOW_en, ANALYSE_IMAGE_VEO3_PROMPT_MODEL_WALK_en, ANALYSE_IMAGE_VEO3_PROMPT_MODEL_SHOW_WITH_SUGGESTION_en, ANALYSE_IMAGE_VEO3_PROMPT_MODEL_WALK_WITH_SUGGESTION_en, ANALYSE_IMAGE_KLING_PROMPT_MODEL_STAND_SHOW_en, ANALYSE_IMAGE_KLING_PROMPT_MODEL_CAT_WALK_en, ANALYSE_IMAGE_KLING_PROMPT_MODEL_STAND_SHOW_WITH_SUGGESTION_en, ANALYSE_IMAGE_KLING_PROMPT_MODEL_CAT_WALK_WITH_SUGGESTION_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en, ANALYSE_IMAGE_HUMAN_PROMPT_WITH_SUGGESTION_en, MODIFY_KLING_PROMPT_WITH_SUGGESTION_en, MODIFY_PROMPT_WITH_SUGGESTION_en
import mimetypes
import json
from vertexai.generative_models import Part
from agent.llm import get_gemini_multimodal_model
from agent.utils import get_url_data
import os
from abc import abstractmethod, ABC
from typing import List
import httpx
import uuid
import time
import asyncio
from config import conf
from config import logger
from google.genai import types
from agent.third_part.aliyunoss import share_file_in_oss
from google import genai
from moviepy.editor import VideoFileClip
import mimetypes
from agent.mini_agent import ActionTypesClassifier
from typing import Literal
action_types = [
    "模特展示衣服",
    "模特走秀",
    "模特转身",
    "模特调整衣服",
    "模特用手抚摸衣服",
    "模特提起裙子"
]

class CreateVideoError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class I2VStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_video_prompt(self, product, product_info, img_path, img_info, duration: int, action_type: str = "model_show"):
        """生成视频提示词
        product: 商品名称
        product_info: 商品信息
        img_path: 模特图片路径
        img_info: 模特图片信息
        duration: 视频时长
        type: 视频类型（model_show, model_walk
        return: 视频提示词
        """
        raise NotImplementedError(
            "generate_video_prompt method must be implemented")

    @abstractmethod
    def generate_video_prompt_with_suggestion(self, product, product_info, img_path, img_info, duration: int, suggestion: str, action_type: str = "model_show"):
        """
        根据suggestion生成视频提示词
        """
        raise NotImplementedError(
            "generate_video_prompt_with_suggestion method must be implemented")

    @abstractmethod
    async def execute_generate_video(self, img_path, positive_prompt: str, negative_prompt: str,  duration: int) -> str:
        """执行策略的逻辑
        img_path: 模特图片路径
        positive_prompt: 视频提示词
        negative_prompt: 视频负向提示词
        duration: 视频时长
        return: 视频url
        """
        raise NotImplementedError("execute method must be implemented")


class I2VStrategyChain:
    def __init__(self, strategies: List[I2VStrategy]):
        self.strategies = strategies

    def get_strategy(self, i2v_strategy: str):
        """
        根据策略名称获取策略
        """
        for strategy in self.strategies:
            if strategy.name == i2v_strategy:
                return strategy
        raise Exception(f"不支持的策略: {i2v_strategy}")

    async def execute_chain_with_prompt(self, img_path, video_positive_prompt: str, video_negative_prompt: str, duration: int, resolution: dict = {},  i2v_strategy: str = "keling"):
        strategy = self.get_strategy(i2v_strategy)
        video_url = await strategy.execute_generate_video(
            img_path=img_path, positive_prompt=video_positive_prompt, negative_prompt=video_negative_prompt, duration=duration)
        return video_url

    async def execute_chain_with_suggestion(self, product, product_info, img_path, img_info, duration: int, resolution: dict = {}, action_type: str = "model_show", suggestion: str = "", i2v_strategy: str = "keling"):
        """
        返回视频提示词，视频负向提示词，视频url
        """
        strategy = self.get_strategy(i2v_strategy)
        video_positive_prompt, video_negative_prompt = strategy.generate_video_prompt_with_suggestion(
            product, product_info, img_path, img_info, duration, suggestion, action_type=action_type)
        video_url = await strategy.execute_generate_video(
            img_path, video_positive_prompt, video_negative_prompt, duration)
        return video_positive_prompt, video_negative_prompt, video_url

    async def execute_chain(self, product, product_info, img_path, img_info, duration: int, resolution: dict = {}, action_type: str = "model_show", i2v_strategy: str = "keling"):
        """
        返回视频提示词，视频负向提示词，视频url(url是global url)
        """
        strategy = self.get_strategy(i2v_strategy)
        video_positive_prompt, video_negative_prompt = strategy.generate_video_prompt(
            product, product_info, img_path, img_info, duration, action_type=action_type)
        video_url = await strategy.execute_generate_video(
            img_path, video_positive_prompt, video_negative_prompt, duration)
        return video_positive_prompt, video_negative_prompt, video_url

    async def execute_chain_with_prompt(self, img_path, video_positive_prompt: str, video_negative_prompt: str, duration: int, resolution: dict = {},  i2v_strategy: str = "keling"):
        strategy = self.get_strategy(i2v_strategy)
        video_url = await strategy.execute_generate_video(
            img_path=img_path, positive_prompt=video_positive_prompt, negative_prompt=video_negative_prompt, duration=duration)
        return video_url

KELING_STRATEGY = "keling"
class Keling(I2VStrategy):
    def __init__(self, model: str = "kling-v2-1"):
        name: str = "keling"
        self.model = model
        super().__init__(name)

    def generate_video_prompt(self, product, product_info, img_path, img_info, duration: int, action_type: str = "模特展示衣服"):
        classifier = ActionTypesClassifier(
            categories=["模特展示衣服", "模特走秀", "模特转身", "模特调整衣服", "模特用手抚摸衣服", "模特提起裙子","以上都不匹配"])
        category = classifier.classify(action_type)
        
        with open(img_path, "rb") as file:
            image_data = file.read()
        mime_type, _ = mimetypes.guess_type(img_path)
        if mime_type is None:
            mime_type = "image/jpeg"
        if category == "模特展示衣服":
            ANALYSE_IMAGE_SYSTEM_PROMPT_en = ANALYSE_IMAGE_KLING_PROMPT_MODEL_STAND_SHOW_en
            video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
        elif category == "模特走秀":
            ANALYSE_IMAGE_SYSTEM_PROMPT_en = ANALYSE_IMAGE_KLING_PROMPT_MODEL_CAT_WALK_en
            video_negative_prompt = "deformation, poor composition, model standing still, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
        elif category == "模特转身":
            video_positive_prompt = "The model stands tall in a neutral pose and begins to turn gracefully in place, rotating her body in a slow full circle. As she turns, the fabric of the clothing subtly flares and sways, revealing the outfit from all angles. The motion is smooth and elegant, highlighting the texture and fit of the garment in motion."
            video_negative_prompt = "deformation, poor composition, model standing still, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            return video_positive_prompt, video_negative_prompt
        elif category == "模特调整衣服":
            video_positive_prompt = "The model stands still in a relaxed posture, using one hand to gently smooth the front of the outfit and subtly adjust the sleeves, collar, or hemline. These refined movements emphasize the fit and texture of the garment, conveying a sense of attention to detail and elegance."
            video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            return video_positive_prompt, video_negative_prompt
        elif category == "模特用手抚摸衣服":
            video_positive_prompt = "The model stands still in an elegant pose, gently raising one hand and slowly gliding it along the contour of the garment to subtly guide attention to its shape and craftsmanship. The movement is smooth and expressive, enhancing the visual appeal of the fabric."
            video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            return video_positive_prompt, video_negative_prompt
        elif category == "模特提起裙子":
            video_positive_prompt = "The model stands gracefully in place and gently lifts both sides of the skirt slightly with her hands, holding the fabric momentarily to reveal its soft drape and inner lining. She then slowly lowers the skirt back into place, allowing it to fall naturally and smoothly. This fluid motion emphasizes the skirt’s volume, texture, and elegance while keeping the overall posture composed and refined."
            video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            return video_positive_prompt, video_negative_prompt
        else:
            # "以上都不匹配"
            video_positive_prompt = action_type
            video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            return video_positive_prompt, video_negative_prompt
        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
            response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)
        response = gemini_generative_model.generate_content(
            [
                ANALYSE_IMAGE_HUMAN_PROMPT_en.format(
                    product=product, product_info=product_info, img_info=img_info, duration=duration),
                Part.from_data(image_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content_json = json.loads(content)
        video_positive_prompt = content_json.get("prompt", "")
        return video_positive_prompt, video_negative_prompt

    def generate_video_prompt_with_suggestion(self, product, product_info, img_path, img_info, duration: int, suggestion: str = "", action_type: str = "模特展示衣服"):
        classifier = ActionTypesClassifier(
            categories=["模特展示衣服", "模特走秀", "模特转身", "模特调整衣服", "模特用手抚摸衣服", "模特提起裙子"])
        category = classifier.classify(action_type+" "+ suggestion)

        with open(img_path, "rb") as file:
            image_data = file.read()
        mime_type, _ = mimetypes.guess_type(img_path)
        if mime_type is None:
            mime_type = "image/jpeg"
        if category == "模特展示衣服" or category == "模特走秀":
            if category == "模特展示衣服":
                ANALYSE_IMAGE_SYSTEM_PROMPT_en = ANALYSE_IMAGE_KLING_PROMPT_MODEL_STAND_SHOW_WITH_SUGGESTION_en
                video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            elif category == "模特走秀":
                ANALYSE_IMAGE_SYSTEM_PROMPT_en = ANALYSE_IMAGE_KLING_PROMPT_MODEL_CAT_WALK_WITH_SUGGESTION_en
                video_negative_prompt = "deformation, poor composition, model standing still, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            gemini_generative_model = get_gemini_multimodal_model(
                system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
                response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)
            response = gemini_generative_model.generate_content(
                [
                    ANALYSE_IMAGE_HUMAN_PROMPT_WITH_SUGGESTION_en.format(
                        product=product, product_info=product_info, img_info=img_info, duration=duration, user_suggestion=suggestion),
                    Part.from_data(image_data, mime_type=mime_type)
                ]
            )
        else:
            if category == "模特转身":
                video_positive_prompt = "The model stands tall in a neutral pose and begins to turn gracefully in place, rotating her body in a slow full circle. As she turns, the fabric of the clothing subtly flares and sways, revealing the outfit from all angles. The motion is smooth and elegant, highlighting the texture and fit of the garment in motion."
                video_negative_prompt = "deformation, poor composition, model standing still, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            elif category == "模特调整衣服":
                video_positive_prompt = "The model stands still in a relaxed posture, using one hand to gently smooth the front of the outfit and subtly adjust the sleeves, collar, or hemline. These refined movements emphasize the fit and texture of the garment, conveying a sense of attention to detail and elegance."
                video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            elif category == "模特用手抚摸衣服":
                video_positive_prompt = "The model stands still in an elegant pose, gently raising one hand and slowly gliding it along the contour of the garment to subtly guide attention to its shape and craftsmanship. The movement is smooth and expressive, enhancing the visual appeal of the fabric."
                video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            elif category == "模特提起裙子":
                video_positive_prompt = "The model stands gracefully in place and gently lifts both sides of the skirt slightly with her hands, holding the fabric momentarily to reveal its soft drape and inner lining. She then slowly lowers the skirt back into place, allowing it to fall naturally and smoothly. This fluid motion emphasizes the skirt’s volume, texture, and elegance while keeping the overall posture composed and refined."
                video_negative_prompt = "deformation, poor composition, camera movement, model walking, appearance of other people or loss of facial or limb structure such as bad teeth, bad eyes, bad limbs."
            gemini_generative_model = get_gemini_multimodal_model(
                system_prompt=MODIFY_KLING_PROMPT_WITH_SUGGESTION_en,
                response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)
            response = gemini_generative_model.generate_content(
                [
                    MODIFY_PROMPT_WITH_SUGGESTION_en.format(
                        video_positive_prompt=video_positive_prompt, user_suggestion=suggestion),
                ]
            )
        content = response.candidates[0].content.parts[0].text
        content_json = json.loads(content)
        video_positive_prompt = content_json.get("prompt", "")
        return video_positive_prompt, video_negative_prompt

    async def execute_generate_video(self, img_path, positive_prompt: str, negative_prompt: str,  duration: Literal[5, 10]) -> str:
        # 使用keling的api生成视频，最终返回一个url，url是视频的地址
        http_client = httpx.Client(timeout=httpx.Timeout(
            600.0, connect=60.0), follow_redirects=True)
        KLING_API_KEY = conf.get("KLING_API_KEY")
        KLING_SECRET = conf.get("KLING_SECRET")
        KLING_API_BASE_URL = conf.get("KLING_API_BASE_URL")
        image_url = share_file_in_oss(img_path, f"{uuid.uuid4()}.jpg")
        payload = {
            # kling-v1, kling-v1-5, kling-v1-6, kling-v2-master, kling-v2-1, kling-v2-1-master
            "model": self.model,
            "mode": "pro",  # std 标准，pro 增强
            "image": image_url,
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "duration": duration  # 枚举值：5，10
        }

        headers = {
            "X-API-Key": KLING_API_KEY,
            "X-Secret-Key": KLING_SECRET,
            "Content-Type": "application/json",
        }
        url = f"{KLING_API_BASE_URL}/gen_video_task_by_image_create"

        response = http_client.post(url, headers=headers, json=payload)
        response = response.json()
        task_id = response["data"]["taskId"]

        headers = {
            "X-API-Key": KLING_API_KEY,
            "X-Secret-Key": KLING_SECRET,
            "Content-Type": "application/json",
        }
        url = f"{KLING_API_BASE_URL}/gen_video_task_by_image_get/{task_id}"
        interval = 30  # 每30秒检查一次任务状态
        start_time = time.time()
        max_wait = 600  # 最长等待时间10分钟

        while True:
            try:
                response = http_client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            except httpx.RequestError as e:
                logger.error(f"请求异常: {type(e).__name__}: {e}")
                raise Exception(f"请求异常: {type(e).__name__}: {e}")
            except httpx.HTTPStatusError as e:
                logger.error(f"请求失败，状态码：{e.response.status_code}")
                raise CreateVideoError(f"请求失败，状态码：{e.response.status_code}")
            except Exception as e:
                logger.error(f"解析响应失败: {e}")
                raise CreateVideoError(f"解析响应失败: {e}")
            task_status = data.get("task_status")
            if time.time() - start_time > max_wait:
                logger.error("等待超时，任务未完成。")
                raise CreateVideoError("等待超时，任务未完成。")

            if task_status == "processing":
                logger.info("视频正在处理中，继续等待...")
            elif task_status == "submitted":
                logger.info("任务已提交，等待处理...")
            elif task_status == "succeed":
                video_list = data.get("videos", [])
                if video_list:
                    url = video_list[0].get("url")
                    if url:
                        return url
                    else:
                        logger.error("视频结果为空。")
                        raise CreateVideoError("视频结果为空。")
                else:
                    logger.error("视频结果为空。")
                    raise CreateVideoError("视频结果为空。")
            elif task_status == "failed":
                logger.error("任务失败，无法获取视频。")
                raise CreateVideoError("任务失败，无法获取视频。")
            else:
                logger.error(f"未知任务状态: {task_status}")
            await asyncio.sleep(interval)
import base64
import subprocess
import requests
import time
import os
from typing import Optional, Dict, Any
class Veo3(I2VStrategy):
    
    def generate_video_prompt(self, product, product_info, img_path, img_info, duration: int, action_type: str = "model_show"):
        pass
    
    def generate_video_prompt_with_suggestion(self, product, product_info, img_path, img_info, duration: int, suggestion: str, action_type: str = "model_show"):
        pass
    
    async def execute_generate_video(self, img_path, positive_prompt: str, negative_prompt: str,  duration: int) -> str:
        pass


    def __init__(self, project_id: str, location_id: str = "us-central1", 
                 output_dir: str = "./output", model_id: str = "veo-3.0-generate-preview"):
        name: str = "veo3"

        super().__init__(name)
        """
        初始化视频生成器
        
        参数:
            project_id (str): Google Cloud项目ID
            location_id (str): 服务位置，默认为us-central1
            output_dir (str): 视频保存目录，默认为./output
            model_id (str): 模型ID，默认为veo-3.0-generate-preview
        """
        self.project_id = project_id
        self.location_id = location_id
        self.model_id = model_id
        self.api_endpoint = f"{location_id}-aiplatform.googleapis.com"
        
        # 创建输出目录
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"✅ Veo3VideoGenerator 初始化完成")
        print(f"   项目ID: {project_id}")
        print(f"   服务位置: {location_id}")
        print(f"   输出目录: {output_dir}")
    
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
        
        url = f"https://{self.api_endpoint}/v1/projects/{self.project_id}/locations/{self.location_id}/publishers/google/models/{self.model_id}:predictLongRunning"
        
        response = requests.post(url, headers=headers, json=request_payload)
        print(f"提交响应: {response.status_code}")
        
        if response.status_code == 200:
            operation_name = response.json().get("name")
            print(f"✅ 任务提交成功，操作ID: {operation_name}")
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
        
        fetch_url = f"https://{self.api_endpoint}/v1/projects/{self.project_id}/locations/{self.location_id}/publishers/google/models/{self.model_id}:fetchPredictOperation"
        payload = {"operationName": operation_name}
        
        while True:
            print("🔍 检查操作状态...")
            response = requests.post(fetch_url, headers=headers, json=payload)
            data = response.json()
            
            if "error" in data:
                raise Exception(f"视频生成失败: {data['error']}")
            elif "done" in data and data["done"]:
                print("✅ 视频生成完成！")
                videos = data.get("response", {}).get("videos", [])
                if videos and "bytesBase64Encoded" in videos[0]:
                    video_base64 = videos[0]["bytesBase64Encoded"]
                    filename = f"video_{int(time.time())}.mp4"
                    filepath = os.path.join(self.output_dir, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(video_base64))
                    print(f"🎬 视频已保存为：{filepath}")
                    return filepath
                else:
                    raise Exception("未找到视频内容")
            else:
                print("⏳ 正在处理中...")
                time.sleep(30)
    
    def generate_video(self, prompt: str, image_path: Optional[str] = None, 
                      aspect_ratio: str = "16:9", duration_seconds: str = "8",
                      resolution: str = "1080p", generate_audio: bool = True,
                      sample_count: int = 1, add_watermark: bool = False) -> str:
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
        print(f"🎬 开始生成视频...")
        print(f"   提示词: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        if image_path:
            print(f"   输入图片: {image_path}")
        
        # 构建请求实例
        instance = {
            "prompt": prompt
        }
        
        # 如果提供了图片路径，添加图片信息
        if image_path:
            pic_base64 = self._image_to_base64(image_path)
            # 从文件扩展名推断MIME类型
            ext = os.path.splitext(image_path)[1].lower()
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
            "endpoint": f"projects/{self.project_id}/locations/{self.location_id}/publishers/google/models/{self.model_id}",
            "instances": [instance],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": sample_count,
                "durationSeconds": duration_seconds,
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
                break
            except Exception as e:
                print(f"视频生成失败: {e}")
                time.sleep(3)
                continue
        print(f"🎉 视频生成完成！文件路径: {video_path}")
        return video_path

i2v_strategy_chain = I2VStrategyChain([Keling()])

    