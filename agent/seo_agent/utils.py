from enum import Enum
from google.oauth2 import service_account
from google.genai import types
from google import genai
from pydantic import BaseModel
from typing import List, Any
from langgraph.graph import StateGraph, START, END
from agent.llm import create_gemini_create_image_model_client
from agent.llm import create_azure_llm
from config import logger
from agent.seo_agent.selector import selectors
import re
import json
import asyncio
import os
from typing import List
from urllib.parse import quote_plus
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai import BrowserConfig
from crawl4ai import CrawlerRunConfig
from io import BytesIO
from PIL import Image
from vertexai.generative_models import Part
from agent.pojo import TaskStatusEnum


async def extracted_content_in_lazada_by_css_selector(url, css_schema):
    """
    css_schema参考schema = {
    "name": str,              # Schema name
    "baseSelector": str,      # Base CSS selector
    "fields": [               # List of fields to extract
        {
            "name": str,      # Field name
            "selector": str,  # CSS selector
            "type": str,     # Field type: "text", "attribute", "html", "regex"
            "attribute": str, # For type="attribute"
            "pattern": str,  # For type="regex"
            "transform": str, # Optional: "lowercase", "uppercase", "strip"
            "default": Any    # Default value if extraction fails
        }
        ]
    }
    """
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=True,
        # proxy="http://localhost:8888",

    )
    css_strategy = JsonCssExtractionStrategy(schema=css_schema)
    crawler_run_config = CrawlerRunConfig(
        # Force the crawler to wait until images are fully loaded
        wait_for_images=True,
        # Option 1: If you want to automatically scroll the page to load images
        scan_full_page=True,  # Tells the crawler to try scrolling the entire page
        scroll_delay=0.5,     # Delay (seconds) between scroll steps
        js_code="window.scrollTo(0, document.body.scrollHeight);",
        wait_for=css_schema["fields"][0]["selector"],
        # cache_mode=CacheMode.BYPASS,
        verbose=True,
        extraction_strategy=css_strategy,

    )
    crawler = AsyncWebCrawler(config=browser_config)
    result = await crawler.arun(url=url, config=crawler_run_config)
    # Handle the result properly based on the actual return type
    if hasattr(result, 'extracted_content'):
        return result.extracted_content
    else:
        return result


def capitalize_title(title: str) -> str:
    """
    将标题中每个词的首个字符大写
    处理特殊情况：保持某些词的小写（如 of, and, the 等介词和冠词）
    """
    # 定义不需要大写的词（介词、冠词、连词等）
    lowercase_words = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if',
                       'in', 'is', 'it', 'of', 'on', 'or', 'the', 'to', 'up', 'with', 'yet'}

    # 分割标题为单词
    words = title.split()
    capitalized_words = []

    for i, word in enumerate(words):
        # 清理单词（去除标点符号）
        clean_word = ''.join(c for c in word if c.isalnum())

        # 如果是第一个词或最后一个词，或者不在小写词列表中，或者长度大于3，则大写
        if (i == 0 or i == len(words) - 1 or
            clean_word.lower() not in lowercase_words or
                len(clean_word) > 3):  # 长度大于3的词通常需要大写
            # 大写第一个字符，保持其他字符不变
            if word:
                capitalized_word = word[0].upper(
                ) + word[1:] if len(word) > 0 else word
                capitalized_words.append(capitalized_word)
            else:
                capitalized_words.append(word)
        else:
            # 保持小写
            capitalized_words.append(word)

    return ' '.join(capitalized_words)


