from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("subir/", views.upload_document, name="upload"),
    path("<slug:slug>/", views.DocumentDetailView.as_view(), name="detail"),
    path("<slug:slug>/descargar/", views.download_document, name="download"),
]
