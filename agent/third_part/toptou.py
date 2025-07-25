from pydantic import BaseModel
from typing import Literal
from agent.third_part.aliyunoss import share_file_in_oss
from agent.utils import judge_file_local_or_url
import requests
import time
import hashlib
import json
import os
from typing import List, Dict, Optional, Any
from config import conf, logger


class ToptouAPI:
    """Toptou API 客户端"""

    def __init__(self, auth_token: Optional[str] = None, base_url: str = "http://toptou-open.tec-do.com"):
        """
        初始化 Toptou API 客户端

        Args:
            auth_token: 认证令牌，如果为None则从配置文件读取
            base_url: API基础URL
        """
        self.auth_token = auth_token or conf.get("toptou_auth_token", "")
        self.base_url = base_url
        self.secret_key = conf.get("toptou_secret_key", "")

        if not self.auth_token:
            logger.warning(
                "Toptou auth_token 未配置，请在 config.json 中添加 toptou_auth_token")

    def _generate_signature(self, timestamp: int) -> str:
        """
        生成签名

        Args:
            timestamp: 时间戳，毫秒级
        """
        if not self.secret_key:
            return ""

        data = {
            "timestamp": str(timestamp),
            "auth-token": self.auth_token
        }

        token = self.secret_key + self._loop_token(data)
        return self._md5(token).lower()

    def _loop_token(self, params: Dict) -> str:
        """
        遍历数据并生成token

        Args:
            params: 参数字典
        """
        encode = []
        keys = sorted(params.keys())

        for key in keys:
            value = params[key]
            if isinstance(value, dict):
                encode.append(f"{key}={self._loop_token(value)}")
            elif isinstance(value, list):
                continue  # 忽略列表类型
            else:
                encode.append(f"{key}={value}")

        return "".join(encode)

    def _md5(self, input: str) -> str:
        """
        生成MD5摘要

        Args:
            input: 输入字符串
        """
        return hashlib.md5(input.encode('utf-8')).hexdigest()

    def _get_headers(self) -> Dict[str, Any]:
        """
        获取公共请求头
        Args:
            data: 请求数据字典

        Returns:
            请求头字典
        """
        timestamp = int(time.time())
        sign = self._generate_signature(timestamp)

        headers = {
            'auth-token': self.auth_token,
            'timestamp': str(timestamp),
            'sign': sign,
            'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
            'content-type': 'application/json;charset=UTF-8',
            'Accept': '*/*',
            'Host': 'toptou-open.tec-do.com',
            'Connection': 'keep-alive',
        }
        return headers

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        发送API请求

        Args:
            method: HTTP方法
            endpoint: API端点
            data: 请求数据

        Returns:
            API响应数据
        """
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(
                    url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Toptou API 请求失败: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Toptou API 响应解析失败: {e}")
            raise


def get_material_folder(parent_folder_ids: Optional[List[str]] = None) -> Dict:
    """
    获取素材文件夹列表

    Args:
        parent_folder_ids: 父文件夹ID列表，如果为空则获取根文件夹

    Returns:
        文件夹列表数据
    """
    api = ToptouAPI()

    data = {
        "parentFolderIds": parent_folder_ids or []
    }

    try:
        result = api._make_request(
            "POST", "open/v1/material/folder/list", data)
        # 根据返回结果
        return result["data"]
    except Exception as e:
        logger.error(f"获取素材文件夹列表失败: {e}")
        return {"success": False, "error": str(e)}


async def upload_material_to_toptou(
    file_path: str,
    folder_id: Optional[int] = None,
    material_name: Optional[str] = None,
    material_type: Literal["image", "video"] = "image"
) -> Dict:
    """
    上传素材到 Toptou

    Args:
        file_path: 文件路径(in local or url)
        folder_id: 目标文件夹ID，如果为None则上传到根目录
        material_name: 素材名称，如果为None则使用文件名
        material_type: 素材类型,1:"image", 2:"video" 

    Returns:
        上传结果数据{"success":表示是否成功，}
    """

    # 判断文件路径是url还是本地文件
    file_type = judge_file_local_or_url(file_path)
    if file_type == "local":
        file_path = share_file_in_oss(file_path, material_name, 0.5)
    api = ToptouAPI()

    # 如果没有指定素材名称，使用文件名
    if not material_name:
        material_name = os.path.basename(file_path)

    items = []

    # 准备上传数据
    item = {
        "url": file_path,
        "name": material_name,
        "materialType": 1 if material_type == "image" else 2,
        "folderId": folder_id,
    }
    items.append(item)

    result = api._make_request(
        "POST", "open/v1/material/upload/async", {"items": items})
    if result["code"] == '0':
        return result["data"]["taskId"]
    else:
        logger.error(f"素材上传失败: {result['message']}")
        raise Exception(f"素材上传失败: {result['message']}")


class MaterialItem(BaseModel):
    file_path: str
    folder_id: Optional[int] = None
    material_name: Optional[str] = None
    material_type: Literal["image", "video"] = "image"


async def upload_material_list_to_toptou(
    material_list: list[MaterialItem]

) -> int:
    # 最后返回一个task_id
    if len(material_list) == 0:
        raise Exception("素材列表为空")
    items = []
    api = ToptouAPI()
    # 创建一个任务
    for material in material_list:
        item = {
            "url": material.file_path,
            "name": material.material_name,
            "materialType": 1 if material.material_type == "image" else 2,
            "folderId": material.folder_id,
        }
        items.append(item)

    result = api._make_request(
        "POST", "open/v1/material/upload/async", {"items": items})
    if result["code"] == '0':
        return result["data"]["taskId"]
    else:
        logger.error(f"素材上传失败: {result['message']}")
        raise Exception(f"素材上传失败: {result['message']}")


def get_folder_id_by_name(folder_name: str) -> int:
    """
    根据文件夹名称获取文件夹ID
    -1表示不存在
    """
    folders = get_material_folder()
    for folder in folders:
        if folder["folderName"] == folder_name:
            return folder["folderId"]
    return -1


def create_material_folder(folder_name: str, parent_folder_id: Optional[int] = None) -> int:
    """
    创建素材文件夹,有问题则报错，没问题则返回文件夹ID

    Args:
        folder_name: 文件夹名称
        parent_folder_id: 父文件夹ID，如果为None则创建在根目录

    Returns:
        创建结果数据
    """
    api = ToptouAPI()

    data = {
        "parentFolderId": parent_folder_id or "",
        "folderName": folder_name
    }

    if parent_folder_id:
        data["parentFolderId"] = parent_folder_id

    result = api._make_request(
        "POST", "open/v1/material/folder/create", data)
    # 根据结果进行判断
    if result["code"] == '0':
        return result["data"]["folderId"]
    elif result["code"] == '500000':
        return get_folder_id_by_name(folder_name=folder_name)
    else:
        logger.error(f"创建素材文件夹失败: {result['message']}")
        raise Exception(f"创建素材文件夹失败: {result['message']}")


def get_upload_task_status(task_id: str) -> Dict:
    # 1:进行中  2:全部成功  3:部分成功 4:失败
    api = ToptouAPI()
    result = api._make_request(
        "POST", f"open/v1/material/task/get", {"taskId": task_id})
    # status: int = result["status"]
    return result