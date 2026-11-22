from django.urls import path
from . import views

urlpatterns = [
    path('', views.gestion_seguimientos, name='gestion_seguimientos'),
]
