from django.urls import path

from . import views

app_name = "posts"

# Literal segments come first so a post slug can never shadow them; the
# reserved-slug guard in the model keeps them from being generated at all.
urlpatterns = [
    path("", views.PostListView.as_view(), name="index"),
    path("nuevo/", views.post_create, name="create"),
    path("mis-apuntes/", views.my_posts, name="mine"),
    path("autoguardar/", views.post_autosave, name="autosave"),
    path("<int:pk>/editar/", views.post_edit, name="edit"),
    path("<int:pk>/publicar/", views.post_publish, name="publish"),
    path("<int:pk>/despublicar/", views.post_unpublish, name="unpublish"),
    path("<int:pk>/eliminar/", views.post_delete, name="delete"),
    path("<slug:slug>/", views.PostDetailView.as_view(), name="detail"),
]
