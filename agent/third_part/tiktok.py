from pydantic import BaseModel
from config import logger
from config import conf
import time
import httpx
import asyncio
from config import conf


async def create_tt_avatar_task(api_key, secret_key, avatar_id, script_text):
    url = conf.get("tiktok_create_avatar_task_url")
    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }
    payload = {
        "material_packages": [
            {
                "avatar_id": avatar_id,
                "script": script_text
            }
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        logger.info(f"创建任务响应：{response.status_code} - {response.text}")
        response.raise_for_status()
        data = response.json()
        task_id = data.get("data", {}).get("list", [])[0].get("task_id")
        return task_id


async def poll_task_status(api_key, secret_key, task_id, interval=30, max_wait=600):
    url = f"https://dev01-ai-orchestration.tec-develop.cn/api/ai/tiktok/v1/tt-avatar/get-task?task_ids={
        task_id}"
    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }

    start_time = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                task_list = data.get("data", {}).get("list", [])
                if not task_list:
                    logger.info("任务列表为空，重试中...")
                else:
                    status = task_list[0].get("status")
                    if status == "SUCCESS":
                        return task_list[0].get("preview_url")
                    elif status == "FAILED":
                        logger.error("任务失败。")
                        return None
                    elif status == "PROCESSING":
                        logger.info("任务正在处理...")
                    elif status == "SUBMITED":
                        logger.info("任务已提交，等待中...")
                    else:
                        logger.error(f"未知状态: {status}")

            except Exception as e:
                logger.error(f"请求或解析出错：{e}")

            if time.time() - start_time > max_wait:
                logger.error("超时未完成任务。")
                return None

            await asyncio.sleep(interval)


async def create_tt_digital_human(text: str, digital_human_id: str = "7393172244749811728"):
    api_key = conf.get("tiktok_api_key")
    secret_key = conf.get("tiktok_secret_key")
    task_id = await create_tt_avatar_task(api_key, secret_key, digital_human_id, text)
    result = await poll_task_status(api_key, secret_key, task_id)
    return result


async def create_tt_avatar_task_list(api_key, secret_key, avatar_id, script_texts: list[str]):
    url = "https://dev01-ai-orchestration.tec-develop.cn/api/ai/tiktok/v1/tt-avatar/create-task"
    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }

    payload = {
        "material_packages": [
            {
                "avatar_id": avatar_id,
                "script": script,
                "package_id": str(i + 1)
            }
            for i, script in enumerate(script_texts)
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        logger.info(f"创建任务响应：{response.status_code} - {response.text}")
        response.raise_for_status()
        data = response.json()

        task_list = data.get("data", {}).get("list", [])
        task_ids = [item.get("task_id") for item in task_list]

        return task_ids


async def get_tt_avatar_task_list(api_key, secret_key, task_ids, interval=30, max_wait=900) -> list[str | None]:
    """
    获取数字人视频任务列表
    max_wait: 最大等待时间，单位秒(超过最大等待时间则重新提交任务)
    interval: 轮询间隔，单位秒
    """
    url = "https://dev01-ai-orchestration.tec-develop.cn/api/ai/tiktok/v1/tt-avatar/get-task"
    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }
    result: list[str | None] = [None] * len(task_ids)
    params = [("task_ids", task_id) for task_id in task_ids]

    start_time = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                task_list = data.get("data", {}).get("list", [])

                if not task_list:
                    logger.info("任务列表为空，重试中...")
                else:
                    all_done = True
                    for task in task_list:
                        if task is None:
                            continue
                        task_id = task.get("task_id")
                        status = task.get("status")

                        if status == "SUCCESS":
                            # task_id 对应的
                            preview_url = task.get("preview_url")
                            # 将结果添加到preview_urls中
                            index = task_ids.index(task_id)
                            result[index] = preview_url
                        elif status == "FAILED":
                            logger.error(f"任务 {task_id} 失败。")
                            all_done = False
                        elif status in ["PROCESSING", "SUBMITED"]:
                            all_done = False
                        else:
                            logger.warning(f"任务 {task_id} 未知状态: {status}")
                            all_done = False

                    if all_done:
                        # 打印完成与未完成的
                        return result

            except Exception as e:
                logger.error(f"请求或解析出错：{e}")
                return result

            if time.time() - start_time > max_wait:
                logger.error("超时未完成所有任务。")
                return result

            await asyncio.sleep(interval)


class CreateTTDigitalHumanTask(BaseModel):
    task_id_list: list[str | None] = []  # 在这里是铺平的
    task_status_list: list[bool] = []  # True表示任务已完成，False表示任务未完成
    script_texts: list[str]
    total_number: int = 0
    completed_number: int = 0
    result: list[str | None] = []

    def __init__(self, script_texts: list[str], **kwargs):
        # Initialize with default values first
        task_status_list = [False] * len(script_texts)
        task_id_list = [None] * len(script_texts)
        total_number = len(script_texts)
        result = [None] * len(script_texts)

        # Call parent __init__ with all the data
        super().__init__(
            script_texts=script_texts,
            task_status_list=task_status_list,
            task_id_list=task_id_list,
            total_number=total_number,
            result=result,
            **kwargs
        )

    def task_id_to_index(self, task_id: str) -> int:
        return self.task_id_list.index(task_id)


async def create_tt_digital_human_list(texts: list[str], digital_human_id: str = "7393172244749811728") -> list[str | None] | None:
    """
    创建数字人视频任务，并返回视频url列表

    Args:
        texts: 文本列表，每个文本对应一个数字人视频
        digital_human_id: 数字人ID

    Returns:
        list[str | None] | None: 视频URL列表，与输入文本顺序对应，失败的任务返回None，如果所有任务都失败则返回None
    """
    if not texts:
        logger.warning("输入文本列表为空")
        return None

    api_key = conf.get("tiktok_api_key")
    secret_key = conf.get("tiktok_secret_key")
    batch_size = 3
    # 任务状态，任务id
    task = CreateTTDigitalHumanTask(texts)
    while task.completed_number < task.total_number:
        # 当前批次
        now_batch_size = 0
        now_batch_texts = []
        now_batch_index = []
        # 总状态
        task_ids_list = []
        # 提交任务
        for i in range(task.total_number):
            if not task.task_status_list[i]:
                now_batch_texts.append(task.script_texts[i])
                now_batch_index.append(i)
                now_batch_size += 1
            if (now_batch_size == batch_size or i == task.total_number - 1) and now_batch_size > 0:
                # task_ids -> list[str]
                task_ids = await create_tt_avatar_task_list(api_key, secret_key, digital_human_id, now_batch_texts)

                for now_index, index in enumerate(now_batch_index):
                    task.task_id_list[index] = task_ids[now_index]
                task_ids_list.append(task_ids)

                # 清空当前批次
                now_batch_size = 0
                now_batch_texts = []
                now_batch_index = []

        # 获取任务结果
        for task_ids in task_ids_list:
            # 120秒后超时，则认为任务失败
            now_results = await get_tt_avatar_task_list(api_key, secret_key, task_ids, interval=30, max_wait=120)
            # task_ids 与 now_results 一一对应

            for ri, url in enumerate(now_results):
                if url is not None:
                    task_id = task_ids[ri]
                    index = task.task_id_to_index(task_id)
                    task.result[index] = url
                    task.task_status_list[index] = True
                    task.completed_number += 1
    return task.result
