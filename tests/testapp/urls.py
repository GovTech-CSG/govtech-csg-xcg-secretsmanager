from django.urls import path

from . import views

urlpatterns = [
    path("mysql/", views.access_mysql_db),
    path("postgresql/", views.access_postgresql_db),
    path("get_secret_key/", views.get_secret_key),
]
