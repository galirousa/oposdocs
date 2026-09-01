from django.urls import path

from . import api

app_name = "search_api"

urlpatterns = [
    path("buscar/", api.api_buscar, name="api_buscar"),
    path("schema/", api.api_schema, name="api_schema"),
]
