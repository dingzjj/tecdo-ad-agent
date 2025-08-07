
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
#  路径二：先文生图获取视角维度信息，然后通过repaint来重新生成图片，产品换产品（识别+溶图）
#  通过gemini分析，判断观看该图片的视角
#  路径三：lora+图生图视
#  路径四：图片编辑模型
#  目前是确定有一张图来辅助，提供位置信息
from agent.llm import get_gemini_multimodal_model
from agent.e_commerce_agent.prompt import ANALYSE_IMAGE_VIEW_SYSTEM_PROMPT_en, ANALYSE_IMAGE_VIEW_RESPONSE_SCHEMA

from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
import mimetypes
import json


async def generate_multi_views_images(image_path, product_topic, output_images_num=20):
    """把物体视为长方体，视角一共有6个，分别是：
    1. 正面
    2. 背面
    3. 左面
    4. 右面
    5. 上面
    6. 下面"""
    # video_url = await Keling().execute_generate_video(image_path, "3D旋转展示，仰视，仰视商品", "视角从左往右，展示产品的背面", 5)
    # # 下载video_path到本地
    # video_data = get_url_data(video_url)
    # video_output_path = os.path.join(
    #     conf.get_path("temp_dir"), "product", f"{get_time_id()}.mp4")
    # with open(video_output_path, "wb") as f:
    #     f.write(video_data)

    # 使用gemini对该图片进行分析

    gemini_generative_model = get_gemini_multimodal_model(
        ANALYSE_IMAGE_VIEW_SYSTEM_PROMPT_en, ANALYSE_IMAGE_VIEW_RESPONSE_SCHEMA)
    with open(image_path, "rb") as file:
        image_data = file.read()

    # 根据文件后缀获取 MIME 类型
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        # 如果无法猜测，默认为 image/jpeg
        mime_type = "image/jpeg"
    response = gemini_generative_model.generate_content(
        [
            "Analyze the perspective information of the following picture",
            Part.from_data(image_data, mime_type=mime_type)
        ]
    )
    content = response.candidates[0].content.parts[0].text
    content = json.loads(content)
    perspective_info = content["perspective"]
    print(perspective_info)


async def generate_multi_background_images(image_path, product_topic,  custom_requirements="", output_images_num=20):
    results = []
    modification_scope = "perspective"
    prompt_list = await generate_prompt(image_path, product_topic, modification_scope, custom_requirements, output_images_num)
    image_output_path = os.path.join(
        conf.get_path("temp_dir"), "product", f"{get_time_id()}")

    for prompt in prompt_list:
        images_list = create_image(input_image_path=image_path, prompt=prompt, output_image_dir=image_output_path,
                                   output_images_num=1, guidance_scale=2.5)
        for image_path in images_list:
            results.append({"prompt": prompt, "image_path": image_path})
    return results
