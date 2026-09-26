# backend/app/core/rate_limit.py
"""
Shared rate limiter instance. Defined in its own module (rather than inline
in main.py) so route files (chat.py, admin_metrics.py, discovery.py) can
import and apply @limiter.limit(...) decorators without a circular import
back to main.py.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
