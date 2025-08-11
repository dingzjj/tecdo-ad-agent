# 爬取（堆量)
from translate import Translator
from config import logger
from urllib.parse import quote
import asyncio
from playwright.async_api import async_playwright
from agent.ad_agent.prompt import SELECT_APPROPRIATE_MATERIAL_EXPERT_KNOWLEDGE_en
from agent.ad_agent.prompt import SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_SCHEMA
from agent.llm import get_gemini_multimodal_model
from agent.ad_agent.prompt import SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_en, SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_en
from agent.llm import chat_with_gemini_in_vertexai
import json
from typing import Dict
import requests
from agent.mini_agent import AnalyseImageAgent
from typing import Optional
from pydantic import BaseModel, Field
import os
from config import conf

os.makedirs(conf.get_path("material_library_dir"), exist_ok=True)

# 路径： 素材库地址 + 素材id


class Material(BaseModel):
    """
    一个素材
    link_list: 链接
    title: 标题(若为电商网站的爬取则为商品名称，若为网页的爬取则为网页标题)
    description: 描述(对于素材的描述，即从哪来等基础信息)
    img_url_list: 图片链接
    """
    id: str = Field(description="素材id")
    link_list: list[str] = Field(description="链接列表")
    title: str = Field(description="标题")
    description: str = Field(description="描述")
    img_id: int = Field(default=1, description="图片id")
    # 只会在v1 or v2存在
    # v1
    img_url_list: list[tuple[str, str]] = Field(
        default=[], description="图片链接列表(图片链接(in web),id)")
    # v2
    img_content_list: list[tuple[str, str, str]] = Field(
        default=[], description="图片内容列表(图片链接(in local),id,图片内容)")

    async def analyze_material(self):
        """
        分析素材,对素材中的内容进行分析（主要是图片部分）
        :param material: 素材
        :return: 分析结果
        """
        # 对img_url_list中的图片进行分析
        img_dir = os.path.join(conf.get_path(
            "material_library_dir"), self.id, "images")
        os.makedirs(img_dir, exist_ok=True)
        for index, (img_url, img_id) in enumerate(self.img_url_list):
            # 1. 通过链接获取图片
            img_path = os.path.join(img_dir, f"{index}.jpg")
            response = requests.get(img_url)
            with open(img_path, "wb") as f:
                f.write(response.content)
            # 2. 对图片进行分析
            analysis_result = AnalyseImageAgent().analyse_image(
                self.title, img_path, source="web")
            # 3. 将分析结果保存到self.img_url_list中

            self.img_content_list.append((img_path, img_id, analysis_result))


async def crawl_material_in_lazada(keyword: str, start_mid: int) -> list[Material]:
    """
    爬取商品链接
    :param keyword: 商品关键词
    :return: Material
    """
    pass


