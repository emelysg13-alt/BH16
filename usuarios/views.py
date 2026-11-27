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
from .models import Persona
from openpyxl import load_workbook
from django.core.files.uploadedfile import UploadedFile

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









def validar_persona(fila):
    errores = []

    nombres = str(fila[0] or '').strip()
    apellidos = str(fila[1] or '').strip()
    tipo_documento = str(fila[2] or '').strip().upper()
    numero_documento = str(fila[3] or '').strip()
    correo = str(fila[4] or '').strip().lower()
    telefono = str(fila[5] or '').strip()

    if not nombres:
        errores.append('Faltan los nombres.')

    if not apellidos:
        errores.append('Faltan los apellidos.')

    if tipo_documento not in ['CC', 'CE', 'TI', 'PP']:
        errores.append('Tipo de documento no válido.')

    if not numero_documento:
        errores.append('Falta el número de documento.')

    if not correo:
        errores.append('Falta el correo electrónico.')
    else:
        try:
            validate_email(correo)
        except ValidationError:
            errores.append('El correo electrónico no es válido.')

    if not telefono:
        errores.append('Falta el teléfono.')

    return errores



def documento_existe(numero_documento):
    return Persona.objects.filter(
        numero_documento=numero_documento
    ).exists()



@require_http_methods(["GET", "POST"])
def carga_masiva_personas(request):

    # Verificar acceso del administrador
    if (
        request.session.get('backhome_rol') != 'administrador'
        or not request.session.get('backhome_user_id')
    ):
        messages.error(request, 'No tienes permisos para acceder.')
        return redirect('iniciar_sesion')

    if request.method == 'POST':

        archivo = request.FILES.get('archivo')

        if not archivo:
            messages.error(request, 'Selecciona un archivo Excel.')
            return redirect('carga_masiva_personas')

        if not archivo.name.lower().endswith('.xlsx'):
            messages.error(request, 'El archivo debe ser .xlsx.')
            return redirect('carga_masiva_personas')

        if archivo.size > 5 * 1024 * 1024:
            messages.error(request, 'El archivo supera los 5 MB.')
            return redirect('carga_masiva_personas')

        try:
            libro = load_workbook(
                archivo,
                read_only=True,
                data_only=True
            )
            hoja = libro.active

            encabezados = [
                str(celda or '').strip().lower()
                for celda in next(hoja.iter_rows(
                    min_row=1,
                    max_row=1,
                    values_only=True
                ))
            ]

            encabezados_esperados = [
                'nombres',
                'apellidos',
                'tipo_documento',
                'numero_documento',
                'correo',
                'telefono'
            ]

            if encabezados != encabezados_esperados:
                libro.close()
                messages.error(
                    request,
                    'Los encabezados del Excel no coinciden con la plantilla.'
                )
                return redirect('carga_masiva_personas')

            registrados = 0
            errores = 0
            documentos_excel = set()

            personas_registradas = []
            personas_rechazadas = []

            for numero_fila, fila in enumerate(
                hoja.iter_rows(min_row=2, values_only=True),
                start=2
            ):

                if not any(valor is not None for valor in fila):
                    continue

                datos = list(fila[:6])
                datos += [None] * (6 - len(datos))

                problemas = validar_persona(datos)

                nombres = str(datos[0] or '').strip()
                apellidos = str(datos[1] or '').strip()
                tipo_documento = str(datos[2] or '').strip().upper()
                numero_documento = str(datos[3] or '').strip()
                correo = str(datos[4] or '').strip().lower()
                telefono = str(datos[5] or '').strip()

                if numero_documento in documentos_excel:
                    problemas.append(
                        'Documento repetido dentro del archivo.'
                    )

                documentos_excel.add(numero_documento)

                if not problemas and documento_existe(numero_documento):
                    problemas.append(
                        'El documento ya está registrado en BackHome.'
                    )

                if problemas:
                    errores += 1

                    personas_rechazadas.append({
                    'fila': numero_fila,
                    'nombres': nombres,
                    'apellidos': apellidos,
                    'documento': numero_documento,
                    'motivos': problemas
                })

                    continue

                try:
                    Persona.objects.create(
                        nombres=nombres,
                        apellidos=apellidos,
                        tipo_documento=tipo_documento,
                        numero_documento=numero_documento,
                        correo=correo,
                        telefono=telefono
                    )

                    registrados += 1

                    personas_registradas.append({
                        'nombres': nombres,
                        'apellidos': apellidos,
                        'documento': numero_documento,
                        'correo': correo
                    })

                except IntegrityError:
                    errores += 1
                    messages.warning(
                        request,
                        f'Fila {numero_fila}: el documento ya existe.'
                    )

            libro.close()

            return render(
                request,
                'usuarios/carga_masiva_personas.html',
                {
                    'resultado': True,
                    'registrados': registrados,
                    'errores': errores,
                    'personas_registradas': personas_registradas,
                    'personas_rechazadas': personas_rechazadas
                }
            )

        except Exception as error:
            print('ERROR EN CARGA MASIVA:', repr(error))
            messages.error(
                request,
                'No fue posible procesar el Excel. Verifica su contenido.'
            )

            return redirect('carga_masiva_personas')

    return render(request, 'usuarios/carga_masiva_personas.html')