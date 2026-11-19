
from decimal import Decimal, InvalidOperation

from django.shortcuts import render
from django.db import connection, DatabaseError, transaction


def pagina_principal(request):
    buscar_refugio = request.GET.get("buscar_refugio", "").strip()
    buscar_consejo = request.GET.get("buscar_consejo", "").strip()

    mensaje_donacion = ""
    tipo_mensaje = ""

    if request.method == "POST":
        correo = request.POST.get("correo", "").strip()
        monto_texto = request.POST.get("monto", "").strip()
        mensaje = request.POST.get("mensaje", "").strip()
        refugio_id = request.POST.get("refugio_id", "").strip()

        try:
            monto = Decimal(monto_texto)

            if not monto.is_finite() or monto <= 0 or monto > Decimal("99999999.99"):
                raise ValueError

            if len(mensaje) > 255:
                raise ValueError

            with transaction.atomic():
                with connection.cursor() as cursor:

                    # Verificar que el correo pertenezca a un cliente activo.
                    cursor.execute("""
                        SELECT c.id_cliente
                        FROM cliente c
                        INNER JOIN personas p
                            ON p.id_persona = c.persona_id
                        WHERE LOWER(p.email) = LOWER(%s)
                          AND p.estado = 'activo'
                        LIMIT 1
                    """, [correo])

                    cliente = cursor.fetchone()

                    if not cliente:
                        raise LookupError(
                            "No encontramos una cuenta de cliente activa "
                            "con ese correo."
                        )

                    cliente_id = cliente[0]

                    # Validar el refugio seleccionado.
                    if refugio_id:
                        cursor.execute("""
                            SELECT id_refugio
                            FROM refugios
                            WHERE id_refugio = %s
                              AND estado = 'activo'
                        """, [refugio_id])

                        if not cursor.fetchone():
                            raise LookupError(
                                "El refugio seleccionado no está disponible."
                            )
                    else:
                        refugio_id = None

                    # Guardar la donación.
                    cursor.execute("""
                        INSERT INTO donaciones
                            (cliente_id, refugio_id, monto, mensaje, estado)
                        VALUES (%s, %s, %s, %s, 'pendiente')
                    """, [
                        cliente_id,
                        refugio_id,
                        monto,
                        mensaje or None
                    ])

                    numero_donacion = cursor.lastrowid

            mensaje_donacion = (
                f"¡Muchas gracias por tu aporte! "
                f"Tu donación quedó registrada con el número "
                f"#{numero_donacion} y está pendiente de confirmación."
            )
            tipo_mensaje = "exito"

        except (InvalidOperation, ValueError):
            mensaje_donacion = (
                "Por favor, ingresa un monto válido y un mensaje "
                "de máximo 255 caracteres."
            )
            tipo_mensaje = "error"

        except LookupError as error:
            mensaje_donacion = str(error)
            tipo_mensaje = "error"

        except DatabaseError:
            mensaje_donacion = (
                "No fue posible registrar tu donación. "
                "Por favor, inténtalo nuevamente."
            )
            tipo_mensaje = "error"

    # Consultar refugios activos.
    consulta_refugios = """
        SELECT
            r.id_refugio,
            r.nombre,
            r.descripcion,
            r.direccion,
            r.telefono,
            r.email,
            l.n_localidad AS localidad
        FROM refugios r
        INNER JOIN localidades l
            ON l.id_localidad = r.localidad_id
        WHERE r.estado = 'activo'
    """

    parametros_refugios = []

    if buscar_refugio:
        consulta_refugios += """
            AND (
                r.nombre LIKE %s
                OR r.descripcion LIKE %s
                OR r.direccion LIKE %s
                OR l.n_localidad LIKE %s
            )
        """
        valor = f"%{buscar_refugio}%"
        parametros_refugios.extend([valor] * 4)

    consulta_refugios += " ORDER BY r.id_refugio DESC LIMIT 12"

    # Consultar consejos publicados.
    consulta_consejos = """
        SELECT id, titulo, descripcion, created_at
        FROM consejos
        WHERE 1 = 1
    """

    parametros_consejos = []

    if buscar_consejo:
        consulta_consejos += """
            AND (titulo LIKE %s OR descripcion LIKE %s)
        """
        valor = f"%{buscar_consejo}%"
        parametros_consejos.extend([valor, valor])

    consulta_consejos += " ORDER BY created_at DESC LIMIT 6"

    with connection.cursor() as cursor:

        cursor.execute(consulta_refugios, parametros_refugios)
        columnas = [col[0] for col in cursor.description]
        refugios = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute(consulta_consejos, parametros_consejos)
        columnas = [col[0] for col in cursor.description]
        consejos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

    return render(request, "inicio/pagina_principal.html", {
        "refugios": refugios,
        "consejos": consejos,
        "buscar_refugio": buscar_refugio,
        "buscar_consejo": buscar_consejo,
        "mensaje_donacion": mensaje_donacion,
        "tipo_mensaje": tipo_mensaje,
    })
