from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('inicio.urls')),
    path('', include('usuarios.urls')),
    path('', include('cliente.urls')),
    path('admin/', admin.site.urls),
    path('panel/', include('panel_admin.urls')),
    path('panel/seguimientos/', include('gestion_seguimientos.urls')),
    path('', include('donaciones.public_urls')),
    path('seguimientos/', include('seguimientos.urls')),
    path('mensajes_soporte/', include('mensajes_soporte.urls')),
    path('mapa/', include('mapa.urls')),
    
    
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )