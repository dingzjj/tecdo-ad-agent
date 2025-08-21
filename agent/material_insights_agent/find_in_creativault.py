from crawl4ai import AsyncWebCrawler
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout
import matplotlib.pyplot as plt
# from config import conf
from agent.llm import chat_with_openai_in_azure

# 定位某个节点，根据 'name' 属性


def from_one_node_to_all_nodes(G, node_name: str) -> list[str]:
    if G.out_degree(node_name) == 0:
        return [node_name]
    result = []
    successors = list(G.successors(node_name))
    for successor in successors:
        result.extend(from_one_node_to_all_nodes(G, successor))
    return result


def get_country_from_natural_language(natural_language: str) -> list[str]:
    # 从自然语言中找到地区，否则默认为全球
    # 1.节点匹配(中文)
    result = []
    G = nx.DiGraph(nx.nx_pydot.read_dot(
        "./agent/material_insights_agent/country.gv"))
    matches = [s for s in G.nodes() if s in natural_language]
    if matches:
        # 一直往下
        for match in matches:
            result.extend(from_one_node_to_all_nodes(G, match))
        return result
    # 2.LLM匹配
    global_nodes = G.nodes()
    print(global_nodes)
    system_prompt = """
    你是一个专业的地理知识专家，请根据用户输入的自然语言，找到对应的地区。如果用户输入的自然语言中包含地区，请返回一个最匹配的地区。
    可以匹配的节点有：{global_nodes}
    例如：用户输入：现在北美的口红卖的最好的广告视频是怎样的，可以返回有效答案
    输出：北美
    """
    prompt = f"{natural_language}"
    response = chat_with_openai_in_azure(system_prompt, prompt)

    if response and response in global_nodes:
        return from_one_node_to_all_nodes(G, response)
    else:
        # 默认全球
        return global_nodes


async def crawl_from_creativault(keyword: str, country: list[str]):
    async with AsyncWebCrawler() as crawler:
        # Run the crawler on a URL
        result = await crawler.arun(url="https://creativault.tec-do.com/materials/search")
        # Print the extracted content
        print(result.markdown)
