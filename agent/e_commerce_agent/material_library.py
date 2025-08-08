# 爬取（堆量)
from typing import Optional


class Material:
    """
    素材库
    link_list: 链接
    title: 标题(若为电商网站的爬取则为商品名称，若为网页的爬取则为网页标题)
    description: 描述(对于素材的描述，即从哪来等基础信息)
    img_url_list: 图片链接
    """

    def __init__(self, link_list: list[str], title: str, description: str, img_url_list: list[str]):
        self.link_list = link_list
        self.title = title
        self.description = description
        self.img_url_list = img_url_list


async def crawl_material_in_aws(keyword: str) -> Material:
    """
    爬取商品链接
    :param keyword: 商品关键词
    :return: Material
    """
    pass
