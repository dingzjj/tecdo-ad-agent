from agent.third_part.multimodel_generation_model.gemini2_t2i import run_gemini2_t2i
from agent.third_part.multimodel_generation_model.gemini2_i2i import run_gemini2_i2i
from agent.third_part.multimodel_generation_model.veo3 import Veo3
from agent.third_part.multimodel_generation_model.kling2_1_i2v import run_kling2_1_i2v
from agent.third_part.multimodel_generation_model.flux_i2i import run_flux_i2i
from agent.llm import get_gemini_multimodal_model
from agent.third_part.prompt import CHOOSE_MODEL_SYSTEM_PROMPT, CHOOSE_MODEL_RESPONSE_SCHEMA
import json
from translate import Translator
from typing import Literal
from config import conf
from abc import abstractmethod, ABC
from config import logger


class MultimodalGenerationModel(ABC):
    def __init__(self, id: str):
        self.id = id

    @abstractmethod
    async def generate(self, **param) -> str:
        """
        param
        t2i: positive_prompt, negative_prompt(optional)
        i2i: image_path, positive_prompt, negative_prompt

        return:
            str: 生成的img or video文件路径
        """
        raise NotImplementedError(
            f"MultimodalGenerationModel {self.id} does not implement generate")


class Gemini2_t2i(MultimodalGenerationModel):
    def __init__(self):
        self.id = "gemini2_t2i"

    async def generate(self, **param) -> str:
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")
        return await run_gemini2_t2i(positive_prompt, conf.get_path("share_material_dir"))


class Gemini2_i2i(MultimodalGenerationModel):
    def __init__(self):
        self.id = "gemini2_i2i"

    async def generate(self, **param) -> str:
        image_path = param["image_path"]
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if image_path is None:
            raise ValueError("image_path不能为空")
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")
        return await run_gemini2_i2i(image_path, positive_prompt, conf.get_path("share_material_dir"))


class Flux_i2i(MultimodalGenerationModel):
    def __init__(self):
        self.id = "flux_i2i"

    async def generate(self, **param) -> str:
        image_path = param["image_path"]
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if image_path is None:
            raise ValueError("image_path不能为空")
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")
        output_paths = run_flux_i2i(image_path, positive_prompt,
                                    conf.get_path("share_material_dir"))
        if len(output_paths) == 0:
            raise ValueError("生成失败")
        return output_paths[0]


class Qwen_t2i(MultimodalGenerationModel):
    def __init__(self):
        self.id = "qwen_t2i"

    async def generate(self, **param) -> str:
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")


class Kling2_1_i2v(MultimodalGenerationModel):
    def __init__(self):
        self.id = "kling2_1_i2v"

    async def generate(self, **param) -> str:
        image_path = param["image_path"]
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if image_path is None:
            raise ValueError("image_path不能为空")
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")
        return await run_kling2_1_i2v(image_path, positive_prompt,
                                      negative_prompt, 5, conf.get_path("share_material_dir"))


class Wan2_1_t2i(MultimodalGenerationModel):
    def __init__(self):
        self.id = "wan2_1_t2i"

    async def generate(self, **param) -> str:
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")


class Wan2_2_5b_t2v(MultimodalGenerationModel):
    def __init__(self):
        self.id = "wan2_2_5b_t2v"

    async def generate(self, **param) -> str:
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")


class Wan2_2_14b_t2v(MultimodalGenerationModel):
    def __init__(self):
        self.id = "wan2_2_14b_t2v"

    async def generate(self, **param) -> str:
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")


class Wan2_2_14b_i2v(MultimodalGenerationModel):
    def __init__(self):
        self.id = "wan2_2_14b_i2v"

    async def generate(self, **param) -> str:
        image_path = param["image_path"]
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if image_path is None:
            raise ValueError("image_path不能为空")
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")


class Veo3_t2v(MultimodalGenerationModel):
    def __init__(self):
        self.id = "veo3_t2v"

    async def generate(self, **param) -> str:
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")
        return await Veo3(output_dir=conf.get_path("share_material_dir")).t2v(positive_prompt, negative_prompt)


