
from datetime import datetime
from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

from xml.sax.saxutils import escape

from .consultas import (
    TABLAS_REPORTES,
    obtener_configuracion,
    construir_consulta,
)


def valor_legible(valor):

    if valor is None:
        return ""

    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y %H:%M:%S")

    return str(valor)


def obtener_datos(request):

    tabla = request.GET.get("tabla", "seguimiento")

    if tabla not in TABLAS_REPORTES:
        tabla = "seguimiento"

    configuracion = obtener_configuracion(tabla)

    resultado = construir_consulta(
        request,
        tabla,
        configuracion
    )

    return tabla, configuracion, resultado


def exportar_excel(tabla, resultado):

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte BackHome"

    color_principal = "C77FA2"
    color_claro = "FCEEF4"

    encabezados = resultado["seleccionadas"]
    filas = resultado["filas"]

    ultima_columna = len(encabezados)

    hoja.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=ultima_columna
    )

    titulo = hoja.cell(
        row=1,
        column=1,
        value=f"BACKHOME - {TABLAS_REPORTES[tabla]}"
    )

    titulo.font = Font(
        bold=True,
        size=16,
        color="FFFFFF"
    )

    titulo.fill = PatternFill(
        "solid",
        fgColor=color_principal
    )

    titulo.alignment = Alignment(
        horizontal="center"
    )

    hoja.merge_cells(
        start_row=2,
        start_column=1,
        end_row=2,
        end_column=ultima_columna
    )

    hoja.cell(
        row=2,
        column=1,
        value=(
            "Generado el: "
            + datetime.now().strftime("%d/%m/%Y %H:%M")
        )
    )

    hoja.cell(row=2, column=1).font = Font(
        italic=True,
        color="777777"
    )

    # ENCABEZADOS

    fila_encabezado = 4

    for numero, nombre in enumerate(encabezados, 1):

        celda = hoja.cell(
            row=fila_encabezado,
            column=numero,
            value=nombre.replace("_", " ").title()
        )

        celda.font = Font(
            bold=True,
            color="FFFFFF"
        )

        celda.fill = PatternFill(
            "solid",
            fgColor=color_principal
        )

        celda.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

    # REGISTROS

    for numero_fila, fila in enumerate(filas, 5):

        for numero_columna, valor in enumerate(fila, 1):

            celda = hoja.cell(
                row=numero_fila,
                column=numero_columna,
                value=valor_legible(valor)
            )

            if numero_fila % 2 == 0:
                celda.fill = PatternFill(
                    "solid",
                    fgColor=color_claro
                )

            celda.alignment = Alignment(
                vertical="center",
                wrap_text=True
            )

    # ANCHOS AUTOMÁTICOS

    for columna in range(1, ultima_columna + 1):

        letra = get_column_letter(columna)

        ancho = 15

        for celda in hoja[letra]:
            if celda.value is not None:
                ancho = max(
                    ancho,
                    min(len(str(celda.value)) + 3, 35)
                )

        hoja.column_dimensions[letra].width = ancho

    hoja.freeze_panes = "A5"
    hoja.auto_filter.ref = (
        f"A4:{get_column_letter(ultima_columna)}"
        f"{max(4, len(filas) + 4)}"
    )

    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)

    respuesta = HttpResponse(
        salida.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    respuesta["Content-Disposition"] = (
        f'attachment; filename="BackHome_{tabla}.xlsx"'
    )

    return respuesta


def exportar_pdf(tabla, resultado):

    salida = BytesIO()

    documento = SimpleDocTemplate(
        salida,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    estilos = getSampleStyleSheet()

    elementos = []

    titulo = Paragraph(
        f"<b>BACKHOME - {escape(TABLAS_REPORTES[tabla])}</b>",
        estilos["Title"]
    )

    elementos.append(titulo)

    elementos.append(
        Paragraph(
            "Reporte administrativo | Generado el "
            + datetime.now().strftime("%d/%m/%Y %H:%M"),
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 8 * mm))

    encabezados = resultado["seleccionadas"]
    filas = resultado["filas"]

    datos = [
        [nombre.replace("_", " ").title() for nombre in encabezados]
    ]

    for fila in filas:
        datos.append([
            valor_legible(valor)
            for valor in fila
        ])

    if not filas:
        datos.append([
            "No se encontraron registros con los filtros seleccionados."
        ])

    cantidad_columnas = max(len(datos[0]), 1)

    if not filas:
        datos[1] = [
            "No se encontraron registros."
        ] + [""] * (cantidad_columnas - 1)

    ancho_disponible = (
        landscape(A4)[0] - 24 * mm
    )

    ancho_columna = ancho_disponible / cantidad_columnas

    tabla_pdf = Table(
        datos,
        colWidths=[ancho_columna] * cantidad_columnas,
        repeatRows=1
    )

    tabla_pdf.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C77FA2")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("LEADING", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E8D9E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#FCEEF4")
            ]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    elementos.append(tabla_pdf)

    elementos.append(Spacer(1, 6 * mm))

    elementos.append(
        Paragraph(
            f"Total de registros encontrados: {len(filas)}",
            estilos["Normal"]
        )
    )

    documento.build(elementos)

    salida.seek(0)

    respuesta = HttpResponse(
        salida.getvalue(),
        content_type="application/pdf"
    )

    respuesta["Content-Disposition"] = (
        f'attachment; filename="BackHome_{tabla}.pdf"'
    )

    return respuesta