async def search_competitors(url, platform="lazada", max_products=5):
    """
    根据商品URL提取标题并搜索竞品
    Args:
        url (str): 商品页面URL
        platform (str): 平台名称，默认lazada
        max_products (int): 最大返回商品数量
    Returns:
        list: 竞品链接列表
    """

    # 提取商品标题
    title_selector = selectors[platform]["title"]
    css_schema = {
        "baseSelector": "#container",
        "fields": [
            {"name": "title",
                "selector": title_selector,
             "type": "text"}
        ],
    }
    title = await extracted_content_in_lazada_by_css_selector(url, css_schema)
    print(f"提取到的商品标题: {title}")
    if not title:
        print("无法提取商品标题，无法继续搜索竞品")
        return []

    # 清理标题作为搜索词
    llm = create_azure_llm()
    prompt = f"""
            请从以下商品标题中提取最重要的3个关键词或短语，代表核心卖点。去除品牌词、型号、重复词和无关修饰词，输出为英文关键词列表：

            商品标题：
            "{title}"

            关键词列表：
            """
    response = await llm.ainvoke(prompt)
    print("提取关键词结果：")
    print(response.content)
    search_term = str(response.content).strip().splitlines()
    search_term = [kw.lstrip('- ').strip() for kw in search_term]
    print(f"清理后的搜索关键词: {search_term}")
    if not search_term:
        print("标题清理后为空")
        return []

    # 爬取 Lazada 竞品
    search_terms = " ".join(search_term)
    search_url = f"https://www.lazada.com.my/catalog/?q={
        quote_plus(search_terms)}"
    competitor_data = []

    css_schema = {
        "name": "lazada_product_list",
        "baseSelector": "div[data-qa-locator='product-item']",
        "fields": [
            {
                "name": "link",
                "selector": "a[href*='/products/']",
                "type": "attribute",
                "attribute": "href"
            },
            {
                "name": "sold",
                "selector": "span._1cEkb > span:first-child",
                "type": "text"
            }
        ]
    }

    try:
        extracted = await extracted_content_in_lazada_by_css_selector(search_url, css_schema)
        # Handle the extracted content properly
        if isinstance(extracted, str):
            extracted = json.loads(extracted)
        elif hasattr(extracted, 'extracted_content'):
            extracted = json.loads(str(extracted.extracted_content))
        else:
            extracted = json.loads(str(extracted))

        original_id = re.search(r'/products/.*-i(\d+)', url)
        original_id = original_id.group(1) if original_id else None

        seen_ids = set()
        for item in extracted:
            if not isinstance(item, dict):
                continue
            link = item.get("link")
            sold_text = item.get("sold", "")

            if not link:
                continue
            full_link = "https:" + link if link.startswith("//") else link
            current_id = re.search(r'/products/.*-i(\d+)', full_link)
            if not current_id:
                continue
            pid = current_id.group(1)

            # 去重及排除原始商品
            if pid == original_id or pid in seen_ids:
                continue

            seen_ids.add(pid)

            # 解析销量文本，转换成数字
            match = re.search(r'([\d\.]+)([KMB]?)', sold_text.replace(",", ""))
            if match:
                num = float(match.group(1))
                suffix = match.group(2)
                if suffix == 'K':
                    num *= 1000
                elif suffix == 'M':
                    num *= 1_000_000
                sold_count = int(num)
            else:
                sold_count = 0

            competitor_data.append({
                "link": full_link,
                "sold_count": sold_count
            })

        # 输出所有商品链接和销量（未截断）
        print("\n所有抓取到的商品（未截断）：")
        for item in competitor_data:
            print(f"链接: {item['link']} | 销量: {item['sold_count']}")

        # 按销量降序排序
        competitor_data.sort(key=lambda x: x["sold_count"], reverse=True)

        # 输出前 max_products 个链接和销量
        print(f"\n按销量排序后前 {max_products} 个商品：")
        top_items = competitor_data[:max_products]
        for item in top_items:
            print(f"链接: {item['link']} | 销量: {item['sold_count']}")

        return [item["link"] for item in top_items]

    except Exception as e:
        print(f"crawl4ai 提取商品链接出错: {e}")
        return []


async def add_background_to_optimize_image_with_product_info(
    product_images: list, product_description: str, output_dir: str
) -> list:
    """
    根据产品信息来为产品图添加背景

    Args:
        product_images: 产品图片路径列表
        product_description: 产品描述信息
        output_dir: 输出目录
    Returns:
        list: 优化后的产品图片路径列表
    """
    if len(product_images) == 0:
        return []

    client = create_gemini_create_image_model_client()
    SYSTEM_INSTRACTION = """You are a picture beautification robot. 
    The user will upload a product image and the direction they wish to modify. 
    All you need to do is to beautify the product images based on the users' descriptions of their demands, 
    so as to attract customers' attention and increase the purchase rate. At the same time, 
    you must first ensure that the product in the generated image matches that in the original product image, 
    and the background beautification should also be in line with the style of the product.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[SYSTEM_INSTRACTION +
                      product_description, product_images],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]),
        )
    except Exception as e:
        print(f"Error during image generation: {e}")
        return []

    generated_images_path = []
    if response:
        index = 0
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                print(f"Text response: {part.text}")
            elif part.inline_data is not None:
                image_data = BytesIO(part.inline_data.data)
                try:
                    if image_data.getbuffer().nbytes > 0:  # Check if data is not empty
                        image = Image.open(image_data)
                        try:
                            # Generate a unique filename for each image
                            # Use index + 1 for human-friendly naming
                            image_filename = f"{output_dir}/generated_image_{
                                index + 1}.png"
                            image.save(image_filename)  # Save the image
                            generated_images_path.append(
                                image_filename
                            )  # Add to the list of generated images
                            image.close()
                        except Exception as e:
                            logger.error(f"Error saving image: {e}")
                            image.close()
                            return []
                    else:
                        print("Generated image data is empty.")
                except Exception as e:
                    print(f"Error saving image data: {e}")

                    return []

    return generated_images_path
