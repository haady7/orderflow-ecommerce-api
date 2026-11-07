from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import CartItem, Product, User
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartOut, CartLineOut

router = APIRouter(prefix="/cart", tags=["Shopping cart"])


def cart_snapshot(db: Session, user_id: int) -> CartOut:
    rows = db.scalars(select(CartItem).options(joinedload(CartItem.product)).where(CartItem.user_id == user_id).order_by(CartItem.id)).all()
    lines = []
    subtotal = Decimal("0.00")
    for row in rows:
        line_total = row.product.price * row.quantity
        subtotal += line_total
        lines.append(CartLineOut(id=row.id, product_id=row.product_id, product_name=row.product.name,
                                 unit_price=row.product.price, quantity=row.quantity, line_total=line_total,
                                 available_stock=row.product.stock))
    return CartOut(items=lines, subtotal=subtotal)


@router.get("", response_model=CartOut)
def get_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cart_snapshot(db, user.id)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_to_cart(payload: CartItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.get(Product, payload.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    item = db.scalar(select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product.id))
    new_quantity = payload.quantity + (item.quantity if item else 0)
    if new_quantity > product.stock:
        raise HTTPException(status_code=409, detail=f"Only {product.stock} units are currently available")
    if item:
        item.quantity = new_quantity
    else:
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=payload.quantity))
    db.commit()
    return cart_snapshot(db, user.id)


@router.patch("/items/{item_id}", response_model=CartOut)
def update_cart_item(item_id: int, payload: CartItemUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id).options(joinedload(CartItem.product)))
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    if payload.quantity > item.product.stock:
        raise HTTPException(status_code=409, detail=f"Only {item.product.stock} units are currently available")
    item.quantity = payload.quantity
    db.commit()
    return cart_snapshot(db, user.id)


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_cart_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id))
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return cart_snapshot(db, user.id)
