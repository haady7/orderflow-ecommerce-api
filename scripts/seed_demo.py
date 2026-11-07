"""Add repeatable demo catalogue data to the configured database."""
from decimal import Decimal
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Product

DEMO_PRODUCTS = [
    {"name": "Everyday Backpack", "sku": "OF-BAG-001", "category": "Accessories", "price": Decimal("1499.00"), "stock": 18, "description": "A lightweight everyday backpack with a padded laptop sleeve."},
    {"name": "Wireless Headphones", "sku": "OF-AUD-002", "category": "Electronics", "price": Decimal("2499.00"), "stock": 12, "description": "Comfort-fit wireless headphones for work and travel."},
    {"name": "Steel Water Bottle", "sku": "OF-HOME-003", "category": "Home", "price": Decimal("599.00"), "stock": 30, "description": "Double-wall insulated stainless steel bottle."},
    {"name": "Desk Lamp", "sku": "OF-HOME-004", "category": "Home", "price": Decimal("1199.00"), "stock": 9, "description": "Minimal adjustable desk lamp with warm LED lighting."},
    {"name": "Mechanical Keyboard", "sku": "OF-TECH-005", "category": "Electronics", "price": Decimal("3299.00"), "stock": 7, "description": "Compact mechanical keyboard with tactile switches."},
    {"name": "Notebook Set", "sku": "OF-STAT-006", "category": "Stationery", "price": Decimal("349.00"), "stock": 40, "description": "Three premium ruled notebooks for notes and planning."},
]

with SessionLocal() as db:
    created = 0
    for data in DEMO_PRODUCTS:
        if not db.scalar(select(Product).where(Product.sku == data["sku"])):
            db.add(Product(**data))
            created += 1
    db.commit()
print(f"Demo catalogue ready. Added {created} product(s).")
