from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods


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

    return render(request, "cliente/mi_cuenta.html", {
        "nombre": request.session.get("backhome_nombre", "Cliente"),
    })