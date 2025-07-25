      
from agent.llm import get_gemini_multimodal_model
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from agent.ad_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en
import mimetypes
from agent.ad_agent.prompt import SELLING_POINTS_CLASSIFIER_SYSTEM_PROMPT_en, SELLING_POINTS_CLASSIFIER_HUMAN_PROMPT_en
from agent.ad_agent.prompt import CLASSIFIER_SYSTEM_PROMPT_en, CLASSIFIER_HUMAN_PROMPT_en
from agent.third_part.prompt import ACTION_TYPES_CLASSIFIER_SYSTEM_PROMPT_en, ACTION_TYPES_CLASSIFIER_HUMAN_PROMPT_en
from agent.llm import chat_with_openai_in_azure
from config import logger
import json
import uuid


class SellingPointsClassifier:
    def __init__(self, categories: list[str]):
        # category_id,category_name
        self.categories = [{"category_id": str(uuid.uuid4()), "category_name": category}
                           for category in categories]

        self.system_prompt = SELLING_POINTS_CLASSIFIER_SYSTEM_PROMPT_en
        self.human_prompt = SELLING_POINTS_CLASSIFIER_HUMAN_PROMPT_en

    def classify(self, input_text: str) -> str:
        while True:
            response = chat_with_openai_in_azure(
                self.system_prompt, self.human_prompt.format(input_text=input_text, categories=self.categories))
            try:
                content = json.loads(response)
                print(content)
                category_id = content["category_id"]
                # 直到能解析出category_id为止
                for category in self.categories:
                    if category["category_id"] == category_id:
                        return category["category_name"]
            except Exception as e:
                logger.error(e)

class ActionTypesClassifier:
    def __init__(self, categories: list[str]):
        # category_id,category_name
        self.categories = [{"category_id": str(uuid.uuid4()), "category_name": category}
                           for category in categories]

        self.system_prompt = ACTION_TYPES_CLASSIFIER_SYSTEM_PROMPT_en
        self.human_prompt = ACTION_TYPES_CLASSIFIER_HUMAN_PROMPT_en

    def classify(self, input_text: str) -> str:
        while True:
            response = chat_with_openai_in_azure(
                self.system_prompt, self.human_prompt.format(input_text=input_text, categories=self.categories))
            try:
                content = json.loads(response)
                print(content)
                category_id = content["category_id"]
                # 直到能解析出category_id为止
                for category in self.categories:
                    if category["category_id"] == category_id:
                        return category["category_name"]
            except Exception as e:
                logger.error(e)

class Classifier:
    """
    分类器，将输入的文本分类为多个类别中的一个
    """

    def __init__(self, categories: list[str]):
        # category_id,category_name
        self.categories = [{"category_id": str(uuid.uuid4()), "category_name": category}
                           for category in categories]

        self.system_prompt = CLASSIFIER_SYSTEM_PROMPT_en
        self.human_prompt = CLASSIFIER_HUMAN_PROMPT_en

    def classify(self, input_text: str) -> str:
        while True:
            response = chat_with_openai_in_azure(
                self.system_prompt, self.human_prompt.format(input_text=input_text, categories=self.categories))
            try:
                content = json.loads(response)
                print(content)
                category_id = content["category_id"]
                # 直到能解析出category_id为止
                for category in self.categories:
                    if category["category_id"] == category_id:
                        return category["category_name"]
            except Exception as e:
                logger.error(e)


class AnalyseImageAgent:
    """
    分析图片(人+商品)，返回图片信息
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    def analyse_image(self, product: str, image_path: str) -> str:

        match self.model:
            case "gemini-2.5-flash":
                return self.analyse_image_with_gemini_2_5_flash(product, image_path)
            case _:
                raise ValueError(f"Unsupported model: {self.model}")

    def analyse_image_with_gemini_2_5_flash(self, product: str, image_path: str) -> str:
        with open(image_path, "rb") as file:
            image_data = file.read()

        # 根据文件后缀获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            # 如果无法猜测，默认为 image/jpeg
            mime_type = "image/jpeg"

        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
            response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=product),
                Part.from_data(image_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        return content["pictorial information"]

    