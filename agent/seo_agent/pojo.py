
from pydantic import BaseModel
from pydantic import Field


class Keywords(BaseModel):
    product_brand: list[str] = Field(description="The brand of the product")
    product_category: list[str] = Field(
        description="The category of the product")
    product_attribute: list[str] = Field(
        description="The attribute of the product")
    selling_points: list[str] = Field(
        description="The selling points of the product")
    other_keywords: list[str] = Field(
        description="The other keywords of the product")

    def to_string(self) -> str:
        return f"product_brand: {self.product_brand}, product_category: {self.product_category}, product_attribute: {self.product_attribute}, selling_points: {self.selling_points}, other_keywords: {self.other_keywords}"


class ProductInfo(BaseModel):
    product_title: str = Field(description="The title of the product")
