from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps import views as sitemap_views
from django.urls import include, path

from core import views as core_views
from core.sitemaps import SITEMAPS

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("allauth.urls")),
    path("healthz", core_views.healthz, name="healthz"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("llms.txt", core_views.llms_txt, name="llms_txt"),
    path(
        "sitemap.xml",
        sitemap_views.index,
        {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap_section"},
        name="sitemap_index",
    ),
    path(
        "sitemap-<section>.xml",
        sitemap_views.sitemap,
        {"sitemaps": SITEMAPS},
        name="sitemap_section",
    ),
    path("aviso-legal/", core_views.aviso_legal, name="aviso_legal"),
    path("politica-de-privacidad/", core_views.privacidad, name="privacidad"),
    path(
        "retirada-de-contenido/",
        core_views.retirada_de_contenido,
        name="retirada_de_contenido",
    ),
    path("consentimiento/registrar/", core_views.log_consent, name="log_consent"),
    path("buscar/", include("search.urls")),
    path("api/", include("search.api_urls")),
    path("documentos/", include("documents.urls")),
    path("apuntes/", include("posts.urls")),
    path("", include("oposiciones.urls")),
]

if settings.DEBUG:
    try:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns += debug_toolbar_urls()
    except ImportError:  # pragma: no cover - dev-only dependency
        pass
