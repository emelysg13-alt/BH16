from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.db import transaction
from django.shortcuts import render
from django.db import connection


def gestion_seguimientos(request):

    buscar = request.GET.get('buscar', '').strip()
    filtro_estado = request.GET.get('estado', '').strip()

    # ESTADÍSTICAS GENERALES

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) AS total,

                SUM(CASE
                    WHEN estado_moderacion = 'pendiente'
                    THEN 1 ELSE 0
                END) AS pendientes,

                SUM(CASE
                    WHEN estado_moderacion = 'aprobado'
                    THEN 1 ELSE 0
                END) AS aprobados,

                SUM(CASE
                    WHEN estado_moderacion = 'rechazado'
                    THEN 1 ELSE 0
                END) AS rechazados

            FROM seguimiento
        """)

        columnas = [columna[0] for columna in cursor.description]
        estadisticas = dict(zip(columnas, cursor.fetchone()))

    # CONSULTA DE SEGUIMIENTOS

    consulta = """
        SELECT
            s.id_seguimiento,
            s.titulo,
            s.estado_seguimiento,
            s.estado_moderacion,
            s.fecha_publicacion,

            a.nombre AS nombre_animal,

            COALESCE(ad.especie, ae.especie) AS especie,

            l.n_localidad,

            CASE
                WHEN sp.seguimiento_id IS NOT NULL THEN 'Perdido'
                WHEN se.seguimiento_id IS NOT NULL THEN 'Encontrado'
                ELSE 'No especificado'
            END AS tipo_reporte

        FROM seguimiento s

        INNER JOIN animal a
            ON s.animal_id = a.id_animal

        LEFT JOIN animal_domestico ad
            ON a.id_animal = ad.animal_id

        LEFT JOIN animal_exotico ae
            ON a.id_animal = ae.animal_id

        INNER JOIN lugares lu
            ON s.lugar_id = lu.id_lugar

        INNER JOIN localidades l
            ON lu.localidad_id = l.id_localidad

        LEFT JOIN seguimiento_perdido sp
            ON s.id_seguimiento = sp.seguimiento_id

        LEFT JOIN seguimiento_encontrado se
            ON s.id_seguimiento = se.seguimiento_id

        WHERE 1 = 1
    """

    parametros = []

    # FILTRO POR ESTADO DE MODERACIÓN

    estados_validos = ['pendiente', 'aprobado', 'rechazado']

    if filtro_estado in estados_validos:
        consulta += """
            AND s.estado_moderacion = %s
        """
        parametros.append(filtro_estado)
    else:
        filtro_estado = ''

    # BÚSQUEDA

    if buscar:
        consulta += """
            AND (
                CAST(s.id_seguimiento AS CHAR) LIKE %s
                OR s.titulo LIKE %s
                OR a.nombre LIKE %s
                OR ad.especie LIKE %s
                OR ae.especie LIKE %s
                OR l.n_localidad LIKE %s
            )
        """

        termino = f'%{buscar}%'
        parametros.extend([termino] * 6)

    consulta += """
        ORDER BY s.fecha_publicacion DESC
    """

    # EJECUTAR CONSULTA

    with connection.cursor() as cursor:
        cursor.execute(consulta, parametros)

        columnas = [columna[0] for columna in cursor.description]

        seguimientos = [
            dict(zip(columnas, fila))

            for fila in cursor.fetchall()
        ]

    return render(
        request,
        'gestion_seguimientos/lista.html',
        {
            'seguimientos': seguimientos,
            'estadisticas': estadisticas,
            'buscar': buscar,
            'filtro_estado': filtro_estado,
        }
    )





def detalle_seguimiento(request, id_seguimiento):

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                s.id_seguimiento,
                s.titulo,
                s.descripcion,
                s.fecha_publicacion,
                s.estado_seguimiento,
                s.estado_moderacion,

                a.nombre AS nombre_animal,
                a.sexo,
                a.color,
                a.tamano,
                a.descripcion AS descripcion_animal,

                COALESCE(ad.especie, ae.especie) AS especie,
                ad.raza,

                lu.direccion,
                l.n_localidad,

                sp.fecha_perdida,
                sp.ultima_fecha_visto,
                sp.descripcion_ultima_ubicacion,

                se.fecha_encontrado,
                se.descripcion_lugar_encontrado,
                se.necesita_refugio,
                r.nombre AS nombre_refugio,
                r.direccion AS direccion_refugio,

                ir.id_ingreso,
                ir.fecha_ingreso,
                ir.estado AS estado_ingreso,
                ir.observacion AS observacion_ingreso,
                ir.fecha_verificacion,

                ri.nombre AS nombre_refugio_ingreso,
                ri.direccion AS direccion_refugio_ingreso,
                li.n_localidad AS localidad_refugio_ingreso

            FROM seguimiento s

            INNER JOIN animal a
                ON s.animal_id = a.id_animal

            LEFT JOIN animal_domestico ad
                ON a.id_animal = ad.animal_id

            LEFT JOIN animal_exotico ae
                ON a.id_animal = ae.animal_id

            INNER JOIN lugares lu
                ON s.lugar_id = lu.id_lugar

            INNER JOIN localidades l
                ON lu.localidad_id = l.id_localidad

            LEFT JOIN seguimiento_perdido sp
                ON s.id_seguimiento = sp.seguimiento_id

            LEFT JOIN seguimiento_encontrado se
                ON s.id_seguimiento = se.seguimiento_id

            LEFT JOIN refugios r
                ON se.refugio_id = r.id_refugio

            LEFT JOIN ingresos_refugio ir
                ON ir.id_ingreso = (
                    SELECT MAX(ir2.id_ingreso)
                    FROM ingresos_refugio ir2
                    WHERE ir2.seguimiento_id = s.id_seguimiento
                    AND ir2.animal_id = a.id_animal
                )

            LEFT JOIN refugios ri
                ON ir.refugio_id = ri.id_refugio

            LEFT JOIN localidades li
                ON ri.localidad_id = li.id_localidad

            WHERE s.id_seguimiento = %s
        """, [id_seguimiento])

        columnas = [
            columna[0] for columna in cursor.description
        ]

        fila = cursor.fetchone()

        if fila:
            seguimiento = dict(zip(columnas, fila))
        else:
            seguimiento = None

    if seguimiento is None:
        raise Http404("El seguimiento no existe.")

    return render(
        request,
        'gestion_seguimientos/detalle.html',
        {'seguimiento': seguimiento}
    )