async def crawl_material_in_aws(keyword: str, start_mid: int, max_link_num: int = 10) -> list[Material]:
    """
    爬取商品链接
    :param keyword: 商品关键词
    :return: Material
    """
    # 将keyword翻译为英文
    keyword = Translator(from_lang="Chinese", to_lang="English").translate(
        keyword)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = await context.new_page()

        # print("Step 1: Go to Amazon search page directly")
        url = f"https://www.amazon.com/s?k={quote(keyword)}"
        logger.info(f"url: {url}")
        await page.goto(url, timeout=30000)

        # print("Step 2: Wait for and select sort option")
        await page.wait_for_selector("select#s-result-sort-select", timeout=30000)
        # exact-aware-popularity-rank按销量排序，review-rank按评分排序,relevanceblender按关键词相关度排序
        await page.select_option("select#s-result-sort-select", value="exact-aware-popularity-rank")

        # print("Step 3: Wait for goods results to load")
        await asyncio.sleep(5)

        # print("Step 4: Extract goods links")
        await page.wait_for_selector('div.s-main-slot')
        elements = await page.locator("div.s-main-slot a.a-link-normal.s-no-outline").all()
        goods_links = []
        for el in elements:
            href = await el.get_attribute("href")
            if href and href.startswith("/"):
                goods_links.append("https://www.amazon.com" + href)

        # print("Step 5: Process each goods link")
        materials = []
        for i, link in enumerate(goods_links, start=1):
            if i > max_link_num:
                break
            logger.info(f"Processing link: {i}/{max_link_num}")
            try:
                await page.goto(link, timeout=30000)
            except:
                print(f"Timeout loading: {link}")
                continue

            await asyncio.sleep(2)  # 等待页面加载

            title = await page.title()
            if title.strip() == "Page Not Found":
                logger.warning(f"Link page not found")
                continue

            if await page.locator("#redir-modal").is_visible():
                # ("redir-modal is visible, skipping this link")
                continue

            thumbs = await page.locator("li.imageThumbnail").all()
            for thumb in thumbs:
                try:
                    await thumb.click()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Hover failed: {e}")
                    continue

            main_images = await page.locator("img.a-dynamic-image").all()
            logger.info(f"主图数量: {len(main_images)}")
            img_list = []
            for img in main_images:
                src = await img.get_attribute("data-old-hires")
                if src and src not in img_list:
                    img_list.append(src)

            if img_list:
                material = Material(
                    id=str(start_mid),
                    link_list=[link],
                    title=title,
                    description=f"Amazon material for '{keyword}'",
                    img_id=len(img_list) + 1,
                    img_url_list=[(img, str(start_mid)+"_"+str(i+1))
                                  for i, img in enumerate(img_list)]
                )
                materials.append(material)
                start_mid += 1
            else:
                content = await page.content()
                logger.info(content[:2000])
                logger.info(f"No images found for {link}")

        logger.info(f"Finished collecting {len(materials)} materials.")
        await browser.close()
        return materials


async def crawl_material_in_web(keyword: str, start_mid: int) -> list[Material]:
    """
    爬取网页链接
    :param keyword: 商品关键词
    :return: Material
    """
    material_list = []
    aws_material_list = await crawl_material_in_aws(keyword, start_mid)
    material_list.extend(aws_material_list)
    return material_list


class MaterialLibrary(BaseModel):
    """
    素材库
    """
    material_list: Dict[str, Material] = Field(default={}, description="id:素材")
    next_id: int = Field(default=1, description="下一个素材id")

    def get_id(self):
        id = self.next_id
        self.next_id += 1
        return id

    def get_all_material_info(self):
        # 返回Json[str格式] - 为llm提供素材库信息
        return json.dumps(self.material_list)

    def get_material_by_id(self, id: str) -> Optional[Material]:
        """
        根据id获取素材
        :param id: 素材id
        :return: 素材,有可能为None
        """
        return self.material_list[id]

    def append_material(self, material: Material):
        """
        添加素材
        :param material: 素材
        """
        self.material_list[material.id] = material

    def select_appropriate_material(self, require: str) -> list[str]:
        """
        根据需求选择合适的素材
        :param require: 需求
        :return: 素材
        """
        gemini_generative_model = get_gemini_multimodal_model(
            SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_en.format(
                expert_knowledge=SELECT_APPROPRIATE_MATERIAL_EXPERT_KNOWLEDGE_en), SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                require
            ]
        )

        content = json.loads(response.candidates[0].content.parts[0].text)

        return content["material_id_list"]

    def crawl_material(self, keyword: str):
        """
        爬取素材
        :param keyword: 商品关键词
        :param start_mid: 开始素材id
        :return: 素材
        """
        material_list = asyncio.run(
            crawl_material_in_web(keyword, self.next_id))
        for material in material_list:
            self.append_material(material)
            self.next_id += 1

    def return_material_list(self):
        """
        返回素材列表
        :return: 素材列表
        """
        material_list = []

        for material in self.material_list.values():
            # v1
            material_list.extend(material.img_url_list)

            # v2
            material_list.extend([(img_path, img_id)
                                 for img_path, img_id in material.img_content_list])

        return material_list
