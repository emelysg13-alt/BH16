from django.urls import path
from . import views

urlpatterns = [
    path(
        'mi-cuenta/',
        views.mi_cuenta,
        name='mi_cuenta'
    ),
]