from config import conf, logger
import httpx
import asyncio
import time
import uuid
from agent.third_part.aliyunoss import share_file_in_oss
from agent.exception import CreateVideoError
from typing import Literal
import os
from agent.utils import get_time_id


async def run_kling2_1_i2v(img_path: str, positive_prompt: str, negative_prompt: str, duration: Literal[5, 10], output_dir: str):
    # 使用keling的api生成视频，最终返回一个url，url是视频的地址
    http_client = httpx.Client(timeout=httpx.Timeout(
        600.0, connect=60.0), follow_redirects=True)
    KLING_API_KEY = conf.get("KLING_API_KEY")
    KLING_SECRET = conf.get("KLING_SECRET")
    KLING_API_BASE_URL = conf.get("KLING_API_BASE_URL")
    image_url = share_file_in_oss(img_path, f"{uuid.uuid4()}.jpg")
    payload = {
        # kling-v1, kling-v1-5, kling-v1-6, kling-v2-master, kling-v2-1, kling-v2-1-master
        "model": "kling-v2-1",
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
            raise CreateVideoError(f"请求异常: {type(e).__name__}: {e}")
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
                    # 将url保存到本地
                    video_path = os.path.join(
                        output_dir, f"{get_time_id()}.mp4")
                    response = http_client.get(url)
                    with open(video_path, "wb") as f:
                        f.write(response.content)
                    return video_path
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
