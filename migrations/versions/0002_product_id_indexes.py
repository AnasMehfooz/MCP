"""Index product_id on variants and product_images.

Postgres indexes primary keys and unique constraints, but not foreign keys. Without these,
loading a product's variants or images, and every cascading delete of a product, scans the
whole child table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 21:02:02.911158
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_product_images_product_id"), "product_images", ["product_id"], unique=False)
    op.create_index(op.f("ix_variants_product_id"), "variants", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_variants_product_id"), table_name="variants")
    op.drop_index(op.f("ix_product_images_product_id"), table_name="product_images")
