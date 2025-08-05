import torch
from diffusers import FluxKontextPipeline
from diffusers.utils import load_image
from PIL import Image
import os
from accelerate import Accelerator


def create_pipe():
    return FluxKontextPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-Kontext-dev",
        torch_dtype=torch.bfloat16,
    ).to("cuda:1")


def create_image(
    input_image_path: str,
    prompt: str,
    output_image_dir: str,
    output_images_num: int = 1,
    guidance_scale: float = 2.5,
) -> list:
    """
    根据输入图像和提示词生成图像，并保存到指定目录。

    参数:
        input_image_path (str): 输入图像的本地路径（不支持直接传 URL）
        prompt (str): 提示词
        output_image_dir (str): 输出图像的保存目录
        output_images_num (int): 要生成的图像数量
        guidance_scale (float): 指导强度

    返回:
        List[str]: 所有生成图像的完整路径
    """

    # 1. 检查输入文件是否存在
    if not os.path.isfile(input_image_path):
        raise FileNotFoundError(f"输入图像文件不存在: {input_image_path}")
    # 2. 提取输入图像的文件名（不带扩展名）
    input_image_name = os.path.splitext(os.path.basename(input_image_path))[0]
    # 3. 确保输出目录存在，否则自动创建
    os.makedirs(output_image_dir, exist_ok=True)
    # 4. 加载模型管道（假设 create_pipe() 已定义）
    pipe = create_pipe()
    # if hasattr(torch, "compile"):
    #     print("启用 torch.compile() 加速...")
    #     pipe.transformer = torch.compile(pipe.transformer, mode="reduce-overhead")
    # 6. 加载输入图像
    input_image = load_image(input_image_path)
    # 7. 生成图像
    images = pipe(
        image=input_image,
        prompt=prompt,
        num_images_per_prompt=output_images_num,
        guidance_scale=guidance_scale,
    ).images
    # 8. 保存图像到输出目录
    output_paths = []
    for i, img in enumerate(images):
        # 构造输出文件名：{输入文件名}_output_{编号}.png
        output_filename = f"{input_image_name}_output_{i}.png"
        output_path = os.path.join(output_image_dir, output_filename)
        img.save(output_path)
        output_paths.append(output_path)

    print(f"成功生成 {len(output_paths)} 张图像，已保存至目录: {output_image_dir}")
    return output_paths
