from django.urls import path

from . import views

app_name = "oposiciones"

# URL taxonomy: designed once, never changed. Lowercase, hyphenated, no IDs.
# /oposiciones/autonomica/{comunidad}/{slug}/ can slot in later without
# breaking these routes because {ambito} is a fixed vocabulary segment.
urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("oposiciones/", views.OposicionIndexView.as_view(), name="index"),
    path(
        "oposiciones/<slug:ambito>/<slug:slug>/",
        views.OposicionDetailView.as_view(),
        name="detail",
    ),
    path(
        "oposiciones/<slug:ambito>/<slug:slug>/temario/",
        views.TemarioView.as_view(),
        name="temario",
    ),
    path(
        "oposiciones/<slug:ambito>/<slug:slug>/convocatorias/",
        views.ConvocatoriaListView.as_view(),
        name="convocatorias",
    ),
    path(
        "convocatorias/<int:anio>/<slug:slug>/",
        views.ConvocatoriaDetailView.as_view(),
        name="convocatoria_detail",
    ),
]
