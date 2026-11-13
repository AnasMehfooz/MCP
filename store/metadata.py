"""Every table in one place.

Importing this module registers all domain models on Base.metadata. Alembic and the tests
use it, so a new domain's models.py only has to be added here to be migrated and tested.
"""

from __future__ import annotations

from store.catalog import models as _catalog  # noqa: F401
from store.db import Base
from store.stores import models as _stores  # noqa: F401

metadata = Base.metadata