@require_POST
def aprobar_seguimiento(request, id_seguimiento):

    persona_id = request.session.get('backhome_user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_admin
            FROM administrador
            WHERE persona_id = %s
        """, [persona_id])

        administrador = cursor.fetchone()

    if not administrador:
        return HttpResponseForbidden("No se encontró el administrador.")

    administrador_id = administrador[0]

    with transaction.atomic():
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    s.estado_moderacion,
                    COALESCE(se.necesita_refugio, 0),
                    se.refugio_id,

                    EXISTS (
                        SELECT 1
                        FROM ingresos_refugio ir
                        WHERE ir.seguimiento_id = s.id_seguimiento
                        AND ir.estado = 'confirmado'
                        AND (
                            se.refugio_id IS NULL
                            OR ir.refugio_id = se.refugio_id
                        )
                    ) AS ingreso_confirmado

                FROM seguimiento s

                LEFT JOIN seguimiento_encontrado se
                    ON se.seguimiento_id = s.id_seguimiento

                WHERE s.id_seguimiento = %s
            """, [id_seguimiento])

            resultado = cursor.fetchone()

            if not resultado:
                raise Http404("El seguimiento no existe.")

            estado_moderacion = resultado[0]
            necesita_refugio = resultado[1]
            refugio_id = resultado[2]
            ingreso_confirmado = resultado[3]

            if estado_moderacion != 'pendiente':
                messages.warning(
                    request,
                    "Este reporte ya fue moderado."
                )
                return redirect(
                    'admin_detalle_seguimiento',
                    id_seguimiento=id_seguimiento
                )

            # Validar el ingreso al refugio
            if (necesita_refugio or refugio_id is not None) and not ingreso_confirmado:
                messages.error(
                    request,
                    "No se puede aprobar este seguimiento porque "
                    "el ingreso al refugio no ha sido confirmado."
                )
                return redirect(
                    'admin_detalle_seguimiento',
                    id_seguimiento=id_seguimiento
                )

            cursor.execute("""
                UPDATE seguimiento
                SET estado_moderacion = 'aprobado'
                WHERE id_seguimiento = %s
            """, [id_seguimiento])

            cursor.execute("""
                INSERT INTO gestion_seguimiento (
                    seguimiento_id,
                    fecha_seguimiento,
                    accion,
                    observacion,
                    administrador_id
                )
                VALUES (%s, NOW(), %s, %s, %s)
            """, [
                id_seguimiento,
                'Aprobación',
                'Reporte aprobado por el administrador.',
                administrador_id
            ])

    messages.success(
        request,
        "El reporte fue aprobado correctamente."
    )

    return redirect(
        'admin_detalle_seguimiento',
        id_seguimiento=id_seguimiento
    )


