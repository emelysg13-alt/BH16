
from django.shortcuts import render, redirect
from django.db import connection, transaction, IntegrityError
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods


def dashboard(request):
    return render(request, 'panel_admin/dashboard.html')


@require_http_methods(["GET", "POST"])
def gestion_usuarios(request):

    # ------------------------------------------
    # CREAR USUARIO
    # ------------------------------------------
    if request.method == 'POST' and request.POST.get('accion') == 'crear':

        tipo_documento = request.POST.get('tipo_documento', '').strip()
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
            tipo_documento, documento, primer_nombre,
            primer_apellido, email, telefono, password, rol
        ]):
            messages.error(request, 'Completa todos los campos obligatorios.')
            return redirect('gestion_usuarios')

        if rol not in ['Cliente', 'Administrador']:
            messages.error(request, 'Selecciona un rol válido.')
            return redirect('gestion_usuarios')

        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener mínimo 8 caracteres.')
            return redirect('gestion_usuarios')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Ingresa un correo electrónico válido.')
            return redirect('gestion_usuarios')

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:

                    cursor.execute(
                        "SELECT id_t_doc FROM tipo_documento WHERE id_t_doc = %s",
                        [tipo_documento]
                    )

                    if not cursor.fetchone():
                        messages.error(request, 'El tipo de documento no existe.')
                        return redirect('gestion_usuarios')

                    cursor.execute("""
                        INSERT INTO personas (
                            t_documento_id, n_documento,
                            primer_nombre, segundo_nombre,
                            primer_apellido, segundo_apellido,
                            email, numero_tel, password, estado
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'activo')
                    """, [
                        tipo_documento, documento,
                        primer_nombre, segundo_nombre or None,
                        primer_apellido, segundo_apellido or None,
                        email, telefono, make_password(password)
                    ])

                    id_persona = cursor.lastrowid

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

            messages.success(request, 'Usuario creado correctamente.')

        except IntegrityError:
            messages.error(
                request,
                'El documento o el correo electrónico ya están registrados.'
            )
        except Exception as error:
            messages.error(request, f'No se pudo crear el usuario: {error}')

        return redirect('gestion_usuarios')

    # ------------------------------------------
    # EDITAR USUARIO
    # ------------------------------------------
    if request.method == 'POST' and request.POST.get('accion') == 'editar':

        id_persona = request.POST.get('id_persona')
        tipo_documento = request.POST.get('tipo_documento', '').strip()
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
            id_persona, tipo_documento, documento,
            primer_nombre, primer_apellido, email, telefono, rol
        ]):
            messages.error(request, 'Completa los campos obligatorios para editar.')
            return redirect('gestion_usuarios')

        if rol not in ['Cliente', 'Administrador']:
            messages.error(request, 'Selecciona un rol válido.')
            return redirect('gestion_usuarios')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Ingresa un correo electrónico válido.')
            return redirect('gestion_usuarios')

        if password and len(password) < 8:
            messages.error(request, 'La nueva contraseña debe tener mínimo 8 caracteres.')
            return redirect('gestion_usuarios')

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:

                    cursor.execute(
                        "SELECT id_t_doc FROM tipo_documento WHERE id_t_doc = %s",
                        [tipo_documento]
                    )
                    if not cursor.fetchone():
                        messages.error(request, 'El tipo de documento no existe.')
                        return redirect('gestion_usuarios')

                    cursor.execute("""
                        SELECT id_persona
                        FROM personas
                        WHERE id_persona = %s
                    """, [id_persona])

                    if not cursor.fetchone():
                        messages.error(request, 'El usuario no existe.')
                        return redirect('gestion_usuarios')

                    if password:
                        cursor.execute("""
                            UPDATE personas
                            SET
                                t_documento_id = %s,
                                n_documento = %s,
                                primer_nombre = %s,
                                segundo_nombre = %s,
                                primer_apellido = %s,
                                segundo_apellido = %s,
                                email = %s,
                                numero_tel = %s,
                                password = %s
                            WHERE id_persona = %s
                        """, [
                            tipo_documento, documento,
                            primer_nombre, segundo_nombre or None,
                            primer_apellido, segundo_apellido or None,
                            email, telefono, make_password(password),
                            id_persona
                        ])
                    else:
                        cursor.execute("""
                            UPDATE personas
                            SET
                                t_documento_id = %s,
                                n_documento = %s,
                                primer_nombre = %s,
                                segundo_nombre = %s,
                                primer_apellido = %s,
                                segundo_apellido = %s,
                                email = %s,
                                numero_tel = %s
                            WHERE id_persona = %s
                        """, [
                            tipo_documento, documento,
                            primer_nombre, segundo_nombre or None,
                            primer_apellido, segundo_apellido or None,
                            email, telefono, id_persona
                        ])

                    # Actualizar el rol sin duplicar relaciones
                    cursor.execute(
                        "DELETE FROM administrador WHERE persona_id = %s",
                        [id_persona]
                    )
                    cursor.execute(
                        "DELETE FROM cliente WHERE persona_id = %s",
                        [id_persona]
                    )

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

            messages.success(request, 'Los datos del usuario se actualizaron correctamente.')

        except IntegrityError:
            messages.error(
                request,
                'No se pudo actualizar. El documento o el correo ya pertenecen a otra cuenta.'
            )
        except Exception as error:
            messages.error(request, f'No se pudo editar el usuario: {error}')

        return redirect('gestion_usuarios')

    # ------------------------------------------
    # CAMBIAR ESTADO
    # ------------------------------------------
    if request.method == 'POST' and request.POST.get('accion') == 'estado':

        id_persona = request.POST.get('id_persona')
        nuevo_estado = request.POST.get('nuevo_estado')

        if nuevo_estado not in ['activo', 'suspendido', 'bloqueado'] or not id_persona:
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

            textos = {
                'activo': 'La cuenta fue reactivada.',
                'suspendido': 'La cuenta fue suspendida.',
                'bloqueado': 'La cuenta fue bloqueada.'
            }
            messages.success(request, textos[nuevo_estado])

        except Exception as error:
            messages.error(request, f'No se pudo cambiar el estado: {error}')

        return redirect('gestion_usuarios')

    # ------------------------------------------
    # CONSULTAR USUARIOS Y FILTROS
    # ------------------------------------------
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
            p.primer_nombre,
            p.segundo_nombre,
            p.primer_apellido,
            p.segundo_apellido,
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
        columnas = [col[0] for col in cursor.description]
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

    return render(request, 'panel_admin/gestion_usuarios.html', contexto)

# ============================================================
# GESTIÓN DE REFUGIOS
# ============================================================

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
        "panel_admin/gestion_refugios.html",
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


# ============================================================
# GESTIÓN DE DONACIONES
# ============================================================

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
        "panel_admin/gestion_donaciones.html",
        contexto
    )

