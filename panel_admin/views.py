
from datetime import date

from django.shortcuts import render
from django.db import connection


def dashboard(request):

    hoy = date.today()

    # Preparar los últimos seis meses, incluyendo el mes actual.
    meses = []
    anio = hoy.year
    mes = hoy.month

    for _ in range(6):
        meses.append((anio, mes))
        mes -= 1

        if mes == 0:
            mes = 12
            anio -= 1

    meses.reverse()

    primer_anio, primer_mes = meses[0]
    ultimo_anio, ultimo_mes = meses[-1]

    fecha_inicio = date(primer_anio, primer_mes, 1)

    if ultimo_mes == 12:
        fecha_fin = date(ultimo_anio + 1, 1, 1)
    else:
        fecha_fin = date(ultimo_anio, ultimo_mes + 1, 1)

    nombres_meses = [
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"
    ]

    actividad = {
        "usuarios": {clave: 0 for clave in meses},
        "refugios": {clave: 0 for clave in meses},
        "donaciones": {clave: 0 for clave in meses},
        "soporte": {clave: 0 for clave in meses},
    }

    with connection.cursor() as cursor:

        # TOTALES GENERALES
        cursor.execute("SELECT COUNT(*) FROM personas")
        total_usuarios = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM refugios")
        total_refugios = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM donaciones")
        total_donaciones = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM mensajes_de_soporte")
        total_soporte = cursor.fetchone()[0] or 0

        # ACTIVIDAD MENSUAL: PERSONAS
        cursor.execute("""
            SELECT YEAR(created_at), MONTH(created_at), COUNT(*)
            FROM personas
            WHERE created_at >= %s AND created_at < %s
            GROUP BY YEAR(created_at), MONTH(created_at)
        """, [fecha_inicio, fecha_fin])

        for anio_registro, mes_registro, cantidad in cursor.fetchall():
            clave = (anio_registro, mes_registro)
            if clave in actividad["usuarios"]:
                actividad["usuarios"][clave] = cantidad

        # ACTIVIDAD MENSUAL: REFUGIOS
        cursor.execute("""
            SELECT YEAR(created_at), MONTH(created_at), COUNT(*)
            FROM refugios
            WHERE created_at >= %s AND created_at < %s
            GROUP BY YEAR(created_at), MONTH(created_at)
        """, [fecha_inicio, fecha_fin])

        for anio_registro, mes_registro, cantidad in cursor.fetchall():
            clave = (anio_registro, mes_registro)
            if clave in actividad["refugios"]:
                actividad["refugios"][clave] = cantidad

        # ACTIVIDAD MENSUAL: DONACIONES
        cursor.execute("""
            SELECT YEAR(fecha_donacion), MONTH(fecha_donacion), COUNT(*)
            FROM donaciones
            WHERE fecha_donacion >= %s AND fecha_donacion < %s
            GROUP BY YEAR(fecha_donacion), MONTH(fecha_donacion)
        """, [fecha_inicio, fecha_fin])

        for anio_registro, mes_registro, cantidad in cursor.fetchall():
            clave = (anio_registro, mes_registro)
            if clave in actividad["donaciones"]:
                actividad["donaciones"][clave] = cantidad

        # ACTIVIDAD MENSUAL: SOPORTE
        cursor.execute("""
            SELECT YEAR(fecha_mensaje), MONTH(fecha_mensaje), COUNT(*)
            FROM mensajes_de_soporte
            WHERE fecha_mensaje >= %s AND fecha_mensaje < %s
            GROUP BY YEAR(fecha_mensaje), MONTH(fecha_mensaje)
        """, [fecha_inicio, fecha_fin])

        for anio_registro, mes_registro, cantidad in cursor.fetchall():
            clave = (anio_registro, mes_registro)
            if clave in actividad["soporte"]:
                actividad["soporte"][clave] = cantidad

    contexto = {
        "total_usuarios": total_usuarios,
        "total_refugios": total_refugios,
        "total_donaciones": total_donaciones,
        "total_soporte": total_soporte,

        "actividad_labels": [
            f"{nombres_meses[mes - 1]} {str(anio)[-2:]}"
            for anio, mes in meses
        ],

        "actividad_usuarios": [
            actividad["usuarios"][(anio, mes)]
            for anio, mes in meses
        ],

        "actividad_refugios": [
            actividad["refugios"][(anio, mes)]
            for anio, mes in meses
        ],

        "actividad_donaciones": [
            actividad["donaciones"][(anio, mes)]
            for anio, mes in meses
        ],

        "actividad_soporte": [
            actividad["soporte"][(anio, mes)]
            for anio, mes in meses
        ],

        "distribucion_modulos": [
            total_usuarios,
            total_refugios,
            total_donaciones,
            total_soporte,
        ],
    }

    return render(
        request,
        "panel_admin/dashboard.html",
        contexto
    )
