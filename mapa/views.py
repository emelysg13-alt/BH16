from django.shortcuts import render
from django.db import connection
from django.http import JsonResponse

def mapa_localidades(request):

    consulta = """
        SELECT
            loc.id_localidad,
            loc.n_localidad,
            loc.poblacion,
            COALESCE(totales.total_seguimientos, 0) AS total_seguimientos

        FROM localidades loc

        LEFT JOIN (
            SELECT
                l.localidad_id,
                COUNT(DISTINCT s.id_seguimiento) AS total_seguimientos

            FROM seguimiento s

            INNER JOIN lugares l
                ON l.id_lugar = s.lugar_id

            LEFT JOIN seguimiento_encontrado se
                ON se.seguimiento_id = s.id_seguimiento

            WHERE
                s.estado_moderacion = 'aprobado'

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

            GROUP BY l.localidad_id

        ) AS totales
            ON totales.localidad_id = loc.id_localidad

        ORDER BY loc.n_localidad
    """

    with connection.cursor() as cursor:
        cursor.execute(consulta)

        columnas = [columna[0] for columna in cursor.description]

        localidades = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        for localidad in localidades:

            poblacion = localidad['poblacion'] or 0
            total = localidad['total_seguimientos']

            localidad['tasa_reportes'] = (
                round((total / poblacion) * 10000, 2)
                if poblacion > 0 else 0
            )

    # Obtener las tres localidades con más seguimientos
    top_localidades = sorted(
        localidades,
        key=lambda localidad: localidad['total_seguimientos'],
        reverse=True
    )[:3]


    return render(
        request,
        'mapa/mapa_localidades.html',
    {
            'localidades': localidades,
            'top_localidades': top_localidades
    }
)



def datos_marcadores(request):

    consulta = """
        SELECT
            s.id_seguimiento,
            s.titulo,
            s.estado_seguimiento,
            a.nombre AS animal_nombre,
            loc.id_localidad,
            loc.n_localidad

        FROM seguimiento s

        INNER JOIN animal a
            ON a.id_animal = s.animal_id

        INNER JOIN lugares l
            ON l.id_lugar = s.lugar_id

        INNER JOIN localidades loc
            ON loc.id_localidad = l.localidad_id

        LEFT JOIN seguimiento_encontrado se
            ON se.seguimiento_id = s.id_seguimiento

        WHERE
            s.estado_moderacion = 'aprobado'

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

    return JsonResponse(seguimientos, safe=False)