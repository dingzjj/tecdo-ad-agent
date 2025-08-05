import mimetypes
from agent.llm import get_gemini_multimodal_model
from vertexai.generative_models import Part
import asyncio
import json
from agent.e_commerce_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en


async def generate_prompt(image_path, Product_Topic, Modification_Scope, Custom_Requirements="", Output_Prompts_number=20):
    with open(image_path, "rb") as file:
        image_data = file.read()
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        mime_type = "image/jpeg"
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
        response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA
    )
    response = gemini_generative_model.generate_content([
        ANALYSE_IMAGE_HUMAN_PROMPT_en.format(Product_Topic=Product_Topic, Modification_Scope=Modification_Scope,
                                             Custom_Requirements=Custom_Requirements, Output_Prompts_number=Output_Prompts_number),
        Part.from_data(image_data, mime_type=mime_type)
    ])
    content = response.candidates[0].content.parts[0].text
    content_json = json.loads(content)
    prompt_list = content_json.get("prompt", [])
    return prompt_list


async def main():
    image_path = "./input_file/flux_test.png"
    Product_Topic = "towel"
    Modification_Scope = "perspective"
    Custom_Requirements = " "
    Output_Prompts_number = 20
    prompt = await generate_prompt(image_path, Product_Topic, Modification_Scope, Custom_Requirements, Output_Prompts_number)
    print(prompt)

if __name__ == "__main__":
    asyncio.run(main())
