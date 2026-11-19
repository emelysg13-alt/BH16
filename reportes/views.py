import csv
from datetime import datetime
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .consultas import (
    TABLAS_REPORTES,
    obtener_configuracion,
    construir_consulta,
)


@require_GET
def gestion_reportes(request):

    tabla = request.GET.get("tabla", "seguimiento")

    if tabla not in TABLAS_REPORTES:
        tabla = "seguimiento"

    try:
        configuracion = obtener_configuracion(tabla)

        resultado = construir_consulta(
            request,
            tabla,
            configuracion
        )

        generar = request.GET.get("generar") == "1"
        formato = request.GET.get("formato", "")

        etiquetas = {
            "columnas": [
                {
                    "nombre": columna["nombre"],
                    "seleccionada": (
                        columna["nombre"] in resultado["seleccionadas"]
                    ),
                    "es_fecha": columna["es_fecha"],
                    "es_numerico": columna["es_numerico"],
                }
                for columna in configuracion["columnas"]
            ],
            "fechas": configuracion["fechas"],
            "numericas": configuracion["numericas"],
        }

        encabezados = resultado["seleccionadas"]

        if formato == "excel":

            salida = StringIO()
            escritor = csv.writer(salida, delimiter=";")

            escritor.writerow(["BACKHOME - " + TABLAS_REPORTES[tabla]])
            escritor.writerow([
                "Generado el",
                datetime.now().strftime("%d/%m/%Y %H:%M")
            ])
            escritor.writerow([])
            escritor.writerow(encabezados)

            for fila in resultado["filas"]:
                escritor.writerow([
                    valor.isoformat(sep=" ")
                    if hasattr(valor, "isoformat")
                    else valor
                    for valor in fila
                ])

            respuesta = HttpResponse(
                "\ufeff" + salida.getvalue(),
                content_type="text/csv; charset=utf-8"
            )

            respuesta["Content-Disposition"] = (
                f'attachment; filename="BackHome_{tabla}.csv"'
            )

            return respuesta

        contexto = {
            "tablas": [
                {"nombre": nombre, "titulo": titulo}
                for nombre, titulo in TABLAS_REPORTES.items()
            ],
            "tabla_actual": tabla,
            "titulo_tabla": TABLAS_REPORTES[tabla],
            "columnas": etiquetas["columnas"],
            "fechas": etiquetas["fechas"],
            "numericas": etiquetas["numericas"],
            "encabezados": encabezados,
            "filas": resultado["filas"] if generar else [],
            "total": len(resultado["filas"]) if generar else 0,
            "generado": generar,
            "buscar": resultado["buscar"],
            "fecha_columna": resultado["fecha_columna"],
            "fecha_desde": resultado["fecha_desde"],
            "fecha_hasta": resultado["fecha_hasta"],
            "ordenar": resultado["ordenar"],
            "direccion": resultado["direccion"],
            "filtros_aplicados": resultado["filtros_aplicados"],
            "error": None,
            "es_pdf": formato == "pdf",
        }

        return render(
            request,
            "reportes/gestion_reportes.html",
            contexto
        )

    except Exception as error:

        return render(
            request,
            "reportes/gestion_reportes.html",
            {
                "tablas": [
                    {"nombre": nombre, "titulo": titulo}
                    for nombre, titulo in TABLAS_REPORTES.items()
                ],
                "tabla_actual": tabla,
                "titulo_tabla": TABLAS_REPORTES[tabla],
                "columnas": [],
                "fechas": [],
                "numericas": [],
                "encabezados": [],
                "filas": [],
                "total": 0,
                "generado": False,
                "error": str(error),
                "es_pdf": False,
            }
        )
