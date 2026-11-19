from django.urls import path
from . import views

urlpatterns = [
    path('registrar/', views.registrar_donacion, name='registrar_donacion'),
]