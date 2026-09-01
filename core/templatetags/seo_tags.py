import json
from typing import Any

from django import template
from django.utils.safestring import SafeString, mark_safe

register = template.Library()


@register.simple_tag
def jsonld(payload: dict[str, Any] | list[Any] | None) -> SafeString:
    """Render a JSON-LD payload as a <script> block. Empty payloads render nothing."""
    if not payload:
        return mark_safe("")
    body = json.dumps(payload, ensure_ascii=False, indent=None)
    # </script> inside JSON strings would break out of the tag.
    body = body.replace("</", "<\\/")
    return mark_safe(f'<script type="application/ld+json">{body}</script>')
