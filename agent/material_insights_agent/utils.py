from typing import Optional
from config import conf
from crawl4ai import AsyncWebCrawler
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout
import matplotlib.pyplot as plt
# from config import conf
from agent.llm import chat_with_openai_in_azure

# 全球为None
from config import logger


def from_one_node_to_all_nodes(G, node_name: str) -> set[str]:
    if G.out_degree(node_name) == 0:
        return {node_name}
    result = set()
    successors = set(G.successors(node_name))
    for successor in successors:
        result.update(from_one_node_to_all_nodes(G, successor))
    return result


def get_country_from_natural_language(natural_language: str, point: Optional[str] = None) -> list[str]:
    """
    返回[]时即不加地区限制
    """

    # 从自然语言中找到地区，否则默认为全球
    # 1.节点匹配(中文)
    result = set()
    G = nx.DiGraph(nx.nx_pydot.read_dot(
        conf.get_path("material_insights_agent.country_graph_path")))
    if point:
        matches = [s for s in G.nodes() if s in point]
    else:
        matches = [s for s in G.nodes() if s in natural_language]
    if matches:
        # 一直往下
        for match in matches:
            result.update(from_one_node_to_all_nodes(G, match))
        return list(result)
    # 2.LLM匹配
    global_nodes = G.nodes()
    system_prompt = """
    你是一个专业的地理知识专家，请根据用户输入的自然语言，找到对应的地区。如果用户输入的自然语言中包含地区，请返回一个最匹配的地区。
    可以匹配的节点有：{global_nodes}
    例如：用户输入：现在北美的口红卖的最好的广告视频是怎样的，可以返回有效答案
    输出：北美
    """
    prompt = f"{natural_language}"
    response = chat_with_openai_in_azure(system_prompt, prompt)

    if response and response in global_nodes:
        return list(from_one_node_to_all_nodes(G, response))
    else:
        logger.warning(f"No country found for {
                       natural_language} and response is {response}")
        # 默认全球
        return []
