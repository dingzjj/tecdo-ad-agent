import json
from config import conf

import os


def get_font(font_name: str):
    with open(conf.get_url("font_dir"), "r", encoding="utf-8") as f:
        font_info = json.load(f)
    if font_name not in font_info:
        raise ValueError(f"字体{font_name}不存在")
    font_info = font_info[font_name]
    font_info["font-dir"] = os.path.join(conf.get_root_dir(),
                                         font_info["font-dir"])
    return font_info
