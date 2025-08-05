from config import logger
import os
import requests
import mimetypes
from config import conf
import oss2


def upload_to_aliyun_oss(access_key_id, access_key_secret, bucket_name, endpoint, file_path, object_name):
    # 创建认证和Bucket对象
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # 上传文件
    with open(file_path, 'rb') as fileobj:
        result = bucket.put_object(object_name, fileobj)

    if result.status == 200:
        # 拼接公网访问地址（前提是你设置了公共读权限）
        public_url = f"https://{bucket_name}.{endpoint}/{object_name}"
        print(f"上传成功，公网访问链接: {public_url}")
        return public_url
    else:
        print(f"上传失败，状态码: {result.status}")
        return None


def upload_file(API_KEY, SECRET_KEY, File_path):
    url = "https://dev01-ai-orchestration.tec-develop.cn/api/ai/s3/v1/upload"
    headers = {
        "X-API-Key": API_KEY,
        "X-Secret-Key": SECRET_KEY
    }
    filename = os.path.basename(File_path)
    mime_type, _ = mimetypes.guess_type(File_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    with open(File_path, "rb") as f:
        files = {
            "file": (filename, f, mime_type)
        }
        response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        data = response.json()
        return data.get("endpoint")
    else:
        logger.error(f"oss上传失败，状态码: {response.status_code}")
        raise Exception(f"oss上传失败，状态码: {response.status_code}")


def share_file_in_oss(local_file_path, object_name, expires: float = 7):
    API_KEY = conf.get("OSS_API_KEY")
    SECRET_KEY = conf.get("OSS_SECRET_KEY")

    return upload_file(API_KEY, SECRET_KEY, local_file_path)
