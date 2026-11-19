from django.shortcuts import render, redirect
from django.db import connection, transaction
from django.contrib import messages
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def gestion_consejos(request):

    if request.method == "POST":

        accion = request.POST.get("accion", "").strip()

        # CREAR CONSEJO
        if accion == "crear":

            titulo = request.POST.get("titulo", "").strip()
            descripcion = request.POST.get("descripcion", "").strip()

            if not titulo or not descripcion:
                messages.error(
                    request,
                    "Debes completar el título y la descripción."
                )
                return redirect("gestion_consejos")

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO consejos (titulo, descripcion)
                            VALUES (%s, %s)
                        """, [titulo, descripcion])

                messages.success(
                    request,
                    "El consejo se creó correctamente."
                )

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo crear el consejo: {error}"
                )

            return redirect("gestion_consejos")

        # EDITAR CONSEJO
        elif accion == "editar":

            id_consejo = request.POST.get("id_consejo")
            titulo = request.POST.get("titulo", "").strip()
            descripcion = request.POST.get("descripcion", "").strip()

            if not id_consejo or not titulo or not descripcion:
                messages.error(
                    request,
                    "Debes completar todos los campos."
                )
                return redirect("gestion_consejos")

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE consejos
                            SET titulo = %s,
                                descripcion = %s
                            WHERE id = %s
                        """, [titulo, descripcion, id_consejo])

                        if cursor.rowcount == 0:
                            cursor.execute("""
                                SELECT id
                                FROM consejos
                                WHERE id = %s
                            """, [id_consejo])

                            if not cursor.fetchone():
                                messages.error(
                                    request,
                                    "El consejo que intentas editar no existe."
                                )
                                return redirect("gestion_consejos")

                messages.success(
                    request,
                    "El consejo se actualizó correctamente."
                )

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo actualizar el consejo: {error}"
                )

            return redirect("gestion_consejos")

        # ELIMINAR CONSEJO
        elif accion == "eliminar":

            id_consejo = request.POST.get("id_consejo")

            if not id_consejo:
                messages.error(request, "No se recibió el consejo que deseas eliminar.")
                return redirect("gestion_consejos")

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            DELETE FROM consejos
                            WHERE id = %s
                        """, [id_consejo])

                        eliminado = cursor.rowcount

                if eliminado:
                    messages.success(
                        request,
                        "El consejo se eliminó correctamente."
                    )
                else:
                    messages.error(
                        request,
                        "El consejo que intentas eliminar no existe."
                    )

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo eliminar el consejo: {error}"
                )

            return redirect("gestion_consejos")

    # CONSULTAR CONSEJOS
    buscar = request.GET.get("buscar", "").strip()

    consulta = """
        SELECT
            id,
            titulo,
            descripcion,
            created_at,
            updated_at
        FROM consejos
        WHERE 1 = 1
    """

    parametros = []

    if buscar:
        consulta += """
            AND (
                titulo LIKE %s
                OR descripcion LIKE %s
            )
        """

        valor = f"%{buscar}%"
        parametros.extend([valor, valor])

    consulta += " ORDER BY created_at DESC"

    with connection.cursor() as cursor:
        cursor.execute(consulta, parametros)

        columnas = [columna[0] for columna in cursor.description]

        consejos = [
            dict(zip(columnas, fila))
            for fila in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT COUNT(*)
            FROM consejos
        """)

        total_consejos = cursor.fetchone()[0] or 0

    contexto = {
        "consejos": consejos,
        "buscar": buscar,
        "total_consejos": total_consejos,
    }

    return render(
        request,
        "consejos/gestion_consejos.html",
        contexto
    )