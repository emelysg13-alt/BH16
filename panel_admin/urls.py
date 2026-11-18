
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Usuarios: se conserva la vista existente
    path('usuarios/', views.gestion_usuarios, name='gestion_usuarios'),

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
]
