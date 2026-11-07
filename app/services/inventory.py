from sqlalchemy import update
from sqlalchemy.orm import Session
from app.models import Product


def reserve_stock(db: Session, product_id: int, quantity: int) -> bool:
    """Atomically decrement stock only when enough units remain.

    The conditional UPDATE is the final overselling guard; checkout also locks
    product rows on databases that support SELECT ... FOR UPDATE.
    """
    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
    )
    return result.rowcount == 1


def restore_stock(db: Session, product_id: int, quantity: int) -> None:
    """Return previously reserved stock when an unpaid order is cancelled/failed."""
    db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(stock=Product.stock + quantity)
    )
