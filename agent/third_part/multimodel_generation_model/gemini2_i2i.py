
from google import genai
from google.genai import types
from google.oauth2 import service_account
from PIL import Image
from io import BytesIO
from typing import Optional
import json
import vertexai
from config import conf
from config import logger, conf
import os
import uuid


async def run_gemini2_i2i(img_path: str, prompt: str, output_image_dir: str):
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get("gemini_conf"))
    vertexai.init(project='ca-biz-vypngh-y97n', credentials=credentials)
    client = genai.Client(
        vertexai=True,
        project=conf.get("gemini_config.project_id"),
        location=conf.get("gemini_config.location"),
        credentials=credentials,
    )
    contents = [prompt]
    image = Image.open(img_path)
    contents.append(image)
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]),
        )
    except Exception as e:
        raise e

    # 处理输出
    for part in response.candidates[0].content.parts:
        if part.text:
            logger.info(f"📄 模型输出文本: {part.text}")
        elif part.inline_data:
            try:
                image_path = os.path.join(
                    output_image_dir, f"{uuid.uuid4()}.png")
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(image_path)
                return output_image_dir
            except Exception as e:
                raise e
