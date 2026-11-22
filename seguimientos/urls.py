from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_seguimientos, name='lista_seguimientos'),

    path(
        'mis-seguimientos/',
        views.mis_seguimientos,
        name='mis_seguimientos'
    ),

    path(
        'mis-seguimientos/<int:id_seguimiento>/',
        views.detalle_mi_seguimiento,
        name='detalle_mi_seguimiento'
    ),

    path('crear/', views.crear_seguimiento, name='crear_seguimiento'),

    path(
        '<int:id_seguimiento>/',
        views.detalle_seguimiento,
        name='detalle_seguimiento'
    ),


    path(
    'mis-seguimientos/<int:id_seguimiento>/eliminar/',
    views.eliminar_seguimiento,
    name='eliminar_seguimiento'
),
]