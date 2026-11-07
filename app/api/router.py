from fastapi import APIRouter
from app.api.routes import auth, products, cart, orders, payments, admin

api_router = APIRouter()
for route_module in (auth, products, cart, orders, payments, admin):
    api_router.include_router(route_module.router)
