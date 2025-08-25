from agent.material_insights_agent.utils import get_country_from_natural_language
from config import logger
import json
from agent.mini_agent import TranslatorAgent
from langchain_core.messages import SystemMessage, HumanMessage
from agent.llm import create_azure_gpt5_llm
from agent.material_insights_agent.prompt import GET_MATERIALS_SEARCH_PARAMS_PROMPT
from crawl4ai import AsyncWebCrawler
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout
import matplotlib.pyplot as plt
# from config import conf
from agent.llm import chat_with_openai_in_azure

# 定位某个节点，根据 'name' 属性


class Material:
    def __init__(self, title: str, industry: str, country: str, objective: str, video_url: str):
        # 标题，行业，国家，目标，视频url
        self.title = title
        self.industry = industry
        self.country = country
        self.objective = objective
        self.video_url = video_url


platforms = {"Facebook", "Tiktok", "Snapchat", "Kwai"}
industry = {"游戏", "应用", "电商"}
objective = {"OUTCOME_SALES", "APP_INSTALLS",
             "CONVERSIONS", "OUTCOME_LEADS", "APP_PROMOTION"}
time_horizon = {"Last 7 days", "Last 30 days", "Last 180 days"}
material_type = {"VIDEO", "IMAGE"}

# search text , industry , country , objective


def search_in_creativault_materials(text: str) -> list[Material]:
    """
    通过自然语言补充在https://creativault.tec-do.com/materials/search上的查询参数search text ,platforms , industry , objective  , material_type
    然后进行查询，返回结果
    """
    # 1.llm返回search text , platforms,industry,objective,material_type
    llm = create_azure_gpt5_llm()
    messages = [
        SystemMessage(content=GET_MATERIALS_SEARCH_PARAMS_PROMPT.format(
            platforms=platforms, industry=industry, objective=objective, material_type=material_type, time_horizon=time_horizon)),
        HumanMessage(content=text)
    ]
    response = llm.invoke(messages)
   # 2.参数获取
    try:
        search_params = json.loads(response.content)
        # 2.中文搜索 + 英文搜索
        # search text
        search_text_zh_of_search_params = search_params["search text"]
        search_text_en_of_search_params = TranslatorAgent().translate(
            from_lang="Chinese", to_lang="English", text=search_text_zh_of_search_params)
        # platforms
        if search_params["platforms"] and search_params["platforms"] not in platforms:
            raise ValueError(
                f"Platforms {search_params['platforms']} not in {platforms}")

        # industry
        if search_params["industry"] and search_params["industry"] not in industry:
            raise ValueError(
                f"Industry {search_params['industry']} not in {industry}")

        # objective
        if search_params["objective"] and search_params["objective"] not in objective:
            raise ValueError(
                f"Objective {search_params['objective']} not in {objective}")

        # material_type
        if search_params["material_type"] and search_params["material_type"] not in material_type:
            raise ValueError(
                f"Material type {search_params['material_type']} not in {material_type}")

        # 只是用来检验
        country_list = get_country_from_natural_language(
            text, search_params["country"])

    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON response: {response.content}")

    # 3.使用参数进行查询
    print(search_params)
    print(search_text_zh_of_search_params)
    print(search_text_en_of_search_params)
    print(country_list)
    # 3.1 中文查询

    # 3.2 英文查询

    # 4.返回结果+检验
