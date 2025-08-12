import time
import httpx
import asyncio
from typing import Literal
from config import conf


async def run_kling2_1_t2v(prompt: str, negative_prompt: str, duration: Literal[5, 10], output_dir: str):
    http_client = httpx.Client(timeout=httpx.Timeout(
        600.0, connect=60.0), follow_redirects=True)
    KLING_API_KEY = conf.get("KLING_API_KEY")
    KLING_SECRET = conf.get("KLING_SECRET")
    KLING_API_BASE_URL = "https://dev01-ai-orchestration.tec-develop.cn/api/ai/kelin/v1"
    payload = {
        "model": "kling-v2-1",  # kling-v1, kling-v1-6, kling-v2-master, kling-v2-1-master
        "mode": "pro",  # std 标准，pro 增强
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "duration": duration,  # 枚举值：5，10
        # "cfg_scale": 0.5,
        # "aspect_ratio": "16:9", # 16:9, 9:16, 1:1
    }

    headers = {
        "X-API-Key": KLING_API_KEY,
        "X-Secret-Key": KLING_SECRET,
        "Content-Type": "application/json"
    }
    url = f"{KLING_API_BASE_URL}/gen_video_task_by_text_create"

    response = http_client.post(url, headers=headers, json=payload)
    task_id = response.json()["data"]["taskId"]
    timeout = httpx.Timeout(600.0, connect=60.0)
    http_client = httpx.Client(timeout=timeout, follow_redirects=True)

    KLING_API_BASE_URL = "https://dev01-ai-orchestration.tec-develop.cn/api/ai/kelin/v1"
    headers = {
        "X-API-Key": KLING_API_KEY,
        "X-Secret-Key": KLING_SECRET,
        "Content-Type": "application/json"
    }
    url = f"{KLING_API_BASE_URL}/gen_video_task_by_text_get/{task_id}"

    interval = 30  # 每30秒检查一次任务状态
    start_time = time.time()
    max_wait = 600  # 最长等待时间10分钟

    while True:
        try:
            response = http_client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as e:
            print(f"请求异常: {type(e).__name__}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            print(f"请求失败，状态码：{e.response.status_code}")
            return None
        except Exception as e:
            print(f"解析响应失败: {e}")
            return None

        task_status = data.get("task_status")
        print(f"任务状态: {task_status}")

        if time.time() - start_time > max_wait:
            print("等待超时，任务未完成。")
            return None

        if task_status == "processing":
            print("视频正在处理中，继续等待...")
        elif task_status == "submitted":
            print("任务已提交，等待处理...")
        elif task_status == "succeed":
            print("视频已生成！")
            video_list = data.get("videos", [])
            if video_list:
                return video_list[0].get("url")
            else:
                print("视频结果为空。")
                return None
        elif task_status == "failed":
            print("任务失败，无法获取视频。")
            return None
        else:
            print(f"未知任务状态: {task_status}")

        await asyncio.sleep(interval)
