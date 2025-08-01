import json
import os

# 获取当前 Python 文件的绝对路径
current_file_absolute_path = os.path.abspath(__file__)
phone_data_path = os.path.join(os.path.dirname(
    current_file_absolute_path), "phone.json")
with open(phone_data_path, "r") as f:
    phone_data = json.load(f)
phone_data = phone_data["phone"]


def get_phone_data(game_width, game_height):
    """
    根据游戏画面宽高，获取最佳适配的手机边框,核心：长宽比尽量类似
    """
    most_appropriate_phone = None

    for phone in phone_data:
        phone_length_width_ratio = phone["length_width_ratio"]
        if most_appropriate_phone is None or abs(phone_length_width_ratio - game_height/game_width) < abs(most_appropriate_phone["length_width_ratio"] - game_height / game_width):
            most_appropriate_phone = phone

    most_appropriate_phone["img_path"] = os.path.join(
        os.path.dirname(current_file_absolute_path), most_appropriate_phone["img_path"])
    return most_appropriate_phone
