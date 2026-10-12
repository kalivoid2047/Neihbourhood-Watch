"""ASGI entrypoint with optional Channels WebSocket support."""

import importlib.util
import os

from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

django_application = get_asgi_application()

if importlib.util.find_spec("channels"):
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator
    from apps.core.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_application,
            "websocket": AllowedHostsOriginValidator(
                URLRouter(websocket_urlpatterns)
            ),
        }
    )
else:
    application = django_application
