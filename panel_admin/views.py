
from django.shortcuts import render
from django.db import connection


def dashboard(request):

    with connection.cursor() as cursor:

        # TOTAL DE USUARIOS
        cursor.execute("""
            SELECT COUNT(*)
            FROM personas
        """)
        total_usuarios = cursor.fetchone()[0] or 0

        # TOTAL DE REFUGIOS
        cursor.execute("""
            SELECT COUNT(*)
            FROM refugios
        """)
        total_refugios = cursor.fetchone()[0] or 0

        # TOTAL DE DONACIONES
        cursor.execute("""
            SELECT COUNT(*)
            FROM donaciones
        """)
        total_donaciones = cursor.fetchone()[0] or 0

        # TOTAL DE SOLICITUDES DE SOPORTE
        cursor.execute("""
            SELECT COUNT(*)
            FROM mensajes_de_soporte
        """)
        total_soporte = cursor.fetchone()[0] or 0

    contexto = {
        'total_usuarios': total_usuarios,
        'total_refugios': total_refugios,
        'total_donaciones': total_donaciones,
        'total_soporte': total_soporte,
    }

    return render(
        request,
        'panel_admin/dashboard.html',
        contexto
    )
