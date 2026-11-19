from django.urls import path, include
from . import views



urlpatterns = [

    # DASHBOARD
    path(
        '',
        views.dashboard,
        name='dashboard'
    ),

    # USUARIOS
    path('usuarios/', include('usuarios.urls')),

    # REFUGIOS
    path('refugios/', include('refugios.urls')),

    # DONACIONES
    path('donaciones/', include('donaciones.urls')),

    # CONSEJOS
    path('consejos/', include('consejos.urls')),

    # SOPORTE
    path('soporte/', include('soporte.urls')),

    # REPORTES
    path('reportes/', include('reportes.urls')),

]