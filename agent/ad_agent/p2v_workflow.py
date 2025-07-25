from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph import StateGraph
import mimetypes
import json
from pydantic import BaseModel, Field
from agent.llm import get_gemini_multimodal_model
from agent.ad_agent.prompt import GENERATE_SELLING_POINT_SYSTEM_PROMPT_en, GENERATE_SELLING_POINT_RESPONSE_SCHEMA, GENERATE_SELLING_POINT_HUMAN_PROMPT_en, GENERATE_IMAGE_PROMPT_SYSTEM_PROMPT_en, GENERATE_IMAGE_PROMPT_RESPONSE_SCHEMA, GENERATE_IMAGE_PROMPT_HUMAN_PROMPT_en
# from agent.third_part.flux_context import Part
import os
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "p2v_agent"

# v1表示纯视频，v2表示视频+音频，v3表示视频+字幕+音频


class VideoFragment(BaseModel):
    id: str = Field(default="", description="视频片段id")
    video_index: int = Field(description="视频索引")
    img_path: str = Field(default="", description="商品图片")
    model_image_info: str = Field(default="", description="模特图片信息")
    video_positive_prompt: str = Field(default="", description="视频正向prompt")
    video_negative_prompt: str = Field(default="", description="视频负向prompt")
    video_script: str = Field(default="", description="视频脚本(即音频文案)")
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")
    video_duration: int = Field(default=5, description="视频时长")
    audio_url: str = Field(default="", description="音频path(in local)")


class ProductImgToVideoState(BaseModel):
    product: str = Field(description="商品名称")
    product_info: str = Field(description="商品信息")
    product_selling_points: list[str] = Field(default=[], description="商品卖点")
    product_img_path: list[str] = Field(description="商品图片path列表")
    video_fragment_duration: int = 5
    video_fragments: list[VideoFragment] = Field(
        default=[], description="视频片段列表")
    video_output_path: str = Field(description="视频输出path")


async def extract_the_selling_points(state: ProductImgToVideoState, config):
    """
    根据产品信息提取商品卖点 (根据卖点来生成视频)
    """
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=GENERATE_SELLING_POINT_SYSTEM_PROMPT_en,
        response_schema=GENERATE_SELLING_POINT_RESPONSE_SCHEMA)
    response = gemini_generative_model.generate_content(
        GENERATE_SELLING_POINT_HUMAN_PROMPT_en.format(product=state.product, product_info=state.product_info))
    selling_points = response.candidates[0].content.parts[0].text
    content = json.loads(selling_points)
    state.product_selling_points = content["selling points"]
    return {"product_selling_points": state.product_selling_points}


async def generate_image_prompt(state: ProductImgToVideoState, config):
    """
    根据商品卖点生成图片prompt(使用Flux Context)
    {'卖点': ['环保时尚且耐用：采用坚固且可持续的亚麻材质打造，尽显日常优雅！??',
    '个性化定制：可随意添加任何名字或首字母，打造独一无二的特别礼物！✨'，
    '多功能伴侣：既适合作为旅行包、存储解决方案或时尚手提包！✈️'，
    "完美的贴心礼物：非常适合母亲节、伴娘、教师等场合！??'，
    '经久耐用：这款包具有天然的坚固性，能经受日常磨损而不变形。??'，
    '环保选择：一款既美观又有益环境的配饰。??"]}
    """
    # 1.判断该如何呈现
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=GENERATE_IMAGE_PROMPT_SYSTEM_PROMPT_en,
        response_schema=GENERATE_IMAGE_PROMPT_RESPONSE_SCHEMA)
    product_img_path = state.product_img_path[0]
    with open(product_img_path, "rb") as file:
        image_data = file.read()

    # 根据文件后缀获取 MIME 类型
    mime_type, _ = mimetypes.guess_type(product_img_path)
    if mime_type is None:
        # 如果无法猜测，默认为 image/jpeg
        mime_type = "image/jpeg"
    for product_selling_point in state.product_selling_points:
        response = gemini_generative_model.generate_content(
            [
                GENERATE_IMAGE_PROMPT_HUMAN_PROMPT_en.format(
                    product=state.product, selling_points=product_selling_point, product_info=state.product_info),
                Part.from_data(image_data, mime_type=mime_type)
            ]
        )
        content = json.loads(response.candidates[0].content.parts[0].text)
        prompt = content["prompt"]
        print(f"product_selling_point:{product_selling_point}")
        print(f"prompt:{prompt}")


async def classify_selling_points(state: ProductImgToVideoState, config):
    """
    根据商品卖点分类
    """
    # 1.添加schema(卖点类别 + workflow)
    # 将类别添加到提示词中

    pass


async def generate_image_with_prompt(state: ProductImgToVideoState, config):
    """
    根据商品卖点生成图片(使用Flux Context)
    """
    pass


async def generate_video(state: ProductImgToVideoState, config):
    """
    根据商品卖点生成视频
    """
    pass


def get_app():
    graph = StateGraph(ProductImgToVideoState)
    graph.add_node("extract_the_selling_points",
                   extract_the_selling_points)
    graph.add_node("generate_image_prompt",
                   generate_image_prompt)
    graph.add_node("generate_video",
                   generate_video)
    graph.add_edge(START, "extract_the_selling_points")
    graph.add_edge("extract_the_selling_points", "generate_image_prompt")
    graph.add_edge("generate_image_prompt", "generate_video")
    graph.add_edge("generate_video", END)
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def ainvoke_p2v_workflow(product: str, product_info: str, product_img_path: list, product_selling_points: list, video_output_path: str, video_fragment_duration: int = 5):

    app = get_app()
    configuration: RunnableConfig = {"configurable": {
        "thread_id": "1"}}
    result = await app.ainvoke({"product": product, "product_info": product_info,
                                "product_selling_points": product_selling_points, "video_output_path": video_output_path,
                                "product_img_path": product_img_path,
                                "video_fragment_duration": video_fragment_duration}, config=configuration)
    return result
