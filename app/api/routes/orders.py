from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import CartItem, Order, OrderEvent, OrderItem, Product, User
from app.schemas.order import CheckoutRequest, OrderOut
from app.services.inventory import reserve_stock, restore_stock

router = APIRouter(prefix="/orders", tags=["Orders"])


def fetch_order(db: Session, order_id: int) -> Order | None:
    return db.scalar(select(Order).options(selectinload(Order.items), selectinload(Order.payments)).where(Order.id == order_id))


@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if idempotency_key:
        if len(idempotency_key) > 80:
            raise HTTPException(status_code=422, detail="Idempotency-Key must be 80 characters or fewer")
        existing = db.scalar(select(Order).where(Order.idempotency_key == f"{user.id}:{idempotency_key}"))
        if existing:
            return fetch_order(db, existing.id)

    cart_items = db.scalars(select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.product_id)).all()
    if not cart_items:
        # A concurrent retry may arrive after the first request has already cleared the cart.
        if idempotency_key:
            existing = db.scalar(select(Order).where(Order.idempotency_key == f"{user.id}:{idempotency_key}"))
            if existing:
                return fetch_order(db, existing.id)
        raise HTTPException(status_code=400, detail="Your cart is empty")

    try:
        product_ids = [item.product_id for item in cart_items]
        products = db.scalars(select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()).all()
        # The product row locks serialize overlapping checkouts. Re-check the idempotency key
        # after acquiring them so simultaneous retries do not reserve inventory twice.
        if idempotency_key:
            existing = db.scalar(select(Order).where(Order.idempotency_key == f"{user.id}:{idempotency_key}"))
            if existing:
                db.rollback()
                return fetch_order(db, existing.id)
        product_map = {product.id: product for product in products}
        subtotal = Decimal("0.00")
        snapshots = []
        for item in cart_items:
            product = product_map.get(item.product_id)
            if not product or not product.is_active:
                raise HTTPException(status_code=409, detail="A product in your cart is no longer available")
            # A conditional UPDATE makes stock reservation safe even where SELECT FOR UPDATE is ignored (e.g. SQLite).
            if not reserve_stock(db, product.id, item.quantity):
                raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.name}")
            line_total = product.price * item.quantity
            subtotal += line_total
            snapshots.append((product, item.quantity, line_total))

        order = Order(user_id=user.id, status="pending_payment", subtotal=subtotal, total=subtotal,
                      currency="INR", shipping_address=payload.shipping_address.model_dump(),
                      idempotency_key=f"{user.id}:{idempotency_key}" if idempotency_key else None)
        db.add(order)
        db.flush()
        for product, quantity, line_total in snapshots:
            db.add(OrderItem(order_id=order.id, product_id=product.id, product_name=product.name, sku=product.sku,
                             unit_price=product.price, quantity=quantity, line_total=line_total))
        db.add(OrderEvent(order_id=order.id, event="order_created", details={"total": str(subtotal)}))
        for item in cart_items:
            db.delete(item)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return fetch_order(db, order.id)


@router.get("/mine", response_model=list[OrderOut])
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Order).options(selectinload(Order.items)).where(Order.user_id == user.id).order_by(Order.created_at.desc())).all())


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = fetch_order(db, order_id)
    if not order or (order.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("", response_model=list[OrderOut])
def list_all_orders(skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
                    db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc()).offset(skip).limit(limit)).all())


@router.patch("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = fetch_order(db, order_id)
    if not order or (order.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in {"pending_payment", "paid"}:
        raise HTTPException(status_code=409, detail=f"Order cannot be cancelled in status '{order.status}'")
    if order.status == "paid":
        raise HTTPException(status_code=409, detail="Paid orders must be refunded by an administrator")
    if any(payment.status == "succeeded" for payment in order.payments):
        raise HTTPException(status_code=409, detail="A successful payment exists; use the refund process")
    for item in order.items:
        if item.product_id:
            restore_stock(db, item.product_id, item.quantity)
    order.status = "cancelled"
    db.add(OrderEvent(order_id=order.id, event="order_cancelled", details={"by_user_id": user.id}))
    db.commit()
    return fetch_order(db, order.id)
