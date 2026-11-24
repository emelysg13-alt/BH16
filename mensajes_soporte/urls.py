from django.urls import path
from . import views

urlpatterns = [
    path(
        '',
        views.mensajes_soporte,
        name='mensajes_soporte'
    ),
]