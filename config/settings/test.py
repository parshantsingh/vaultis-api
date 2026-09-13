from .dev import *  # noqa: F401,F403

# The concurrency tests fire a burst of requests from the same user in rapid succession —
# that's exactly what DEFAULT_THROTTLE_RATES exists to block, but it has nothing to do
# with what those tests are actually checking. A real rate limit here would fail tests
# for a reason unrelated to the behavior under test.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
