from django.shortcuts import render, redirect
from django.db import connection


def lista_seguimientos(request):

    consulta = """
        SELECT
            s.id_seguimiento,
            s.titulo,
            s.descripcion,
            s.fecha_publicacion,
            s.estado_seguimiento,

            a.nombre AS animal_nombre,
            a.sexo,
            a.color,
            a.tamano,

            COALESCE(ad.especie, ae.especie) AS especie,
            ad.raza,

            l.direccion,
            loc.n_localidad AS localidad,

            (
                SELECT i.ruta_imagen
                FROM imagenes_seguimiento i
                WHERE i.seguimiento_id = s.id_seguimiento
                ORDER BY i.imagen_principal DESC, i.id_imagen ASC
                LIMIT 1
            ) AS imagen_principal,

            (
                SELECT au.mensaje
                FROM actualizaciones_seguimiento au
                WHERE au.seguimiento_id = s.id_seguimiento
                ORDER BY au.created_at DESC, au.id_actualizacion DESC
                LIMIT 1
            ) AS ultima_actualizacion

        FROM seguimiento s

        INNER JOIN animal a
            ON a.id_animal = s.animal_id

        LEFT JOIN animal_domestico ad
            ON ad.animal_id = a.id_animal

        LEFT JOIN animal_exotico ae
            ON ae.animal_id = a.id_animal

        INNER JOIN lugares l
            ON l.id_lugar = s.lugar_id

        INNER JOIN localidades loc
            ON loc.id_localidad = l.localidad_id

        LEFT JOIN seguimiento_encontrado se
            ON se.seguimiento_id = s.id_seguimiento

        WHERE s.estado_moderacion = 'aprobado'

        AND (
            (
                COALESCE(se.necesita_refugio, 0) = 0
                AND se.refugio_id IS NULL
            )

            OR EXISTS (
                SELECT 1
                FROM ingresos_refugio ir
                WHERE ir.seguimiento_id = s.id_seguimiento
                AND ir.animal_id = s.animal_id
                AND ir.estado = 'confirmado'
                AND (
                    se.refugio_id IS NULL
                    OR ir.refugio_id = se.refugio_id
                )
            )
        )

        ORDER BY s.fecha_publicacion DESC
    """

    with connection.cursor() as cursor:
        cursor.execute(consulta)

        columnas = [columna[0] for columna in cursor.description]

        seguimientos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

    return render(
        request,
        'seguimientos/lista_seguimientos.html',
        {'seguimientos': seguimientos}
    )

