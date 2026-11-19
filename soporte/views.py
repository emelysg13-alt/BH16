from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.contrib import messages
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def gestion_soporte(request):

    # ELIMINAR MENSAJE
    if request.method == "POST":

        accion = request.POST.get("accion", "").strip()

        if accion == "eliminar":

            id_mensaje = request.POST.get("id_mensaje")

            if not id_mensaje:
                messages.error(
                    request,
                    "No se recibió el mensaje que deseas eliminar."
                )
                return redirect("gestion_soporte")

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            DELETE FROM mensajes_de_soporte
                            WHERE id_mensaje = %s
                        """, [id_mensaje])

                        eliminado = cursor.rowcount

                if eliminado:
                    messages.success(
                        request,
                        "El mensaje se eliminó correctamente."
                    )
                else:
                    messages.error(
                        request,
                        "El mensaje que intentas eliminar no existe."
                    )

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo eliminar el mensaje: {error}"
                )

            return redirect("gestion_soporte")

    # BUSCADOR DE MENSAJES
    buscar = request.GET.get("buscar", "").strip()

    consulta = """
        SELECT
            ms.id_mensaje,
            ms.mensaje_cliente,
            ms.fecha_mensaje,
            c.id_cliente,

            CONCAT_WS(' ',
                NULLIF(p.primer_nombre, ''),
                NULLIF(p.segundo_nombre, ''),
                NULLIF(p.primer_apellido, ''),
                NULLIF(p.segundo_apellido, '')
            ) AS nombre_cliente,

            p.email AS email_cliente,
            p.numero_tel AS telefono_cliente

        FROM mensajes_de_soporte ms

        INNER JOIN cliente c
            ON c.id_cliente = ms.cliente_id

        INNER JOIN personas p
            ON p.id_persona = c.persona_id

        WHERE 1 = 1
    """

    parametros = []

    if buscar:
        consulta += """
            AND (
                p.primer_nombre LIKE %s
                OR p.segundo_nombre LIKE %s
                OR p.primer_apellido LIKE %s
                OR p.segundo_apellido LIKE %s
                OR p.email LIKE %s
                OR p.numero_tel LIKE %s
                OR ms.mensaje_cliente LIKE %s
                OR CAST(ms.id_mensaje AS CHAR) LIKE %s
            )
        """

        valor = f"%{buscar}%"
        parametros.extend([valor] * 8)

    consulta += " ORDER BY ms.fecha_mensaje DESC"

    with connection.cursor() as cursor:

        cursor.execute(consulta, parametros)

        columnas = [columna[0] for columna in cursor.description]

        solicitudes = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(
                    SUM(DATE(fecha_mensaje) = CURDATE()),
                    0
                )
            FROM mensajes_de_soporte
        """)

        resultado = cursor.fetchone()

    estadisticas = {
        "total": resultado[0] or 0,
        "hoy": resultado[1] or 0,
    }

    contexto = {
        "solicitudes": solicitudes,
        "buscar": buscar,
        "estadisticas": estadisticas,
    }

    return render(
        request,
        "soporte/gestion_soporte.html",
        contexto
    )