@require_GET
def gestion_reportes(request):

    tabla = request.GET.get("tabla", "seguimiento")

    contexto_base = {
        "tablas": [
            {"nombre": nombre, "titulo": titulo}
            for nombre, titulo in TABLAS_REPORTES.items()
        ],
        "tabla_actual": tabla,
        "generado": False,
        "error": None,
        "columnas": [],
        "fechas": [],
        "encabezados": [],
        "filas": [],
        "total": 0,
        "buscar": "",
        "fecha_columna": "",
        "fecha_desde": "",
        "fecha_hasta": "",
        "ordenar": "",
        "direccion": "DESC",
        "filtros_aplicados": [],
    }

    if tabla not in TABLAS_REPORTES:
        tabla = "seguimiento"

    contexto_base["tabla_actual"] = tabla

    try:

        tabla, configuracion, resultado = obtener_datos(request)

        generar = request.GET.get("generar") == "1"
        formato = request.GET.get("formato", "")

        if formato == "excel":
            return exportar_excel(tabla, resultado)

        if formato == "pdf":
            return exportar_pdf(tabla, resultado)

        contexto_base.update({
            "titulo_tabla": TABLAS_REPORTES[tabla],

            "columnas": [
                {
                    "nombre": columna["nombre"],
                    "seleccionada": (
                        columna["nombre"]
                        in resultado["seleccionadas"]
                    ),
                    "es_fecha": columna["es_fecha"],
                    "es_numerico": columna["es_numerico"],
                    "valor_filtro": request.GET.get(
                        f'filtro_{columna["nombre"]}', ""
                    ),
                    "operador": request.GET.get(
                        f'operador_{columna["nombre"]}',
                        "contiene"
                    ),
                }
                for columna in configuracion["columnas"]
            ],

            "fechas": configuracion["fechas"],
            "encabezados": resultado["seleccionadas"],

            "filas": (
                resultado["filas"] if generar else []
            ),

            "total": (
                len(resultado["filas"]) if generar else 0
            ),

            "generado": generar,
            "buscar": resultado["buscar"],
            "fecha_columna": resultado["fecha_columna"],
            "fecha_desde": resultado["fecha_desde"],
            "fecha_hasta": resultado["fecha_hasta"],
            "ordenar": resultado["ordenar"],
            "direccion": resultado["direccion"],
            "filtros_aplicados": resultado["filtros_aplicados"],
        })

    except Exception as error:

        contexto_base["error"] = str(error)

        try:
            configuracion = obtener_configuracion(tabla)

            contexto_base["columnas"] = [
                {
                    "nombre": columna["nombre"],
                    "seleccionada": True,
                    "es_fecha": columna["es_fecha"],
                    "es_numerico": columna["es_numerico"],
                    "valor_filtro": request.GET.get(
                        f'filtro_{columna["nombre"]}', ""
                    ),
                    "operador": request.GET.get(
                        f'operador_{columna["nombre"]}',
                        "contiene"
                    ),
                }
                for columna in configuracion["columnas"]
            ]

            contexto_base["fechas"] = configuracion["fechas"]

        except Exception:
            pass

    return render(
        request,
        "reportes/gestion_reportes.html",
        contexto_base
    )
