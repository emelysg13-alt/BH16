from django.urls import path
from . import views

urlpatterns = [
    path('', views.mapa_localidades, name='mapa_localidades'),
    path('datos/', views.datos_marcadores, name='datos_marcadores'),
]