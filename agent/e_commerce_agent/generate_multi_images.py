
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


async def generate_multi_views_images_v1(image_path, product_topic, custom_requirements="", output_images_num=20):
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


async def generate_multi_images_v1(image_path, product_topic, modification_scope, custom_requirements="", output_images_num=20):
    results = []
    prompt_list = await generate_prompt(image_path, product_topic, modification_scope, custom_requirements, output_images_num)
    image_output_path = os.path.join(
        conf.get_path("temp_dir"), "product", f"{get_time_id()}")

    for prompt in prompt_list:
        images_list = create_image(input_image_path=image_path, prompt=prompt, output_image_dir=image_output_path,
                                   output_images_num=1, guidance_scale=2.5)
        for image_path in images_list:
            results.append({"prompt": prompt, "image_path": image_path})
    return results
