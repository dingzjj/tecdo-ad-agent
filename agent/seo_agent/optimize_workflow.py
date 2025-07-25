from agent.seo_agent.utils import capitalize_title
from agent.seo_agent.pojo import ProductInfo
from agent.seo_agent.agent import CreateTitleAgent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from agent.seo_agent.agent import GetKeywordsAgent
from langgraph.graph import StateGraph, START, END
from config import logger
from pydantic import BaseModel, Field
from agent.seo_agent.utils import extracted_content_in_lazada_by_css_selector, add_background_to_optimize_image_with_product_info
from agent.seo_agent.selector import selectors
import os
from agent.seo_agent.pojo import Keywords
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "seo_agent"


class OptimizeState(BaseModel):
    # 商品的url
    product_url: str
    # 商品的标题
    product_title: str = Field(default="")
    # 商品的描述
    product_description: str = Field(default="")
    # 商品的图片
    product_images: list = []
    # 商品类别
    product_category: str = Field(default="")
    # 商品的评论
    product_reviews: list[str] = []
    # 符合商品的关键词(热点词)
    product_keywords: Keywords = Field(default=Keywords(product_brand=[], product_category=[
    ], product_attribute=[], selling_points=[], other_keywords=[]))
    # 相关商品(存放url)
    related_products_urls: list[str] = []
    # 错误信息
    suggest: str = ""


async def crawl_product_info(state: OptimizeState):
    """
    通过url来爬取商品的标题 描述  图片
    TODO 获取商品图片（未完成）
    """

    css_schema = {
        "baseSelector": "#container",
        "fields": [
            {"name": "product_title",
                "selector": selectors["lazada"]["product_title"], "type": "text"},
            {"name": "product_description",
                "selector": selectors["lazada"]["product_description"], "type": "text"},
            {"name": "product_images",
                "selector": selectors["lazada"]["product_images"], "type": "html"},
        ],
    }
    extracted_result = await extracted_content_in_lazada_by_css_selector(
        state.product_url, css_schema)
    state.product_title = extracted_result["product_title"]
    state.product_description = extracted_result["product_description"]
    state.product_images = extracted_result["product_images"]
    return state


# 为llm提供模版与关键词(热点词)


async def get_keywords(state: OptimizeState):
    # 一部分热点词从自己这来，一部分从别的商店那里来
    # 1. 从自己这来(商品的品牌，类别，属性)，根据商品的标题，产品介绍
    product_title = state.product_title
    # 商品的描述
    product_description = state.product_description

    product_category = state.product_category
    keywords: Keywords = await GetKeywordsAgent().invoke(product_title, product_description, product_category)

    return {"product_keywords": keywords}
    # 假如缺少任何一个都向客户进行询问

    # 2. 从别的商店那里来(补充商品属性)
    # related_products_urls = s
    # tate.related_products_urls


async def check_keywords(state: OptimizeState):
    # 用户检查关键词
    # interrupt("check keywords")
    # 关键词更新完毕
    return state


async def create_title(state: OptimizeState):
    # 品牌名称+产品类型+产品属性+产品规格+详细信息(有热点信息则存放热点信息)    /优点/使用地点,字符限制为255个字符,使用" ( "和" / "等分隔符有助于你的标题更易于阅读。但是尽量少在分隔符周围留空格。
    # 雨树芒果茶袋红茶，香气清新->Raintree芒果红茶茶包（100杯/袋/茶包），清真认证，锡兰天然水果茶，每天作为冰茶或热茶饮用，味道清爽，香气浓郁。

    # 根据是否有错误信息判断进行创建还是修改
    create_title_agent = CreateTitleAgent()
    product_info: ProductInfo = await create_title_agent.invoke(
        state.product_title, state.product_description, state.suggest, state.product_keywords)

    # capitalizemytitle ->大写每个词的首个字符

    # 应用标题大写处理
    capitalized_title = capitalize_title(product_info.product_title)
    product_info.product_title = capitalized_title
    return {"product_title": product_info.product_title}


async def check_title(state: OptimizeState):
    # 检查标题是否符合要求
    # 1.判断是否与类别不一致
    # 2.矛盾词
    # 3.无效关键词
    # 用户提出建议
    # interrupt("check title")
    return state


async def create_description(state: OptimizeState):
    # 创建描述

    return state


async def check_description(state: OptimizeState):
    # 检查描述是否符合要求
    # 1.判断是否与类别不一致
    # 2.矛盾词
    # 3.无效关键词
    # 用户提出建议
    # interrupt("check description")
    return state


async def optimize_image(state: OptimizeState):
    # 优化图片(实现：+背景)
    product_images = state.product_images
    product_description = state.product_description
    after_optimize_product_images = await add_background_to_optimize_image_with_product_info(product_images, product_description)
    return state


def get_app():
    graph = StateGraph(OptimizeState)
    graph.add_node("crawl_product_info", crawl_product_info)
    graph.add_node("get_keywords", get_keywords)
    graph.add_node("user_check_keywords", check_keywords)
    graph.add_node("create_title", create_title)
    graph.add_node("check_title", check_title)
    graph.add_node("create_description", create_description)
    graph.add_node("check_description", check_description)
    graph.add_node("optimize_image", optimize_image)
    graph.add_edge(START, "crawl_product_info")
    graph.add_edge("crawl_product_info", "get_keywords")
    graph.add_edge("get_keywords", "user_check_keywords")
    graph.add_edge("user_check_keywords", "create_title")
    graph.add_edge("create_title", "check_title")
    graph.add_edge("check_title", "create_description")
    graph.add_edge("create_description", "check_description")
    graph.add_edge("check_description", "optimize_image")
    graph.add_edge("optimize_image", END)
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def invoke_optimize_workflow(product_url: str, product_title: str = "", product_description: str = "", product_category: str = ""):
    """
    假如提供了product_title和product_description，则直接调用get_keywords节点，否则调用crawl_product_info节点
    """
    configuration: RunnableConfig = {"configurable": {"thread_id": "1"}}
    app = get_app()
    result = await app.ainvoke(OptimizeState(product_url=product_url, product_title=product_title, product_description=product_description, product_category=product_category), config=configuration, stream_mode="values")
    return result
