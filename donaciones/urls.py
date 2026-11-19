from django.urls import path
from . import views

urlpatterns = [
    path(
        '',
        views.gestion_donaciones,
        name='gestion_donaciones'
    ),
]