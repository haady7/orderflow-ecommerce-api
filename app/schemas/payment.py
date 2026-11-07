from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class PaymentOut(BaseModel):
    id: int
    order_id: int
    provider: str
    provider_order_id: str | None
    provider_payment_id: str | None
    amount: Decimal
    currency: str
    status: str
    model_config = ConfigDict(from_attributes=True)


class SimulatePaymentRequest(BaseModel):
    success: bool = True
