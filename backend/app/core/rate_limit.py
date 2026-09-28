# backend/app/core/rate_limit.py
"""
This file caps how many requests any one visitor can make per minute,
so one person (or a bug, or an attacker) can't hammer the API and slow
it down for everyone else. Chat, feedback, and admin routes each set
their own limit using the shared tool defined here.

Shared rate limiter instance. Defined in its own module (rather than inline
in main.py) so route files (chat.py, admin_metrics.py, discovery.py) can
import and apply @limiter.limit(...) decorators without a circular import
back to main.py.
"""
# ─────────────────────────────────────────────────────────────────────────
# [OPS:RATE-001] limiter
#
# What it does: creates one shared rate limiter that counts requests per
# visitor IP address, not per logged-in account — a logged-in and
# anonymous request from the same IP share the same counter. By default
# any route gets 120 requests/minute; specific routes (like chat, at
# 20/minute) set their own tighter limit and override this default.
#
# Lives in its own file, separate from main.py, only so route files can
# import it without creating a circular import back to main.py.
#
# Called by: every route decorated with @limiter.limit(...) in chat.py,
# discovery.py, and admin_metrics.py.
# ─────────────────────────────────────────────────────────────────────────
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
