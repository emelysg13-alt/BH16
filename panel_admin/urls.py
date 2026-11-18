
from django.urls import path
from . import views
from . import reportes
from .consejos_soporte import gestion_consejos, gestion_soporte


urlpatterns = [

    # DASHBOARD
    path(
        '',
        views.dashboard,
        name='dashboard'
    ),

    # USUARIOS
    path(
        'usuarios/',
        views.gestion_usuarios,
        name='gestion_usuarios'
    ),

    # REFUGIOS
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

    # DONACIONES
    path(
        'donaciones/',
        views.gestion_donaciones,
        name='gestion_donaciones'
    ),

    # CONSEJOS
    path(
        'consejos/',
        gestion_consejos,
        name='gestion_consejos'
    ),

    # SOPORTE
    path(
        'soporte/',
        gestion_soporte,
        name='gestion_soporte'
    ),

    # REPORTES
    path(
        'reportes/',
        reportes.gestion_reportes,
        name='gestion_reportes'
    ),

]
