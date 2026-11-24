
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

        # CREAR REFUGIO
        if accion == "crear":

            if not all([nombre, direccion, localidad_id]):
                messages.error(request, "Completa los campos obligatorios.")
                return redirect("gestion_refugios")

            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO refugios
                        (
                            nombre, descripcion, direccion,
                            telefono, email, localidad_id, estado
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'activo')
                    """, [
                        nombre,
                        descripcion or None,
                        direccion,
                        telefono or None,
                        email or None,
                        localidad_id
                    ])

                messages.success(request, "Refugio registrado correctamente.")

            except Exception as error:
                messages.error(request, f"No se pudo registrar el refugio: {error}")

            return redirect("gestion_refugios")

        # EDITAR REFUGIO
        if accion == "editar":

            id_refugio = request.POST.get("id_refugio")
            nuevo_estado = request.POST.get("estado", "").strip()

            if not all([id_refugio, nombre, direccion, localidad_id]):
                messages.error(request, "Completa los campos obligatorios.")
                return redirect("gestion_refugios")

            if nuevo_estado not in ["activo", "inactivo"]:
                messages.error(request, "El estado seleccionado no es válido.")
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
                            localidad_id = %s,
                            estado = %s
                        WHERE id_refugio = %s
                    """, [
                        nombre,
                        descripcion or None,
                        direccion,
                        telefono or None,
                        email or None,
                        localidad_id,
                        nuevo_estado,
                        id_refugio
                    ])

                    if cursor.rowcount == 0:
                        messages.error(request, "No se encontró el refugio.")
                    else:
                        messages.success(request, "Refugio actualizado correctamente.")

            except Exception as error:
                messages.error(request, f"No se pudo actualizar el refugio: {error}")

            return redirect("gestion_refugios")

        # ACTIVAR / DESACTIVAR REFUGIO
        if accion == "estado":

            id_refugio = request.POST.get("id_refugio")
            nuevo_estado = (
                request.POST.get("nuevo_estado")
                or request.POST.get("estado")
            )

            if not id_refugio:
                messages.error(request, "No se recibió el ID del refugio.")
                return redirect("gestion_refugios")

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

                    if cursor.rowcount == 0:
                        messages.error(request, "No se encontró el refugio.")
                    else:
                        messages.success(
                            request,
                            f"El refugio ahora está {nuevo_estado}."
                        )

            except Exception as error:
                messages.error(request, f"No se pudo cambiar el estado: {error}")

            return redirect("gestion_refugios")

        messages.error(request, "La acción solicitada no es válida.")
        return redirect("gestion_refugios")

    # CONSULTAR REFUGIOS
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
            r.created_at,

            (
                SELECT COUNT(*)
                FROM ingresos_refugio ir
                WHERE ir.refugio_id = r.id_refugio
            ) AS total_ingresos,

            (
                SELECT COUNT(*)
                FROM ingresos_refugio ir
                WHERE ir.refugio_id = r.id_refugio
                AND ir.estado = 'confirmado'
            ) AS ingresos_confirmados

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

        # LOCALIDADES
        cursor.execute("""
            SELECT id_localidad, n_localidad
            FROM localidades
            ORDER BY n_localidad
        """)

        localidades = cursor.fetchall()

        # ESTADÍSTICAS
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


# ELIMINAR REFUGIO
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


# CONSULTAR ANIMALES E HISTORIAL DE UN REFUGIO
@require_http_methods(["GET"])
def animales_refugio(request, id_refugio):

    buscar = request.GET.get("buscar", "").strip()
    filtro_estado = request.GET.get("estado", "").strip()

    with connection.cursor() as cursor:

        # DATOS DEL REFUGIO
        cursor.execute("""
            SELECT id_refugio, nombre, direccion
            FROM refugios
            WHERE id_refugio = %s
        """, [id_refugio])

        refugio_fila = cursor.fetchone()

        if not refugio_fila:
            messages.error(request, "No se encontró el refugio solicitado.")
            return redirect("gestion_refugios")

        refugio = {
            "id_refugio": refugio_fila[0],
            "nombre": refugio_fila[1],
            "direccion": refugio_fila[2]
        }

        # CONSULTAR INGRESOS Y ANIMALES
        consulta = """
            SELECT
                ir.id_ingreso,
                ir.fecha_ingreso,
                ir.observacion,
                ir.estado,

                a.id_animal,
                a.nombre AS nombre_animal,
                a.sexo,
                a.color,
                a.tamano,
                a.descripcion,

                COALESCE(
                    ad.especie,
                    ae.especie,
                    'No especificada'
                ) AS especie,

                COALESCE(
                    ad.raza,
                    'No especificada'
                ) AS raza

            FROM ingresos_refugio ir

            INNER JOIN animal a
                ON a.id_animal = ir.animal_id

            LEFT JOIN animal_domestico ad
                ON ad.animal_id = a.id_animal

            LEFT JOIN animal_exotico ae
                ON ae.animal_id = a.id_animal

            WHERE ir.refugio_id = %s
        """

        parametros = [id_refugio]

        if buscar:
            consulta += """
                AND (
                    a.nombre LIKE %s
                    OR a.color LIKE %s
                    OR COALESCE(ad.especie, ae.especie, '') LIKE %s
                    OR COALESCE(ad.raza, '') LIKE %s
                )
            """

            valor = f"%{buscar}%"
            parametros.extend([valor, valor, valor, valor])

        if filtro_estado in ["pendiente", "confirmado", "rechazado"]:
            consulta += " AND ir.estado = %s"
            parametros.append(filtro_estado)

        consulta += """
            ORDER BY ir.fecha_ingreso DESC, ir.id_ingreso DESC
        """

        cursor.execute(consulta, parametros)

        columnas = [col[0] for col in cursor.description]

        ingresos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        # HISTORIAL DE MOVIMIENTOS
        cursor.execute("""
            SELECT
                h.id_historial_refugio,
                h.fecha_cambio,
                h.estado_anterior,
                h.estado_nuevo,
                h.observacion,
                ir.id_ingreso,
                a.nombre AS nombre_animal,
                a.id_animal

            FROM historial_refugio h

            INNER JOIN ingresos_refugio ir
                ON ir.id_ingreso = h.ingreso_id

            INNER JOIN animal a
                ON a.id_animal = ir.animal_id

            WHERE ir.refugio_id = %s

            ORDER BY
                h.fecha_cambio DESC,
                h.id_historial_refugio DESC
        """, [id_refugio])

        columnas_historial = [
            col[0] for col in cursor.description
        ]

        historial = [
            dict(zip(columnas_historial, fila))
            for fila in cursor.fetchall()
        ]

        # RESUMEN
        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(estado = 'confirmado'), 0),
                COALESCE(SUM(estado = 'pendiente'), 0),
                COALESCE(SUM(estado = 'rechazado'), 0)

            FROM ingresos_refugio
            WHERE refugio_id = %s
        """, [id_refugio])

        resumen = cursor.fetchone()

    contexto = {
        "refugio": refugio,
        "ingresos": ingresos,
        "historial": historial,
        "buscar": buscar,
        "filtro_estado": filtro_estado,

        "resumen": {
            "total": resumen[0] or 0,
            "confirmados": resumen[1] or 0,
            "pendientes": resumen[2] or 0,
            "rechazados": resumen[3] or 0,
        },
    }

    return render(
        request,
        "refugios/animales_refugio.html",
        contexto
    )
