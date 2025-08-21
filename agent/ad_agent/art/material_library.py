# 爬取（堆量)
from shutil import move
from agent.mini_agent import AnalyseMaterialAgent
from typing import Literal
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
import shutil
os.makedirs(conf.get_path("material_library_dir"), exist_ok=True)

# 路径： 素材库地址 + 素材id

# 素材所在Path: 素材库地址 + 素材id


class Material(BaseModel):
    """
    一个素材
    link_list: 链接
    title: 标题(若为电商网站的爬取则为商品名称，若为网页的爬取则为网页标题)
    description: 描述(对于素材的描述，即从哪来等基础信息)
    以下Path都为相对路径，相对于素材的路径，素材的路径 = 素材库地址 + 素材id
    """
    id: str = Field(description="素材id")
    link: str = Field(default=[], description="链接")
    title: str = Field(description="标题")
    material_path: str = Field(description="素材路径")
    analysis_result: Optional[str] = Field(default=None, description="分析结果")
    is_analyzed: bool = Field(default=False, description="是否已经分析")

    async def analyze_material(self, material_library_dir: str):
        """
        分析素材,对素材中的内容进行分析（主要是图片部分）
        :param material: 素材
        :return: 分析结果
        """
        analysis_result = asyncio.run(
            AnalyseMaterialAgent().analyse_material(
                product=self.title,
                material_path=os.path.join(
                    material_library_dir, self.material_path),
                source="local"
            )
        )
        self.analysis_result = analysis_result
        self.is_analyzed = True


