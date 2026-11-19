from django.urls import path
from . import views

urlpatterns = [
    path(
        'iniciar-sesion/',
        views.iniciar_sesion,
        name='iniciar_sesion'
    ),
    path(
        'cerrar-sesion/',
        views.cerrar_sesion,
        name='cerrar_sesion'
    ),
]