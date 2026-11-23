from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.db import DatabaseError, connection
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib import messages
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from django.core.files.storage import default_storage


@require_http_methods(["GET"])
def mi_cuenta(request):
    """Muestra la información personal del cliente."""

    if not request.session.get("backhome_user_id"):
        return redirect("/iniciar-sesion/?next=/mi-cuenta/")

    if request.session.get("backhome_rol") == "administrador":
        return redirect("/panel/")

    if request.session.get("backhome_rol") != "cliente":
        request.session.flush()
        return redirect("/iniciar-sesion/")

    persona_id = request.session.get("backhome_user_id")

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.id_persona,
                    p.primer_nombre,
                    p.segundo_nombre,
                    p.primer_apellido,
                    p.segundo_apellido,
                    p.t_documento_id,
                    td.n_doc AS tipo_documento,
                    p.n_documento,
                    p.email,
                    p.numero_tel,
                    p.estado,
                    p.foto_perfil
                FROM personas p
                INNER JOIN cliente c
                    ON c.persona_id = p.id_persona
                LEFT JOIN tipo_documento td
                    ON td.id_t_doc = p.t_documento_id
                WHERE p.id_persona = %s
                LIMIT 1
            """, [persona_id])

            fila = cursor.fetchone()

            if not fila:
                request.session.flush()
                return redirect("/iniciar-sesion/")

            columnas = [
                columna[0] for columna in cursor.description
            ]

            persona = dict(zip(columnas, fila))

    except DatabaseError as error:
        print("ERROR AL CONSULTAR EL PERFIL:", repr(error))
        return redirect("/")

    nombre_completo = " ".join(
        str(persona[campo]).strip()
        for campo in [
            "primer_nombre",
            "segundo_nombre",
            "primer_apellido",
            "segundo_apellido"
        ]
        if persona[campo]
    )

    return render(request, "cliente/mi_cuenta.html", {
        "persona": persona,
        "nombre": nombre_completo,
    })





@require_http_methods(["GET", "POST"])
def editar_perfil(request):
    """Permite al cliente actualizar sus datos y foto de perfil."""

    if not request.session.get("backhome_user_id"):
        return redirect("/iniciar-sesion/?next=/mi-cuenta/")

    if request.session.get("backhome_rol") != "cliente":
        return redirect("/mi-cuenta/")

    persona_id = request.session.get("backhome_user_id")
    errores = []
    tipo_documentos = []
    nueva_foto = None
    foto_anterior = None
    foto_validada = None
    extension_foto = None

    try:
        with connection.cursor() as cursor:

            # Consultar información actual
            cursor.execute("""
                SELECT
                    primer_nombre,
                    segundo_nombre,
                    primer_apellido,
                    segundo_apellido,
                    t_documento_id,
                    n_documento,
                    email,
                    numero_tel,
                    foto_perfil
                FROM personas
                WHERE id_persona = %s
                LIMIT 1
            """, [persona_id])

            fila = cursor.fetchone()

            if not fila:
                request.session.flush()
                return redirect("/iniciar-sesion/")

            columnas = [
                columna[0] for columna in cursor.description
            ]

            persona = dict(zip(columnas, fila))
            foto_anterior = persona.get("foto_perfil")

            # Consultar tipos de documento
            cursor.execute("""
                SELECT id_t_doc, n_doc
                FROM tipo_documento
                ORDER BY n_doc
            """)

            tipo_documentos = cursor.fetchall()

            if request.method == "POST":

                datos = {
                    "primer_nombre": request.POST.get("primer_nombre", "").strip(),
                    "segundo_nombre": request.POST.get("segundo_nombre", "").strip(),
                    "primer_apellido": request.POST.get("primer_apellido", "").strip(),
                    "segundo_apellido": request.POST.get("segundo_apellido", "").strip(),
                    "t_documento_id": request.POST.get("t_documento_id", "").strip(),
                    "n_documento": request.POST.get("n_documento", "").strip(),
                    "email": request.POST.get("email", "").strip().lower(),
                    "numero_tel": request.POST.get("numero_tel", "").strip(),
                }

                # Validar campos obligatorios
                for campo in [
                    "primer_nombre",
                    "primer_apellido",
                    "n_documento",
                    "email",
                    "numero_tel",
                    "t_documento_id"
                ]:
                    if not datos[campo]:
                        errores.append(
                            "Completa todos los campos obligatorios."
                        )
                        break

                # Validar correo electrónico
                if datos["email"]:
                    try:
                        validate_email(datos["email"])
                    except ValidationError:
                        errores.append(
                            "Ingresa un correo electrónico válido."
                        )

                # Validar tipo de documento
                tipos_validos = [
                    str(tipo[0]) for tipo in tipo_documentos
                ]

                if datos["t_documento_id"] not in tipos_validos:
                    errores.append(
                        "Selecciona un tipo de documento válido."
                    )

                # Comprobar correo duplicado
                if datos["email"]:
                    cursor.execute("""
                        SELECT id_persona
                        FROM personas
                        WHERE LOWER(email) = LOWER(%s)
                        AND id_persona != %s
                        LIMIT 1
                    """, [datos["email"], persona_id])

                    if cursor.fetchone():
                        errores.append(
                            "Este correo electrónico ya está registrado."
                        )

                # Comprobar documento duplicado
                if datos["n_documento"]:
                    cursor.execute("""
                        SELECT id_persona
                        FROM personas
                        WHERE n_documento = %s
                        AND id_persona != %s
                        LIMIT 1
                    """, [datos["n_documento"], persona_id])

                    if cursor.fetchone():
                        errores.append(
                            "Este número de documento ya está registrado."
                        )

                # Validar fotografía, si se seleccionó una
                foto = request.FILES.get("foto_perfil")

                if foto:
                    if foto.size > 5 * 1024 * 1024:
                        errores.append(
                            "La fotografía no puede superar los 5 MB."
                        )
                    else:
                        try:
                            imagen = Image.open(foto)
                            formato = imagen.format

                            formatos_permitidos = {
                                "JPEG": "jpg",
                                "PNG": "png",
                                "WEBP": "webp",
                            }

                            if formato not in formatos_permitidos:
                                errores.append(
                                    "La imagen debe estar en formato JPG, PNG o WEBP."
                                )
                            else:
                                imagen.verify()
                                foto.seek(0)

                                extension = formatos_permitidos[formato]

                                foto_validada = foto
                                extension_foto = extension

                        except (UnidentifiedImageError, OSError, ValueError):
                            errores.append(
                                "El archivo seleccionado no es una imagen válida."
                            )

                # Actualizar información si no hay errores
                if not errores:

                    if foto_validada:
                        nombre_archivo = (
                            f"perfiles/usuario_{persona_id}_"
                            f"{uuid4().hex}.{extension_foto}"
                        )

                    nueva_foto = default_storage.save(
                        nombre_archivo,
                        foto_validada
                    )

                    if nueva_foto:
                        cursor.execute("""
                            UPDATE personas
                            SET
                                primer_nombre = %s,
                                segundo_nombre = %s,
                                primer_apellido = %s,
                                segundo_apellido = %s,
                                t_documento_id = %s,
                                n_documento = %s,
                                email = %s,
                                numero_tel = %s,
                                foto_perfil = %s
                            WHERE id_persona = %s
                        """, [
                            datos["primer_nombre"],
                            datos["segundo_nombre"] or None,
                            datos["primer_apellido"],
                            datos["segundo_apellido"] or None,
                            datos["t_documento_id"],
                            datos["n_documento"],
                            datos["email"],
                            datos["numero_tel"],
                            nueva_foto,
                            persona_id
                        ])

                    else:
                        cursor.execute("""
                            UPDATE personas
                            SET
                                primer_nombre = %s,
                                segundo_nombre = %s,
                                primer_apellido = %s,
                                segundo_apellido = %s,
                                t_documento_id = %s,
                                n_documento = %s,
                                email = %s,
                                numero_tel = %s
                            WHERE id_persona = %s
                        """, [
                            datos["primer_nombre"],
                            datos["segundo_nombre"] or None,
                            datos["primer_apellido"],
                            datos["segundo_apellido"] or None,
                            datos["t_documento_id"],
                            datos["n_documento"],
                            datos["email"],
                            datos["numero_tel"],
                            persona_id
                        ])

                    # Actualizar nombre de sesión
                    nombre_completo = " ".join(
                        valor for valor in [
                            datos["primer_nombre"],
                            datos["segundo_nombre"],
                            datos["primer_apellido"],
                            datos["segundo_apellido"]
                        ] if valor
                    )

                    request.session["backhome_nombre"] = nombre_completo

                    # Eliminar fotografía anterior si se reemplazó
                    if nueva_foto and foto_anterior:
                        if default_storage.exists(foto_anterior):
                            default_storage.delete(foto_anterior)

                    messages.success(
                        request,
                        "¡Tus datos se actualizaron correctamente!"
                    )

                    return redirect("mi_cuenta")

                # Conservar los datos si hay errores
                persona.update(datos)

    except DatabaseError as error:
        # Si se guardó una imagen pero falló la actualización,
        # eliminar el archivo nuevo para evitar archivos huérfanos.
        if nueva_foto and default_storage.exists(nueva_foto):
            default_storage.delete(nueva_foto)

        print("ERROR AL EDITAR EL PERFIL:", repr(error))
        errores.append(
            "No fue posible actualizar la información. Inténtalo nuevamente."
        )

    return render(request, "cliente/editar_perfil.html", {
        "persona": persona,
        "tipo_documentos": tipo_documentos,
        "errores": errores,
    })
