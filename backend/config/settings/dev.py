"""Development settings — verbose, permissive, easy to iterate against."""
from .base import *  # noqa: F401,F403
from .base import CORS_ALLOWED_ORIGINS, REST_FRAMEWORK, env_list

DEBUG = True

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "*") or ["*"]

# In dev, allow the browsable API for quick poking.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# In dev, additionally allow Vite preview servers on common ports so local
# previews started via Claude Code can hit the API without per-env CORS config.
_DEV_EXTRA_ORIGINS = [
    f"http://localhost:{port}" for port in (5173, 5174, 5175, 5180)
]
CORS_ALLOWED_ORIGINS = list(
    {*CORS_ALLOWED_ORIGINS, *_DEV_EXTRA_ORIGINS}
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
