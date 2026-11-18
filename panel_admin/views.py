
from django.shortcuts import render, redirect
from django.db import connection, transaction, IntegrityError
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.views.decorators.http import require_http_methods


def dashboard(request):
    return render(request, 'panel_admin/dashboard.html')


@require_http_methods(["GET", "POST"])
def gestion_usuarios(request):

    # CREAR USUARIO
    if request.method == 'POST' and request.POST.get('accion') == 'crear':

        documento_tipo = request.POST.get('tipo_documento', '').strip()
        documento = request.POST.get('documento', '').strip()
        primer_nombre = request.POST.get('primer_nombre', '').strip()
        segundo_nombre = request.POST.get('segundo_nombre', '').strip()
        primer_apellido = request.POST.get('primer_apellido', '').strip()
        segundo_apellido = request.POST.get('segundo_apellido', '').strip()
        email = request.POST.get('email', '').strip().lower()
        telefono = request.POST.get('telefono', '').strip()
        password = request.POST.get('password', '')
        rol = request.POST.get('rol', '').strip()

        if not all([
            documento_tipo, documento, primer_nombre,
            primer_apellido, email, telefono, password, rol
        ]):
            messages.error(request, 'Completa todos los campos obligatorios.')
            return redirect('gestion_usuarios')

        if rol not in ['Cliente', 'Administrador']:
            messages.error(request, 'El rol seleccionado no es válido.')
            return redirect('gestion_usuarios')

        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener mínimo 8 caracteres.')
            return redirect('gestion_usuarios')

        if '@' not in email or '.' not in email.split('@')[-1]:
            messages.error(request, 'Ingresa un correo electrónico válido.')
            return redirect('gestion_usuarios')

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:

                    # Comprobar que el tipo de documento exista
                    cursor.execute(
                        "SELECT id_t_doc FROM tipo_documento WHERE id_t_doc = %s",
                        [documento_tipo]
                    )
                    if not cursor.fetchone():
                        messages.error(request, 'El tipo de documento no existe.')
                        return redirect('gestion_usuarios')

                    # Registrar persona
                    cursor.execute("""
                        INSERT INTO personas (
                            t_documento_id,
                            n_documento,
                            primer_nombre,
                            segundo_nombre,
                            primer_apellido,
                            segundo_apellido,
                            email,
                            numero_tel,
                            password,
                            estado
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'activo')
                    """, [
                        documento_tipo,
                        documento,
                        primer_nombre,
                        segundo_nombre or None,
                        primer_apellido,
                        segundo_apellido or None,
                        email,
                        telefono,
                        make_password(password)
                    ])

                    id_persona = cursor.lastrowid

                    # Asignar rol
                    if rol == 'Administrador':
                        cursor.execute("""
                            INSERT INTO administrador (persona_id)
                            VALUES (%s)
                        """, [id_persona])
                    else:
                        cursor.execute("""
                            INSERT INTO cliente (persona_id)
                            VALUES (%s)
                        """, [id_persona])

            messages.success(request, '¡Usuario registrado correctamente!')

        except IntegrityError:
            messages.error(
                request,
                'No se pudo registrar. El documento o el correo ya están registrados.'
            )
        except Exception as error:
            messages.error(request, f'No se pudo registrar el usuario: {error}')

        return redirect('gestion_usuarios')

    # CAMBIAR ESTADO DEL USUARIO
    if request.method == 'POST' and request.POST.get('accion') == 'estado':

        id_persona = request.POST.get('id_persona')
        nuevo_estado = request.POST.get('nuevo_estado')

        estados_validos = ['activo', 'suspendido', 'bloqueado']

        if not id_persona or nuevo_estado not in estados_validos:
            messages.error(request, 'La acción solicitada no es válida.')
            return redirect('gestion_usuarios')

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE personas
                    SET estado = %s
                    WHERE id_persona = %s
                """, [nuevo_estado, id_persona])

                if cursor.rowcount == 0:
                    cursor.execute("""
                        SELECT id_persona FROM personas
                        WHERE id_persona = %s
                    """, [id_persona])

                    if not cursor.fetchone():
                        messages.error(request, 'No se encontró el usuario.')
                        return redirect('gestion_usuarios')

            mensajes_estado = {
                'activo': 'La cuenta fue reactivada correctamente.',
                'suspendido': 'La cuenta fue suspendida correctamente.',
                'bloqueado': 'La cuenta fue bloqueada correctamente.'
            }

            messages.success(request, mensajes_estado[nuevo_estado])

        except Exception as error:
            messages.error(request, f'No se pudo cambiar el estado: {error}')

        return redirect('gestion_usuarios')

    # FILTROS
    buscar = request.GET.get('buscar', '').strip()
    filtro_estado = request.GET.get('estado', '').strip()
    filtro_rol = request.GET.get('rol', '').strip()

    consulta = """
        SELECT
            p.id_persona,
            p.t_documento_id,
            td.n_doc AS nombre_documento,
            p.n_documento,

            CONCAT_WS(' ',
                NULLIF(p.primer_nombre, ''),
                NULLIF(p.segundo_nombre, ''),
                NULLIF(p.primer_apellido, ''),
                NULLIF(p.segundo_apellido, '')
            ) AS nombre_completo,

            p.email,
            p.numero_tel,
            p.estado,

            CASE
                WHEN a.id_admin IS NOT NULL THEN 'Administrador'
                WHEN c.id_cliente IS NOT NULL THEN 'Cliente'
                ELSE 'Sin rol'
            END AS rol

        FROM personas p

        LEFT JOIN tipo_documento td
            ON td.id_t_doc = p.t_documento_id

        LEFT JOIN administrador a
            ON a.persona_id = p.id_persona

        LEFT JOIN cliente c
            ON c.persona_id = p.id_persona

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
                OR p.n_documento LIKE %s
                OR p.email LIKE %s
            )
        """
        valor = f'%{buscar}%'
        parametros.extend([valor] * 6)

    if filtro_estado in ['activo', 'suspendido', 'bloqueado']:
        consulta += " AND p.estado = %s"
        parametros.append(filtro_estado)

    if filtro_rol == 'Administrador':
        consulta += " AND a.id_admin IS NOT NULL"
    elif filtro_rol == 'Cliente':
        consulta += " AND c.id_cliente IS NOT NULL"

    consulta += " ORDER BY p.id_persona DESC"

    with connection.cursor() as cursor:
        cursor.execute(consulta, parametros)
        columnas = [columna[0] for columna in cursor.description]
        usuarios = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(estado = 'activo'), 0),
                COALESCE(SUM(estado = 'suspendido'), 0),
                COALESCE(SUM(estado = 'bloqueado'), 0)
            FROM personas
        """)

        resultado = cursor.fetchone()

        cursor.execute("""
            SELECT id_t_doc, n_doc
            FROM tipo_documento
            ORDER BY n_doc
        """)
        tipos_documento = cursor.fetchall()

    estadisticas = {
        'total': resultado[0] or 0,
        'activos': resultado[1] or 0,
        'suspendidos': resultado[2] or 0,
        'bloqueados': resultado[3] or 0,
    }

    contexto = {
        'usuarios': usuarios,
        'estadisticas': estadisticas,
        'tipos_documento': tipos_documento,
        'buscar': buscar,
        'filtro_estado': filtro_estado,
        'filtro_rol': filtro_rol,
    }

    return render(
        request,
        'panel_admin/gestion_usuarios.html',
        contexto
    )
