from django.urls import path
from . import views
from .autenticacion import (
    iniciar_sesion,
    cerrar_sesion,
    mi_cuenta,
)

app_name = 'inicio'

urlpatterns = [
    path(
        '',
        views.pagina_principal,
        name='pagina_principal'
    ),

    path(
        'iniciar-sesion/',
        iniciar_sesion,
        name='iniciar_sesion'
    ),

    path(
        'mi-cuenta/',
        mi_cuenta,
        name='mi_cuenta'
    ),

    path(
        'cerrar-sesion/',
        cerrar_sesion,
        name='cerrar_sesion'
    ),
]