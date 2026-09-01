from typing import Any

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, Any]:
    return {
        "SITE_URL": settings.SITE_URL,
        "SITE_NAME": settings.SITE_NAME,
        "ADS_ENABLED": settings.ADS_ENABLED,
        "ADSENSE_CLIENT_ID": settings.ADSENSE_CLIENT_ID,
        "CANONICAL_URL": settings.SITE_URL + request.path,
    }
