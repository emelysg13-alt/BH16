
from django.urls import path
from . import views

urlpatterns = [
    path('', views.gestion_refugios, name='gestion_refugios'),

    path(
        '<int:id_refugio>/animales/',
        views.animales_refugio,
        name='animales_refugio'
    ),

    path(
        'eliminar/<int:id_refugio>/',
        views.eliminar_refugio,
        name='eliminar_refugio'
    ),
]