@require_POST
def rechazar_seguimiento(request, id_seguimiento):

    motivo = request.POST.get('motivo', '').strip()

    if not motivo:
        messages.error(request, "Debes escribir el motivo del rechazo.")
        return redirect(
            'detalle_seguimiento',
            id_seguimiento=id_seguimiento
        )

    persona_id = request.session.get('backhome_user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_admin
            FROM administrador
            WHERE persona_id = %s
        """, [persona_id])

        administrador = cursor.fetchone()

    if not administrador:
        return HttpResponseForbidden("No se encontró el administrador.")

    administrador_id = administrador[0]

    with transaction.atomic():
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT estado_moderacion
                FROM seguimiento
                WHERE id_seguimiento = %s
            """, [id_seguimiento])

            resultado = cursor.fetchone()

            if not resultado:
                raise Http404("El seguimiento no existe.")

            if resultado[0] != 'pendiente':
                messages.warning(
                    request,
                    "Este reporte ya fue moderado."
                )
                return redirect(
                    'detalle_seguimiento',
                    id_seguimiento=id_seguimiento
                )

            cursor.execute("""
                UPDATE seguimiento
                SET estado_moderacion = 'rechazado'
                WHERE id_seguimiento = %s
            """, [id_seguimiento])

            cursor.execute("""
                INSERT INTO gestion_seguimiento (
                    seguimiento_id,
                    fecha_seguimiento,
                    accion,
                    observacion,
                    administrador_id
                )
                VALUES (%s, NOW(), %s, %s, %s)
            """, [
                id_seguimiento,
                'Rechazo',
                motivo,
                administrador_id
            ])

    messages.success(request, "El reporte fue rechazado correctamente.")

    return redirect(
        'admin_detalle_seguimiento',
        id_seguimiento=id_seguimiento
    )





def gestion_ingresos_refugio(request):

    consulta = """
        SELECT
            ir.id_ingreso,
            ir.fecha_ingreso,
            ir.estado,
            ir.observacion,
            ir.fecha_verificacion,

            a.nombre AS nombre_animal,
            COALESCE(ad.especie, ae.especie) AS especie,

            s.id_seguimiento,
            s.titulo AS titulo_reporte,

            r.nombre AS nombre_refugio,
            r.direccion AS direccion_refugio,

            l.n_localidad AS localidad_refugio

        FROM ingresos_refugio ir

        INNER JOIN animal a
            ON a.id_animal = ir.animal_id

        LEFT JOIN animal_domestico ad
            ON ad.animal_id = a.id_animal

        LEFT JOIN animal_exotico ae
            ON ae.animal_id = a.id_animal

        INNER JOIN seguimiento s
            ON s.id_seguimiento = ir.seguimiento_id

        INNER JOIN refugios r
            ON r.id_refugio = ir.refugio_id

        INNER JOIN localidades l
            ON l.id_localidad = r.localidad_id

        ORDER BY ir.fecha_ingreso DESC
    """

    with connection.cursor() as cursor:
        cursor.execute(consulta)

        columnas = [
            columna[0] for columna in cursor.description
        ]

        ingresos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

    return render(
        request,
        'gestion_seguimientos/ingresos_refugio.html',
        {'ingresos': ingresos}
    )





@require_POST
def confirmar_ingreso_refugio(request, id_ingreso):

    persona_id = request.session.get('backhome_user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_admin
            FROM administrador
            WHERE persona_id = %s
        """, [persona_id])

        administrador = cursor.fetchone()

    if not administrador:
        return HttpResponseForbidden("No se encontró el administrador.")

    administrador_id = administrador[0]

    with transaction.atomic():
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT seguimiento_id, estado
                FROM ingresos_refugio
                WHERE id_ingreso = %s
            """, [id_ingreso])

            ingreso = cursor.fetchone()

            if not ingreso:
                raise Http404("El ingreso no existe.")

            id_seguimiento, estado = ingreso

            if estado != 'pendiente':
                messages.warning(
                    request,
                    "Esta solicitud ya fue verificada."
                )
            else:
                cursor.execute("""
                    UPDATE ingresos_refugio
                    SET estado = 'confirmado',
                        administrador_id = %s,
                        fecha_verificacion = NOW()
                    WHERE id_ingreso = %s
                """, [administrador_id, id_ingreso])

                messages.success(
                    request,
                    "El ingreso al refugio fue confirmado."
                )

    return redirect(
        'admin_detalle_seguimiento',
        id_seguimiento=id_seguimiento
    )


@require_POST
def rechazar_ingreso_refugio(request, id_ingreso):

    persona_id = request.session.get('backhome_user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_admin
            FROM administrador
            WHERE persona_id = %s
        """, [persona_id])

        administrador = cursor.fetchone()

    if not administrador:
        return HttpResponseForbidden("No se encontró el administrador.")

    administrador_id = administrador[0]

    with transaction.atomic():
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT seguimiento_id, estado
                FROM ingresos_refugio
                WHERE id_ingreso = %s
            """, [id_ingreso])

            ingreso = cursor.fetchone()

            if not ingreso:
                raise Http404("El ingreso no existe.")

            id_seguimiento, estado = ingreso

            if estado != 'pendiente':
                messages.warning(
                    request,
                    "Esta solicitud ya fue verificada."
                )
            else:
                cursor.execute("""
                    UPDATE ingresos_refugio
                    SET estado = 'rechazado',
                        administrador_id = %s,
                        fecha_verificacion = NOW()
                    WHERE id_ingreso = %s
                """, [administrador_id, id_ingreso])

                messages.success(
                    request,
                    "El ingreso al refugio fue rechazado."
                )

    return redirect(
        'admin_detalle_seguimiento',
        id_seguimiento=id_seguimiento
    )
