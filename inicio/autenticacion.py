
from django.contrib.auth.hashers import check_password, make_password
from django.utils.crypto import constant_time_compare
from django.db import DatabaseError, connection
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods


def _destino_por_rol(rol):
    return "/panel/" if rol == "administrador" else "/mi-cuenta/"


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

    return render(request, "inicio/iniciar_sesion.html", {
        "error": error,
        "next": request.POST.get(
            "next",
            request.GET.get("next", "")
        ),
    })


@require_http_methods(["GET"])
def mi_cuenta(request):
    """Destino provisional del cliente mientras se construye su dashboard."""

    if not request.session.get("backhome_user_id"):
        return redirect("/iniciar-sesion/?next=/mi-cuenta/")

    if request.session.get("backhome_rol") == "administrador":
        return redirect("/panel/")

    if request.session.get("backhome_rol") != "cliente":
        request.session.flush()
        return redirect("/iniciar-sesion/")

    return render(request, "inicio/mi_cuenta.html", {
        "nombre": request.session.get("backhome_nombre", "Cliente"),
    })


@require_http_methods(["POST"])
def cerrar_sesion(request):
    request.session.flush()
    return redirect("/")
