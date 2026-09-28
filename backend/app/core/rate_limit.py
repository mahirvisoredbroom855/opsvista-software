# backend/app/core/rate_limit.py
"""
Shared rate limiter instance. Defined in its own module (rather than inline
in main.py) so route files (chat.py, admin_metrics.py, discovery.py) can
import and apply @limiter.limit(...) decorators without a circular import
back to main.py.
"""
# ─────────────────────────────────────────────────────────────────────────
# [OPS:RATE-001] limiter — the shared slowapi Limiter instance
#
# WHAT: key_func=get_remote_address means limits are per-client-IP, not
#       per-user — an authenticated and anonymous request from the same
#       IP share one bucket. default_limits=["120/minute"] applies to
#       any route WITHOUT its own @limiter.limit(...) decorator; routes
#       that specify one (e.g. [OPS:CHAT-015] 20/minute, [OPS:ADMIN-001]
#       3/minute) override the default for that route specifically.
# WHY A SEPARATE MODULE: main.py registers the SlowAPIMiddleware and the
#       429 exception handler against this same `limiter` instance — if
#       route files imported it from main.py instead, that would create
#       a circular import (main.py imports the routers, which would need
#       to import back from main.py).
# CALLED BY: every @router.post/@router.get decorated with
#       @limiter.limit(...) across chat.py, discovery.py, admin_metrics.py.
# ─────────────────────────────────────────────────────────────────────────
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
