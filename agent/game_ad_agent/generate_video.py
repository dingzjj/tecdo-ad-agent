import mimetypes
from sqlalchemy import desc
from agent.llm import get_gemini_multimodal_model
from vertexai.generative_models import Part
import asyncio
import json
from agent.game_ad_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en


def generate_video_prompt(img_path, description):
    """生成视频提示词"""
    with open(img_path, "rb") as file:
        image_data = file.read()
    mime_type, _ = mimetypes.guess_type(img_path)
    if mime_type is None:
        mime_type = "image/jpeg"
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
        response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA
    )
    response = gemini_generative_model.generate_content(
        [
            ANALYSE_IMAGE_HUMAN_PROMPT_en.format(description=description),
            Part.from_data(image_data, mime_type=mime_type)
        ]
    )
    content = response.candidates[0].content.parts[0].text  # 取原始 JSON 字符串
    content_json = json.loads(content)
    prompt = content_json.get("prompt", "")
    return prompt


# async def main():
#     description = "An Asian man in a suit and tie stands on the deck of a Viking longship caught in a dramatic sea storm. Powerful waves rise around the ship as it sways intensely. Viking warriors around him raise their axes and rush forward with great energy. Amid the turbulence, the man remains composed, calmly lifting a tablet toward the camera, which clearly displays a strategy card game interface."
#     img_path = "./input_file/game_test2.png"
#     prompt = await generate_video_prompt(img_path, description)
#     print(prompt)

# if __name__ == "__main__":
#     asyncio.run(main())
