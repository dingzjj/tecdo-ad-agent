
# 从左往右看，从下往上看
from agent.e_commerce_agent.flux_generate_images import create_image
from agent.third_part.i2v import Keling
import asyncio
import os
# 使用keling的api生成多视角图片

# Modification_Scope使用bit来存储
from agent.utils import get_url_data
from config import conf
from agent.utils import get_time_id
from agent.e_commerce_agent.generate_prompt import generate_prompt

#  路径一：通过keling图生视频，然后通过视频生成多视角图片
#  路径二：


async def generate_multi_views_images(image_path, product_topic, output_images_num=20):

    video_url = await Keling().execute_generate_video(image_path, "上下旋转", "", 5)
    # 下载video_path到本地
    video_data = get_url_data(video_url)
    video_output_path = os.path.join(
        conf.get_path("temp_dir"), "product", f"{get_time_id()}.mp4")
    with open(video_output_path, "wb") as f:
        f.write(video_data)


async def generate_multi_background_images(image_path, product_topic,  custom_requirements="", output_images_num=20):
    results = []
    modification_scope = "perspective"
    prompt_list = await generate_prompt(image_path, product_topic, modification_scope, custom_requirements, output_images_num)
    image_output_path = os.path.join(
        conf.get_path("temp_dir"), "product", f"{get_time_id()}.mp4")

    for prompt in prompt_list:
        create_image(input_image_path=image_path, prompt=prompt, output_image_dir=image_output_path,
                     output_images_num=output_images_num, guidance_scale=2.5)
        results.append({"prompt": prompt, "image_path": image_output_path})
    return results
