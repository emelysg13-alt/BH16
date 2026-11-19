from django.db import DatabaseError, connection
from django.shortcuts import redirect


class BackHomeAccessMiddleware:
    """Protege el panel administrativo y el espacio privado del cliente."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        es_panel = (
            request.path == "/panel"
            or request.path.startswith("/panel/")
        )

        es_cliente = (
            request.path == "/mi-cuenta"
            or request.path.startswith("/mi-cuenta/")
        )

        if es_panel or es_cliente:
            persona_id = request.session.get("backhome_user_id")
            rol = request.session.get("backhome_rol")

            requerido = (
                "administrador" if es_panel else "cliente"
            )

            if not persona_id or rol != requerido:
                return redirect(
                    f"/iniciar-sesion/?next={request.path}"
                )

            try:
                with connection.cursor() as cursor:

                    if requerido == "administrador":
                        cursor.execute("""
                            SELECT a.id_admin
                            FROM administrador a
                            INNER JOIN personas p
                                ON p.id_persona = a.persona_id
                            WHERE p.id_persona = %s
                            AND p.estado = 'activo'
                            LIMIT 1
                        """, [persona_id])

                    else:
                        cursor.execute("""
                            SELECT c.id_cliente
                            FROM cliente c
                            INNER JOIN personas p
                                ON p.id_persona = c.persona_id
                            WHERE p.id_persona = %s
                            AND p.estado = 'activo'
                            LIMIT 1
                        """, [persona_id])

                    autorizado = cursor.fetchone()

            except DatabaseError:
                autorizado = None

            if not autorizado:
                request.session.flush()
                return redirect(
                    f"/iniciar-sesion/?next={request.path}"
                )

        return self.get_response(request)