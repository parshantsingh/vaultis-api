from .dev import *  # noqa: F401

# The concurrency tests fire a burst of requests from the same user in rapid succession —
# that's exactly what rate limiting exists to block, but it has nothing to do with what
# those tests are actually checking. A real rate limit here would fail tests for a reason
# unrelated to the behavior under test. The throttle tests set their own low limits.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "login": "10000/min",
        "register": "10000/min",
        "transfers": "10000/min",
    },
}

# In-process cache so the test suite doesn't need a running Redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
