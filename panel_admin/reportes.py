
import csv
import re
from datetime import datetime
from io import StringIO

from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


# ==========================================================
# TABLAS DISPONIBLES PARA GENERAR REPORTES
# Los nombres corresponden al SQL real de BackHome.
# ==========================================================

TABLAS_REPORTES = {
    "personas": "Usuarios y personas",
    "administrador": "Administradores",
    "cliente": "Clientes",
    "tipo_documento": "Tipos de documento",
    "localidades": "Localidades",
    "lugares": "Lugares y direcciones",
    "animal": "Animales",
    "animal_domestico": "Animales domésticos",
    "animal_exotico": "Animales exóticos",
    "prioridades": "Prioridades",
    "seguimiento": "Seguimientos",
    "seguimiento_perdido": "Seguimientos de animales perdidos",
    "seguimiento_encontrado": "Seguimientos de animales encontrados",
    "refugios": "Refugios",
    "historial_estado_seguimiento": "Historial de estados",
    "actualizaciones_seguimiento": "Actualizaciones de seguimientos",
    "imagenes_seguimiento": "Imágenes de seguimientos",
    "gestion_seguimiento": "Gestiones administrativas",
    "mensajes_de_soporte": "Mensajes de soporte",
    "consejos": "Consejos",
    "control_acciones": "Control de acciones",
    "ingresos_refugio": "Ingresos a refugios",
    "coincidencias": "Coincidencias",
    "donaciones": "Donaciones",
}


# No se permite exportar contraseñas ni tokens.
COLUMNAS_PRIVADAS = {
    "password",
    "remember_token",
}


def obtener_columnas(tabla):
    """Obtiene las columnas reales de una tabla permitida."""

    with connection.cursor() as cursor:
        cursor.execute(f"SHOW COLUMNS FROM `{tabla}`")
        resultado = cursor.fetchall()

    columnas = []

    for fila in resultado:
        nombre = fila[0]
        tipo = fila[1].lower()

        if nombre.lower() in COLUMNAS_PRIVADAS:
            continue

        columnas.append({
            "nombre": nombre,
            "tipo": tipo,
            "es_fecha": any(
                palabra in tipo
                for palabra in ["date", "time", "year"]
            ),
            "es_numerico": any(
                palabra in tipo
                for palabra in [
                    "int", "decimal", "float",
                    "double", "numeric"
                ]
            ),
        })

    return columnas


def obtener_configuracion(tabla):
    columnas = obtener_columnas(tabla)

    return {
        "columnas": columnas,
        "nombres": [c["nombre"] for c in columnas],
        "fechas": [
            c["nombre"] for c in columnas if c["es_fecha"]
        ],
        "numericas": [
            c["nombre"] for c in columnas if c["es_numerico"]
        ],
    }


def construir_consulta(request, tabla, configuracion):
    """Construye una consulta segura con filtros combinables."""

    columnas_validas = configuracion["nombres"]

    seleccionadas = request.GET.getlist("columnas")

    if seleccionadas:
        seleccionadas = [
            columna for columna in seleccionadas
            if columna in columnas_validas
        ]
    else:
        seleccionadas = columnas_validas[:]

    if not seleccionadas:
        seleccionadas = columnas_validas[:]

    nombres_sql = ", ".join(
        f"`{columna}`" for columna in seleccionadas
    )

    consulta = f"SELECT {nombres_sql} FROM `{tabla}` WHERE 1=1"
    parametros = []

    # ------------------------------------------------------
    # BÚSQUEDA GENERAL
    # ------------------------------------------------------

    buscar = request.GET.get("buscar", "").strip()

    if buscar:
        condiciones = []

        for columna in columnas_validas:
            condiciones.append(f"CAST(`{columna}` AS CHAR) LIKE %s")
            parametros.append(f"%{buscar}%")

        consulta += " AND (" + " OR ".join(condiciones) + ")"

    # ------------------------------------------------------
    # FILTRO DE FECHAS
    # ------------------------------------------------------

    fecha_columna = request.GET.get("fecha_columna", "")

    if fecha_columna in configuracion["fechas"]:

        fecha_desde = request.GET.get("fecha_desde", "").strip()
        fecha_hasta = request.GET.get("fecha_hasta", "").strip()

        if fecha_desde:
            consulta += f" AND DATE(`{fecha_columna}`) >= %s"
            parametros.append(fecha_desde)

        if fecha_hasta:
            consulta += f" AND DATE(`{fecha_columna}`) <= %s"
            parametros.append(fecha_hasta)

    # ------------------------------------------------------
    # FILTROS POR COLUMNA
    # ------------------------------------------------------

    filtros_aplicados = []

    for columna in columnas_validas:

        valor = request.GET.get(
            f"filtro_{columna}", ""
        ).strip()

        if not valor:
            continue

        operador = request.GET.get(
            f"operador_{columna}", "contiene"
        )

        if operador not in [
            "contiene",
            "igual",
            "diferente",
            "mayor",
            "menor",
        ]:
            operador = "contiene"

        if operador == "contiene":
            consulta += f" AND CAST(`{columna}` AS CHAR) LIKE %s"
            parametros.append(f"%{valor}%")

        elif operador == "igual":
            consulta += f" AND `{columna}` = %s"
            parametros.append(valor)

        elif operador == "diferente":
            consulta += f" AND `{columna}` != %s"
            parametros.append(valor)

        elif operador == "mayor":
            consulta += f" AND `{columna}` > %s"
            parametros.append(valor)

        elif operador == "menor":
            consulta += f" AND `{columna}` < %s"
            parametros.append(valor)

        filtros_aplicados.append({
            "columna": columna,
            "operador": operador,
            "valor": valor,
        })

    # ------------------------------------------------------
    # ORDENAMIENTO
    # ------------------------------------------------------

    ordenar = request.GET.get("ordenar", "")

    if ordenar not in columnas_validas:
        ordenar = seleccionadas[0]

    direccion = request.GET.get("direccion", "DESC").upper()

    if direccion not in ["ASC", "DESC"]:
        direccion = "DESC"

    consulta += f" ORDER BY `{ordenar}` {direccion}"

    # Límite para proteger el rendimiento.
    consulta += " LIMIT 10000"

    with connection.cursor() as cursor:
        cursor.execute(consulta, parametros)
        filas = cursor.fetchall()

    return {
        "seleccionadas": seleccionadas,
        "filas": filas,
        "buscar": buscar,
        "filtros_aplicados": filtros_aplicados,
        "fecha_columna": fecha_columna,
        "fecha_desde": request.GET.get("fecha_desde", ""),
        "fecha_hasta": request.GET.get("fecha_hasta", ""),
        "ordenar": ordenar,
        "direccion": direccion,
    }


# ==========================================================
# VISTA PRINCIPAL
# ==========================================================

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
            "panel_admin/gestion_reportes.html",
            contexto
        )

    except Exception as error:

        return render(
            request,
            "panel_admin/gestion_reportes.html",
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
