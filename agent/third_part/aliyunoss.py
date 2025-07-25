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


def share_file_in_oss(local_file_path, object_name, expires: float = 7):
    access_key_id = conf.get("aliyun_oss_access_key_id")
    access_key_secret = conf.get("aliyun_oss_access_key_secret")
    bucket_name = conf.get("aliyun_oss_bucket_name")
    endpoint = conf.get("aliyun_oss_endpoint")

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # 上传文件
    with open(local_file_path, 'rb') as fileobj:
        result = bucket.put_object(object_name, fileobj)

    if result.status == 200:
        # 拼接公网访问地址（前提是你设置了公共读权限）
        public_url = f"https://{bucket_name}.{endpoint}/{object_name}"
        return public_url
    else:
        raise Exception(f"上传失败，状态码: {result.status}")
