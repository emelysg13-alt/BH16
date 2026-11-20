
from django.shortcuts import render
from django.db import connection


def dashboard(request):
    # Consultar el total de usuarios registrados
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM personas
        """)
        total_usuarios = cursor.fetchone()[0]

    contexto = {
        'total_usuarios': total_usuarios,
    }

    return render(
        request,
        'panel_admin/dashboard.html',
        contexto
    )
