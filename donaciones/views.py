from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def gestion_donaciones(request):

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "estado":
            id_donacion = request.POST.get("id_donacion")
            nuevo_estado = request.POST.get("nuevo_estado")

            if nuevo_estado not in [
                "pendiente", "confirmada", "cancelada"
            ]:
                messages.error(request, "El estado seleccionado no es válido.")
                return redirect("gestion_donaciones")

            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE donaciones
                        SET estado = %s
                        WHERE id_donacion = %s
                    """, [nuevo_estado, id_donacion])

                    if cursor.rowcount == 0:
                        cursor.execute("""
                            SELECT id_donacion
                            FROM donaciones
                            WHERE id_donacion = %s
                        """, [id_donacion])

                        if not cursor.fetchone():
                            messages.error(request, "La donación no existe.")
                            return redirect("gestion_donaciones")

                messages.success(
                    request,
                    "Estado de la donación actualizado correctamente."
                )

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo actualizar la donación: {error}"
                )

            return redirect("gestion_donaciones")

    buscar = request.GET.get("buscar", "").strip()
    filtro_estado = request.GET.get("estado", "").strip()

    consulta = """
        SELECT
            d.id_donacion,
            d.monto,
            d.mensaje,
            d.fecha_donacion,
            d.estado,
            d.cliente_id,
            d.refugio_id,

            CONCAT_WS(' ',
                NULLIF(p.primer_nombre, ''),
                NULLIF(p.segundo_nombre, ''),
                NULLIF(p.primer_apellido, ''),
                NULLIF(p.segundo_apellido, '')
            ) AS donante,

            p.email AS email_donante,
            r.nombre AS refugio

        FROM donaciones d

        INNER JOIN cliente c
            ON c.id_cliente = d.cliente_id

        INNER JOIN personas p
            ON p.id_persona = c.persona_id

        LEFT JOIN refugios r
            ON r.id_refugio = d.refugio_id

        WHERE 1 = 1
    """

    parametros = []

    if buscar:
        consulta += """
            AND (
                p.primer_nombre LIKE %s
                OR p.primer_apellido LIKE %s
                OR p.email LIKE %s
                OR r.nombre LIKE %s
                OR CAST(d.id_donacion AS CHAR) LIKE %s
            )
        """
        valor = f"%{buscar}%"
        parametros.extend([valor] * 5)

    if filtro_estado in ["pendiente", "confirmada", "cancelada"]:
        consulta += " AND d.estado = %s"
        parametros.append(filtro_estado)

    consulta += " ORDER BY d.fecha_donacion DESC"

    with connection.cursor() as cursor:
        cursor.execute(consulta, parametros)

        columnas = [col[0] for col in cursor.description]
        donaciones = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(estado = 'pendiente'), 0),
                COALESCE(SUM(estado = 'confirmada'), 0),
                COALESCE(SUM(estado = 'cancelada'), 0),
                COALESCE(
                    SUM(
                        CASE
                            WHEN estado = 'confirmada' THEN monto
                            ELSE 0
                        END
                    ), 0
                )
            FROM donaciones
        """)

        resultado = cursor.fetchone()

    estadisticas = {
        "total": resultado[0] or 0,
        "pendientes": resultado[1] or 0,
        "confirmadas": resultado[2] or 0,
        "canceladas": resultado[3] or 0,
        "dinero_confirmado": resultado[4] or 0,
    }

    contexto = {
        "donaciones": donaciones,
        "estadisticas": estadisticas,
        "buscar": buscar,
        "filtro_estado": filtro_estado,
    }

    return render(
        request,
        "donaciones/gestion_donaciones.html",
        contexto
    )

