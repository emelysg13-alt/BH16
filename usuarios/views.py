from django.contrib.auth.hashers import check_password, make_password
from django.utils.crypto import constant_time_compare
from django.db import DatabaseError, connection
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def _destino_por_rol(rol):
    return "/panel/" if rol == "administrador" else "/"

@require_http_methods(["GET", "POST"])
def iniciar_sesion(request):
    """Permite iniciar sesión a administradores y clientes activos."""

    if request.session.get("backhome_user_id"):
        return redirect(
            _destino_por_rol(request.session.get("backhome_rol"))
        )

    error = ""

    if request.method == "POST":
        identificador = request.POST.get("identificador", "").strip()
        password = request.POST.get("password", "")
        destino = request.POST.get("next", "").strip()

        if not identificador or not password:
            error = "Ingresa tu correo o documento y tu contraseña."
        else:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT
                            p.id_persona,
                            p.password,
                            p.primer_nombre,
                            p.primer_apellido,
                            a.id_admin,
                            c.id_cliente
                        FROM personas p
                        LEFT JOIN administrador a
                            ON a.persona_id = p.id_persona
                        LEFT JOIN cliente c
                            ON c.persona_id = p.id_persona
                        WHERE (
                            LOWER(p.email) = LOWER(%s)
                            OR p.n_documento = %s
                        )
                        AND p.estado = 'activo'
                        LIMIT 1
                    """, [identificador, identificador])

                    persona = cursor.fetchone()

                if not persona:
                    error = "Credenciales incorrectas o cuenta inactiva."
                else:
                    password_valida = check_password(
                        password,
                        persona[1]
                    )

                    # Compatibilidad con contraseñas antiguas guardadas
                    # como texto plano. Se convierten a hash al iniciar sesión.
                    if not password_valida and constant_time_compare(
                        password, str(persona[1] or "")
                    ):
                        password_valida = True

                        with connection.cursor() as cursor:
                            cursor.execute(
                                """
                                UPDATE personas
                                SET password = %s
                                WHERE id_persona = %s
                                """,
                                [make_password(password), persona[0]],
                            )

                    if not password_valida:
                        error = "Credenciales incorrectas o cuenta inactiva."
                    else:
                        (
                            persona_id,
                            _,
                            nombre,
                            apellido,
                            admin_id,
                            cliente_id
                        ) = persona

                        if admin_id:
                            rol = "administrador"
                        elif cliente_id:
                            rol = "cliente"
                        else:
                            rol = None

                        if not rol:
                            error = (
                                "Tu cuenta no tiene un perfil de acceso asignado."
                            )
                        else:
                            request.session.cycle_key()

                            request.session["backhome_user_id"] = persona_id
                            request.session["backhome_rol"] = rol
                            request.session["backhome_nombre"] = (
                                f"{nombre or ''} {apellido or ''}"
                            ).strip()

                            destino_default = _destino_por_rol(rol)

                            prefijo_permitido = (
                                "/panel/"
                                if rol == "administrador"
                                else "/mi-cuenta/"
                            )

                            if (
                                destino.startswith(prefijo_permitido)
                                and url_has_allowed_host_and_scheme(
                                    destino,
                                    allowed_hosts={request.get_host()},
                                    require_https=request.is_secure(),
                                )
                            ):
                                return redirect(destino)

                            return redirect(destino_default)

            except DatabaseError as e:
                print("ERROR REAL DEL LOGIN:", repr(e))
                error = (
                    "No fue posible validar el acceso. "
                    "Inténtalo nuevamente."
                )

    return render(request, "usuarios/iniciar_sesion.html", {
        "error": error,
        "next": request.POST.get(
            "next",
            request.GET.get("next", "")
        ),
    })


@require_http_methods(["POST"])
def cerrar_sesion(request):
    request.session.flush()
    return redirect("/")



@require_http_methods(["GET", "POST"])
def registrar_cliente(request):
    """Registra una nueva cuenta de cliente."""

    errores = []
    datos = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id_t_doc, n_doc
                FROM tipo_documento
                ORDER BY n_doc
            """)
            tipos_documento = cursor.fetchall()

        if request.method == "POST":
            tipo_documento = request.POST.get(
                "tipo_documento", ""
            ).strip()
            documento = request.POST.get("documento", "").strip()
            primer_nombre = request.POST.get(
                "primer_nombre", ""
            ).strip()
            segundo_nombre = request.POST.get(
                "segundo_nombre", ""
            ).strip()
            primer_apellido = request.POST.get(
                "primer_apellido", ""
            ).strip()
            segundo_apellido = request.POST.get(
                "segundo_apellido", ""
            ).strip()
            email = request.POST.get("email", "").strip().lower()
            telefono = request.POST.get("telefono", "").strip()
            password = request.POST.get("password", "")
            confirmar_password = request.POST.get(
                "confirmar_password", ""
            )

            datos = request.POST.dict()

            # Validar campos obligatorios.
            if not all([
                tipo_documento, documento, primer_nombre,
                primer_apellido, email, telefono,
                password, confirmar_password
            ]):
                errores.append("Completa todos los campos obligatorios.")

            # Validar tipo y número de documento.
            if tipo_documento and not any(
                tipo[0] == tipo_documento
                for tipo in tipos_documento
            ):
                errores.append("Selecciona un tipo de documento válido.")

            if documento and len(documento) > 20:
                errores.append("El documento no puede superar 20 caracteres.")

            # Validar correo.
            try:
                validate_email(email)
            except ValidationError:
                errores.append("Ingresa un correo electrónico válido.")

            if len(email) > 150:
                errores.append("El correo no puede superar 150 caracteres.")

            # Validar contraseña.
            if len(password) < 8:
                errores.append("La contraseña debe tener mínimo 8 caracteres.")

            if password != confirmar_password:
                errores.append("Las contraseñas no coinciden.")

            if not errores:
                with transaction.atomic():
                    with connection.cursor() as cursor:

                        # Comprobar documento o correo existente.
                        cursor.execute("""
                            SELECT id_persona
                            FROM personas
                            WHERE n_documento = %s
                               OR LOWER(email) = LOWER(%s)
                            LIMIT 1
                        """, [documento, email])

                        if cursor.fetchone():
                            errores.append(
                                "El documento o correo ya están registrados."
                            )
                        else:
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
                                VALUES (
                                    %s, %s, %s, %s, %s, %s,
                                    %s, %s, %s, 'activo'
                                )
                            """, [
                                tipo_documento,
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

                            cursor.execute("""
                                INSERT INTO cliente (persona_id)
                                VALUES (%s)
                            """, [id_persona])

                if not errores:
                    messages.success(
                        request,
                        "Tu cuenta fue creada correctamente. Ya puedes iniciar sesión."
                    )
                    return redirect("iniciar_sesion")

    except IntegrityError:
        errores.append(
            "El documento o correo ya están registrados."
        )
    except DatabaseError:
        errores.append(
            "No fue posible completar el registro. Inténtalo nuevamente."
        )

    return render(request, "usuarios/registrar_cliente.html", {
        "tipos_documento": tipos_documento,
        "errores": errores,
        "datos": datos,
    })



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

    return render(request, 'usuarios/gestion_usuarios.html', contexto)
