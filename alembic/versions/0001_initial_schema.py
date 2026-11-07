"""Initial OrderFlow schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("products",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""), sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default="General"), sa.Column("price", sa.Numeric(10,2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"), sa.Column("image_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_product_price_nonnegative"), sa.CheckConstraint("stock >= 0", name="ck_product_stock_nonnegative"))
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    op.create_index("ix_products_category", "products", ["category"])
    op.create_table("cart_items",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"), sa.CheckConstraint("quantity > 0", name="ck_cart_quantity_positive"))
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])
    op.create_index("ix_cart_items_product_id", "cart_items", ["product_id"])
    op.create_table("orders",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_payment"), sa.Column("subtotal", sa.Numeric(10,2), nullable=False),
        sa.Column("total", sa.Numeric(10,2), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("shipping_address", sa.JSON(), nullable=False), sa.Column("idempotency_key", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total >= 0", name="ck_order_total_nonnegative"), sa.UniqueConstraint("idempotency_key"))
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_table("order_items",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")), sa.Column("product_name", sa.String(180), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False), sa.Column("unit_price", sa.Numeric(10,2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("line_total", sa.Numeric(10,2), nullable=False))
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_table("payments",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="mock"), sa.Column("provider_order_id", sa.String(120)),
        sa.Column("provider_payment_id", sa.String(120)), sa.Column("amount", sa.Numeric(10,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"), sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("provider_order_id"), sa.UniqueConstraint("provider_payment_id"))
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_table("refunds",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10,2), nullable=False), sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])
    op.create_table("order_events",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(80), nullable=False), sa.Column("details", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])


def downgrade():
    for table in ("order_events", "refunds", "payments", "order_items", "orders", "cart_items", "products", "users"):
        op.drop_table(table)
