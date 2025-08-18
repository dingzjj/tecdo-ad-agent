
import asyncio
from google_play_scraper import search
import agent.third_part.amazon_scraper as amazon_scraper

import pandas as pd


def google_play_search(query: str):
    result = {
        "title": [],
        "description": [],
        "url": []
    }
    search_result = search(
        query,
        lang="en",  # defaults to 'en'
        country="us",  # defaults to 'us'
        n_hits=3  # defaults to 30 (= Google's maximum)
    )
    for index, item in enumerate(search_result):
        result["title"].append(item['title'])
        result["description"].append(item['description'])
        result["url"].append(
            f"https://play.google.com/store/apps/details?id={item['appId']}")

    return pd.DataFrame(result)


def amazon_search(query: str):
    search_result: list[amazon_scraper.ProductInAWS] = asyncio.run(
        amazon_scraper.amazon_search(query))
    result = {
        "title": [],
        "description": [],
        "url": []
    }
    for index, item in enumerate(search_result):
        result["title"].append(item.title)
        result["description"].append(item.description)
        result["url"].append(item.url)
    return pd.DataFrame(result)
