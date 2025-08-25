from agent.mini_agent import TranslatorAgent
from typing import Literal
import re

# 只要包含中文的就是中文


def is_chinese(text: str) -> bool:
    """
    检查文本中是否包含中文字符

    Args:
        text: 要检查的文本字符串

    Returns:
        bool: 如果文本包含中文字符则返回True，否则返回False
    """
    if not text:
        return False

    # 使用正则表达式匹配中文字符
    # 中文字符的Unicode范围：\u4e00-\u9fff
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')

    return bool(chinese_pattern.search(text))


global_language = "English"


def lan(text: str, to_lang: Literal["Chinese", "English"] = global_language) -> str:
    """
    将语言进行同步
    """
    if is_chinese(text):
        if to_lang == "Chinese":
            return text
        else:
            return TranslatorAgent().translate(
                from_lang="Chinese", to_lang="English", text=text)
    else:
        if to_lang == "English":
            return text
        else:
            return TranslatorAgent().translate(
                from_lang="English", to_lang="Chinese", text=text)
