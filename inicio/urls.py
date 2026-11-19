
from django.urls import path
from . import views

app_name = 'inicio'

urlpatterns = [
    path('', views.pagina_principal, name='pagina_principal'),
]
