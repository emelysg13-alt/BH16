from django.urls import path
from . import views

urlpatterns = [
    # AUTENTICACIÓN
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

    # GESTIÓN DE USUARIOS
    path(
        'gestion/',
        views.gestion_usuarios,
        name='gestion_usuarios'
    ),
]