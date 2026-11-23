from django.urls import path
from . import views

urlpatterns = [
    path('', views.gestion_seguimientos, name='gestion_seguimientos'),

    path(
    'detalle/<int:id_seguimiento>/',
    views.detalle_seguimiento,
    name='admin_detalle_seguimiento'
),

    path(
        'aprobar/<int:id_seguimiento>/',
        views.aprobar_seguimiento,
        name='aprobar_seguimiento'
    ),

    path(
        'rechazar/<int:id_seguimiento>/',
        views.rechazar_seguimiento,
        name='rechazar_seguimiento'
    ),

    path(
    'ingresos-refugio/',
    views.gestion_ingresos_refugio,
    name='gestion_ingresos_refugio'
),


    path(
    'ingreso-refugio/confirmar/<int:id_ingreso>/',
    views.confirmar_ingreso_refugio,
    name='confirmar_ingreso_refugio'
),

    path(
    'ingreso-refugio/rechazar/<int:id_ingreso>/',
    views.rechazar_ingreso_refugio,
    name='rechazar_ingreso_refugio'
),
]