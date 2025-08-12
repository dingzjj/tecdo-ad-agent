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
    link_list: list[str] = Field(default=[], description="链接列表")
    title: str = Field(description="标题")
    description: str = Field(description="描述")
    sub_material_id: int = Field(default=1, description="next sub_material id")
    # 只会在v1 or v2 存在
    # v1 没有经过分析
    sub_material_path_list: dict[int, str] = Field(
        default={}, description="id:sub_material链接(in local)")
    # v2 经过分析or有确切描述的，会将子素材放入此处，material内容(有经过gemini2.5-flash分析 or 有确切描述)
    sub_material_content_list: dict[int, tuple[str, str]] = Field(
        default={}, description="id:sub_material链接(in local),material内容")

    async def analyze_material(self):
        """
        分析素材,对素材中的内容进行分析（主要是图片部分）
        :param material: 素材
        :return: 分析结果
        """
        # 并行分析素材
        tasks = []
        for sub_material_id, sub_material_path in self.sub_material_path_list.items():
            tasks.append((
                sub_material_id,
                sub_material_path,
                asyncio.create_task(
                    AnalyseMaterialAgent().analyse_material(
                        product=self.title,
                        material_path=os.path.join(
                            conf.get_path("material_library_dir"), self.id, sub_material_path),
                        source="local"
                    )
                )
            ))

        # 等待所有分析完成
        results = await asyncio.gather(*(t[2] for t in tasks))

        # 保存结果
        for (sub_material_id, sub_material_path, _), analysis_result in zip(tasks, results):
            self.sub_material_content_list[sub_material_id] = (
                sub_material_path, analysis_result
            )
        # 清空
        self.sub_material_path_list = {}

    async def get_material_by_id(self, sub_material_id: int):
        """
        根据id获取素材
        :param id: 素材id（详细ID）
        :return:sub_material_path_list or sub_material_content_list
        """
        if sub_material_id in self.sub_material_path_list:
            return self.sub_material_path_list[sub_material_id]
        elif sub_material_id in self.sub_material_content_list:
            return self.sub_material_content_list[sub_material_id][0]
        return None


class MaterialLibrary(BaseModel):
    """
    素材库
    """
    material_list: Dict[str, Material] = Field(default={}, description="id:素材")
    next_id: int = Field(default=1, description="下一个素材id")
    material_library_dir: str = Field(description="素材库地址")

    def get_id(self):
        id = self.next_id
        self.next_id += 1
        return id

    def get_all_material_info(self):
        # 返回Json[str格式] - 为llm提供素材库信息
        return json.dumps(
            {k: v.model_dump() for k, v in self.material_list.items()},
            ensure_ascii=False
        )

    def get_material_by_id(self, id: str):
        """
        根据id获取素材
        :param id: 素材id（详细ID），例如3_1，表示素材3的子素材1
        :return: 素材,有可能为None
        """
        id_list = id.split("_")
        material_id = id_list[0]
        sub_material_id = id_list[1]
        sub_material_path = asyncio.run(
            self.material_list[material_id].get_material_by_id(int(sub_material_id)))
        return os.path.join(self.material_library_dir, material_id, sub_material_path)

    def append_material(self, material: Material):
        """
        添加素材
        :param material: 素材
        """
        self.material_list[material.id] = material
        logger.info(f"append material: {material}")

    def insert_material_with_one_sub_material_to_v2(self, title, description, sub_material_path: str):
        """上传到的是v2部分"""
        material_id = self.get_id()
        # 创建素材目录
        os.makedirs(os.path.join(self.material_library_dir,
                    str(material_id)), exist_ok=True)
        # 将sub_material_path移动到素材目录
        new_sub_material_path = os.path.join(
            self.material_library_dir, str(material_id), f"{material_id}_1.{sub_material_path.split('.')[-1]}")

        shutil.move(sub_material_path, new_sub_material_path)

        self.append_material(Material(id=str(material_id), title=title,
                                      description=description, sub_material_id=2, sub_material_content_list={1: (f"{material_id}_1.{sub_material_path.split('.')[-1]}", description)}))

    def insert_material_with_one_sub_material_to_v1(self, title, description, sub_material_path: str):
        """上传到的是v1部分"""
        material_id = self.get_id()
        # 创建素材目录
        os.makedirs(os.path.join(self.material_library_dir,
                    str(material_id)), exist_ok=True)
        # 将sub_material_path移动到素材目录
        new_sub_material_path = os.path.join(
            self.material_library_dir, str(material_id), f"{material_id}_1.{sub_material_path.split('.')[-1]}")
        shutil.move(sub_material_path, new_sub_material_path)
        self.append_material(Material(id=str(material_id), title=title,
                                      description=description, sub_material_id=1, sub_material_path_list={1: f"{material_id}_1.{sub_material_path.split('.')[-1]}"}))

    def get_material_id(self, sub_material_path: str):
        """获取素材id"""
        return sub_material_path.split('/')[-1].split('.')[0]

    def select_appropriate_material(self, require: str) -> list[str]:
        """
        根据需求选择合适的素材
        :param require: 需求
        :return: 素材
        """
        # 先对所有素材进行分析(并行运行),对没有分析过的素材进行分析
        for material in self.material_list.values():
            asyncio.run(material.analyze_material())

        material_library = self.get_all_material_info()
        gemini_generative_model = get_gemini_multimodal_model(
            SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_en.format(
                expert_knowledge=SELECT_APPROPRIATE_MATERIAL_EXPERT_KNOWLEDGE_en, material_library=material_library), SELECT_APPROPRIATE_MATERIAL_SYSTEM_PROMPT_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                require
            ]
        )
        content = json.loads(response.candidates[0].content.parts[0].text)

        return content["material_id_list"]

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
                    print("已点击 Stay on Amazon.sg 按钮")
                except:
                    print("按钮不存在，继续执行")
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
                    await material.analyze_material()
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
        material_list = []

        for material_id, material in self.material_list.items():
            """
            # v1 - 只要有图片就下载下来
        img_path_list: dict[int, str] = Field(
            default={}, description="id:(图片链接(in local))")
        # v2
        img_content_list: dict[int, tuple[str, str]] = Field(
        default={}, description="id:(图片链接(in local),图片内容)")
            """
            material_list.extend([(os.path.join(self.material_library_dir, material_id, sub_material_path), str(f"{material_id}_{sub_material_id}"))
                                 for sub_material_id, sub_material_path in material.sub_material_path_list.items()])
            material_list.extend([(os.path.join(self.material_library_dir, material_id, sub_material_path), str(f"{material_id}_{sub_material_id}"))
                                 for sub_material_id, (sub_material_path, _) in material.sub_material_content_list.items()])
        return material_list

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
        # 将keyword翻译为英文
        keyword = Translator(from_lang="ZH", to_lang="EN-US").translate(
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