def detalle_seguimiento(request, id_seguimiento):

    consulta = """
        SELECT
            s.id_seguimiento,
            s.titulo,
            s.descripcion,
            s.fecha_publicacion,
            s.estado_seguimiento,

            a.nombre AS animal_nombre,
            a.sexo,
            a.color,
            a.tamano,

            COALESCE(ad.especie, ae.especie) AS especie,
            ad.raza,

            l.direccion,
            loc.n_localidad AS localidad,

            sp.fecha_perdida,
            sp.ultima_fecha_visto,
            sp.descripcion_ultima_ubicacion,

            se.fecha_encontrado,
            se.descripcion_lugar_encontrado,
            se.necesita_refugio,

            r.nombre AS refugio_nombre,
            r.direccion AS refugio_direccion

        FROM seguimiento s

        INNER JOIN animal a
            ON a.id_animal = s.animal_id

        LEFT JOIN animal_domestico ad
            ON ad.animal_id = a.id_animal

        LEFT JOIN animal_exotico ae
            ON ae.animal_id = a.id_animal

        INNER JOIN lugares l
            ON l.id_lugar = s.lugar_id

        INNER JOIN localidades loc
            ON loc.id_localidad = l.localidad_id

        LEFT JOIN seguimiento_perdido sp
            ON sp.seguimiento_id = s.id_seguimiento

        LEFT JOIN seguimiento_encontrado se
            ON se.seguimiento_id = s.id_seguimiento

        LEFT JOIN refugios r
            ON r.id_refugio = se.refugio_id

        WHERE s.id_seguimiento = %s
        AND s.estado_moderacion = 'aprobado'

        AND (
            (
                COALESCE(se.necesita_refugio, 0) = 0
                AND se.refugio_id IS NULL
            )

            OR EXISTS (
                SELECT 1
                FROM ingresos_refugio ir
                WHERE ir.seguimiento_id = s.id_seguimiento
                AND ir.animal_id = s.animal_id
                AND ir.estado = 'confirmado'
                AND (
                    se.refugio_id IS NULL
                    OR ir.refugio_id = se.refugio_id
                )
            )
        )

        LIMIT 1
    """

    with connection.cursor() as cursor:
        cursor.execute(consulta, [id_seguimiento])

        columnas = [columna[0] for columna in cursor.description]

        fila = cursor.fetchone()

    if not fila:
        from django.http import Http404
        raise Http404("Seguimiento no encontrado")

    seguimiento = dict(zip(columnas, fila))

        # Fotografías del seguimiento
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                id_imagen,
                ruta_imagen,
                imagen_principal
            FROM imagenes_seguimiento
            WHERE seguimiento_id = %s
            ORDER BY imagen_principal DESC, id_imagen ASC
        """, [id_seguimiento])

        columnas_imagenes = [
            columna[0] for columna in cursor.description
        ]

        imagenes = [
            dict(zip(columnas_imagenes, imagen))
            for imagen in cursor.fetchall()
        ]

    # Historial de actualizaciones
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                mensaje,
                created_at
            FROM actualizaciones_seguimiento
            WHERE seguimiento_id = %s
            ORDER BY created_at DESC, id_actualizacion DESC
        """, [id_seguimiento])

        columnas_actualizaciones = [
            columna[0] for columna in cursor.description
        ]

        actualizaciones = [
            dict(zip(columnas_actualizaciones, actualizacion))
            for actualizacion in cursor.fetchall()
        ]

        return render(
        request,
        'seguimientos/detalle_seguimiento.html',
        {
            'seguimiento': seguimiento,
            'imagenes': imagenes,
            'actualizaciones': actualizaciones,
        }
    )


    from django.shortcuts import redirect


def mis_seguimientos(request):

    # Verificar que el usuario haya iniciado sesión
    persona_id = request.session.get('backhome_user_id')
    rol = request.session.get('backhome_rol')

    if not persona_id:
        return redirect('iniciar_sesion')

    # Solo los clientes pueden consultar esta sección
    if rol != 'cliente':
        return redirect('pagina_principal')

    consulta = """
        SELECT
            s.id_seguimiento,
            s.titulo,
            s.fecha_publicacion,
            s.estado_seguimiento,
            s.estado_moderacion,

            a.nombre AS animal_nombre,

            COALESCE(ad.especie, ae.especie) AS especie,

            loc.n_localidad AS localidad

        FROM seguimiento s

        INNER JOIN cliente c
            ON c.id_cliente = s.cliente_id

        INNER JOIN personas p
            ON p.id_persona = c.persona_id

        INNER JOIN animal a
            ON a.id_animal = s.animal_id

        LEFT JOIN animal_domestico ad
            ON ad.animal_id = a.id_animal

        LEFT JOIN animal_exotico ae
            ON ae.animal_id = a.id_animal

        INNER JOIN lugares l
            ON l.id_lugar = s.lugar_id

        INNER JOIN localidades loc
            ON loc.id_localidad = l.localidad_id

        WHERE p.id_persona = %s

        ORDER BY s.fecha_publicacion DESC
    """

    with connection.cursor() as cursor:
        cursor.execute(consulta, [persona_id])

        columnas = [
            columna[0] for columna in cursor.description
        ]

        seguimientos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

    return render(
        request,
        'seguimientos/mis_seguimientos.html',
        {
            'seguimientos': seguimientos
        }
    )