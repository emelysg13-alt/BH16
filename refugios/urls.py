from django.urls import path
from . import views

urlpatterns = [
    path(
        '',
        views.gestion_refugios,
        name='gestion_refugios'
    ),
    path(
        'eliminar/<int:id_refugio>/',
        views.eliminar_refugio,
        name='eliminar_refugio'
    ),
]