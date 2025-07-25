      
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
    def generate_video_prompt(self, product, product_info, img_path, img_info, duration: int, type: str = "model_show"):
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
    def generate_video_prompt_with_suggestion(self, product, product_info, img_path, img_info, duration: int, suggestion: str, type: str = "model_show"):
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

    @abstractmethod
    async def adapt_resolution(self, src_video_path, resolution: dict):
        """对生成的视频进行适配
        src_video_path: 源视频路径(在本地)
        resolution: 目标分辨率
        return: 适配后的视频路径
        """
        raise NotImplementedError(
            "adapt_resolution method must be implemented")

    @abstractmethod
    async def remove_watermark(self, src_video_path, desc_video_path):
        """
        移除水印(水印在视频右下角)
        """
        raise NotImplementedError(
            "remove_watermark method must be implemented")


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

    async def execute_chain_with_suggestion(self, product, product_info, img_path, img_info, duration: int, resolution: dict = {}, video_type: str = "model_show", suggestion: str = "", i2v_strategy: str = "keling"):
        """
        返回视频提示词，视频负向提示词，视频url
        """
        strategy = self.get_strategy(i2v_strategy)
        video_positive_prompt, video_negative_prompt = strategy.generate_video_prompt_with_suggestion(
            product, product_info, img_path, img_info, duration, suggestion, type=video_type)
        video_url = await strategy.execute_generate_video(
            img_path, video_positive_prompt, video_negative_prompt, duration)
        return video_positive_prompt, video_negative_prompt, video_url

    async def execute_chain(self, product, product_info, img_path, img_info, duration: int, resolution: dict = {}, video_type: str = "model_show", i2v_strategy: str = "keling"):
        """
        返回视频提示词，视频负向提示词，视频url(url是global url)
        """
        strategy = self.get_strategy(i2v_strategy)
        video_positive_prompt, video_negative_prompt = strategy.generate_video_prompt(
            product, product_info, img_path, img_info, duration, type=video_type)
        video_url = await strategy.execute_generate_video(
            img_path, video_positive_prompt, video_negative_prompt, duration)
        return video_positive_prompt, video_negative_prompt, video_url

    async def execute_chain_with_prompt(self, img_path, video_positive_prompt: str, video_negative_prompt: str, duration: int, resolution: dict = {},  i2v_strategy: str = "keling"):
        strategy = self.get_strategy(i2v_strategy)
        video_url = await strategy.execute_generate_video(
            img_path=img_path, positive_prompt=video_positive_prompt, negative_prompt=video_negative_prompt, duration=duration)
        return video_url


class Keling(I2VStrategy):
    def __init__(self, model: str = "kling-v2-1"):
        name: str = "keling"
        self.model = model
        super().__init__(name)

    def generate_video_prompt(self, product, product_info, img_path, img_info, duration: int, type: str = "模特展示衣服"):
        classifier = ActionTypesClassifier(
            categories=["模特展示衣服", "模特走秀", "模特转身", "模特调整衣服", "模特用手抚摸衣服", "模特提起裙子","以上都不匹配"])
        category = classifier.classify(type)
        
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
            video_positive_prompt = type
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

    def generate_video_prompt_with_suggestion(self, product, product_info, img_path, img_info, duration: int, suggestion: str = "", type: str = "模特展示衣服"):
        classifier = ActionTypesClassifier(
            categories=["模特展示衣服", "模特走秀", "模特转身", "模特调整衣服", "模特用手抚摸衣服", "模特提起裙子"])
        category = classifier.classify(type+" "+ suggestion)

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

    async def remove_watermark(self, src_video_path, desc_video_path):
        """
        移除水印(水印在视频右下角)
        """
        pass

    async def adapt_resolution(self, src_video_path, resolution: dict):
        # 返回原文件
        return share_file_in_oss(src_video_path, f"{str(uuid.uuid4())}.mp4")

    async def execute_generate_video(self, img_path, positive_prompt: str, negative_prompt: str,  duration: int) -> str:
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


i2v_strategy_chain = I2VStrategyChain([Keling()])

    