class Veo3_i2v(MultimodalGenerationModel):
    def __init__(self):
        self.id = "veo3_i2v"

    async def generate(self, **param) -> str:
        image_path = param["image_path"]
        positive_prompt = param["positive_prompt"]
        if "negative_prompt" in param:
            negative_prompt = param["negative_prompt"]
        else:
            negative_prompt = ""
        if image_path is None:
            raise ValueError("image_path不能为空")
        if positive_prompt is None:
            raise ValueError("positive_prompt不能为空")
        return await Veo3(output_dir=conf.get_path("share_material_dir")).i2v(image_path, positive_prompt, negative_prompt)


class ModelFactory:
    """
    模型工厂
    1.选择模型
    2.根据模型ID返回模型实例
    """

    def __init__(self):
        self.models = {
            "gemini2_t2i": Gemini2_t2i(),
            "gemini2_i2i": Gemini2_i2i(),
            "flux_i2i": Flux_i2i(),
            "qwen_t2i": Qwen_t2i(),
            "kling2_1_i2v": Kling2_1_i2v(),
            "wan2_1_t2i": Wan2_1_t2i(),
            "wan2_2_5b_t2v": Wan2_2_5b_t2v(),
            "wan2_2_14b_t2v": Wan2_2_14b_t2v(),
            "wan2_2_14b_i2v": Wan2_2_14b_i2v(),
            "veo3_t2v": Veo3_t2v(),
            "veo3_i2v": Veo3_i2v(),
        }

    def get_model_by_id(self, model_id: str) -> MultimodalGenerationModel:
        return self.models[model_id]

    def choose_model_by_specific_function(self, require: str, specific_function: Literal["text to image", "image to image", "text to video", "image to video"]) -> str:
        # 首先通过specific_function对模型进行筛选
        try:
            with open(conf.get_path("models_file"), "r", encoding="utf-8") as f:
                models = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"❌ Error in reading model file: {e}")

        filtered_models = []

        # 遍历 models 字典中的所有项
        for model_name, model_list in models.items():
            # 遍历每一个模型列表中的项
            for model in model_list:
                # 如果模型的 application 匹配 specific_function，则添加到结果列表
                if model["application"] == specific_function:
                    filtered_models.append(model)

        models = filtered_models
        logger.info(f"{specific_function} -> filtered_models:{filtered_models}")
        # 将中文转换为英文
        require_en = Translator(from_lang="ZH",
                                to_lang="EN-US").translate(require)
        multimodal_model = get_gemini_multimodal_model(
            system_prompt=CHOOSE_MODEL_SYSTEM_PROMPT.format(
                models=str(models)), response_schema=CHOOSE_MODEL_RESPONSE_SCHEMA)

        # 询问模型
        try:
            response = multimodal_model.generate_content(
                [
                    require_en
                ]
            )
        except Exception as e:
            logger.error(f"❌ Error in querying the model: {e}")
            raise

        # 接收信息
        content = json.loads(response.candidates[0].content.parts[0].text)
        logger.info(f"require:{require} -> select model:{content['model_id']}")
        return content["model_id"]

    def choose_model(self, require: str) -> str:
        """
        使用 Gemini 多模态模型分析文本内容。

        该函数通过 Vertex AI 调用 Gemini 模型，将提供的文本提示（prompt）发送给模型，
        并返回模型生成的分析结果文本。

        Args:
            human_prompt (str): 发送给模型的文本提示，用于指导模型进行分析。

        Returns:
            str: 选择的模型 ID。

        Raises:
            Exception: 如果在加载配置文件、读取视频文件、初始化模型或查询模型时发生任何错误，将抛出异常。
        """
        require_en = Translator(from_lang="Chinese",
                                to_lang="English").translate(require)
        try:
            with open(conf.get_path("models_file"), "r", encoding="utf-8") as f:
                models = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"❌ Error in reading model file: {e}")

        multimodal_model = get_gemini_multimodal_model(
            system_prompt=CHOOSE_MODEL_SYSTEM_PROMPT.format(
                models=str(models)), response_schema=CHOOSE_MODEL_RESPONSE_SCHEMA)

        # 询问模型
        try:
            response = multimodal_model.generate_content(
                [
                    require_en
                ]
            )
        except Exception as e:
            logger.error(f"❌ Error in querying the model: {e}")
            raise

        # 接收信息
        content = json.loads(response.candidates[0].content.parts[0].text)
        return content["model_id"]


model_factory = ModelFactory()
