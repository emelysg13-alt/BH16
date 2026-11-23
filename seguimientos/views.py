from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename
from pathlib import Path
import uuid
from PIL import Image
from django.utils.dateparse import parse_datetime
from django.contrib import messages

MAX_FOTOGRAFIAS = 5
MAX_TAMANO_IMAGEN = 5 * 1024 * 1024  # 5 MB

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
            (
    SELECT ir.estado
    FROM ingresos_refugio ir
    WHERE ir.seguimiento_id = s.id_seguimiento
    ORDER BY ir.id_ingreso DESC
    LIMIT 1
) AS estado_ingreso,


            a.nombre AS animal_nombre,

            COALESCE(ad.especie, ae.especie) AS especie,

            loc.n_localidad AS localidad,

            (
                SELECT i.ruta_imagen
                FROM imagenes_seguimiento i
                WHERE i.seguimiento_id = s.id_seguimiento
                ORDER BY i.imagen_principal DESC, i.id_imagen ASC
                LIMIT 1
            ) AS fotografia

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

    for seguimiento in seguimientos:

        seguimiento['estado_seguimiento'] = (
            seguimiento['estado_seguimiento']
        .replace('_', ' ')
        .capitalize()
    )

        if seguimiento['estado_moderacion']:
            seguimiento['estado_moderacion'] = (
                seguimiento['estado_moderacion']
            .replace('_', ' ')
            .capitalize()
        )

        if seguimiento['estado_ingreso']:
            seguimiento['estado_ingreso'] = (
                seguimiento['estado_ingreso']
            .replace('_', ' ')
            .capitalize()
        )

    return render(
        request,
        'seguimientos/mis_seguimientos.html',
        {
            'seguimientos': seguimientos
        }
    )





def detalle_mi_seguimiento(request, id_seguimiento):

    # Verificar sesión
    persona_id = request.session.get('backhome_user_id')
    rol = request.session.get('backhome_rol')

    if not persona_id:
        return redirect('iniciar_sesion')

    if rol != 'cliente':
        return redirect('pagina_principal')

    # Consultar el seguimiento y verificar que pertenezca al cliente
    consulta = """
        SELECT
            s.id_seguimiento,
            s.titulo,
            s.descripcion,
            s.fecha_publicacion,
            s.estado_seguimiento,
            s.estado_moderacion,

            a.nombre AS animal_nombre,
            a.sexo,
            a.color,
            a.tamano,
            a.descripcion AS descripcion_animal,

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

        INNER JOIN cliente c
            ON c.id_cliente = s.cliente_id

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
        AND c.persona_id = %s

        LIMIT 1
    """

    with connection.cursor() as cursor:
        cursor.execute(consulta, [id_seguimiento, persona_id])

        columnas = [columna[0] for columna in cursor.description]
        fila = cursor.fetchone()

    if not fila:
        from django.http import Http404
        raise Http404("Seguimiento no encontrado")

    seguimiento = dict(zip(columnas, fila))

    # Consultar fotografías
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_imagen, ruta_imagen, imagen_principal
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

    # Consultar historial de actualizaciones
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT mensaje, created_at
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
        'seguimientos/detalle_mi_seguimiento.html',
        {
            'seguimiento': seguimiento,
            'imagenes': imagenes,
            'actualizaciones': actualizaciones,
        }
    )




def eliminar_seguimiento(request, id_seguimiento):

    # Solo permitir solicitudes POST
    if request.method != 'POST':
        return redirect('mis_seguimientos')

    # Verificar sesión
    persona_id = request.session.get('backhome_user_id')
    rol = request.session.get('backhome_rol')

    if not persona_id:
        return redirect('iniciar_sesion')

    if rol != 'cliente':
        return redirect('pagina_principal')

    # Verificar que el seguimiento pertenezca al cliente
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                s.animal_id,
                s.lugar_id
            FROM seguimiento s
            INNER JOIN cliente c
                ON c.id_cliente = s.cliente_id
            WHERE s.id_seguimiento = %s
            AND c.persona_id = %s
        """, [id_seguimiento, persona_id])

        resultado = cursor.fetchone()

    if not resultado:
        return redirect('mis_seguimientos')

    animal_id, lugar_id = resultado

    # Verificar si existe un ingreso confirmado al refugio
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM ingresos_refugio
            WHERE seguimiento_id = %s
            AND estado = 'confirmado'
        """, [id_seguimiento])

        ingreso_confirmado = cursor.fetchone()[0]

    if ingreso_confirmado > 0:
        messages.error(
            request,
            'No puedes eliminar este seguimiento porque tiene '
            'un ingreso al refugio confirmado.'
        )
        return redirect('mis_seguimientos')


    

    # Eliminar el seguimiento y sus registros relacionados
    with transaction.atomic():

        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM seguimiento
                WHERE id_seguimiento = %s
            """, [id_seguimiento])

            # Eliminar el animal si ya no está siendo utilizado
            cursor.execute("""
                SELECT COUNT(*)
                FROM seguimiento
                WHERE animal_id = %s
            """, [animal_id])

            seguimientos_restantes = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM ingresos_refugio
                WHERE animal_id = %s
            """, [animal_id])

            ingresos_restantes = cursor.fetchone()[0]

            if seguimientos_restantes == 0 and ingresos_restantes == 0:
                cursor.execute("""
                    DELETE FROM animal
                    WHERE id_animal = %s
                """, [animal_id])

            # Eliminar el lugar si ya no está siendo utilizado
            cursor.execute("""
                SELECT COUNT(*)
                FROM seguimiento
                WHERE lugar_id = %s
            """, [lugar_id])

            lugares_restantes = cursor.fetchone()[0]

            if lugares_restantes == 0:
                cursor.execute("""
                    DELETE FROM lugares
                    WHERE id_lugar = %s
                """, [lugar_id])

    return redirect('mis_seguimientos')




