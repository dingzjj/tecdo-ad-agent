"""
配置管理模块
提供配置文件的读取、验证、路径管理等功能
"""

from datetime import datetime
import json
import os
import logging
from typing import Dict, Any, Optional, List

# 模块路径
modules_path = os.path.dirname(os.path.realpath(__file__))


class Config:
    """
    配置管理类，用于读取和管理config.json配置文件

    支持嵌套配置访问、路径处理、配置验证等功能
    """

    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，默认为config.json
        """
        self.config_file = config_file
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """
        加载配置文件

        从JSON文件中读取配置数据，如果文件不存在或格式错误会记录警告
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                logging.info(f"成功加载配置文件: {self.config_file}")
            else:
                logging.warning(f"配置文件 {self.config_file} 不存在，使用默认配置")
        except json.JSONDecodeError as e:
            logging.error(f"配置文件格式错误: {e}")
        except Exception as e:
            logging.error(f"加载配置文件时发生错误: {e}")

    def save_config(self) -> bool:
        """
        保存配置到文件

        Returns:
            保存是否成功
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
            logging.info(f"配置已保存到: {self.config_file}")
            return True
        except Exception as e:
            logging.error(f"保存配置文件时发生错误: {e}")
            return False

    def get_root_dir(self) -> str:
        """
        获取项目根目录

        Returns:
            项目根目录的绝对路径
        """
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def get(self, key: str, default: Any = None, is_path: bool = False) -> Any:
        """
        获取配置值，支持嵌套配置访问

        如果返回的是路径，则会返回绝对路径（父目录+配置中的路径）

        Args:
            key: 配置键名，支持点号分隔的嵌套键，如 "database.host" 或 "api.openai.key"
            default: 默认值
            is_path: 是否将返回值作为路径处理，如果为True则返回绝对路径

        Returns:
            配置值或默认值，如果是路径且is_path=True则返回绝对路径

        Examples:
            config.get("openai_api_key")  # 获取顶级配置
            config.get("database.host", "localhost")  # 获取嵌套配置
            config.get("api.openai.model", "gpt-3.5-turbo")  # 获取深层嵌套配置
            config.get("log_dir", "logs", is_path=True)  # 获取路径配置并返回绝对路径
        """
        # 获取配置值
        if "." not in key:
            value = self.config_data.get(key, default)
        else:
            # 处理嵌套键
            keys = key.split(".")
            current = self.config_data

            try:
                for k in keys:
                    if isinstance(current, dict) and k in current:
                        current = current[k]
                    else:
                        value = default
                        break
                else:
                    value = current
            except (KeyError, TypeError):
                value = default

        # 如果指定为路径且值为字符串，则转换为绝对路径
        if is_path and isinstance(value, str) and value:
            value = self._resolve_path(value)

        return value

    def _resolve_path(self, path: str) -> str:
        """
        解析相对路径为绝对路径

        Args:
            path: 相对路径

        Returns:
            绝对路径
        """
        # 获取配置文件所在目录作为父目录
        parent_dir = os.path.dirname(os.path.abspath(self.config_file))
        # 如果路径不是绝对路径，则拼接父目录
        if not os.path.isabs(path):
            path = os.path.join(parent_dir, path)
        # 标准化路径（处理 .. 和 . 等）
        return os.path.normpath(path)

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值，支持嵌套配置设置

        Args:
            key: 配置键名，支持点号分隔的嵌套键，如 "database.host" 或 "api.openai.key"
            value: 配置值

        Examples:
            config.set("openai_api_key", "sk-...")  # 设置顶级配置
            config.set("database.host", "localhost")  # 设置嵌套配置
            config.set("api.openai.model", "gpt-4")  # 设置深层嵌套配置
        """
        if "." not in key:
            self.config_data[key] = value
            return

        # 处理嵌套键
        keys = key.split(".")
        current = self.config_data

        # 遍历到最后一个键之前，确保路径存在
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        # 设置最终值
        current[keys[-1]] = value

    def has(self, key: str) -> bool:
        """
        检查配置键是否存在，支持嵌套配置检查

        Args:
            key: 配置键名，支持点号分隔的嵌套键

        Returns:
            如果键存在返回True，否则返回False

        Examples:
            config.has("openai_api_key")  # 检查顶级配置
            config.has("database.host")  # 检查嵌套配置
        """
        if "." not in key:
            return key in self.config_data

        # 处理嵌套键
        keys = key.split(".")
        current = self.config_data

        try:
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return False
            return True
        except (KeyError, TypeError):
            return False

    def validate_config(self) -> List[str]:
        """
        验证配置的有效性

        Returns:
            错误信息列表
        """
        errors = []

        # 检查必需的配置项
        if not self.get("openai_api_key"):
            errors.append("OpenAI API Key 未设置")

        # 检查端口号范围
        port = self.get("server_port", 7860)
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append("服务器端口号必须在1-65535之间")

        # 检查语言设置
        language = self.get("language", "auto")
        valid_languages = ["auto", "en_US", "ja_JP", "zh_CN"]
        if language not in valid_languages:
            errors.append(f"不支持的语言设置: {language}")

        return errors

    def reload(self) -> None:
        """重新加载配置文件"""
        self.load_config()

    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config_data.copy()

    def get_path(self, key: str, default: str = "", create_if_not_exists: bool = False) -> str:
        """
        获取路径配置值，自动转换为绝对路径

        Args:
            key: 配置键名，支持点号分隔的嵌套键
            default: 默认路径值
            create_if_not_exists: 如果路径不存在是否创建目录

        Returns:
            绝对路径字符串

        Examples:
            config.get_path("log_dir", "logs")  # 返回绝对路径
            config.get_path("data.output_dir", "output", create_if_not_exists=True)  # 返回嵌套配置的绝对路径并创建目录
        """
        path = self.get(key, default, is_path=True)

        if create_if_not_exists and path:
            os.makedirs(path, exist_ok=True)
        return path

    def get_url(self, key: str, default: str = "") -> str:
        """
        获取URL配置值，如果URL中包含local_url配置项，则将其替换为localhost

        Args:
            key: 配置键名，支持点号分隔的嵌套键
            default: 默认URL值

        Returns:
            处理后的URL字符串

        Examples:
            config.get_url("api_base_url", "http://localhost:8000")  # 返回处理后的URL
            config.get_url("minio.endpoint", "http://minio:9000")  # 返回处理后的MinIO端点
        """
        # 获取原始URL
        url = self.get(key, default)

        if not url or not isinstance(url, str):
            return default

        # 获取local_url配置
        local_url = self.get("local_url")

        # 如果local_url存在且URL中包含local_url，则替换为localhost
        if local_url and local_url in url:
            url = url.replace(local_url, "localhost")

        return url

    def ensure_path_exists(self, key: str, default: str = "") -> str:
        """
        确保路径存在，如果不存在则创建目录

        Args:
            key: 配置键名，支持点号分隔的嵌套键
            default: 默认路径值

        Returns:
            绝对路径字符串

        Examples:
            config.ensure_path_exists("log_dir", "logs")  # 确保日志目录存在
        """
        return self.get_path(key, default, create_if_not_exists=True)

    def get_file_path(self, key: str, default: str = "", check_exists: bool = False) -> str:
        """
        获取文件路径配置值，自动转换为绝对路径

        Args:
            key: 配置键名，支持点号分隔的嵌套键
            default: 默认文件路径值
            check_exists: 是否检查文件是否存在

        Returns:
            绝对文件路径字符串

        Examples:
            config.get_file_path("config_file", "config.json")  # 返回配置文件绝对路径
            config.get_file_path("data.input_file", "input.txt", check_exists=True)  # 检查文件是否存在
        """
        file_path = self.get_path(key, default)

        if check_exists and file_path and not os.path.isfile(file_path):
            logging.warning(f"文件不存在: {file_path}")

        return file_path


# 全局配置实例
conf = Config()
# os.environ["GOOGLE_CLOUD_PROJECT"] = conf.get("google_cloud_project")
# os.environ["GOOGLE_CLOUD_LOCATION"] = conf.get("google_cloud_location")
# os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# getLogger中无论设不设置name,都没有区别，输出都为2025-07-14 09:56:56,409|INFO|[test_utils.py:97]|test


def get_logger(name: str):
    """获取logger实例"""
    """配置日志记录"""
    # 创建日志目录
    log_dir = conf.ensure_path_exists('log_dir', 'logs')

    # 使用日期作为文件名
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{date_str}.log")

    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 清除现有的handlers
    logger.handlers.clear()

    log_format = '%(asctime)s|%(levelname)s|[%(filename)s:%(lineno)d]|%(message)s'
    # 创建文件handler，只记录ERROR及以上级别
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        log_format))

    # 创建控制台handler，只记录INFO级别
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        log_format))

    # 添加handlers到logger
    logger.addHandler(file_handler)
    # logger.addHandler(console_handler)

    return logger


# 创建全局logger实例
logger = get_logger(__name__)
