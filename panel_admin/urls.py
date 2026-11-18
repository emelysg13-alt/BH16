
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
]