def obtener_cliente_id(persona_id):

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_cliente
            FROM cliente
            WHERE persona_id = %s
        """, [persona_id])

        resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    return None


def validar_fotografia(imagen):

    formatos_permitidos = {
        'JPEG': '.jpg',
        'PNG': '.png',
        'WEBP': '.webp'
    }

    try:
        imagen.seek(0)

        archivo = Image.open(imagen)
        formato = archivo.format

        if formato not in formatos_permitidos:
            return None

        archivo.verify()

        imagen.seek(0)

        return formatos_permitidos[formato]

    except (Image.UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None


def crear_seguimiento(request):

    # Verificar sesión
    persona_id = request.session.get('backhome_user_id')
    rol = request.session.get('backhome_rol')

    if not persona_id:
        return redirect('iniciar_sesion')

    if rol != 'cliente':
        return redirect('pagina_principal')

    # Obtener cliente autenticado
    cliente_id = obtener_cliente_id(persona_id)

    if cliente_id is None:
        return redirect('pagina_principal')

    # Consultar datos para los select del formulario
    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT id_localidad, n_localidad
            FROM localidades
            ORDER BY n_localidad
        """)
        localidades = cursor.fetchall()

        cursor.execute("""
            SELECT id_refugio, nombre, direccion, localidad_id
            FROM refugios
            WHERE estado = 'activo'
            ORDER BY nombre
        """)
        refugios = cursor.fetchall()

        cursor.execute("""
            SELECT id_prioridad, nombre, descripcion
            FROM prioridades
            WHERE estado = 'activo'
            ORDER BY nivel
        """)
        prioridades = cursor.fetchall()

    contexto = {
        'localidades': localidades,
        'refugios': refugios,
        'prioridades': prioridades
    }

    # Mostrar formulario mediante GET
    if request.method == 'GET':
        return render(
            request,
            'seguimientos/crear_seguimiento.html',
            contexto
        )

    # Obtener fotografías
    fotografias = request.FILES.getlist('fotografias')

    def error_formulario(mensaje):
        contexto['error'] = mensaje
        return render(
            request,
            'seguimientos/crear_seguimiento.html',
            contexto
        )

    # Validar cantidad de fotografías
    if not fotografias:
        return error_formulario(
            'Debes cargar al menos una fotografía del animal.'
        )

    if len(fotografias) > MAX_FOTOGRAFIAS:
        return error_formulario(
            'Puedes cargar máximo 5 fotografías.'
        )

    # Validar tamaño y formato
    extensiones = []

    for imagen in fotografias:

        if imagen.size > MAX_TAMANO_IMAGEN:
            return error_formulario(
                'Cada fotografía debe pesar máximo 5 MB.'
            )

        extension = validar_fotografia(imagen)

        if extension is None:
            return error_formulario(
                'Una o más fotografías no tienen un formato válido. Usa JPG, PNG o WEBP.'
            )

        extensiones.append(extension)

    # Obtener datos generales
    tipo_caso = request.POST.get('tipo_caso')
    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    prioridad_id = request.POST.get('prioridad_id')

    # Obtener ubicación
    localidad_id = request.POST.get('localidad_id')
    direccion = request.POST.get('direccion', '').strip()

    # Obtener información del animal
    nombre_animal = request.POST.get('nombre_animal', '').strip()
    tipo_animal = request.POST.get('tipo_animal')
    especie = request.POST.get('especie', '').strip()
    raza = request.POST.get('raza', '').strip()
    sexo = request.POST.get('sexo')
    color = request.POST.get('color', '').strip()
    tamano = request.POST.get('tamano') or None
    descripcion_animal = request.POST.get(
        'descripcion_animal', ''
    ).strip()

    # Obtener datos de animal perdido
    fecha_perdida = request.POST.get('fecha_perdida')
    ultima_fecha_visto = request.POST.get('ultima_fecha_visto')
    descripcion_ultima_ubicacion = request.POST.get(
        'descripcion_ultima_ubicacion', ''
    ).strip()

    # Obtener datos de animal encontrado
    fecha_encontrado = request.POST.get('fecha_encontrado')
    descripcion_lugar_encontrado = request.POST.get(
        'descripcion_lugar_encontrado', ''
    ).strip()

    necesita_refugio = request.POST.get('necesita_refugio', '0')
    refugio_id = request.POST.get('refugio_id')

    # Validar confirmación
    if not request.POST.get('confirmar_informacion'):
        return error_formulario(
            'Debes confirmar que la información proporcionada es correcta.'
        )

    # Validar datos generales
    if not all([
        tipo_caso,
        titulo,
        descripcion,
        prioridad_id,
        localidad_id,
        direccion
    ]):
        return error_formulario(
            'Completa todos los campos obligatorios.'
        )

    if len(titulo) > 150:
        return error_formulario(
            'El título no puede superar los 150 caracteres.'
        )

    # Validar tipo de caso
    if tipo_caso not in ['perdido', 'encontrado']:
        return error_formulario(
            'El tipo de caso seleccionado no es válido.'
        )

    # Validar datos del animal
    if not all([
        tipo_animal,
        especie,
        sexo,
        color,
        descripcion_animal
    ]):
        return error_formulario(
            'Completa la información obligatoria del animal.'
        )

    if tipo_animal not in ['domestico', 'exotico']:
        return error_formulario(
            'El tipo de animal seleccionado no es válido.'
        )

    if sexo not in ['macho', 'hembra', 'desconocido']:
        return error_formulario(
            'El sexo seleccionado no es válido.'
        )

    if tamano and tamano not in ['pequeño', 'mediano', 'grande']:
        return error_formulario(
            'El tamaño seleccionado no es válido.'
        )

    if tipo_animal == 'domestico' and not raza:
        return error_formulario(
            'Debes indicar la raza del animal doméstico.'
        )

    if tipo_animal == 'domestico' and len(raza) > 100:
        return error_formulario(
            'La raza no puede superar los 100 caracteres.'
        )

    if len(especie) > 100 or len(color) > 50:
        return error_formulario(
            'La especie o el color superan la longitud permitida.'
        )

    # Convertir identificadores a enteros
    try:
        prioridad_id = int(prioridad_id)
        localidad_id = int(localidad_id)

        if necesita_refugio == '1' and refugio_id:
            refugio_id = int(refugio_id)

    except (ValueError, TypeError):
        return error_formulario(
            'Uno de los identificadores seleccionados no es válido.'
        )

    # Validar prioridad y localidad
    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT id_prioridad
            FROM prioridades
            WHERE id_prioridad = %s
            AND estado = 'activo'
        """, [prioridad_id])

        prioridad_valida = cursor.fetchone()

        cursor.execute("""
            SELECT id_localidad
            FROM localidades
            WHERE id_localidad = %s
        """, [localidad_id])

        localidad_valida = cursor.fetchone()

    if not prioridad_valida or not localidad_valida:
        return error_formulario(
            'La prioridad o localidad seleccionada no es válida.'
        )

    # Validar fechas
    if tipo_caso == 'perdido':

        fecha_perdida_dt = parse_datetime(fecha_perdida or '')

        if not fecha_perdida_dt:
            return error_formulario(
                'Debes indicar una fecha válida de pérdida.'
            )

        ultima_fecha_visto_dt = None

        if ultima_fecha_visto:
            ultima_fecha_visto_dt = parse_datetime(
                ultima_fecha_visto
            )

            if not ultima_fecha_visto_dt:
                return error_formulario(
                    'La última fecha en que se vio al animal no es válida.'
                )

    else:

        fecha_encontrado_dt = parse_datetime(
            fecha_encontrado or ''
        )

        if not fecha_encontrado_dt:
            return error_formulario(
                'Debes indicar una fecha válida de encuentro.'
            )

    # Validar necesidad de refugio
    if tipo_caso == 'encontrado':

        if necesita_refugio not in ['0', '1']:
            return error_formulario(
                'La selección de refugio no es válida.'
            )

        if necesita_refugio == '1' and not refugio_id:
            return error_formulario(
                'Debes seleccionar un refugio.'
            )

    # Validar refugio activo
    if tipo_caso == 'encontrado' and necesita_refugio == '1':

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id_refugio
                FROM refugios
                WHERE id_refugio = %s
                AND estado = 'activo'
            """, [refugio_id])

            refugio_valido = cursor.fetchone()

        if not refugio_valido:
            return error_formulario(
                'El refugio seleccionado no existe o no está activo.'
            )

    # Preparar control de archivos
    archivos_guardados = []

    try:

        # Iniciar transacción
        with transaction.atomic():

            with connection.cursor() as cursor:

                # Registrar información general del animal
                cursor.execute("""
                    INSERT INTO animal (
                        nombre,
                        sexo,
                        color,
                        tamano,
                        descripcion
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, [
                    nombre_animal or None,
                    sexo,
                    color,
                    tamano,
                    descripcion_animal
                ])

                animal_id = cursor.lastrowid

                # Registrar clasificación del animal
                if tipo_animal == 'domestico':

                    cursor.execute("""
                        INSERT INTO animal_domestico (
                            animal_id,
                            especie,
                            raza
                        )
                        VALUES (%s, %s, %s)
                    """, [
                        animal_id,
                        especie,
                        raza
                    ])

                else:

                    cursor.execute("""
                        INSERT INTO animal_exotico (
                            animal_id,
                            especie
                        )
                        VALUES (%s, %s)
                    """, [
                        animal_id,
                        especie
                    ])

                # Registrar ubicación
                cursor.execute("""
                    INSERT INTO lugares (
                        direccion,
                        localidad_id
                    )
                    VALUES (%s, %s)
                """, [
                    direccion,
                    localidad_id
                ])

                lugar_id = cursor.lastrowid

                # Registrar seguimiento principal
                cursor.execute("""
                    INSERT INTO seguimiento (
                        titulo,
                        descripcion,
                        estado_seguimiento,
                        estado_moderacion,
                        animal_id,
                        lugar_id,
                        cliente_id,
                        prioridad_id
                    )
                    VALUES (%s, %s, %s, 'pendiente', %s, %s, %s, %s)
                """, [
                    titulo,
                    descripcion,
                    tipo_caso,
                    animal_id,
                    lugar_id,
                    cliente_id,
                    prioridad_id
                ])

                seguimiento_id = cursor.lastrowid

                # Registrar caso perdido
                if tipo_caso == 'perdido':

                    cursor.execute("""
                        INSERT INTO seguimiento_perdido (
                            seguimiento_id,
                            fecha_perdida,
                            ultima_fecha_visto,
                            descripcion_ultima_ubicacion
                        )
                        VALUES (%s, %s, %s, %s)
                    """, [
                        seguimiento_id,
                        fecha_perdida_dt,
                        ultima_fecha_visto_dt,
                        descripcion_ultima_ubicacion or None
                    ])

                # Registrar caso encontrado
                else:

                    cursor.execute("""
                        INSERT INTO seguimiento_encontrado (
                            seguimiento_id,
                            fecha_encontrado,
                            descripcion_lugar_encontrado,
                            necesita_refugio,
                            refugio_id
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, [
                        seguimiento_id,
                        fecha_encontrado_dt,
                        descripcion_lugar_encontrado or None,
                        int(necesita_refugio),
                        refugio_id if necesita_refugio == '1' else None
                    ])

                # Registrar solicitud de ingreso al refugio
                if tipo_caso == 'encontrado' and necesita_refugio == '1':

                    cursor.execute("""
                        INSERT INTO ingresos_refugio (
                            refugio_id,
                            animal_id,
                            seguimiento_id,
                            observacion,
                            estado
                        )
                        VALUES (%s, %s, %s, %s, 'pendiente')
                    """, [
                        refugio_id,
                        animal_id,
                        seguimiento_id,
                        descripcion_lugar_encontrado or None
                    ])

                # Guardar fotografías
                for indice, (imagen, extension) in enumerate(
                    zip(fotografias, extensiones)
                ):

                    nombre_archivo = (
                        f"seguimientos/{uuid.uuid4().hex}{extension}"
                    )

                    imagen.seek(0)

                    ruta_guardada = default_storage.save(
                        nombre_archivo,
                        ContentFile(imagen.read())
                    )

                    archivos_guardados.append(ruta_guardada)

                    # Registrar fotografía en MariaDB
                    cursor.execute("""
                        INSERT INTO imagenes_seguimiento (
                            seguimiento_id,
                            ruta_imagen,
                            imagen_principal
                        )
                        VALUES (%s, %s, %s)
                    """, [
                        seguimiento_id,
                        ruta_guardada,
                        1 if indice == 0 else 0
                    ])

    except Exception:
        # Eliminar archivos si el registro falla
        for ruta in archivos_guardados:
            default_storage.delete(ruta)

        return error_formulario(
            'No fue posible registrar el seguimiento. '
            'Verifica la información e inténtalo nuevamente.'
        )

    # Registro completado
    return redirect('mis_seguimientos')

