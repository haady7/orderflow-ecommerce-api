import hashlib
import hmac
import json
import uuid
from decimal import Decimal
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import Order, OrderEvent, Payment, Refund, User
from app.schemas.order import RefundRequest
from app.schemas.payment import PaymentOut, SimulatePaymentRequest
from app.services.inventory import restore_stock

router = APIRouter(tags=["Payments & refunds"])


def get_owned_payment(db: Session, payment_id: int, user: User) -> Payment:
    payment = db.scalar(select(Payment).options(selectinload(Payment.order)).where(Payment.id == payment_id))
    if not payment or (payment.order.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


def restore_order_stock(db: Session, order: Order) -> None:
    for item in order.items:
        if item.product_id:
            restore_stock(db, item.product_id, item.quantity)


@router.post("/orders/{order_id}/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = db.scalar(select(Order).options(selectinload(Order.payments)).where(Order.id == order_id))
    if not order or (order.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "pending_payment":
        raise HTTPException(status_code=409, detail="Only pending orders can be paid")
    existing = next((p for p in order.payments if p.status == "created"), None)
    if existing:
        return existing

    provider = settings.payment_provider.lower()
    if provider == "razorpay":
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise HTTPException(status_code=503, detail="Razorpay credentials are not configured")
        try:
            response = httpx.post("https://api.razorpay.com/v1/orders",
                                  auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
                                  json={"amount": int(order.total * 100), "currency": order.currency,
                                        "receipt": f"order_{order.id}", "notes": {"orderflow_order_id": str(order.id)}}, timeout=15)
            response.raise_for_status()
            provider_order_id = response.json()["id"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Could not create payment with Razorpay") from exc
    elif provider == "mock":
        provider_order_id = f"mock_ord_{uuid.uuid4().hex[:18]}"
    else:
        raise HTTPException(status_code=503, detail="Unsupported PAYMENT_PROVIDER; use mock or razorpay")

    payment = Payment(order_id=order.id, provider=provider, provider_order_id=provider_order_id,
                      amount=order.total, currency=order.currency, status="created")
    db.add(payment)
    db.add(OrderEvent(order_id=order.id, event="payment_created", details={"provider": provider}))
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/payments/{payment_id}/simulate", response_model=PaymentOut)
def simulate_payment(payment_id: int, payload: SimulatePaymentRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payment = get_owned_payment(db, payment_id, user)
    if payment.provider != "mock" or settings.payment_provider.lower() != "mock":
        raise HTTPException(status_code=400, detail="Payment simulation is available only in mock mode")
    if payment.status != "created":
        raise HTTPException(status_code=409, detail=f"Payment is already {payment.status}")
    order = payment.order
    if payload.success:
        payment.status = "succeeded"
        payment.provider_payment_id = f"mock_pay_{uuid.uuid4().hex[:18]}"
        order.status = "paid"
        db.add(OrderEvent(order_id=order.id, event="payment_succeeded", details={"payment_id": payment.id, "mode": "mock"}))
    else:
        payment.status = "failed"
        order.status = "cancelled"
        restore_order_stock(db, order)
        db.add(OrderEvent(order_id=order.id, event="payment_failed", details={"payment_id": payment.id, "stock_restored": True}))
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/payments/webhook", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None)):
    """Verify Razorpay webhook signatures before applying payment/refund state changes."""
    if settings.payment_provider.lower() != "razorpay" or not settings.razorpay_webhook_secret:
        raise HTTPException(status_code=503, detail="Razorpay webhook is not configured")
    body = await request.body()
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not x_razorpay_signature or not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        event_data = json.loads(body)
        event_name = event_data["event"]
        if event_name in {"payment.captured", "payment.failed"}:
            entity = event_data["payload"]["payment"]["entity"]
            provider_order_id = entity["order_id"]
        elif event_name in {"refund.processed", "refund.failed"}:
            entity = event_data["payload"]["refund"]["entity"]
            provider_payment_id = entity["payment_id"]
        else:
            return {"received": True, "ignored": "unsupported_event"}
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed payment webhook") from exc

    from app.db.session import SessionLocal
    with SessionLocal() as db:
        if event_name in {"payment.captured", "payment.failed"}:
            payment = db.scalar(select(Payment).options(selectinload(Payment.order).selectinload(Order.items))
                                 .where(Payment.provider_order_id == provider_order_id))
            if not payment:
                return {"received": True, "ignored": "unknown_order"}
            if payment.status != "created":
                return {"received": True, "ignored": "already_processed"}
            order = payment.order
            if event_name == "payment.captured":
                payment.status = "succeeded"
                payment.provider_payment_id = entity.get("id")
                order.status = "paid"
            else:
                payment.status = "failed"
                order.status = "cancelled"
                restore_order_stock(db, order)
        else:
            payment = db.scalar(select(Payment).options(selectinload(Payment.order), selectinload(Payment.refunds))
                                 .where(Payment.provider_payment_id == provider_payment_id))
            if not payment:
                return {"received": True, "ignored": "unknown_payment"}
            refund = max(payment.refunds, key=lambda item: item.id, default=None)
            if not refund or refund.status != "requested":
                return {"received": True, "ignored": "no_pending_refund"}
            if event_name == "refund.processed":
                refund.status = "processed"
                payment.status = "refunded"
                payment.order.status = "refunded"
            else:
                refund.status = "failed"
        db.add(OrderEvent(order_id=payment.order_id, event=event_name.replace(".", "_"), details={"payment_id": payment.id}))
        db.commit()
    return {"received": True}


@router.post("/payments/{payment_id}/refunds", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def request_refund(payment_id: int, payload: RefundRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payment = get_owned_payment(db, payment_id, user)
    if payment.status != "succeeded":
        raise HTTPException(status_code=409, detail="Only successful payments can be refunded")
    if payment.refunds:
        raise HTTPException(status_code=409, detail="A refund has already been requested")
    if payment.provider == "razorpay":
        try:
            response = httpx.post(f"https://api.razorpay.com/v1/payments/{payment.provider_payment_id}/refund",
                                  auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
                                  json={"amount": int(payment.amount * 100), "notes": {"reason": payload.reason}}, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Razorpay refund request failed") from exc
    refund_status = "processed" if payment.provider == "mock" else "requested"
    db.add(Refund(payment_id=payment.id, amount=payment.amount, reason=payload.reason, status=refund_status))
    if payment.provider == "mock":
        payment.status = "refunded"
        payment.order.status = "refunded"
    db.add(OrderEvent(order_id=payment.order_id, event="refund_requested", details={"payment_id": payment.id, "status": refund_status}))
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/payments/mine", response_model=list[PaymentOut])
def my_payments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Payment).join(Order).where(Order.user_id == user.id).order_by(Payment.created_at.desc())
    return list(db.scalars(stmt).all())


@router.get("/admin/payments", response_model=list[PaymentOut])
def list_payments(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(200)).all())
