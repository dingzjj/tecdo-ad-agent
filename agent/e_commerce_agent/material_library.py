# 爬取（堆量)
from typing import Optional
from pydantic import BaseModel, Field
import os
from config import conf

os.makedirs(conf.get_path("material_library_dir"), exist_ok=True)


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
    img_url_list: list[str] = Field(description="图片链接列表")
    img_content_list: list[tuple[str, str]] = Field(
        description="图片内容列表(图片链接,图片内容)")
    local_path: str = Field(description="本地路径")

    async def analyze_material(self):
        """
        分析素材,对素材中的内容进行分析（主要是图片部分）
        :param material: 素材
        :return: 分析结果
        """
        # 对img_url_list中的图片进行分析
        for img_url in self.img_url_list:
            # 1. 通过链接获取图片
            # 2. 对图片进行分析
            # 3. 将分析结果保存到self.img_url_list中


async def crawl_material_in_aws(keyword: str) -> list[Material]:
    """
    爬取商品链接
    :param keyword: 商品关键词
    :return: Material
    """
    pass


async def crawl_material_in_web(keyword: str) -> list[Material]:
    """
    爬取网页链接
    :param keyword: 商品关键词
    :return: Material
    """
    material_list = await crawl_material_in_aws(keyword)


async def create_video_in_material(material: Material):
    """
    根据素材创建视频
    :param material: 素材
    :return: 视频
    """
    pass
    # 1.视频生成的基调  - material


async def create_video_freedom(require: str):
    pass

    # 1.文生图(sdxl,wan2,1,qwen) , 文生视频(wan2.2,keling,veo3) ,图生视频(wan2.2,keling,veo3),修图(flux)


def get_material(keyword: str):
    # 1.通过链接获取素材，在此基础上进行二创

    # 2.自由创作
    pass
