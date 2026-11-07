from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class ShippingAddress(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    postal_code: str = Field(min_length=4, max_length=12)
    country: str = Field(default="India", min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)


class CheckoutRequest(BaseModel):
    shipping_address: ShippingAddress


class OrderItemOut(BaseModel):
    id: int
    product_id: int | None
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: int
    status: str
    subtotal: Decimal
    total: Decimal
    currency: str
    shipping_address: dict
    created_at: datetime
    items: list[OrderItemOut]
    model_config = ConfigDict(from_attributes=True)


class RefundRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=300)
