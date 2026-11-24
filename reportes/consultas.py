
from datetime import date
from django.db import connection
from django.core.exceptions import ValidationError


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

COLUMNAS_PRIVADAS = {
    "password",
    "remember_token",
    "token",
    "access_token",
    "refresh_token",
}


def obtener_configuracion(tabla):

    if tabla not in TABLAS_REPORTES:
        raise ValidationError("El módulo seleccionado no es válido.")

    with connection.cursor() as cursor:
        cursor.execute(f"SHOW COLUMNS FROM `{tabla}`")
        resultado = cursor.fetchall()

    columnas = []

    for fila in resultado:
        nombre = fila[0]
        tipo = fila[1].lower()

        if nombre.lower() in COLUMNAS_PRIVADAS:
            continue

        es_fecha = any(
            palabra in tipo
            for palabra in ("date", "time", "year")
        )

        es_numerico = any(
            palabra in tipo
            for palabra in (
                "int", "decimal", "float",
                "double", "numeric"
            )
        )

        columnas.append({
            "nombre": nombre,
            "tipo": tipo,
            "es_fecha": es_fecha,
            "es_numerico": es_numerico,
        })

    if not columnas:
        raise ValidationError(
            "No hay columnas disponibles para este reporte."
        )

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

    columnas_validas = configuracion["nombres"]

    seleccionadas = request.GET.getlist("columnas")

    if not seleccionadas:
        seleccionadas = columnas_validas[:]

    seleccionadas = [
        c for c in seleccionadas if c in columnas_validas
    ]

    if not seleccionadas:
        raise ValidationError(
            "Debes seleccionar al menos una columna."
        )

    condiciones = []
    parametros = []

    buscar = request.GET.get("buscar", "").strip()

    # BÚSQUEDA GENERAL

    if buscar:
        partes = []

        for columna in columnas_validas:
            partes.append(
                f"CAST(`{columna}` AS CHAR) LIKE %s"
            )
            parametros.append(f"%{buscar}%")

        condiciones.append(
            "(" + " OR ".join(partes) + ")"
        )

    # FILTRO DE FECHAS

    fecha_columna = request.GET.get(
        "fecha_columna", ""
    )

    fecha_desde = request.GET.get(
        "fecha_desde", ""
    ).strip()

    fecha_hasta = request.GET.get(
        "fecha_hasta", ""
    ).strip()

    if fecha_columna:

        if fecha_columna not in configuracion["fechas"]:
            raise ValidationError(
                "La columna de fecha seleccionada no es válida."
            )

        if fecha_desde and fecha_hasta:
            if fecha_desde > fecha_hasta:
                raise ValidationError(
                    "La fecha inicial no puede ser posterior a la fecha final."
                )

        if fecha_desde:
            condiciones.append(
                f"DATE(`{fecha_columna}`) >= %s"
            )
            parametros.append(fecha_desde)

        if fecha_hasta:
            condiciones.append(
                f"DATE(`{fecha_columna}`) <= %s"
            )
            parametros.append(fecha_hasta)

    # FILTROS INDIVIDUALES

    filtros_aplicados = []

    operadores_permitidos = {
        "contiene",
        "igual",
        "diferente",
        "mayor",
        "menor",
    }

    for columna in columnas_validas:

        valor = request.GET.get(
            f"filtro_{columna}", ""
        ).strip()

        if not valor:
            continue

        operador = request.GET.get(
            f"operador_{columna}", "contiene"
        )

        if operador not in operadores_permitidos:
            continue

        es_numerico = any(
            c["nombre"] == columna and c["es_numerico"]
            for c in configuracion["columnas"]
        )

        if operador in ("mayor", "menor") and not es_numerico:
            continue

        if operador == "contiene":
            condiciones.append(
                f"CAST(`{columna}` AS CHAR) LIKE %s"
            )
            parametros.append(f"%{valor}%")

        elif operador == "igual":
            condiciones.append(f"`{columna}` = %s")
            parametros.append(valor)

        elif operador == "diferente":
            condiciones.append(f"`{columna}` != %s")
            parametros.append(valor)

        elif operador == "mayor":
            condiciones.append(f"`{columna}` > %s")
            parametros.append(valor)

        elif operador == "menor":
            condiciones.append(f"`{columna}` < %s")
            parametros.append(valor)

        filtros_aplicados.append({
            "columna": columna,
            "operador": operador,
            "valor": valor,
        })

    # CONSULTA SQL

    consulta = (
        f"SELECT {', '.join(f'`{c}`' for c in seleccionadas)} "
        f"FROM `{tabla}`"
    )

    if condiciones:
        consulta += " WHERE " + " AND ".join(condiciones)

    # ORDENAMIENTO

    ordenar = request.GET.get("ordenar", "")

    if ordenar not in columnas_validas:
        ordenar = seleccionadas[0]

    direccion = request.GET.get(
        "direccion", "DESC"
    ).upper()

    if direccion not in ("ASC", "DESC"):
        direccion = "DESC"

    consulta += f" ORDER BY `{ordenar}` {direccion}"

    # LÍMITE DE SEGURIDAD

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
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "ordenar": ordenar,
        "direccion": direccion,
    }
