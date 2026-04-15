"""Rooms router package — split from the original monolithic rooms.py.

All sub-modules register their routes on a single shared ``router``
defined in ``_shared``.  Importing this package triggers route
registration and exposes the same public API as the old rooms.py::

    from app.routers.rooms import router
    from app.routers.rooms import init_redis_from_app
"""

# Import sub-modules so their @router decorators execute and register routes.
from . import crud  # noqa: F401
from . import members  # noqa: F401
from . import messages  # noqa: F401
from . import ai  # noqa: F401
from . import websocket  # noqa: F401

# Re-export public symbols that external code depends on.
from ._shared import init_redis_from_app, router

__all__ = ["router", "init_redis_from_app"]
