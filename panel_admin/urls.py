
from django.urls import path
from . import views
from . import consejos_soporte

urlpatterns = [
    # Dashboard
    path(
        '',
        views.dashboard,
        name='dashboard'
    ),

    # Usuarios
    path(
        'usuarios/',
        views.gestion_usuarios,
        name='gestion_usuarios'
    ),

    # Refugios
    path(
        'refugios/',
        views.gestion_refugios,
        name='gestion_refugios'
    ),

    path(
        'refugios/eliminar/<int:id_refugio>/',
        views.eliminar_refugio,
        name='eliminar_refugio'
    ),

    # Donaciones
    path(
        'donaciones/',
        views.gestion_donaciones,
        name='gestion_donaciones'
    ),

    # Consejos
    path(
        'consejos/',
        consejos_soporte.gestion_consejos,
        name='gestion_consejos'
    ),

    # Soporte
    path(
        'soporte/',
        consejos_soporte.gestion_soporte,
        name='gestion_soporte'
    ),
]
