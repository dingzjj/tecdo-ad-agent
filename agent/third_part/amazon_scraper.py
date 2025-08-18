from playwright.async_api import async_playwright
from urllib.parse import quote
import asyncio
from typing import List
from pydantic import BaseModel
from agent.mini_agent import TranslatorAgent


class ProductInAWS(BaseModel):
    title: str
    description: str
    url: str


async def amazon_search(keyword: str, max_link_num: int = 3) -> List[ProductInAWS]:
    # 将keyword翻译成英文
    keyword = TranslatorAgent().translate(
        from_lang="Chinese", to_lang="English", text=keyword)
    result: List[ProductInAWS] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            locale="en-US"
        )
        page = await context.new_page()
        url = f"https://www.amazon.com/s?k={quote(keyword)}"
        await page.goto(url, timeout=30000)
        await page.wait_for_selector("select#s-result-sort-select", timeout=30000)
        # exact-aware-popularity-rank按销量排序，review-rank按评分排序,relevanceblender按关键词相关度排序
        await page.select_option("select#s-result-sort-select", value="exact-aware-popularity-rank")
        await asyncio.sleep(3)
        product_cards = await page.query_selector_all(
            "div.s-main-slot div[data-asin][data-component-type='s-search-result']"
        )
        first_card_html = await product_cards[0].evaluate("node => node.outerHTML")
        # print(first_card_html)
        for card in product_cards[:max_link_num]:
            link_el = await card.query_selector("a.a-link-normal.s-link-style")
            title = None
            url = None
            if link_el:
                # 提取url
                href = await link_el.get_attribute("href")
                if href:
                    url = href if href.startswith(
                        "http") else "https://www.amazon.com" + href
                # 提取标题
                h2_el = await link_el.query_selector("h2")
                if h2_el:
                    # 优先 aria-label
                    title = await h2_el.get_attribute("aria-label")
                    if not title:
                        span_el = await h2_el.query_selector("span")
                        if span_el:
                            title = await span_el.text_content()
            if title and url:
                product = ProductInAWS(
                    title=title.strip(),
                    description=f"Product link from Amazon for keyword '{
                        keyword}'",
                    url=url
                )
                result.append(product)
        await browser.close()
    return result
