import PIL.Image as Image
import torch
from torchvision import transforms
import matplotlib.pyplot as plt
import numpy as np
import warnings
import os


def generate_resize_size_list(center_size: tuple[int, int], resize_ratio_list: list[tuple[int, int]]):
    """
    生成不同纵横比的尺寸列表

    :param center_size: 基准尺寸，格式为 (宽度, 高度)
    :param resize_ratio_list: 纵横比列表，格式为 [(宽比1, 高比1), (宽比2, 高比2), ...]
    :return: 生成的尺寸列表，格式为 [(宽度1, 高度1), (宽度2, 高度2), ...]
    """
    width, height = center_size
    resize_sizes = []

    # 根据不同的纵横比计算尺寸
    for ratio in resize_ratio_list:
        aspect_width, aspect_height = ratio

        # 计算宽度和高度
        if aspect_width == aspect_height:  # 1:1
            resize_sizes.append((width, height))
        elif aspect_width > aspect_height:  # 宽度扩展
            new_width = int(height * aspect_width / aspect_height)
            resize_sizes.append((new_width, height))
        elif aspect_width < aspect_height:  # 高度扩展
            new_height = int(width * aspect_height / aspect_width)
            resize_sizes.append((width, new_height))

    return resize_sizes


def data_enhance(image_dir_path: str, resize_size_list: list[tuple[int, int]], save_dir_path: str):
    image_list = os.listdir(image_dir_path)
    for image_name in image_list:
        image_path = os.path.join(image_dir_path, image_name)
        # image_name 去掉后缀
        image_name = image_name.split(".")[0]
        image = Image.open(image_path)

        for resize_size in resize_size_list:
            # Resize/Rescale (等比例缩放，并且利用空白来进行填充)
            resize_transform = transforms.Resize(resize_size)
            img_resized = resize_transform(image)
            # 保存为 PNG 格式
            save_path = os.path.join(save_dir_path, f"{image_name}_{
                                     resize_size[0]}_{resize_size[1]}.png")
            img_resized.save(save_path, format='PNG')

        flipping_transform = transforms.RandomHorizontalFlip()
        img_flipped = flipping_transform(image)
        save_path = os.path.join(save_dir_path, f"{image_name}_flipped.png")
        img_flipped.save(save_path, format='PNG')

        transform = transforms.RandomRotation(15)
        img_rotated = transform(image)
        save_path = os.path.join(save_dir_path, f"{image_name}_rotated_15.png")
        img_rotated.save(save_path, format='PNG')

        transform = transforms.RandomRotation(30)
        img_rotated = transform(image)
        save_path = os.path.join(save_dir_path, f"{image_name}_rotated_30.png")
        img_rotated.save(save_path, format='PNG')


if __name__ == "__main__":
    data_enhance(
        image_dir_path="/data/dzj/dataset/product1/images",
        resize_size_list=generate_resize_size_list(
            (768, 768), [(1, 1), (2, 1), (1, 2), (3, 4), (4, 3), (9, 16), (16, 9)]),
        save_dir_path="/data/dzj/dataset/product1/data_enhance"
    )
