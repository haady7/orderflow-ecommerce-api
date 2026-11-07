from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=5000)
    sku: str = Field(min_length=2, max_length=64)
    category: str = Field(default="General", max_length=80)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    image_url: HttpUrl | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=80)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)
    image_url: HttpUrl | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    sku: str
    category: str
    price: Decimal
    stock: int
    image_url: str | None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
