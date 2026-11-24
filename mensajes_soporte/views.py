from django.shortcuts import render, redirect
from django.db import connection, DatabaseError
from django.contrib import messages


def mensajes_soporte(request):

    # Verificar que el usuario haya iniciado sesión
    if not request.session.get("backhome_user_id"):
        return redirect("/iniciar-sesion/?next=/mensajes-soporte/")

    # Verificar que sea un cliente
    if request.session.get("backhome_rol") != "cliente":
        return redirect("mi_cuenta")

    persona_id = request.session.get("backhome_user_id")

# Obtener el identificador del cliente
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_cliente
            FROM cliente
            WHERE persona_id = %s
            LIMIT 1
        """, [persona_id])

        resultado = cursor.fetchone()

    if not resultado:
        messages.error(
            request,
            "No se encontró un registro de cliente asociado a tu cuenta."
        )
        return redirect("mi_cuenta")

    cliente_id = resultado[0]

    if request.method == "POST":
        mensaje = request.POST.get("mensaje", "").strip()

        if not mensaje:
            messages.error(
                request,
                "Por favor, escribe un mensaje antes de enviarlo."
            )
        else:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO mensajes_de_soporte
                            (cliente_id, mensaje_cliente)
                        VALUES (%s, %s)
                    """, [cliente_id, mensaje])

                messages.success(
                    request,
                    "¡Tu mensaje de soporte fue enviado correctamente!"
                )

                return redirect("mensajes_soporte")

            except DatabaseError as error:
                print("ERROR AL ENVIAR MENSAJE DE SOPORTE:", repr(error))

                messages.error(
                    request,
                    "No fue posible enviar tu mensaje. Inténtalo nuevamente."
                )

    return render(
        request,
        "mensajes_soporte/mensajes_soporte.html"
    )
