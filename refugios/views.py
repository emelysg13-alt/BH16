from django.shortcuts import render, redirect
from django.db import connection, transaction, IntegrityError
from django.contrib import messages
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def gestion_refugios(request):

    if request.method == "POST":
        accion = request.POST.get("accion")

        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        email = request.POST.get("email", "").strip()
        localidad_id = request.POST.get("localidad_id", "").strip()

        if accion == "crear":
            if not all([nombre, direccion, localidad_id]):
                messages.error(request, "Completa los campos obligatorios.")
                return redirect("gestion_refugios")

            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO refugios
                        (nombre, descripcion, direccion, telefono, email,
                         localidad_id, estado)
                        VALUES (%s, %s, %s, %s, %s, %s, 'activo')
                    """, [
                        nombre, descripcion or None, direccion,
                        telefono or None, email or None, localidad_id
                    ])

                messages.success(request, "Refugio registrado correctamente.")

            except Exception as error:
                messages.error(request, f"No se pudo registrar el refugio: {error}")

            return redirect("gestion_refugios")

        if accion == "editar":
            id_refugio = request.POST.get("id_refugio")

            if not all([id_refugio, nombre, direccion, localidad_id]):
                messages.error(request, "Completa los campos obligatorios.")
                return redirect("gestion_refugios")

            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE refugios
                        SET nombre = %s,
                            descripcion = %s,
                            direccion = %s,
                            telefono = %s,
                            email = %s,
                            localidad_id = %s
                        WHERE id_refugio = %s
                    """, [
                        nombre, descripcion or None, direccion,
                        telefono or None, email or None,
                        localidad_id, id_refugio
                    ])

                messages.success(request, "Refugio actualizado correctamente.")

            except Exception as error:
                messages.error(request, f"No se pudo actualizar: {error}")

            return redirect("gestion_refugios")

        if accion == "estado":
            id_refugio = request.POST.get("id_refugio")
            nuevo_estado = request.POST.get("nuevo_estado")

            if nuevo_estado not in ["activo", "inactivo"]:
                messages.error(request, "Estado no válido.")
                return redirect("gestion_refugios")

            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE refugios
                        SET estado = %s
                        WHERE id_refugio = %s
                    """, [nuevo_estado, id_refugio])

                messages.success(request, "Estado del refugio actualizado.")

            except Exception as error:
                messages.error(request, f"No se pudo cambiar el estado: {error}")

            return redirect("gestion_refugios")

    buscar = request.GET.get("buscar", "").strip()
    filtro_estado = request.GET.get("estado", "").strip()

    consulta = """
        SELECT
            r.id_refugio,
            r.nombre,
            r.descripcion,
            r.direccion,
            r.telefono,
            r.email,
            r.localidad_id,
            l.n_localidad AS localidad,
            r.estado,
            r.created_at
        FROM refugios r
        INNER JOIN localidades l
            ON l.id_localidad = r.localidad_id
        WHERE 1 = 1
    """

    parametros = []

    if buscar:
        consulta += """
            AND (
                r.nombre LIKE %s
                OR r.direccion LIKE %s
                OR r.email LIKE %s
                OR l.n_localidad LIKE %s
            )
        """
        valor = f"%{buscar}%"
        parametros.extend([valor] * 4)

    if filtro_estado in ["activo", "inactivo"]:
        consulta += " AND r.estado = %s"
        parametros.append(filtro_estado)

    consulta += " ORDER BY r.id_refugio DESC"

    with connection.cursor() as cursor:
        cursor.execute(consulta, parametros)
        columnas = [col[0] for col in cursor.description]
        refugios = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT id_localidad, n_localidad
            FROM localidades
            ORDER BY n_localidad
        """)
        localidades = cursor.fetchall()

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(estado = 'activo'), 0),
                COALESCE(SUM(estado = 'inactivo'), 0)
            FROM refugios
        """)
        estadisticas = cursor.fetchone()

    contexto = {
        "refugios": refugios,
        "localidades": localidades,
        "buscar": buscar,
        "filtro_estado": filtro_estado,
        "estadisticas": {
            "total": estadisticas[0] or 0,
            "activos": estadisticas[1] or 0,
            "inactivos": estadisticas[2] or 0,
        }
    }

    return render(
        request,
        "refugios/gestion_refugios.html",
        contexto
    )


@require_http_methods(["POST"])
def eliminar_refugio(request, id_refugio):

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:

                cursor.execute("""
                    DELETE FROM refugios
                    WHERE id_refugio = %s
                """, [id_refugio])

                if cursor.rowcount == 0:
                    messages.error(request, "El refugio no existe.")
                    return redirect("gestion_refugios")

        messages.success(request, "Refugio eliminado correctamente.")

    except IntegrityError:
        messages.error(
            request,
            "No se puede eliminar este refugio porque tiene registros relacionados."
        )

    except Exception as error:
        messages.error(request, f"No se pudo eliminar: {error}")

    return redirect("gestion_refugios")