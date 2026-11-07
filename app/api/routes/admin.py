from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import require_admin
from app.db.session import get_db
from app.models import Order, Payment, Product, User

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/metrics")
def dashboard_metrics(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    order_count = db.scalar(select(func.count(Order.id))) or 0
    customer_count = db.scalar(select(func.count(User.id)).where(User.role == "customer")) or 0
    product_count = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    paid_revenue = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "succeeded")) or Decimal("0.00")
    status_rows = db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
    low_stock = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True), Product.stock <= 5)) or 0
    return {"orders": order_count, "customers": customer_count, "active_products": product_count,
            "paid_revenue": str(paid_revenue), "currency": "INR",
            "orders_by_status": {status: count for status, count in status_rows}, "low_stock_products": low_stock}
