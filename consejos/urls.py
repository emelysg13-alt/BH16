from django.urls import path
from . import views

urlpatterns = [
    path(
        '',
        views.gestion_consejos,
        name='gestion_consejos'
    ),
]