class MaterialLibrary:
    """
    素材库
    """

    def __init__(self, material_library_dir: str):
        self.material_list: Dict[str, Material] = {}
        self.next_id: int = 1
        self.material_library_dir: str = material_library_dir
        os.makedirs(material_library_dir, exist_ok=True)

    def get_id(self):
        id = self.next_id
        self.next_id += 1
        return id

    def get_all_material_info(self):
        # 返回Json[str格式] - 为llm提供素材库信息
        all_material_info = {}
        for material_id, material in self.material_list.items():
            all_material_info[material_id] = material.analysis_result
        return json.dumps(all_material_info, ensure_ascii=False)

    def get_material_by_id(self, id: str) -> Optional[Material]:
        """
        根据id获取素材
        :param id: 素材id
        :return: 素材,有可能为None
        """
        return self.material_list[id]

    def append_material_without_analysis(self, material_path: str, title: str, link: str = "", id=None):
        """
        添加素材，不进行分析
        :param material: 素材
        """
        assert isinstance(material_path, str),"material_path must be string"
        if id is None:
            material_id = str(self.get_id())
        else:
            material_id = id
        # 将其拷贝到material_library_dir中

        new_material_path = os.path.join(
            self.material_library_dir, f"{material_id}.{material_path.split('.')[-1]}")
        shutil.copy(material_path,  new_material_path)
        material = Material(
            id=material_id,
            material_path=new_material_path,
            title=title,
            link=link,
            analysis_result=None,
            is_analyzed=False
        )
        self.append_material(material)
        return material_id

    def append_material_with_analysis(self, material_path: str, title: str, description: str, link: str = "", analysis_result: str = None, id=None):
        """
        添加素材，进行分析
        :param material: 素材
        """
        if id is None:
            material_id = self.get_id()
        else:
            material_id = id
        # 将其拷贝到material_library_dir中
        new_material_path = os.path.join(
            self.material_library_dir, f"{str(material_id)}.{material_path.split('.')[-1]}")
        shutil.copy(material_path, new_material_path)
        material = Material(
            id=str(material_id),
            material_path=new_material_path,
            title=title,
            link=link,
            analysis_result=analysis_result,
            is_analyzed=True
        )
        self.append_material(material)

    def append_material(self, material: Material):
        """
        添加素材
        :param material: 素材
        """
        assert isinstance(material.id, str)
        self.material_list[material.id] = material
        logger.info(f"append material: {material}")

    def select_appropriate_material(self, require: str) -> list[str]:
        """
        根据需求选择合适的素材
        :param require: 需求
        :return: 素材
        """
        # 先对所有素材进行分析(并行运行),对没有分析过的素材进行分析
        for material in self.material_list.values():
            asyncio.run(material.analyze_material(self.material_library_dir))
        material_library_info = self.get_all_material_info()
        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_en.format(
                expert_knowledge=SELECT_APPROPRIATE_MATERIAL_EXPERT_KNOWLEDGE_en, material_library=material_library_info),
            response_schema=SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                require
            ]
        )
        content = json.loads(response.candidates[0].content.parts[0].text)
        logger.info(f"require: {require}, now material_library:{
                    material_library_info}, select_appropriate_material: {content["material_id_list"]}")
        return f"素材库中符合需求的素材id列表为: {content['material_id_list']}"

    async def crawl_material_by_link(self, link: str):
        """
        根据链接获取素材
        :param link: 链接
        :return: 素材
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                locale="en-US"
            )
            page = await context.new_page()
            try:
                await page.goto(link, timeout=10000)
                await asyncio.sleep(2)
                try:
                    await page.wait_for_selector("a#redir-stay-at-www", timeout=1000)
                    await page.click("a#redir-stay-at-www")
                    logger.info("已点击 Stay on Amazon.sg 按钮")
                except:
                    logger.info("按钮不存在，继续执行")
                title = await page.title()

                thumbs = await page.locator("li.imageThumbnail").all()
                for thumb in thumbs:
                    await thumb.click()
                    await asyncio.sleep(0.5)

                main_images = await page.locator("img.a-dynamic-image").all()
                img_list = []
                for img in main_images:
                    src = await img.get_attribute("data-old-hires")
                    if src and src not in img_list:
                        img_list.append(src)
                if len(img_list) > 0:
                    # 将图片下载到本地
                    img_path_dict = {}
                    material_id = self.get_id()
                    os.makedirs(os.path.join(self.material_library_dir, str(
                        material_id)), exist_ok=True)

                    for i, img in enumerate(img_list):
                        img_path = os.path.join(self.material_library_dir, str(
                            material_id), f"{str(material_id)}_{i+1}.jpg")
                        response = requests.get(img)

                        with open(img_path, "wb") as f:
                            f.write(response.content)
                        img_path_dict[i+1] = f"{str(material_id)}_{i+1}.jpg"
                    material = Material(
                        id=str(material_id),
                        link_list=[link],
                        title=title,
                        description=f"Amazon material for '{title}'",
                        sub_material_path_list=img_path_dict,
                        sub_material_content_list={}
                    )
                    self.append_material(material)
                else:
                    content = await page.content()
                    logger.info(content[:2000])
                    logger.info(f"No images found for {link}")
            except Exception as e:
                logger.error(f"Error processing link {link}: {e}")
        await browser.close()
        if img_list and len(img_list) > 0:
            return True
        return False

    def return_material_list(self):
        """
        返回素材列表
        :return: 素材列表
        """
        return_material_list = []

        for material_id, material in self.material_list.items():
            material_id = str(material_id)
            if not material_id.startswith("#"):
                return_material_list.append((os.path.join(
                    self.material_library_dir, material.material_path), material_id))
        return return_material_list

    async def crawl_material_in_web(self, keyword: str) -> list[Material]:
        """
        爬取网页链接
        :param keyword: 商品关键词
        :return: Material
        """
        await self.crawl_material_in_aws(keyword)

    async def crawl_material_in_aws(self, keyword: str, max_link_num: int = 10) -> list[Material]:
        """
        爬取商品链接
        :param keyword: 商品关键词
        :return: Material
        """
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
            for i, link in enumerate(goods_links, start=1):
                if i > max_link_num:
                    break
                logger.info(f"Processing link: {i}/{max_link_num}")
                try:
                    await page.goto(link, timeout=30000)
                except:
                    logger.info(f"Timeout loading: {link}")
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
                logger.info(f"number of images(crawl from amazon): {
                            len(main_images)}")
                img_list = []
                for img in main_images:
                    src = await img.get_attribute("data-old-hires")
                    if src and src not in img_list:
                        img_list.append(src)

                if len(img_list) > 0:
                    # 将图片下载到本地
                    img_path_dict = {}
                    material_id = self.get_id()
                    os.makedirs(os.path.join(self.material_library_dir, str(
                        material_id)), exist_ok=True)
                    for i, img in enumerate(img_list):
                        img_path = os.path.join(self.material_library_dir, str(
                            material_id), f"{str(material_id)}_{i+1}.jpg")
                        response = requests.get(img)

                        with open(img_path, "wb") as f:
                            f.write(response.content)
                        img_path_dict[i+1] = f"{str(material_id)}_{i+1}.jpg"
                    material = Material(
                        id=str(material_id),
                        link_list=[link],
                        title=title,
                        description=f"Amazon material for '{keyword}'",
                        sub_material_path_list=img_path_dict,
                        sub_material_content_list={}
                    )
                    self.append_material(material)
                else:
                    content = await page.content()
                    logger.info(content[:2000])
                    logger.info(f"No images found for {link}")

            await browser.close()


material_librarys: dict[str, MaterialLibrary] = {}
