
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
