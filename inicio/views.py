
from django.shortcuts import render
from django.db import connection


def pagina_principal(request):
    buscar_refugio = request.GET.get("buscar_refugio", "").strip()
    buscar_consejo = request.GET.get("buscar_consejo", "").strip()

    

    # Consultar refugios activos.
    consulta_refugios = """
        SELECT
            r.id_refugio,
            r.nombre,
            r.descripcion,
            r.direccion,
            r.telefono,
            r.email,
            l.n_localidad AS localidad
        FROM refugios r
        INNER JOIN localidades l
            ON l.id_localidad = r.localidad_id
        WHERE r.estado = 'activo'
    """

    parametros_refugios = []

    if buscar_refugio:
        consulta_refugios += """
            AND (
                r.nombre LIKE %s
                OR r.descripcion LIKE %s
                OR r.direccion LIKE %s
                OR l.n_localidad LIKE %s
            )
        """
        valor = f"%{buscar_refugio}%"
        parametros_refugios.extend([valor] * 4)

    consulta_refugios += " ORDER BY r.id_refugio DESC LIMIT 12"

    # Consultar consejos publicados.
    consulta_consejos = """
        SELECT id, titulo, descripcion, created_at
        FROM consejos
        WHERE 1 = 1
    """

    parametros_consejos = []

    if buscar_consejo:
        consulta_consejos += """
            AND (titulo LIKE %s OR descripcion LIKE %s)
        """
        valor = f"%{buscar_consejo}%"
        parametros_consejos.extend([valor, valor])

    consulta_consejos += " ORDER BY created_at DESC LIMIT 6"

    with connection.cursor() as cursor:

        cursor.execute(consulta_refugios, parametros_refugios)
        columnas = [col[0] for col in cursor.description]
        refugios = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute(consulta_consejos, parametros_consejos)
        columnas = [col[0] for col in cursor.description]
        consejos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        mensaje_donacion = request.session.pop("mensaje_donacion", "")
        tipo_mensaje = request.session.pop("tipo_mensaje", "")

    return render(request, "inicio/pagina_principal.html", {
        "refugios": refugios,
        "consejos": consejos,
        "buscar_refugio": buscar_refugio,
        "buscar_consejo": buscar_consejo,
        "mensaje_donacion": mensaje_donacion,
        "tipo_mensaje": tipo_mensaje,
    })
