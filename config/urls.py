from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('inicio.urls')),
    path('', include('usuarios.urls')),
    path('', include('cliente.urls')),
    path('admin/', admin.site.urls),
    path('panel/', include('panel_admin.urls')),
]