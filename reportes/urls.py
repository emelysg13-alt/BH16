from django.urls import path
from . import views

urlpatterns = [
    path(
        '',
        views.gestion_reportes,
        name='gestion_reportes'
    ),
]