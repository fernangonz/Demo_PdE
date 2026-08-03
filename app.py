"""Herramienta web: Riesgo por cambio climático en puertos.

Secciones (barra lateral):
  - Puertos: desplegable + mapa de España con cada puerto como punto.
  - Impactos a evaluar: carga el inventario de matriz de impactos y muestra la
    lista única de modos de fallo / modos de parada.

Ejecutar desde VSCode / terminal:
    streamlit run app.py
"""

from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass
from hashlib import sha1

import io

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from core.data_loader import (
    auditar_fuentes_excel,
    cargar_lista_puertos,
    directorio_fuente,
    directorios_datos_display,
    lista_modos_fallo,
    cargar_datos_clima,
    resumen_unicos_clima,
    tabla_impactos_indicadores,
    cargar_configuracion_puerto,
    cargar_preguntar_impactos,
    cargar_relacion_modelos_activos_indicadores,
    cargar_umbrales_curvas_dano,
    cargar_tipo_de_uo,
    firma_cache_excel,
    fuentes_excel_faltantes,
    _normalizar,
)
from core.branding import (
    BRAND_NAVY,
    abrir_cabecera_branding,
    inyectar_estilos_branding,
    mostrar_logo_puertos,
    mostrar_pie_branding,
)
from core.datos import RepositorioDatos
from core.fuentes_datos import fuente, nombre_archivo_display
from core.impact_models import (
    export_resumen_activo_xlsx,
    html_tabla_resumen_activo,
    iteraciones_desde_calculo_activo,
    resumen_activo_desde_calculo_activo,
)
from core.modelos.catalogo_impactos import (
    CATALOGO_MODOS_IMPACTO,
    COLUMNAS_LISTA_MODELOS,
    entradas_por_tipo_impacto,
    titulo_modo_display,
    titulo_modo_impacto,
)
from core.modelos.flujos import buscar_diagrama
from core.modelos.impacto.calculo_activo import calcular_impactos_puerto
from core.modelos.impacto.impactos_no_factibles import FiltroImpactosNoFactibles
from core.modelos.impacto.validacion_puerto import (
    ResultadoValidacionPuerto,
    resumen_validacion,
    validar_puerto_antes_calculo,
)
from core.modelos.impacto.pi_agitacion import ParametrosEntrada
from core.modelos.impacto.pi_agitacion.interpretacion import (
    regla_variacion_cierre,
    resolver_unidad_cierre,
)
from core.modelos.impacto.pi_agitacion.utilidades import (
    columna_por_patron,
    fila_configuracion,
    nombre_activo_resumen,
)
from core.modelos.fichas_modelo import FichaModelo, nombre_motor_display, resolver_ficha
from core.modelos.impacto.vista_resultados import (
    construir_vista_resultados_activo,
    listar_activos_config,
)

st.set_page_config(
    page_title="Riesgo climático en puertos",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Claves internas de vista (coinciden con las secciones existentes).
V_PUERTOS = "Puertos"
V_HERRAMIENTA = "__herramienta__"
V_TIPOS_UO = fuente("tipos_uo").seccion
V_IMPACTOS = fuente("impactos").seccion
V_RELACION_IVC = fuente("relacion_ivc").seccion
V_UMBRALES = fuente("umbrales").seccion
V_RELACION_MODELOS = fuente("relacion_modelos").seccion
V_CONFIG_PUERTO = fuente("config_puerto").seccion
V_CONFIG_IMPACTOS_NO_FACTIBLES = "Configuración de impactos no factibles"
V_CLIMA = fuente("clima").seccion
V_EXPLORADOR_INDICADORES = "Explorador de indicadores"
V_MODELOS_IMPACTOS = "Modelos de impactos"
V_MODELOS_ECONOMICOS = "Modelos económicos"
V_CALCULO_IMPACTOS = "Cálculo de impactos"
V_ADAPTACION = "__adaptacion__"
V_RESUMEN = "__resumen__"


@dataclass(frozen=True)
class _ItemMenu:
    etiqueta: str
    vista: str


@dataclass(frozen=True)
class _GrupoMenu:
    titulo: str
    items: tuple[_ItemMenu, ...] = ()
    icono: str = ""  # Icono Material (p. ej. ":material/home:") mostrado antes del título.


GRUPOS_MENU: tuple[_GrupoMenu, ...] = (
    _GrupoMenu(
        "DATOS BASE",
        (
            _ItemMenu("Tipos de UO", V_TIPOS_UO),
            _ItemMenu("Impactos a evaluar", V_IMPACTOS),
            _ItemMenu("Relación impactos vs variables climáticas", V_RELACION_IVC),
            _ItemMenu("Relación umbrales y curvas de daño vs activos", V_UMBRALES),
            _ItemMenu("Relación modelos, activos e indicadores", V_RELACION_MODELOS),
            _ItemMenu("Excels de entrada", V_HERRAMIENTA),
        ),
        icono=":material/home:",
    ),
    _GrupoMenu(
        "INICIO",
        (
            _ItemMenu("Puertos", V_PUERTOS),
        ),
    ),
    _GrupoMenu(
        "CONFIGURACIÓN",
        (
            _ItemMenu("Configuración del puerto", V_CONFIG_PUERTO),
            _ItemMenu(
                "Configuración de impactos no factibles",
                V_CONFIG_IMPACTOS_NO_FACTIBLES,
            ),
        ),
        icono=":material/settings:",
    ),
    _GrupoMenu(
        "CLIMA",
        (
            _ItemMenu("Indicadores climáticos", V_CLIMA),
            _ItemMenu("Explorador de indicadores", V_EXPLORADOR_INDICADORES),
        ),
        icono=":material/cloud:",
    ),
    _GrupoMenu(
        "MODELOS",
        (
            _ItemMenu("Modelos de impactos", V_MODELOS_IMPACTOS),
            _ItemMenu("Modelos económicos", V_MODELOS_ECONOMICOS),
        ),
        icono=":material/account_tree:",
    ),
    _GrupoMenu(
        "RIESGO",
        (
            _ItemMenu("Cálculo de impactos", V_CALCULO_IMPACTOS),
        ),
        icono=":material/warning:",
    ),
    _GrupoMenu("ADAPTACIÓN", icono=":material/eco:"),
)

VISTAS_MENU: frozenset[str] = frozenset(
    {V_ADAPTACION, V_RESUMEN}
    | {item.vista for grupo in GRUPOS_MENU for item in grupo.items}
)

# Orden de los tipos de impacto (estado límite): ELO, ELS, ELU; el resto al final.
ORDEN_ESTADO = {"elo": 0, "els": 1, "elu": 2}

# Opción del desplegable que muestra todos los puertos.
TODOS = "Todos los puertos"

# Vista por defecto de España (coincide con la vista general peninsular).
CENTRO_ESPANA = [40.2, -3.5]
ZOOM_ESPANA = 6

# Zoom que se aplica al hacer foco sobre un puerto concreto.
ZOOM_PUERTO = 12

# Versión del estilo del mapa base: al cambiar, se invalida el `mapa_base`
# cacheado en `st.session_state` y se reconstruye con el nuevo estilo (p. ej.
# colores de marcadores).
MAPA_STYLE_VERSION = 2


def _fmt_lat(lat: float) -> str:
    """Devuelve la latitud con 4 decimales, símbolo ° y hemisferio (N/S)."""
    hemi = "N" if lat >= 0 else "S"
    return f"{abs(lat):.4f}° {hemi}"


def _fmt_lon(lon: float) -> str:
    """Devuelve la longitud con 4 decimales, símbolo ° y hemisferio (E/W)."""
    hemi = "E" if lon >= 0 else "W"
    return f"{abs(lon):.4f}° {hemi}"


# ---------------------------------------------------------------------------
# Carga de datos (cacheada; se invalida al cambiar los Excel en data_modelos / data_secciones)
# ---------------------------------------------------------------------------
def _firma_datos_excel() -> str:
    """Clave de caché ligada a la fecha/tamaño de los Excel."""
    return firma_cache_excel()


def _limpiar_resultados_calculo() -> None:
    """Elimina resultados de cálculo en sesión (fuerza vista fresca)."""
    st.session_state.pop("resultado_pi", None)
    st.session_state.pop("resultado_calculo_activo", None)
    st.session_state.pop("resultado_calculo_puerto", None)
    st.session_state.pop("ultima_validacion_puerto", None)
    st.session_state.pop("_huella_filtro_nf_resultado", None)


def _invalidar_resultados_si_cambian_excel() -> None:
    """Borra resultados de modelos si el usuario ha actualizado los Excel."""
    firma = _firma_datos_excel()
    if st.session_state.get("_firma_excel") != firma:
        st.session_state["_firma_excel"] = firma
        _limpiar_resultados_calculo()


def _mensaje_excel_no_encontrado(meta) -> str:
    carpeta = directorio_fuente(meta)
    return (
        f"No se encontró `{nombre_archivo_display(meta)}` en `{carpeta}`. "
        "Coloca o actualiza el Excel en esa carpeta; la herramienta se alimenta "
        "solo de esos archivos."
    )


def _mostrar_alerta_estado_excel() -> None:
    """Alerta global si falta algún Excel de entrada."""
    auditoria = auditar_fuentes_excel()
    faltantes = [a for a in auditoria if not a.encontrado]
    carpetas_inexistentes = [
        a.carpeta for a in auditoria
        if not a.carpeta.is_dir()
    ]

    if carpetas_inexistentes:
        for carpeta in dict.fromkeys(carpetas_inexistentes):
            st.error(
                f"No existe la carpeta de datos `{carpeta}`. "
                "Créala y coloca ahí los Excel de entrada."
            )

    if faltantes:
        st.error(f"Faltan {len(faltantes)} archivos Excel de entrada.")
        lineas = [
            f"- **{a.seccion}** → `{a.archivo}` en `{a.carpeta}`"
            for a in faltantes
        ]
        st.markdown("\n".join(lineas))
        st.caption(
            f"Carpetas de datos: {directorios_datos_display()}. "
            "Al guardar un Excel, la caché se invalida automáticamente."
        )
    elif not carpetas_inexistentes:
        with st.expander("Excel de entrada (OK)", expanded=False):
            for a in auditoria:
                if a.ruta:
                    st.caption(f"**{a.seccion}**")
                    st.code(str(a.ruta), language=None)


@st.cache_data(show_spinner="Cargando lista de puertos...")
def _obtener_puertos(_firma_excel: str):
    return cargar_lista_puertos()


@st.cache_data(show_spinner="Cargando inventario de impactos...")
def _obtener_modos(_firma_excel: str):
    return lista_modos_fallo()


@st.cache_data(show_spinner="Cargando indicadores climáticos...")
def _obtener_clima(_firma_excel: str):
    return cargar_datos_clima()


@st.cache_data(show_spinner="Cargando relación impactos-indicadores...")
def _obtener_relacion(_firma_excel: str):
    return tabla_impactos_indicadores()


@st.cache_data(show_spinner="Cargando configuración del puerto...")
def _obtener_config_puerto(_firma_excel: str):
    return cargar_configuracion_puerto()


@st.cache_data(show_spinner="Cargando impactos a preguntar...")
def _obtener_preguntar_impactos(_firma_excel: str):
    return cargar_preguntar_impactos()


UMBRALES_LOADER_VERSION = 2  # Incrementar si cambia qué hojas se muestran en la UI.


@st.cache_data(show_spinner="Cargando umbrales y curvas de daño...")
def _obtener_umbrales_curvas(_firma_excel: str, loader_version: int = UMBRALES_LOADER_VERSION):
    return cargar_umbrales_curvas_dano()


@st.cache_data(show_spinner="Cargando tipos de UO...")
def _obtener_tipos_uo(_firma_excel: str):
    return cargar_tipo_de_uo()


@st.cache_data(show_spinner="Cargando relación modelos–activos–indicadores...")
def _obtener_relacion_modelos(_firma_excel: str):
    return cargar_relacion_modelos_activos_indicadores()


@st.cache_data(show_spinner="Cargando datos del puerto...")
def _obtener_repositorio(_firma_excel: str):
    return RepositorioDatos.cargar()


# ---------------------------------------------------------------------------
# Indicador sutil de fuente de datos (solo visible al pulsar ⓘ)
# ---------------------------------------------------------------------------
def _detalle_fuente(f: dict) -> None:
    """Muestra ruta o descripción de una fuente dentro del popover."""
    st.caption(f["nombre"])
    if f.get("ruta"):
        st.code(f["ruta"], language=None)
    if f.get("descripcion"):
        st.caption(f["descripcion"])
    if f.get("detalle"):
        st.caption(f["detalle"])


def _popover_fuente(fuentes: list[dict], *, key: str) -> None:
    """Botón ⓘ que abre un popover con la fuente (desplegable si hay varias)."""
    with st.popover("ⓘ", help="Fuente de datos"):
        if len(fuentes) == 1:
            _detalle_fuente(fuentes[0])
        else:
            nombres = [f["nombre"] for f in fuentes]
            sel = st.selectbox(
                "Archivo",
                nombres,
                label_visibility="collapsed",
                key=f"fuente_{key}",
            )
            _detalle_fuente(next(f for f in fuentes if f["nombre"] == sel))


def _cabecera_seccion(titulo: str, fuentes: list[dict] | None = None, *, key: str = "") -> None:
    """Subheader con indicador ⓘ alineado a la derecha."""
    if fuentes:
        c1, c2 = st.columns([24, 1], vertical_alignment="center")
        with c1:
            st.subheader(titulo)
        with c2:
            _popover_fuente(fuentes, key=key or titulo)
    else:
        st.subheader(titulo)


def _indicador_fuente(fuentes: list[dict], *, key: str) -> None:
    """Solo el ⓘ en la esquina superior derecha (secciones sin título único)."""
    _, c2 = st.columns([40, 1])
    with c2:
        _popover_fuente(fuentes, key=key)


# ---------------------------------------------------------------------------
# Exportación de tablas (CSV ; + Excel)
# ---------------------------------------------------------------------------
# Columnas de la tabla Relación impactos-indicadores (orden de visualización = exportación).
COLUMNAS_RELACION = [
    "Nº",
    "Tipo de impacto",
    "Modos de fallo / Modos de parada",
    "Variable",
    "Activo físico u Operacional",
    "Tipo activo/servicio",
]


def _preparar_descargas(
    df: pd.DataFrame,
    hoja: str = "Datos",
    *,
    column_order: list[str] | None = None,
) -> tuple[bytes, bytes]:
    """Genera bytes CSV (sep ;, utf-8-sig) y XLSX del DataFrame, sin índice."""
    if column_order:
        cols = [c for c in column_order if c in df.columns]
        export = df[cols].copy() if cols else df.copy()
    else:
        export = df.copy()

    csv_bytes = export.to_csv(index=False, sep=";").encode("utf-8-sig")
    buffer_xlsx = io.BytesIO()
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name=hoja[:31])
    buffer_xlsx.seek(0)
    return csv_bytes, buffer_xlsx.getvalue()


def _botones_descarga(
    df: pd.DataFrame,
    nombre_base: str,
    hoja: str = "Datos",
    *,
    column_order: list[str] | None = None,
    key_prefix: str | None = None,
) -> None:
    """Muestra botones Descargar CSV y Descargar Excel del DataFrame indicado."""
    csv_bytes, xlsx_bytes = _preparar_descargas(df, hoja=hoja, column_order=column_order)
    clave = key_prefix or nombre_base
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(
            "Descargar Excel",
            data=xlsx_bytes,
            file_name=f"{nombre_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{clave}_xlsx",
        )
    with col_d2:
        st.download_button(
            "Descargar CSV",
            data=csv_bytes,
            file_name=f"{nombre_base}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{clave}_csv",
        )


def _altura_tabla(n: int, altura_max: int = 560) -> int:
    """Altura del dataframe según nº de filas (compacta con pocas filas)."""
    # Sin suelo fijo de 110px: en tablas de 1–2 filas dejaba hueco vacío
    # bajo la última fila (línea/artefacto en el borde redondeado).
    return min(max(n * 36 + 42, 56), altura_max)


def _column_config_relleno(cfg: dict, cols: list[str]) -> dict:
    """Quita el ancho fijo de la última columna para que llene el espacio sobrante."""
    if not cfg or not cols:
        return {k: v for k, v in (cfg or {}).items() if k in cols}
    filtrado = {k: v for k, v in cfg.items() if k in cols}
    ultima = cols[-1]
    if ultima not in filtrado:
        return filtrado
    col = dict(filtrado[ultima])
    col["width"] = None
    filtrado[ultima] = col
    return filtrado


def _serializar_celda_tabla(valor: object) -> str:
    """Evita errores de PyArrow cuando una columna mezcla int y str."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor)


def _mostrar_tabla(
    df: pd.DataFrame,
    *,
    column_order: list[str] | None = None,
    column_config: dict | None = None,
    altura_max: int = 560,
    conservar_columnas_vacias: bool = False,
) -> None:
    """Tabla ajustada: ancho completo, altura proporcional y columnas configuradas."""
    cols = column_order or list(df.columns)
    cols = [c for c in cols if c in df.columns]
    data = df[cols].copy() if cols else df.copy()

    # Quitar columnas totalmente vacías (evitan columnas fantasma).
    if not conservar_columnas_vacias:
        vacias = [
            c for c in data.columns
            if data[c].isna().all()
            or data[c].astype(str).str.strip().isin(("", "nan", "None")).all()
        ]
    else:
        vacias = [
            c for c in data.columns
            if str(c).startswith("col_")
            and (
                data[c].isna().all()
                or data[c].astype(str).str.strip().isin(("", "nan", "None")).all()
            )
        ]
    if vacias:
        data = data.drop(columns=vacias)
        cols = [c for c in cols if c not in vacias]

    for col in list(data.columns):
        if col == "Valor" or pd.api.types.is_object_dtype(data[col]):
            data[col] = data[col].map(_serializar_celda_tabla)

    kwargs: dict = {
        "data": data,
        "use_container_width": True,
        "hide_index": True,
        "height": _altura_tabla(len(data), altura_max),
    }
    if column_config and cols:
        kwargs["column_config"] = _column_config_relleno(column_config, list(data.columns))
    st.dataframe(**kwargs)


def _config_columnas_clima(columnas: list[str]) -> dict:
    """Anchos sugeridos para columnas de indicadores climáticos."""
    cfg = {}
    for col in columnas:
        n = col.lower()
        if col in ("Indicador", "Descripción") or "indicador" in n or "descripcion" in n:
            cfg[col] = st.column_config.TextColumn(col, width="large")
        elif col in ("Mes", "Percentil", "Lon", "Lat"):
            cfg[col] = st.column_config.TextColumn(col, width="small")
        else:
            cfg[col] = st.column_config.TextColumn(col, width="medium")
    return cfg


def _mostrar_tabla_relacion(df: pd.DataFrame) -> None:
    """Tabla de relación impactos-indicadores."""
    _mostrar_tabla(
        df,
        column_order=COLUMNAS_RELACION,
        column_config={
            "Nº": st.column_config.NumberColumn("Nº", width="small"),
            "Tipo de impacto": st.column_config.TextColumn("Tipo de impacto", width="small"),
            "Modos de fallo / Modos de parada": st.column_config.TextColumn(
                "Modos de fallo / Modos de parada", width="large"
            ),
            "Variable": st.column_config.TextColumn("Variable", width="medium"),
            "Activo físico u Operacional": st.column_config.TextColumn(
                "Activo físico u Operacional", width="medium"
            ),
            "Tipo activo/servicio": st.column_config.TextColumn(
                "Tipo activo/servicio", width="medium"
            ),
        },
    )


def _mostrar_tabla_puertos(df: pd.DataFrame) -> None:
    """Tabla de puertos."""
    orden = [c for c in ("puerto", "autoridad_portuaria", "lat", "lon") if c in df.columns]
    orden += [c for c in df.columns if c not in orden]
    cfg = {
        "puerto": st.column_config.TextColumn("Puerto", width="medium"),
        "autoridad_portuaria": st.column_config.TextColumn("Autoridad portuaria", width="medium"),
        "lat": st.column_config.NumberColumn("Lat", width="small", format="%.4f"),
        "lon": st.column_config.NumberColumn("Lon", width="small", format="%.4f"),
    }
    _mostrar_tabla(df, column_order=orden, column_config=cfg)


def _mostrar_tabla_impactos(df: pd.DataFrame) -> None:
    """Tabla de impactos."""
    _mostrar_tabla(
        df,
        column_order=["Impacto"],
        column_config={"Impacto": st.column_config.TextColumn("Impacto", width="large")},
    )


# ---------------------------------------------------------------------------
# Ventanas modales de consulta de datos
# ---------------------------------------------------------------------------
@st.dialog("Datos cargados", width="large")
def _dialogo_puertos(df: pd.DataFrame, info: dict) -> None:
    if info["origen"] != "excel":
        st.warning("Datos por defecto (no se encontró el Excel real).")
    st.markdown(f"**{len(df)} puertos cargados**")
    _mostrar_tabla_puertos(df)


@st.dialog("Resumen de indicadores climáticos", width="large")
def _dialogo_resumen_clima(info: dict) -> None:
    resumen = resumen_unicos_clima(info)
    st.caption("Valores únicos por campo (sin 'Valor' ni coordenadas)")
    _mostrar_tabla(
        resumen,
        column_order=["Campo", "Valores"],
        column_config={
            "Campo": st.column_config.TextColumn("Campo", width="medium"),
            "Valores": st.column_config.TextColumn("Valores", width="large"),
        },
    )


# ---------------------------------------------------------------------------
# Mapa
# ---------------------------------------------------------------------------
def construir_mapa(df: pd.DataFrame) -> folium.Map:
    """Mapa base de España con un punto por puerto.

    La figura es estable (siempre los mismos puntos y estilo): el acercamiento a
    un puerto NO se hace reconstruyendo el mapa, sino moviendo la vista con los
    parámetros `center`/`zoom` de `st_folium`. Así la transición es fluida.
    """
    df_geo = df.dropna(subset=["lat", "lon"])

    mapa = folium.Map(
        location=CENTRO_ESPANA,
        zoom_start=ZOOM_ESPANA,
        tiles="CartoDB positron",
        control_scale=True,
    )

    for _, fila in df_geo.iterrows():
        folium.CircleMarker(
            location=[fila["lat"], fila["lon"]],
            radius=6,
            color=BRAND_NAVY,
            weight=2,
            fill=False,
            fill_opacity=0,
            # El tooltip es el nombre del puerto: se usa para detectar el clic.
            tooltip=fila["puerto"],
            popup=folium.Popup(
                f"<b>{fila['puerto']}</b><br>Lat: {fila['lat']:.3f}<br>Lon: {fila['lon']:.3f}",
                max_width=250,
            ),
        ).add_to(mapa)

    return mapa


def _mapa_base(df: pd.DataFrame) -> folium.Map:
    """Construye el mapa una sola vez por sesión y lo reutiliza.

    Reutilizar el mismo objeto mantiene el HTML idéntico entre recargas, evita
    que `st_folium` vuelva a montar el componente y permite que el cambio de
    vista sea una animación suave.
    """
    if (
        "mapa_base" not in st.session_state
        or st.session_state.get("mapa_n_puertos") != len(df)
        or st.session_state.get("mapa_style_version") != MAPA_STYLE_VERSION
    ):
        st.session_state.mapa_base = construir_mapa(df)
        st.session_state.mapa_n_puertos = len(df)
        st.session_state.mapa_style_version = MAPA_STYLE_VERSION
    return st.session_state.mapa_base


# ---------------------------------------------------------------------------
# Herramienta (estado Excel y recarga de datos)
# ---------------------------------------------------------------------------
def _seccion_herramienta() -> None:
    st.subheader("Excels de entrada")
    if st.button("Recargar datos Excel", use_container_width=True, key="recargar_excel"):
        st.cache_data.clear()
        _limpiar_resultados_calculo()
        st.session_state.pop("_firma_excel", None)
        st.rerun()
    _mostrar_alerta_estado_excel()


# ---------------------------------------------------------------------------
# Menú superior (navegación)
# ---------------------------------------------------------------------------
def _vista_por_defecto_grupo(grupo: _GrupoMenu) -> str:
    if grupo.titulo == "ADAPTACIÓN":
        return V_ADAPTACION
    if grupo.titulo == "RESUMEN":
        return V_RESUMEN
    if grupo.items:
        return grupo.items[0].vista
    return V_PUERTOS


def _resolver_vista_navegacion() -> str:
    """Lee ?v= de la URL o mantiene la vista en session_state."""
    param = st.query_params.get("v")
    if isinstance(param, list):
        param = param[0] if param else None
    if param and param in VISTAS_MENU:
        st.session_state["nav_vista"] = param
    elif "nav_vista" not in st.session_state:
        st.session_state["nav_vista"] = V_PUERTOS
    return st.session_state["nav_vista"]


def _grupo_activo_para_vista(vista: str) -> str | None:
    for grupo in GRUPOS_MENU:
        if grupo.items and any(item.vista == vista for item in grupo.items):
            return grupo.titulo
        if not grupo.items and _vista_por_defecto_grupo(grupo) == vista:
            return grupo.titulo
    return None


def _ir_a_vista(vista: str) -> None:
    st.session_state["nav_vista"] = vista
    st.query_params["v"] = vista
    st.rerun()


def _menu_navegacion_popovers(vista_actual: str) -> None:
    """Menu superior con desplegables nativos de Streamlit (clic fiable).

    Se emiten markers auxiliares (ocultos por CSS) para permitir que
    core/branding.py estilice:
      - `.pde-nav-slot`   -> franja blanca continua que agrupa los popovers.
      - `.pde-nav-brand`  -> primera seccion (DATOS BASE) destacada mas grande.
      - `.pde-nav-active` -> subrayado navy bajo la seccion activa.
    """
    grupo_activo = _grupo_activo_para_vista(vista_actual)
    # Ancho proporcional al texto para que no se corten (DATOS BASE algo mayor).
    pesos = [max(1.0, len(g.titulo) * 0.11 + (0.7 if g.icono else 0.3)) for g in GRUPOS_MENU]
    pesos[0] += 0.6  # DATOS BASE destacado.
    nav_cols = st.columns(pesos, gap="small")

    for idx, (col, grupo) in enumerate(zip(nav_cols, GRUPOS_MENU)):
        activo = grupo.titulo == grupo_activo
        etiqueta = f"{grupo.icono} {grupo.titulo}".strip() if grupo.icono else grupo.titulo
        with col:
            if idx == 0:
                st.markdown(
                    '<span class="pde-nav-slot"></span>', unsafe_allow_html=True
                )
                st.markdown(
                    '<span class="pde-nav-brand"></span>', unsafe_allow_html=True
                )
            if activo:
                st.markdown(
                    '<span class="pde-nav-active"></span>', unsafe_allow_html=True
                )
            if grupo.items:
                with st.popover(etiqueta):
                    for item in grupo.items:
                        if st.button(
                            item.etiqueta,
                            key=f"nav_{grupo.titulo}_{item.vista}",
                            use_container_width=True,
                        ):
                            _ir_a_vista(item.vista)
            else:
                vista = _vista_por_defecto_grupo(grupo)
                if st.button(
                    etiqueta,
                    key=f"nav_{grupo.titulo}",
                    use_container_width=True,
                ):
                    _ir_a_vista(vista)


def _cabecera_branding_y_menu() -> str:
    """Cabecera institucional + menu desplegable convencional."""
    inyectar_estilos_branding()
    vista = _resolver_vista_navegacion()
    col_logo, col_nav = abrir_cabecera_branding()
    with col_logo:
        mostrar_logo_puertos()
    with col_nav:
        _menu_navegacion_popovers(vista)
    return vista


def _seccion_en_desarrollo(nombre_grupo: str) -> None:
    st.subheader(nombre_grupo)
    st.info("Sección en desarrollo. Próximamente estará disponible en esta herramienta.")


def _render_vista(vista: str) -> None:
    """Despacha a la vista existente según la clave de navegación."""
    if vista == V_PUERTOS:
        _seccion_puertos()
    elif vista == V_HERRAMIENTA:
        _seccion_herramienta()
    elif vista == V_TIPOS_UO:
        _seccion_tipos_uo()
    elif vista == V_CLIMA:
        _seccion_clima()
    elif vista == V_EXPLORADOR_INDICADORES:
        _seccion_explorador_indicadores()
    elif vista == V_IMPACTOS:
        _seccion_impactos()
    elif vista == V_RELACION_IVC:
        _seccion_relacion()
    elif vista == V_UMBRALES:
        _seccion_umbrales_curvas()
    elif vista == V_RELACION_MODELOS:
        _seccion_relacion_modelos()
    elif vista == V_CONFIG_PUERTO:
        _seccion_configuracion_puerto()
    elif vista == V_CONFIG_IMPACTOS_NO_FACTIBLES:
        _seccion_preguntar_impactos()
    elif vista == V_MODELOS_IMPACTOS:
        _seccion_modelos_impactos()
    elif vista == V_MODELOS_ECONOMICOS:
        _seccion_modelos_economicos()
    elif vista == V_CALCULO_IMPACTOS:
        _seccion_calculo_impactos()
    elif vista == V_ADAPTACION:
        _seccion_en_desarrollo("ADAPTACIÓN")
    elif vista == V_RESUMEN:
        _seccion_en_desarrollo("RESUMEN")
    else:
        st.warning(f"Vista no configurada: {vista}")


# ---------------------------------------------------------------------------
# Sección: Puertos
# ---------------------------------------------------------------------------
def _seccion_puertos() -> None:
    df, info = _obtener_puertos(_firma_datos_excel())
    meta = fuente("puertos")

    if info["origen"] == "excel":
        _indicador_fuente(
            [{"nombre": nombre_archivo_display(meta), "ruta": info["ruta"]}],
            key="puertos",
        )
    else:
        _indicador_fuente(
            [{
                "nombre": nombre_archivo_display(meta),
                "descripcion": "Sin Excel; datos incorporados en la aplicación.",
            }],
            key="puertos",
        )

    # Consulta de datos en la vista principal (no en barra lateral).
    if info["origen"] != "excel":
        st.warning(_mensaje_excel_no_encontrado(meta) + " Se muestra la lista por defecto de Puertos del Estado.")

    puertos = sorted(df["puerto"].dropna().unique().tolist())
    opciones = [TODOS] + puertos
    _ajustar_selectbox("puerto_sel", opciones)
    if "puerto_sel" not in st.session_state:
        st.session_state.puerto_sel = TODOS

    col_izq, col_der = st.columns([1, 2], gap="large")

    with col_izq:
        st.subheader("Puertos")
        st.caption("Selecciona un puerto para centrar el mapa.")
        st.selectbox(
            "Puerto",
            options=opciones,
            key="puerto_sel",
            label_visibility="collapsed",
        )

        puerto_sel = st.session_state.puerto_sel

        if puerto_sel != TODOS:
            fila = df[df["puerto"] == puerto_sel].iloc[0]
            st.markdown(f"### {puerto_sel}")
            if "autoridad_portuaria" in df.columns and pd.notna(fila.get("autoridad_portuaria")):
                st.write(f"**Autoridad Portuaria:** {fila['autoridad_portuaria']}")
            lat, lon = fila.get("lat"), fila.get("lon")
            if pd.notna(lat) and pd.notna(lon):
                lat_txt = fila.get("lat_grados")
                lon_txt = fila.get("lon_grados")
                lat_ok = pd.notna(lat_txt) and str(lat_txt).strip() not in {"", "nan"}
                lon_ok = pd.notna(lon_txt) and str(lon_txt).strip() not in {"", "nan"}
                lat_str = str(lat_txt).strip() if lat_ok else _fmt_lat(float(lat))
                lon_str = str(lon_txt).strip() if lon_ok else _fmt_lon(float(lon))
                st.write(f"**Latitud:** {lat_str} · **Longitud:** {lon_str}")
            else:
                st.info("Este puerto no tiene coordenadas; no aparecerá en el mapa.")

        st.metric("Puertos disponibles", len(puertos))

        with st.popover("Info ▾"):
            st.caption("Consulta y descarga de datos de puertos.")
            if st.button("Consultar datos", key="consultar_puertos", use_container_width=True):
                _dialogo_puertos(df, info)
            _botones_descarga(df, meta.archivo.lower(), hoja="Puertos")

    # Vista del mapa según la selección (centro y zoom).
    centro, zoom = CENTRO_ESPANA, ZOOM_ESPANA
    if puerto_sel != TODOS:
        sel = df[df["puerto"] == puerto_sel]
        if not sel.empty and pd.notna(sel.iloc[0]["lat"]) and pd.notna(sel.iloc[0]["lon"]):
            centro = [float(sel.iloc[0]["lat"]), float(sel.iloc[0]["lon"])]
            zoom = ZOOM_PUERTO

    salida = None
    with col_der:
        st.subheader("Mapa de puertos (España)")
        mapa = _mapa_base(df)
        # Key estable + center/zoom: la vista se desplaza de forma fluida (sin remontar).
        salida = st_folium(
            mapa,
            center=centro,
            zoom=zoom,
            height=560,
            use_container_width=True,
            returned_objects=["last_object_clicked_tooltip"],
            key="mapa_puertos",
        )

    # Clic en un punto del mapa -> seleccionar ese puerto y acercarse.
    if salida:
        clic = salida.get("last_object_clicked_tooltip")
        if clic and clic in puertos and clic != st.session_state.puerto_sel:
            st.session_state.puerto_sel = clic
            st.rerun()


# ---------------------------------------------------------------------------
# Sección: Tipos de UO
# ---------------------------------------------------------------------------
def _seccion_tipos_uo() -> None:
    meta = fuente("tipos_uo")
    try:
        df, info = _obtener_tipos_uo(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    _cabecera_seccion(
        meta.seccion,
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": f"Hoja «{info['hoja']}» · {info['total']} tipos",
        }],
        key="tipos_uo",
    )

    cols = list(df.columns)
    col_tipo = "Tipo de UO" if "Tipo de UO" in cols else cols[-1]
    _mostrar_tabla(
        df,
        column_order=cols,
        column_config={
            "Nº": st.column_config.NumberColumn("Nº", width="small"),
            col_tipo: st.column_config.TextColumn(col_tipo, width="large"),
        },
    )
    _botones_descarga(df, meta.archivo.lower(), hoja="Tipos de UO")


# ---------------------------------------------------------------------------
# Sección: Explorador de indicadores (.mat espacial / por puerto)
# ---------------------------------------------------------------------------
def _seccion_explorador_indicadores() -> None:
    import importlib

    import core.ui_explorador as ui_explorador

    # Forzar recarga: Streamlit a veces conserva una version antigua del modulo.
    ui_explorador = importlib.reload(ui_explorador)
    ui_explorador.render_explorador_indicadores()


# ---------------------------------------------------------------------------
# Sección: Indicadores climáticos
# ---------------------------------------------------------------------------
def _seccion_clima() -> None:
    meta = fuente("clima")
    try:
        info = _obtener_clima(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    variables = info["variables"]
    if not variables:
        st.warning("El Excel de clima no tiene hojas legibles.")
        return

    _indicador_fuente(
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": f"{len(variables)} hojas (variables climáticas)",
        }],
        key="clima",
    )

    col_izq, col_der = st.columns([1, 2], gap="large")

    with col_izq:
        st.subheader("Indicadores climáticos")
        variable = st.selectbox("Variable climática", options=variables, key="clima_var")
        datos_var = info["por_variable"][variable]

        escenarios = datos_var["escenarios"]

        esc_sel = st.selectbox("Escenario", options=["Todos"] + escenarios, key="clima_esc")

        # El año depende del escenario: Historic solo tiene su año (2005) y los
        # escenarios SSP no incluyen 2005. Se ofrecen solo los años con datos.
        if esc_sel == "Todos":
            anios_validos = datos_var["anios"]
        else:
            anios_validos = sorted({
                c["anio"]
                for c in datos_var["columnas_clima"]
                if c["escenario"] == esc_sel and c["anio"] is not None
            })
        anio_sel = st.selectbox(
            "Año (horizonte)",
            options=["Todos"] + [str(a) for a in anios_validos],
            key="clima_anio",
        )

        st.button("Restaurar filtros", on_click=_reset_filtros_clima, use_container_width=True)

        st.metric("Indicadores", len(datos_var["df"]))

        if st.button("Ver resumen (todas las variables)", use_container_width=True):
            _dialogo_resumen_clima(info)

    with col_der:
        st.subheader(variable)

        # Seleccionar las columnas de clima que coinciden con escenario/año.
        cols_clima = {
            c["columna"]
            for c in datos_var["columnas_clima"]
            if (esc_sel == "Todos" or c["escenario"] == esc_sel)
            and (anio_sel == "Todos" or str(c["anio"]) == anio_sel)
        }
        seleccionadas = set(datos_var["columnas_meta"]) | cols_clima
        # Conservar el orden original del Excel (Lon/Lat quedan al final).
        columnas = [c for c in datos_var["df"].columns if c in seleccionadas]

        df_mostrar = datos_var["df"][columnas] if columnas else datos_var["df"]
        if not cols_clima and (escenarios or anios):
            st.caption("No hay columna para esa combinación de escenario/año; se muestran solo los datos descriptivos.")

        st.caption(f"{len(df_mostrar)} de {len(datos_var['df'])} filas")
        _mostrar_tabla(
            df_mostrar,
            column_order=columnas,
            column_config=_config_columnas_clima(columnas),
        )
        _botones_descarga(df_mostrar, f"indicadores_{variable.lower().replace(' ', '_')}", hoja=variable)


def _seccion_impactos() -> None:
    meta = fuente("impactos")
    try:
        modos, info = _obtener_modos(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    _cabecera_seccion(
        meta.seccion,
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": f"{info['total']} impactos únicos · {len(info['hojas_leidas'])} hojas",
        }],
        key="impactos",
    )
    filtro = st.text_input("Filtrar", placeholder="Escribe para filtrar...", key="imp_filtro")
    st.button("Restaurar filtros", on_click=_reset_filtros_impactos)

    if filtro:
        modos_mostrar = [m for m in modos if filtro.lower() in m.lower()]
    else:
        modos_mostrar = modos
    df_impactos = pd.DataFrame({"Impacto": modos_mostrar})
    st.caption(f"{len(df_impactos)} de {len(modos)} impactos")
    _mostrar_tabla_impactos(df_impactos)
    _botones_descarga(df_impactos, "impactos", hoja="Impactos")


def _reset_filtros_clima() -> None:
    for k in ("clima_var", "clima_esc", "clima_anio"):
        st.session_state.pop(k, None)


def _reset_filtros_impactos() -> None:
    st.session_state.pop("imp_filtro", None)


def _tipos_impacto_opciones(df: pd.DataFrame) -> list[str]:
    """Tipos ELO/ELS/ELU presentes en el subconjunto, en orden metodológico."""
    presentes = {
        str(v).strip()
        for v in df["Tipo de impacto"].dropna()
        if str(v).strip()
    }
    ordenados = sorted(
        presentes,
        key=lambda t: (ORDEN_ESTADO.get(t.lower(), 99), t.lower()),
    )
    return ["Todos"] + ordenados


def _variables_opciones(df: pd.DataFrame) -> list[str]:
    """Variables climáticas presentes en el subconjunto."""
    vals = sorted(
        {str(v).strip() for v in df["Variable"].dropna() if str(v).strip()},
        key=str.lower,
    )
    return ["Todos"] + vals


def _modos_fallo_opciones(df: pd.DataFrame) -> list[str]:
    """Modos de fallo únicos (normalizados) presentes en el subconjunto."""
    modo_por_clave: dict[str, str] = {}
    for v in df["Modos de fallo / Modos de parada"].dropna():
        clave = _normalizar(v)
        if clave and clave not in modo_por_clave:
            etiqueta = str(v).strip().lower()
            modo_por_clave[clave] = etiqueta[:1].upper() + etiqueta[1:]
    return ["Todos"] + sorted(modo_por_clave.values(), key=str.lower)


def _ajustar_selectbox(key: str, opciones: list[str]) -> None:
    """Si la selección guardada ya no es válida, vuelve a 'Todos'."""
    actual = st.session_state.get(key)
    if actual is not None and actual not in opciones:
        st.session_state[key] = opciones[0]


def _reset_filtros_relacion() -> None:
    """Borra las keys de los filtros para que vuelvan a su valor por defecto."""
    for k in ("rel_filtro", "rel_tipo", "rel_var", "rel_modo", "rel_orden"):
        st.session_state.pop(k, None)


def _seccion_relacion() -> None:
    meta = fuente("relacion_ivc")
    try:
        df, info = _obtener_relacion(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    _cabecera_seccion(
        meta.seccion,
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": (
                f"Hoja «{info['hoja']}» · {info['total']} filas · "
                "matriz impacto–activo (misma fuente que umbrales)"
            ),
        }],
        key="relacion",
    )

    campos_orden = [
        "Nº",
        "Tipo de impacto",
        "Variable",
        "Modos de fallo / Modos de parada",
        "Activo físico u Operacional",
        "Tipo activo/servicio",
    ]

    # Fila 1: buscador (ancho) + Ordenar por.
    fila1_a, fila1_b = st.columns([3, 1])
    with fila1_a:
        filtro = st.text_input(
            "Filtrar", placeholder="Impacto, tipo, activo...", key="rel_filtro"
        )
    with fila1_b:
        orden_sel = st.selectbox(
            "Ordenar por", options=campos_orden, index=1, key="rel_orden"
        )

    # Fila 2: filtros dependientes (como escenario → año en clima).
    fila2_a, fila2_b, fila2_c = st.columns([1, 1, 2])

    tipos_opciones = _tipos_impacto_opciones(df)
    _ajustar_selectbox("rel_tipo", tipos_opciones)
    with fila2_a:
        tipo_sel = st.selectbox("Tipo de impacto", options=tipos_opciones, key="rel_tipo")

    df_tras_tipo = df if tipo_sel == "Todos" else df[df["Tipo de impacto"] == tipo_sel]
    variables_opciones = _variables_opciones(df_tras_tipo)
    _ajustar_selectbox("rel_var", variables_opciones)
    with fila2_b:
        var_sel = st.selectbox("Variable", options=variables_opciones, key="rel_var")

    df_tras_var = (
        df_tras_tipo if var_sel == "Todos" else df_tras_tipo[df_tras_tipo["Variable"] == var_sel]
    )
    modos_opciones = _modos_fallo_opciones(df_tras_var)
    _ajustar_selectbox("rel_modo", modos_opciones)
    with fila2_c:
        modo_sel = st.selectbox(
            "Modos de fallo / Modos de parada", options=modos_opciones, key="rel_modo"
        )

    st.button("Restaurar filtros", on_click=_reset_filtros_relacion)

    # Aplicar filtros en cascada sobre el dataframe.
    df_mostrar = df_tras_var
    if modo_sel != "Todos":
        clave_sel = _normalizar(modo_sel)
        df_mostrar = df_mostrar[
            df_mostrar["Modos de fallo / Modos de parada"].map(
                lambda x: _normalizar(x) == clave_sel
            )
        ]
    if filtro:
        f = filtro.lower()
        mask = df_mostrar.apply(
            lambda fila: fila.astype(str).str.lower().str.contains(f, regex=False).any(),
            axis=1,
        )
        df_mostrar = df_mostrar[mask]

    # Ordenación: por Tipo de impacto se respeta ELO, ELS, ELU; Nº numérico; resto alfabético.
    if orden_sel == "Tipo de impacto":
        clave = df_mostrar["Tipo de impacto"].astype(str).str.strip().str.lower().map(
            lambda t: ORDEN_ESTADO.get(t, 99)
        )
        df_mostrar = df_mostrar.assign(_orden=clave).sort_values("_orden", kind="stable")
    elif orden_sel == "Nº":
        df_mostrar = df_mostrar.sort_values("Nº", kind="stable")
    else:
        clave = df_mostrar[orden_sel].astype(str).str.strip().str.lower()
        df_mostrar = df_mostrar.assign(_orden=clave).sort_values("_orden", kind="stable")
    df_mostrar = df_mostrar.drop(columns="_orden", errors="ignore")

    # Nº se conserva tal cual viene del Excel (clave para cruzar con umbrales/curvas).
    st.caption(f"{len(df_mostrar)} de {len(df)} filas")
    if df_mostrar.empty:
        st.info("No hay filas para esa combinación de filtros.")
    else:
        _botones_descarga(
            df_mostrar,
            "relacion_impactos_listrelacion",
            hoja="ListRelacion impactos-indicador",
            column_order=COLUMNAS_RELACION,
        )
        _mostrar_tabla_relacion(df_mostrar)


def _reset_filtros_umbrales() -> None:
    st.session_state.pop("umb_filtro", None)


_TODAS_PESTANAS = "Todas"


def _df_con_pestana(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    """Añade columna Pestaña sin duplicar si ya existía (p. ej. caché o re-ejecución)."""
    tmp = df.copy()
    if "Pestaña" in tmp.columns:
        tmp = tmp.drop(columns=["Pestaña"])
    tmp.insert(0, "Pestaña", nombre)
    return tmp


def _filtrar_hojas_umbrales_ui(
    por_hoja: dict[str, pd.DataFrame],
    info: dict,
) -> dict[str, pd.DataFrame]:
    """Excluye UnidadMedida del listado y de «Todas las pestañas»."""
    hoja_um = info.get("hoja_unidad_medida")
    return {
        nombre: df
        for nombre, df in por_hoja.items()
        if nombre != hoja_um
        and not (
            "unidad" in _normalizar(nombre).replace("_", " ")
            and "medida" in _normalizar(nombre).replace("_", " ")
        )
    }


def _seccion_umbrales_curvas() -> None:
    meta = fuente("umbrales")
    try:
        por_hoja, info = _obtener_umbrales_curvas(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    por_hoja = _filtrar_hojas_umbrales_ui(por_hoja, info)
    hojas = list(por_hoja.keys())
    if not hojas:
        st.warning("El Excel no tiene hojas cargables (todas excluidas o vacías).")
        return

    excl = ", ".join(info["hojas_excluidas"]) if info["hojas_excluidas"] else "—"
    _cabecera_seccion(
        meta.seccion,
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": f"{len(hojas)} pestañas · omitidas: {excl}",
        }],
        key="umbrales_curvas",
    )

    col_hoja, col_filtro = st.columns([1, 2])
    with col_hoja:
        hoja_sel = st.selectbox(
            "Pestaña",
            options=[_TODAS_PESTANAS] + hojas,
            key="umb_hoja",
        )
    with col_filtro:
        filtro = st.text_input(
            "Filtrar",
            placeholder="Buscar en cualquier columna...",
            key="umb_filtro",
        )

    st.button("Restaurar filtros", on_click=_reset_filtros_umbrales)

    if hoja_sel == _TODAS_PESTANAS:
        frames = [
            _df_con_pestana(df_h, nombre)
            for nombre, df_h in por_hoja.items()
        ]
        df_base = pd.concat(frames, ignore_index=True, sort=False)
        total_base = sum(info["totales"].values())
    else:
        df_base = por_hoja[hoja_sel].copy()
        if "Pestaña" in df_base.columns:
            df_base = df_base.drop(columns=["Pestaña"])
        total_base = info["totales"][hoja_sel]

    df_mostrar = df_base.copy()
    if filtro:
        f = filtro.lower()
        mask = df_mostrar.apply(
            lambda fila: fila.astype(str).str.lower().str.contains(f, regex=False).any(),
            axis=1,
        )
        df_mostrar = df_mostrar[mask]

    st.caption(
        f"{len(df_mostrar)} de {total_base} filas · "
        f"{len(df_mostrar.columns)} columnas"
    )

    if df_mostrar.empty:
        st.info("No hay filas para ese filtro.")
        return

    slug = (
        "todas"
        if hoja_sel == _TODAS_PESTANAS
        else _normalizar(hoja_sel).replace(" ", "_").replace("/", "-")
    )
    hoja_export = "Todas" if hoja_sel == _TODAS_PESTANAS else hoja_sel[:31]
    _botones_descarga(
        df_mostrar,
        f"{meta.archivo.lower()}_{slug}",
        hoja=hoja_export,
    )
    _mostrar_tabla(df_mostrar, altura_max=620, conservar_columnas_vacias=True)


def _reset_filtros_config_puerto() -> None:
    st.session_state.pop("cfg_filtro", None)


_COL_SELECCIONAR_IMPACTO = "Seleccionar"
_KEY_IMPACTOS_SELECCION = "pde_impactos_preguntar_seleccion"
_KEY_IMPACTOS_EDITOR = "pde_impactos_preguntar_editor"
_KEY_IMPACTOS_META = "pde_impactos_preguntar_meta"


def _marcar_todos_impactos(n: int) -> None:
    st.session_state[_KEY_IMPACTOS_SELECCION] = [True] * n
    st.session_state.pop(_KEY_IMPACTOS_EDITOR, None)


def _desmarcar_todos_impactos(n: int) -> None:
    st.session_state[_KEY_IMPACTOS_SELECCION] = [False] * n
    st.session_state.pop(_KEY_IMPACTOS_EDITOR, None)


def _seccion_configuracion_puerto() -> None:
    meta = fuente("config_puerto")
    try:
        _, info = _obtener_config_puerto(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    hojas = info.get("hojas") or []
    por_hoja = info.get("por_hoja") or {}
    if not hojas:
        st.warning("El Excel de configuración no tiene hojas con datos.")
        return

    _cabecera_seccion(
        meta.seccion,
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": f"{len(hojas)} pestaña(s) · {sum(info['totales'].values())} filas en total",
        }],
        key="config_puerto",
    )

    if len(hojas) > 1:
        col_hoja, col_filtro = st.columns([1, 2])
        with col_hoja:
            hoja_sel = st.selectbox("Pestaña", options=hojas, key="cfg_hoja")
        with col_filtro:
            filtro = st.text_input(
                "Filtrar",
                placeholder="Buscar en cualquier columna...",
                key="cfg_filtro",
            )
    else:
        hoja_sel = hojas[0]
        filtro = st.text_input(
            "Filtrar",
            placeholder="Buscar en cualquier columna...",
            key="cfg_filtro",
        )

    st.button("Restaurar filtros", on_click=_reset_filtros_config_puerto)

    df_base = por_hoja[hoja_sel]
    df_mostrar = df_base.copy()
    if filtro:
        f = filtro.lower()
        mask = df_mostrar.apply(
            lambda fila: fila.astype(str).str.lower().str.contains(f, regex=False).any(),
            axis=1,
        )
        df_mostrar = df_mostrar[mask]

    st.caption(
        f"{len(df_mostrar)} de {info['totales'][hoja_sel]} filas · "
        f"{len(df_mostrar.columns)} columnas"
    )

    if df_mostrar.empty:
        st.info("No hay filas para ese filtro.")
        return

    slug = _normalizar(hoja_sel).replace(" ", "_").replace("/", "-")
    _botones_descarga(
        df_mostrar,
        f"{meta.archivo.lower()}_{slug}",
        hoja=hoja_sel[:31],
    )
    _mostrar_tabla(df_mostrar, altura_max=620, conservar_columnas_vacias=True)


def _seccion_preguntar_impactos() -> None:
    """Configuración de impactos no factibles: casillas por fila (todas marcadas por defecto)."""
    try:
        df, info = _obtener_preguntar_impactos(_firma_datos_excel())
    except FileNotFoundError as exc:
        st.warning(str(exc))
        return

    if df.empty:
        st.warning("El Excel de impactos a calcular no tiene filas.")
        return

    _cabecera_seccion(
        V_CONFIG_IMPACTOS_NO_FACTIBLES,
        [{
            "nombre": "Preguntar_si_se_calculan.xlsx",
            "ruta": info["ruta"],
            "detalle": (
                f"Hoja «{info.get('hoja', '—')}» · {info.get('total', 0)} filas · "
                "marque los impactos no factibles (no se calcularán)"
            ),
        }],
        key="preguntar_impactos",
    )

    n = len(df)
    meta = (info["ruta"], info.get("total", n), tuple(df.columns))
    if st.session_state.get(_KEY_IMPACTOS_META) != meta:
        st.session_state.pop(_KEY_IMPACTOS_EDITOR, None)
        st.session_state[_KEY_IMPACTOS_META] = meta
        st.session_state[_KEY_IMPACTOS_SELECCION] = [True] * n

    if (
        _KEY_IMPACTOS_SELECCION not in st.session_state
        or len(st.session_state[_KEY_IMPACTOS_SELECCION]) != n
    ):
        st.session_state[_KEY_IMPACTOS_SELECCION] = [True] * n

    col_marcar, col_desmarcar, _ = st.columns([1, 1, 4])
    with col_marcar:
        st.button(
            "Marcar todos",
            key="impactos_marcar_todos",
            on_click=_marcar_todos_impactos,
            args=(n,),
            use_container_width=True,
        )
    with col_desmarcar:
        st.button(
            "Desmarcar todos",
            key="impactos_desmarcar_todos",
            on_click=_desmarcar_todos_impactos,
            args=(n,),
            use_container_width=True,
        )

    editor_df = df.copy()
    editor_df.insert(0, _COL_SELECCIONAR_IMPACTO, st.session_state[_KEY_IMPACTOS_SELECCION])

    cfg_cols: dict = {
        _COL_SELECCIONAR_IMPACTO: st.column_config.CheckboxColumn(
            "No factible",
            help="Marcado = impacto no factible (no se calcula). Desmarcado = se puede calcular.",
            default=True,
            width="small",
        ),
    }
    for col in df.columns:
        ancho = "small" if "tipo de impacto" in str(col).lower() else "medium"
        if "modos de fallo" in str(col).lower() or "activo" in str(col).lower():
            ancho = "large"
        cfg_cols[col] = st.column_config.TextColumn(str(col), width=ancho)

    editados = st.data_editor(
        editor_df,
        hide_index=True,
        use_container_width=True,
        height=_altura_tabla(n, 620),
        column_config=cfg_cols,
        disabled=[c for c in editor_df.columns if c != _COL_SELECCIONAR_IMPACTO],
        key=_KEY_IMPACTOS_EDITOR,
    )

    seleccion = [bool(v) for v in editados[_COL_SELECCIONAR_IMPACTO].tolist()]
    st.session_state[_KEY_IMPACTOS_SELECCION] = seleccion
    # Si el filtro ya no coincide con el último cálculo, ocultar resultados viejos.
    _invalidar_resultados_si_cambia_filtro_no_factibles()
    n_no_factibles = sum(seleccion)
    n_disponibles = n - n_no_factibles
    st.caption(
        f"{n_no_factibles} de {n} marcados como no factibles (no se calcularán) · "
        f"{n_disponibles} disponibles para calcular"
    )


def _seccion_relacion_modelos() -> None:
    meta = fuente("relacion_modelos")
    df, info = _obtener_relacion_modelos(_firma_datos_excel())
    if info.get("origen") == "ausente" or not info.get("ruta"):
        st.warning(_mensaje_excel_no_encontrado(meta))
        return

    _cabecera_seccion(
        meta.seccion,
        [{
            "nombre": nombre_archivo_display(meta),
            "ruta": info["ruta"],
            "detalle": f"Hoja «{info.get('hoja', '—')}» · {info.get('total', 0)} filas",
        }],
        key="relacion_modelos",
    )

    filtro = st.text_input(
        "Filtrar",
        placeholder="Buscar en cualquier columna...",
        key="relmod_filtro",
    )
    df_mostrar = df.copy()
    if filtro:
        f = filtro.lower()
        mask = df_mostrar.apply(
            lambda fila: fila.astype(str).str.lower().str.contains(f, regex=False).any(),
            axis=1,
        )
        df_mostrar = df_mostrar[mask]

    st.caption(f"{len(df_mostrar)} de {info.get('total', len(df))} filas")
    if df_mostrar.empty:
        st.info("No hay filas para ese filtro.")
        return

    slug = _normalizar(str(info.get("hoja", "datos"))).replace(" ", "_").replace("/", "-")
    _botones_descarga(
        df_mostrar,
        f"{meta.archivo.lower()}_{slug}",
        hoja=str(info.get("hoja", "Datos"))[:31],
    )
    _mostrar_tabla(df_mostrar, altura_max=620, conservar_columnas_vacias=True)


def _tabla_resultado_economico(df: pd.DataFrame, columnas: list[str]) -> None:
    """Muestra una tabla de resultados con formato numerico."""
    cols = [c for c in columnas if c in df.columns]
    if df.empty or not cols:
        return
    present = df[cols].copy()
    cfg = {}
    for c in cols:
        if c in ("Año", "Escenario"):
            cfg[c] = st.column_config.TextColumn(c, width="small")
        else:
            cfg[c] = st.column_config.NumberColumn(c, format="%.2f")
    _mostrar_tabla(present, column_order=cols, column_config=cfg)


def _vista_modelo_economico_tipo(
    df: pd.DataFrame,
    *,
    incluir_capex: bool = True,
) -> None:
    """Pestañas economicas: CAPEX/OPEX/Pérdida o solo OPEX/Pérdida (equivalente anual)."""
    base = ["Año", "Escenario"] if "Año" in df.columns else ["Escenario"]

    if incluir_capex:
        tabs = st.tabs(["CAPEX (ELU)", "OPEX (ELS)", "Pérdida de ingresos (ELO)"])
        with tabs[0]:
            _tabla_resultado_economico(df, base + ["CAPEX (ELU)"])
        with tabs[1]:
            col_opex = next((c for c in df.columns if "OPEX" in c), "OPEX (ELS)")
            _tabla_resultado_economico(df, base + [col_opex])
        with tabs[2]:
            col_elo = next(
                (c for c in df.columns if "Pérdida" in c or "ELO" in c),
                "Pérdida de ingresos (ELO)",
            )
            _tabla_resultado_economico(df, base + [col_elo])
    else:
        tabs = st.tabs(["OPEX (ELS)", "Pérdida de ingresos (ELO)"])
        with tabs[0]:
            col_opex = next((c for c in df.columns if "OPEX" in c), "OPEX (ELS)")
            _tabla_resultado_economico(df, base + [col_opex])
        with tabs[1]:
            col_elo = next(
                (c for c in df.columns if "Pérdida" in c or "ELO" in c),
                "Pérdida de ingresos (ELO)",
            )
            _tabla_resultado_economico(df, base + [col_elo])


def _df_indicadores_ordenados(indicadores) -> pd.DataFrame:
    """Seleccionados primero; después descartados."""
    ordenados = sorted(
        indicadores,
        key=lambda i: (not i.seleccionado, i.descartado, str(i.nombre).lower()),
    )
    return pd.DataFrame([
        {
            "Indicador": i.nombre,
            "Estado": "Seleccionado" if i.seleccionado else "Descartado",
        }
        for i in ordenados
    ])


def _unidad_cierre_iteracion(r) -> str | None:
    """Unidad de cierre (horas|dias) desde variable/indicador de la iteración."""
    return resolver_unidad_cierre(
        variable=getattr(r, "variable_climatica", None),
        indicador=getattr(r, "indicador_seleccionado", None),
    )


def _mostrar_valores_indicador_por_escenario(r) -> None:
    """Tabla de valores del indicador por escenario (bajo el indicador seleccionado)."""
    tabla = getattr(r, "tabla_resultado", None)
    if tabla is None or getattr(tabla, "empty", True):
        st.caption("Sin valores por escenario.")
        return

    ind_sel = str(getattr(r, "indicador_seleccionado", "") or "").strip()
    if ind_sel:
        st.caption(f"Indicador seleccionado: **{ind_sel}**")
    else:
        st.caption("Indicador seleccionado: —")

    if "h" in tabla.columns and "NM" in tabla.columns:
        st.caption(
            "h = NM − h₀ − h sedimentación. "
            "NM = MA + MM + SLR. "
            "Si umbral ≤ h → es necesario dragar; si umbral > h → no es necesario dragar."
        )
        cols_tabla = [
            "Escenario",
            "NM",
            "h sedimentacion",
            "h0",
            "h",
            "Umbral",
            "Interpretación",
        ]
        cfg = {
            "Escenario": st.column_config.TextColumn("Escenario", width="medium"),
            "NM": st.column_config.NumberColumn("NM", format="%.3f"),
            "h sedimentacion": st.column_config.NumberColumn("h sedimentación", format="%.3f"),
            "h0": st.column_config.NumberColumn("h₀", format="%.3f"),
            "h": st.column_config.NumberColumn("h", format="%.3f"),
            "Umbral": st.column_config.NumberColumn("Umbral", format="%.3f"),
            "Interpretación": st.column_config.TextColumn("Interpretación", width="medium"),
        }
    else:
        st.caption(
            "Indicador = valor físico del Excel. "
            "Cambio = indicador del escenario − indicador histórico. "
            + regla_variacion_cierre(_unidad_cierre_iteracion(r))
        )
        cols_tabla = [
            "Escenario",
            "Indicador",
            "Cambio respecto al histórico",
            "Interpretación",
        ]
        cfg = {
            "Escenario": st.column_config.TextColumn("Escenario", width="medium"),
            "Indicador": st.column_config.NumberColumn("Indicador", format="%d"),
            "Cambio respecto al histórico": st.column_config.NumberColumn(
                "Cambio respecto al histórico",
                format="%d",
            ),
            "Interpretación": st.column_config.TextColumn("Interpretación", width="small"),
        }

    cols_existentes = [c for c in cols_tabla if c in tabla.columns]
    if not cols_existentes:
        st.caption("La tabla de resultado no tiene columnas de escenario reconocibles.")
        return
    _mostrar_tabla(
        tabla,
        column_order=cols_existentes,
        column_config={k: v for k, v in cfg.items() if k in cols_existentes},
        altura_max=420,
    )


def _mostrar_resumen_iteracion(r, *, titulo: str | None = None) -> None:
    """Contenido del resumen de una iteración PI (sin cabecera)."""
    if titulo:
        st.markdown(f"**{titulo}**")
    campos = pd.DataFrame([
        {"Campo": "Iteración", "Valor": r.numero},
        {"Campo": "Activo", "Valor": r.activo},
        {"Campo": "Tipo UO", "Valor": r.tipo_uo},
        {"Campo": "Modo de fallo", "Valor": r.modo_fallo},
        {"Campo": "Variable climática", "Valor": r.variable_climatica},
        {"Campo": "Umbral", "Valor": r.umbral},
        {"Campo": "Indicador seleccionado", "Valor": r.indicador_seleccionado},
        {"Campo": "Percentil", "Valor": r.percentil},
        {
            "Campo": "Origen percentil/indicador",
            "Valor": (
                "Excel (Relacion_modelos_activos_e_indicadores)"
                if getattr(r, "origen_regla", "") == "excel"
                else "Diagrama (umbral + P99 + filtros)"
            ),
        },
    ])
    _mostrar_tabla(campos, column_order=["Campo", "Valor"], altura_max=280)

    # Valores del indicador por escenario (justo bajo el indicador seleccionado)
    st.markdown("**Valores del indicador por escenario**")
    _mostrar_valores_indicador_por_escenario(r)

    st.markdown("**Indicadores encontrados**")
    ind_df = _df_indicadores_ordenados(r.indicadores)
    _mostrar_tabla(ind_df, column_order=["Indicador", "Estado"], altura_max=220)

    if r.advertencia_negativos:
        st.warning(r.advertencia_negativos)

    rc = r.resumen_cambios
    if rc:
        st.markdown("**Síntesis de cambios**")
        unidad = _unidad_cierre_iteracion(r)
        sufijo = " d" if unidad == "dias" else " h" if unidad == "horas" else ""
        if rc.mayor_empeoramiento:
            st.markdown(
                f"- **Mayor empeoramiento:** {rc.mayor_empeoramiento} "
                f"(cambio {rc.mayor_empeoramiento_cambio:+.0f}{sufijo})"
            )
        else:
            st.markdown("- **Mayor empeoramiento:** ningún escenario empeora")
        if rc.mayor_mejora:
            st.markdown(
                f"- **Mayor mejora:** {rc.mayor_mejora} "
                f"(cambio {rc.mayor_mejora_cambio:+.0f}{sufijo})"
            )
        else:
            st.markdown("- **Mayor mejora:** ningún escenario mejora")


def _mostrar_resumen_activo(resumen) -> None:
    """Resumen del activo: nombre del activo y tabla como la plantilla Excel."""
    st.markdown(f"**{resumen.activo}**")
    if not resumen.filas:
        return
    st.markdown(html_tabla_resumen_activo(resumen), unsafe_allow_html=True)


def _botones_descarga_resumen_activo(
    resumen,
    nombre_base: str,
    *,
    key_prefix: str | None = None,
) -> None:
    """Descarga CSV plano y Excel con cabeceras combinadas."""
    df = resumen.tabla_resumen
    csv_bytes = df.to_csv(index=False, sep=";").encode("utf-8-sig")
    xlsx_bytes = export_resumen_activo_xlsx(resumen)
    clave = key_prefix or nombre_base
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(
            "Descargar Excel",
            data=xlsx_bytes,
            file_name=f"{nombre_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{clave}_xlsx",
        )
    with col_d2:
        st.download_button(
            "Descargar CSV",
            data=csv_bytes,
            file_name=f"{nombre_base}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{clave}_csv",
        )


def _mostrar_resultados_por_pasos(pasos, *, usar_expander: bool = True) -> None:
    """Trazabilidad paso a paso (procedimiento auditable).

    Si `usar_expander` es False, cada paso se muestra en un contenedor con borde
    (sin expander) para poder anidarlo dentro de otro expander sin que Streamlit
    lance el error de expanders anidados.
    """
    if pasos is None or not pasos.pasos:
        st.caption("No hay pasos registrados.")
        return

    st.caption(
        "Cada paso: Procedimiento → Entrada → Match → Salida. "
        "La fuente Excel aparece una sola vez por paso."
    )

    for paso in pasos.pasos:
        titulo_paso = f"Paso {paso.numero} — {paso.nombre}"

        if usar_expander:
            contenedor = st.expander(titulo_paso, expanded=False)
        else:
            contenedor = st.container(border=True)
        with contenedor:
            if not usar_expander:
                st.markdown(f"**{titulo_paso}**")

            if paso.excel and paso.excel != "-":
                st.caption(f"Fuente: {paso.excel}")

            procedimiento = str(getattr(paso, "procedimiento", "") or "").strip()
            if procedimiento:
                st.markdown("**Procedimiento**")
                st.code(procedimiento, language=None)

            entradas: list = []
            matches: list = []
            salidas: list = []
            otras: list = []
            for t in paso.tablas:
                titulo = (t.titulo or "").lower()
                if any(k in titulo for k in ("entrada", "input", "clave")):
                    entradas.append(t)
                elif any(k in titulo for k in ("match", "accion", "acción")):
                    matches.append(t)
                elif any(k in titulo for k in ("salida", "output", "fallo", "resultado")):
                    salidas.append(t)
                else:
                    otras.append(t)

            bloques = [
                ("Entrada", entradas),
                ("Match", matches),
                ("Salida", salidas + otras),
            ]
            for etiqueta, tablas in bloques:
                if not tablas:
                    continue
                st.markdown(f"**{etiqueta}**")
                for tabla in tablas:
                    # Evitar repetir "1. Entrada…" / "3. Salida…" si ya está el bloque
                    titulo_t = (tabla.titulo or "").strip()
                    if titulo_t and not any(
                        titulo_t.lower().startswith(p)
                        for p in ("1. entrada", "2. match", "3. salida")
                    ):
                        st.caption(titulo_t)
                    if not tabla.filas:
                        st.caption("Sin datos.")
                        continue
                    df = pd.DataFrame(tabla.filas)
                    cols = [c for c in tabla.columnas if c in df.columns]
                    altura = min(480, 72 + 32 * len(df))
                    _mostrar_tabla(df, column_order=cols, altura_max=altura)


def _mostrar_diagrama_flujo(modelo_id: str, *, compacto: bool = False) -> None:
    """Muestra el PDF esquemático; el TXT queda detrás del botón fijo «TXT»."""
    from core.modelos.flujos import (
        CARPETA_FLUJOS,
        buscar_diagrama_pdf,
        buscar_diagrama_texto,
        mensaje_diagrama_faltante,
        nombre_esperado_diagrama,
    )

    pdf = buscar_diagrama_pdf(modelo_id)
    txt = buscar_diagrama_texto(modelo_id)
    if pdf is None and txt is None:
        st.error(
            f"{mensaje_diagrama_faltante(modelo_id)}. "
            f"Prerrequisito del procedimiento de cálculo: se espera "
            f"«{nombre_esperado_diagrama(modelo_id)}.pdf» (o .txt) en "
            f"«{CARPETA_FLUJOS.name}/» (no se reutiliza el diagrama de otra familia)."
        )
        return

    if txt is not None:
        mostrar_txt = st.toggle("TXT", value=False, key=f"diag_txt_{modelo_id}")
    else:
        mostrar_txt = False

    if mostrar_txt and txt is not None:
        _mostrar_txt_diagrama(txt.ruta)
    elif pdf is not None:
        _mostrar_pdf_en_frontend(
            pdf.ruta,
            height=360 if compacto else 520,
            key=f"diag_pdf_{modelo_id}",
        )
    elif txt is not None:
        st.warning("No hay PDF esquemático; se muestra el TXT.")
        _mostrar_txt_diagrama(txt.ruta)



def _mostrar_lista_pasos(pasos, *, modelo_id: str = "", usar_expander: bool = True) -> None:
    """Muestra una lista de pasos (sin cabecera de modelo)."""
    if not pasos:
        st.caption("Sin pasos registrados.")
        return
    wrapper = type("PasosView", (), {"pasos": pasos, "modelo_id": modelo_id})()
    _mostrar_resultados_por_pasos(wrapper, usar_expander=usar_expander)


@contextmanager
def _plegable(titulo: str, key: str, *, expanded: bool = False):
    """Sección plegable con session_state (usable dentro de st.expander).

    Streamlit no admite expanders anidados; este helper imita el comportamiento
    con un botón de cabecera y contenido condicional.

    El toggle usa ``on_click`` para que abra/cierre a la primera pulsación
    (asignar estado dentro de ``if st.button`` suele exigir doble clic).
    """
    state_key = f"pde_pleg_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = expanded

    def _toggle_plegable() -> None:
        st.session_state[state_key] = not bool(st.session_state.get(state_key, False))

    abierto = bool(st.session_state[state_key])
    flecha = "▾" if abierto else "▸"
    st.button(
        f"{flecha}  {titulo}",
        key=f"btn_{state_key}",
        use_container_width=True,
        on_click=_toggle_plegable,
    )
    # Tras on_click, en este rerun el estado ya está actualizado.
    yield bool(st.session_state[state_key])


def _mostrar_ficha_modelo(
    ficha: FichaModelo,
    *,
    key: str,
    expanded: bool = True,
    unidad_cierre: str | None = None,
    variable: str | None = None,
    indicador: str | None = None,
) -> None:
    """Ficha del modelo: ecuación e interpretación (plegable)."""
    with _plegable(
        f"Ficha del modelo · {titulo_modo_display(ficha.nombre)} ({ficha.motor_id})",
        f"{key}_ficha",
        expanded=expanded,
    ) as abierta:
        if not abierta:
            return
        st.caption(
            f"{ficha.familia} · tipo {ficha.tipo_impacto}"
            + (f" · {ficha.notas}" if ficha.notas else "")
        )
        from core.modelos.flujos import mensaje_diagrama_faltante, tiene_diagrama

        if ficha.motor_id and not tiene_diagrama(ficha.motor_id):
            st.warning(
                "Prerrequisito del procedimiento: "
                + mensaje_diagrama_faltante(ficha.motor_id)
                + "."
            )
        st.markdown("**Ecuación**")
        if ficha.ecuacion:
            try:
                st.latex(ficha.ecuacion)
            except Exception:
                st.code(ficha.ecuacion, language=None)
        if getattr(ficha, "ecuacion_extra", ""):
            try:
                st.latex(ficha.ecuacion_extra)
            except Exception:
                st.code(ficha.ecuacion_extra, language=None)
        if ficha.ecuacion_umbral:
            try:
                st.latex(ficha.ecuacion_umbral)
            except Exception:
                st.code(ficha.ecuacion_umbral, language=None)

        regla = ficha.regla_interpretacion
        if ficha.motor_id == "PI_AGITACION":
            regla = regla_variacion_cierre(
                unidad_cierre,
                variable=variable,
                indicador=indicador,
            )
        if regla:
            st.caption(regla)


def _mostrar_vista_cp_im(vista) -> None:
    """Resultados organizados: CP (activo) → diagnóstico / detalle IM / resumen.

    Jerarquía plegada por defecto:
      CP (expander) → Diagnóstico / Detalle (IM + ficha) / Resumen

    Nota: la trazabilidad por pasos (Pasos 3–4 y procedimiento paso a paso)
    se omite en el frontend; el backend sigue construyendo los pasos.
    """
    iter_por_modo = {it.modo_fallo: it for it in vista.iteraciones}
    cp_clave = f"cp{vista.cp_numero}"
    n_ok = sum(1 for g in vista.modos if getattr(g, "estado", "ok") == "ok")
    n_err = sum(1 for g in vista.modos if getattr(g, "estado", "ok") == "error")

    with st.expander(
        f"CP {vista.cp_numero}/{vista.cp_total} — {vista.activo}",
        expanded=False,
    ):
        diagnostico = getattr(vista, "diagnostico", None) or []
        if diagnostico:
            with _plegable(
                "Diagnóstico por modo (estado / motivo)",
                f"{cp_clave}_diagnostico",
            ) as diag_abierto:
                if diag_abierto:
                    st.caption(f"{n_ok} OK / {n_err} error")
                    st.dataframe(pd.DataFrame(diagnostico), use_container_width=True, hide_index=True)

        with _plegable(
            f"Detalle del cálculo · {len(vista.modos)} modo(s) de fallo (IM)",
            f"{cp_clave}_detalle",
        ) as detalle_abierto:
            if detalle_abierto:
                for im_num, grupo in enumerate(vista.modos, start=1):
                    it = iter_por_modo.get(grupo.modo_fallo)
                    estado = getattr(grupo, "estado", "ok") or "ok"
                    familia = getattr(grupo, "familia", "") or (
                        getattr(it, "familia", "") if it is not None else ""
                    )
                    motor = getattr(grupo, "motor_id", "") or (
                        getattr(it, "motor_id", "") if it is not None else ""
                    )
                    tipo_imp = getattr(grupo, "tipo_impacto", "") or (
                        getattr(it, "tipo_impacto", "") if it is not None else ""
                    )
                    nombre_motor = titulo_modo_display(
                        getattr(grupo, "nombre_motor", "")
                        or (getattr(it, "nombre_motor", "") if it is not None else "")
                        or nombre_motor_display(
                            motor,
                            familia=familia,
                            tipo_impacto=tipo_imp,
                            modo_fallo=grupo.modo_fallo,
                            titulo=getattr(grupo, "titulo", "") or "",
                            fallback=motor,
                        )
                    )
                    etiqueta_estado = estado.upper()
                    extras = " · ".join(
                        x for x in (etiqueta_estado, familia, nombre_motor) if x
                    )
                    im_key = f"{cp_clave}_im_{im_num}"
                    with _plegable(
                        f"IM {im_num} — {grupo.modo_fallo} [{extras}]",
                        im_key,
                    ) as im_abierto:
                        if not im_abierto:
                            continue

                        st.markdown(
                            f"**Modo:** {grupo.modo_fallo}  \n"
                            f"**Estado:** {etiqueta_estado}"
                            + (f" · **Familia:** {familia}" if familia else "")
                            + (f" · **Motor:** {nombre_motor}" if nombre_motor else "")
                            + (f" · **Tipo:** {tipo_imp}" if tipo_imp else "")
                        )

                        ficha = resolver_ficha(
                            motor_id=motor,
                            familia=familia,
                            tipo_impacto=tipo_imp,
                            modo_fallo=grupo.modo_fallo,
                            titulo=getattr(grupo, "titulo", "") or "",
                        )
                        if ficha is not None:
                            var_it = (
                                getattr(it, "variable_climatica", None)
                                if it is not None
                                else None
                            ) or grupo.modo_fallo
                            ind_it = (
                                getattr(it, "indicador_seleccionado", None)
                                if it is not None
                                else None
                            )
                            _mostrar_ficha_modelo(
                                ficha,
                                key=im_key,
                                expanded=True,
                                variable=var_it,
                                indicador=ind_it,
                            )
                        else:
                            st.caption("Sin ficha de modelo para este motor.")

                        motivo = getattr(grupo, "motivo", None) or (
                            getattr(it, "motivo", None) if it is not None else None
                        )
                        if estado != "ok":
                            codigo = getattr(grupo, "error_code", None) or (
                                getattr(it, "error_code", None) if it is not None else None
                            )
                            msg = motivo or "No calculó"
                            if codigo:
                                msg = f"{msg} ({codigo})"
                            st.error(msg)

                        if (
                            it is not None
                            and estado == "ok"
                            and it.tabla_resultado is not None
                            and not it.tabla_resultado.empty
                        ):
                            with _plegable(
                                "Resultado del modo",
                                f"{im_key}_resultado",
                                expanded=True,
                            ) as resultado_abierto:
                                if not resultado_abierto:
                                    continue
                                _mostrar_resumen_iteracion(it)
                                if "h" in it.tabla_resultado.columns and "NM" in it.tabla_resultado.columns:
                                    cols_dl = [
                                        "Escenario", "NM", "h sedimentacion", "h0", "h",
                                        "Umbral", "Interpretación",
                                    ]
                                    prefijo = f"{cp_clave}_calado_im_{im_num}"
                                else:
                                    cols_dl = [
                                        "Escenario", "Indicador", "Cambio respecto al histórico",
                                        "Interpretación", "Texto auxiliar",
                                    ]
                                    prefijo = f"{cp_clave}_pi_im_{im_num}"
                                cols_existentes = [
                                    c for c in cols_dl if c in it.tabla_resultado.columns
                                ]
                                if cols_existentes:
                                    _botones_descarga(
                                        it.tabla_resultado[cols_existentes],
                                        prefijo,
                                        hoja=grupo.modo_fallo[:31],
                                        key_prefix=prefijo,
                                    )

        if vista.resumen_activo is not None:
            with _plegable(
                "Resumen consolidado del activo (todos los IM)",
                f"{cp_clave}_resumen",
            ) as resumen_abierto:
                if resumen_abierto:
                    _mostrar_resumen_activo(vista.resumen_activo)
                    if vista.resumen_activo.filas:
                        _botones_descarga_resumen_activo(
                            vista.resumen_activo,
                            f"{cp_clave}_impactos_resumen_activo",
                            key_prefix=f"{cp_clave}_impactos_resumen_activo",
                        )


def _selector_activo_cp(config_df: pd.DataFrame) -> tuple[str, str, int, int, pd.Series | None]:
    """Devuelve activo (display), activo raw, CP índice, CP total y fila config."""
    activos = listar_activos_config(config_df)
    if not activos:
        return "—", "", 0, 0, None

    cp_total = len(activos)
    activo_raw = activos[0]
    cp_num = 1

    fila = fila_configuracion(config_df, activo=activo_raw)
    return nombre_activo_resumen(activo_raw), activo_raw, cp_num, cp_total, fila


def _fila_config_activo(config_df: pd.DataFrame, *, activo_raw: str | None = None) -> pd.Series | None:
    params = ParametrosEntrada()
    activo = activo_raw or params.activo
    return fila_configuracion(
        config_df,
        tipo_uo=params.tipo_uo,
        activo=activo,
    )


def _activo_calculo_actual(config_df: pd.DataFrame, *, activo_raw: str | None = None) -> str:
    """Activo que usará el cálculo unificado."""
    activo = activo_raw
    if activo is None:
        params = ParametrosEntrada()
        fila = fila_configuracion(
            config_df,
            tipo_uo=params.tipo_uo,
            activo=params.activo,
        )
    else:
        fila = fila_configuracion(config_df, activo=activo)
    if fila is None:
        return "—"
    cols = list(config_df.columns)
    col_activo = columna_por_patron(cols, "activo fisico u operacional", "activo")
    activo_txt = str(fila[col_activo]).strip() if col_activo else activo or ""
    return nombre_activo_resumen(activo_txt)


def _filtro_impactos_no_factibles_sesion() -> FiltroImpactosNoFactibles:
    """Construye el filtro desde Excel + casillas de sesión (marcado = no calcular)."""
    try:
        df, _info = _obtener_preguntar_impactos(_firma_datos_excel())
    except FileNotFoundError:
        return FiltroImpactosNoFactibles.vacio()
    seleccion = st.session_state.get(_KEY_IMPACTOS_SELECCION)
    return FiltroImpactosNoFactibles.desde_dataframe(df, seleccion)


def _huella_filtro_no_factibles(
    filtro: FiltroImpactosNoFactibles | None = None,
) -> str:
    """Huella estable de la selección actual (invalida resultados al cambiar)."""
    if filtro is None:
        filtro = _filtro_impactos_no_factibles_sesion()
    seleccion = st.session_state.get(_KEY_IMPACTOS_SELECCION)
    if seleccion is None:
        flags = "default"
    else:
        flags = "".join("1" if bool(v) else "0" for v in seleccion)
    triples = "\n".join(
        sorted(
            f"{t.activo}|{t.tipo_impacto}|{t.modo_fallo}" for t in filtro.marcados
        )
    )
    return sha1(f"{flags}\n{triples}".encode("utf-8")).hexdigest()


def _invalidar_resultados_si_cambia_filtro_no_factibles() -> None:
    """Si cambian las casillas de no factibles, no reutilizar el último cálculo."""
    huella_resultado = st.session_state.get("_huella_filtro_nf_resultado")
    if not huella_resultado:
        return
    if huella_resultado != _huella_filtro_no_factibles():
        _limpiar_resultados_calculo()


def _bloque_calculo_activo() -> tuple[bool, ParametrosEntrada]:
    """Botón de cálculo CP sobre todos los activos del puerto."""
    params = ParametrosEntrada()
    _, col_btn = st.columns([3, 1.2], gap="large", vertical_alignment="center")
    with col_btn:
        pulsar = st.button(
            "Calcular impactos del puerto",
            use_container_width=True,
            key="btn_calc_impactos_activo",
        )
    return pulsar, params


def _mostrar_modos_sin_modelo(modos) -> None:
    if not modos:
        return
    with st.expander(
        f"Modos de fallo sin modelo implementado ({len(modos)})",
        expanded=False,
    ):
        for modo in modos:
            n_rel = f"Nº {modo.n_relacion}" if modo.n_relacion is not None else "—"
            st.markdown(
                f"- **{modo.activo}** · {n_rel} · "
                f"{modo.modo_fallo} / {modo.variable} / {modo.tipo_impacto}"
            )


def _etiqueta_catalogo_modo(entrada) -> str:
    """Etiqueta del catálogo: Flujo-style para calado/francobordo; resto familia+modo."""
    if entrada.id in {
        "falta_francobordo_elo",
        "falta_calado_elo",
        "falta_calado_els",
        "falta_calado_elu",
    }:
        bruto = entrada.motor_nombre
    else:
        bruto = titulo_modo_impacto(entrada)
    return titulo_modo_display(bruto)



def _mostrar_txt_diagrama(ruta, *, altura_max: int = 640) -> None:
    """TXT del procedimiento como antes: bloque monoespaciado con saltos de línea."""
    from core.modelos.flujos import leer_texto_diagrama

    st.caption(f"Fuente: {ruta.name}")
    contenido = leer_texto_diagrama(ruta)
    # st.text conserva saltos de línea (no lo aplasta a párrafo).
    st.text(contenido)


def _pdf_media_url(data: bytes, *, coordinates: str, file_name: str) -> str | None:
    """Registra bytes en el MediaFileManager y devuelve la URL /media/..."""
    try:
        from streamlit import runtime
    except Exception:
        return None
    if not runtime.exists():
        return None
    try:
        return runtime.get_instance().media_file_mgr.add(
            data,
            "application/pdf",
            coordinates,
            file_name=file_name,
        )
    except Exception:
        return None


def _mostrar_pdf_via_media_iframe(
    data: bytes,
    *,
    height: int,
    file_name: str,
    key: str,
) -> bool:
    """Fallback sin data-URI: iframe apuntando a la URL media de Streamlit."""
    import streamlit.components.v1 as components

    coords = f"pdf_fallback_{key or file_name}"
    url = _pdf_media_url(data, coordinates=coords, file_name=file_name)
    if not url:
        return False
    # URL http(s)/relativa del runtime: Edge/Chrome la aceptan (a diferencia de data:).
    components.html(
        (
            f'<iframe src="{url}" title="{file_name}" '
            f'width="100%" height="{int(height)}" '
            f'style="border:0;min-height:{int(height)}px;"></iframe>'
        ),
        height=int(height) + 16,
    )
    return True


def _mostrar_pdf_en_frontend(ruta, *, height: int = 640, key: str = "") -> None:
    """Carga el PDF en el frontend (streamlit-pdf / st.pdf / iframe media).

    Edge/Chrome bloquean iframes con ``data:application/pdf``; no usar ese
    fallback. Preferimos ``streamlit_pdf.pdf_viewer`` con bytes + height int
    (``st.pdf`` a veces pasa height como str y el iframe queda a altura 0).
    """
    from pathlib import Path

    path = Path(ruta)
    if not path.is_file():
        st.error(f"No se encuentra el PDF en disco: `{path}`")
        return

    st.caption(f"Diagrama: {path.name}")
    data = path.read_bytes()
    if not data:
        st.error(f"El PDF está vacío: `{path.name}`")
        return

    height_i = int(height)
    widget_key = key or None
    errores: list[str] = []

    # 1) API directa del componente (height int; evita el str() de PdfMixin).
    try:
        import streamlit_pdf

        streamlit_pdf.pdf_viewer(file=data, height=height_i, key=widget_key)
        return
    except Exception as exc:
        errores.append(f"streamlit_pdf.pdf_viewer(bytes): {type(exc).__name__}: {exc}")

    # 2) st.pdf con Path (Streamlit lee el fichero) y luego con bytes.
    for label, payload in (("path", path), ("bytes", data)):
        try:
            st.pdf(payload, height=height_i, key=widget_key)
            return
        except TypeError:
            try:
                st.pdf(payload, height=height_i)
                return
            except Exception as exc:
                errores.append(f"st.pdf({label}): {type(exc).__name__}: {exc}")
        except Exception as exc:
            errores.append(f"st.pdf({label}): {type(exc).__name__}: {exc}")

    # 3) Fallback visible: iframe sobre /media/... (sin data-URI).
    if _mostrar_pdf_via_media_iframe(
        data, height=height_i, file_name=path.name, key=key or path.stem
    ):
        st.info(
            "Visor `streamlit-pdf` no disponible; se muestra el PDF vía URL media de Streamlit."
        )
        return

    msg = " | ".join(errores[-3:]) if errores else "sin detalle"
    if any("streamlit-pdf" in e.lower() or "streamlit[pdf]" in e.lower() for e in errores):
        st.error(
            "El visor PDF necesita el componente **streamlit-pdf**.\n\n"
            "En local: `pip install -r requirements.txt` "
            "(o `pip install \"streamlit-pdf>=1.0.0,<2\"`) y reinicia Streamlit.\n\n"
            "En Streamlit Cloud: espera el redeploy tras el push de `requirements.txt`.\n\n"
            f"Detalle: {msg}"
        )
        return
    st.error(
        "No se pudo mostrar el PDF. En la carpeta del proyecto ejecuta "
        "`pip install -r requirements.txt` (incluye `streamlit-pdf` y `pyarrow`) "
        "y reinicia Streamlit.\n\n"
        f"Archivo: `{path}`\n\nDetalle: {msg}"
    )


_CATALOGO_SEL_MAESTRO = "maestro"
_KEY_CATALOGO_SEL = "pde_catalogo_modo_sel"
_KEY_CATALOGO_VISTA = "pde_catalogo_vista"


def _set_catalogo_modo(idx: int, vista: str | None = None) -> None:
    # Reclic con diagrama abierto → cierra todo; si el diagrama estaba
    # cerrado, lo reabre (PDF). Primer clic: selecciona + abre PDF.
    if vista is None and st.session_state.get(_KEY_CATALOGO_SEL) == idx:
        if st.session_state.get(_KEY_CATALOGO_VISTA) in ("pdf", "txt"):
            _cerrar_seleccion_catalogo()
            return
        st.session_state[_KEY_CATALOGO_VISTA] = "pdf"
        return
    st.session_state[_KEY_CATALOGO_SEL] = idx
    st.session_state[_KEY_CATALOGO_VISTA] = vista if vista is not None else "pdf"


def _set_catalogo_maestro(vista: str | None = None) -> None:
    """Selecciona el procedimiento maestro (diagrama de flujo único)."""
    if (
        vista is None
        and st.session_state.get(_KEY_CATALOGO_SEL) == _CATALOGO_SEL_MAESTRO
    ):
        if st.session_state.get(_KEY_CATALOGO_VISTA) in ("pdf", "txt"):
            _cerrar_seleccion_catalogo()
            return
        st.session_state[_KEY_CATALOGO_VISTA] = "pdf"
        return
    st.session_state[_KEY_CATALOGO_SEL] = _CATALOGO_SEL_MAESTRO
    st.session_state[_KEY_CATALOGO_VISTA] = vista if vista is not None else "pdf"


def _set_catalogo_vista(vista: str) -> None:
    st.session_state[_KEY_CATALOGO_VISTA] = vista


def _cerrar_vista_catalogo() -> None:
    """Cierra el visor PDF/TXT / panel del catálogo."""
    st.session_state[_KEY_CATALOGO_VISTA] = None


def _cerrar_seleccion_catalogo() -> None:
    st.session_state[_KEY_CATALOGO_SEL] = None
    st.session_state[_KEY_CATALOGO_VISTA] = None


def _indice_catalogo(entrada) -> int:
    for i, e in enumerate(CATALOGO_MODOS_IMPACTO):
        if e.id == entrada.id:
            return i
    return -1


def _visor_diagrama_catalogo(
    *,
    modelo_id: str,
    key_suffix: str,
    permitir_cerrar: bool = True,
) -> None:
    """Muestra el PDF/TXT según ``pde_catalogo_vista`` (abierto al clicar el nombre).

    Solo pinta contenido cuando la vista activa es pdf/txt. Incluye un
    conmutador PDF/TXT en el panel de detalle (no en la tarjeta).
    """
    from core.modelos.flujos import (
        buscar_diagrama,
        buscar_diagrama_pdf,
        buscar_diagrama_texto,
        mensaje_diagrama_faltante,
        nombre_esperado_diagrama,
    )

    vista = st.session_state.get(_KEY_CATALOGO_VISTA)
    if vista not in ("pdf", "txt"):
        return

    if not modelo_id:
        st.warning("Diagrama no disponible (sin id de modelo).")
        return

    pdf = buscar_diagrama_pdf(modelo_id)
    txt = buscar_diagrama_texto(modelo_id)

    c_cerrar, c_pdf, c_txt, _ = st.columns([1.4, 0.7, 0.7, 3.2], gap="small")
    with c_cerrar:
        if permitir_cerrar:
            st.button(
                "Cerrar diagrama",
                key=f"pde_cat_cerrar_{key_suffix}",
                use_container_width=True,
                on_click=_cerrar_vista_catalogo,
            )
    with c_pdf:
        if pdf is not None or txt is not None:
            st.button(
                "PDF",
                key=f"pde_cat_fmt_pdf_{key_suffix}",
                use_container_width=True,
                type="primary" if vista == "pdf" else "secondary",
                disabled=pdf is None,
                on_click=_set_catalogo_vista,
                args=("pdf",),
            )
    with c_txt:
        if pdf is not None or txt is not None:
            st.button(
                "TXT",
                key=f"pde_cat_fmt_txt_{key_suffix}",
                use_container_width=True,
                type="primary" if vista == "txt" else "secondary",
                disabled=txt is None,
                on_click=_set_catalogo_vista,
                args=("txt",),
            )

    if vista == "pdf":
        if pdf is not None:
            st.caption(f"Conectado: `{pdf.ruta}`")
            _mostrar_pdf_en_frontend(
                pdf.ruta,
                height=640,
                key=f"pde_cat_pdf_{key_suffix}",
            )
            return
        if txt is not None:
            st.warning(
                "No hay PDF esquemático para este modelo "
                f"(se esperaba «{nombre_esperado_diagrama(modelo_id)}.pdf» "
                f"en Flujo de modelos). Se muestra el TXT."
            )
            _mostrar_txt_diagrama(txt.ruta)
            return
        st.warning(mensaje_diagrama_faltante(modelo_id))
        return

    # vista == "txt"
    if txt is not None:
        _mostrar_txt_diagrama(txt.ruta)
        return
    if pdf is not None:
        st.warning("No hay TXT; se muestra el PDF.")
        _mostrar_pdf_en_frontend(
            pdf.ruta,
            height=640,
            key=f"pde_cat_pdf_fallback_{key_suffix}",
        )
        return
    diagrama = buscar_diagrama(modelo_id)
    if diagrama is not None and diagrama.tipo == "imagen":
        st.image(str(diagrama.ruta), use_container_width=True)
        return
    st.warning(mensaje_diagrama_faltante(modelo_id))


def _mostrar_controles_diagrama_catalogo(
    *,
    modelo_id: str,
    titulo: str,
    key_suffix: str,
) -> None:
    """Compat: título opcional + visor enlazado a la vista del catálogo."""
    if titulo:
        st.markdown(f"**{titulo}**")
    _visor_diagrama_catalogo(modelo_id=modelo_id, key_suffix=key_suffix)


def _mostrar_esquema_catalogo(*, modelo_id: str, key_suffix: str, entrada=None) -> None:
    """Imagen del boton i: primero imagenes de Ficha.xlsx; si no, ESQUEMA en Flujo."""
    from core.modelos.fichas_excel import imagenes_ficha_por_entrada
    from core.modelos.flujos import buscar_esquema

    st.markdown("**Esquema / imagen**")
    imgs = imagenes_ficha_por_entrada(entrada) if entrada is not None else ()
    if imgs:
        st.caption(f"Fuente: Fichas/Ficha.xlsx")
        for i, ruta in enumerate(imgs):
            if ruta.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
                st.image(str(ruta), use_container_width=True)
            else:
                st.caption(f"Archivo no mostrable como imagen: {ruta.name}")
        return

    esquema = buscar_esquema(modelo_id) if modelo_id else None
    if esquema is None:
        st.caption("No hay imagen de esquema para este modelo.")
        return

    st.caption(f"Fuente: {esquema.ruta.name}")
    if esquema.tipo == "pdf":
        _mostrar_pdf_en_frontend(
            esquema.ruta,
            height=520,
            key=f"pde_cat_esquema_pdf_{key_suffix}",
        )
    elif esquema.tipo == "imagen":
        st.image(str(esquema.ruta), use_container_width=True)
    else:
        _mostrar_txt_diagrama(esquema.ruta)


def _mostrar_ficha_catalogo(
    *,
    titulo: str,
    entrada=None,
    key_suffix: str = "ficha",
    permitir_cerrar: bool = False,
) -> None:
    """Ficha documental desde Fichas/Ficha.xlsx (hoja emparejada al modelo).

    Respeta merges, colores y ecuaciones Excel; omite notas editoriales.
    """
    from core.modelos.fichas_excel import ARCHIVO_FICHAS, ficha_excel_por_entrada

    if permitir_cerrar:
        c_cerrar, _ = st.columns([1, 5], gap="small")
        with c_cerrar:
            st.button(
                "Cerrar ficha",
                key=f"pde_cat_cerrar_ficha_{key_suffix}",
                use_container_width=True,
                on_click=_cerrar_seleccion_catalogo,
            )

    st.markdown(f"**Ficha · {titulo}**")
    if entrada is None:
        st.info("Sin modelo seleccionado.")
        return

    ficha = ficha_excel_por_entrada(entrada)
    if ficha is None:
        st.info(
            "No hay hoja en `Fichas/Ficha.xlsx` emparejada a este modelo. "
            f"Archivo: `{ARCHIVO_FICHAS.name}`."
        )
        return

    st.caption(f"Hoja Excel: **{ficha.hoja}** · {ARCHIVO_FICHAS.as_posix()}")
    html = getattr(ficha, "html", "") or ""
    if html:
        st.markdown(html, unsafe_allow_html=True)
        return
    if ficha.tabla is None or ficha.tabla.empty:
        st.warning("La hoja existe pero no tiene celdas con texto.")
        return
    st.dataframe(ficha.tabla, use_container_width=True, hide_index=True)


def _tarjeta_modelo_catalogo(entrada, *, idx: int, seleccionado: bool) -> None:
    """Tarjeta: solo el nombre. Clic abre ficha + diagrama en el detalle."""
    etiqueta = _etiqueta_catalogo_modo(entrada)
    tipo_btn = "primary" if seleccionado else "secondary"

    with st.container(border=True):
        st.markdown(
            '<span class="pde-modelo-card-marker"></span>',
            unsafe_allow_html=True,
        )
        st.button(
            etiqueta,
            key=f"pde_cat_card_nom_{idx}",
            use_container_width=True,
            type=tipo_btn,
            on_click=_set_catalogo_modo,
            args=(idx, None),
        )


def _tarjeta_maestro_catalogo(*, seleccionado: bool) -> None:
    """Tarjeta del procedimiento maestro: solo el nombre (abre el diagrama)."""
    tipo_btn = "primary" if seleccionado else "secondary"

    with st.container(border=True):
        st.markdown(
            '<span class="pde-modelo-card-marker"></span>',
            unsafe_allow_html=True,
        )
        st.button(
            "Diagrama de flujo único",
            key="pde_cat_card_maestro",
            use_container_width=True,
            type=tipo_btn,
            on_click=_set_catalogo_maestro,
            args=(None,),
        )


def _detalle_modelo_catalogo(entrada, *, idx: int) -> None:
    """Detalle al seleccionar un modelo: ficha (+esquema) y diagrama si está abierto."""
    from core.modelos.fichas_excel import imagenes_ficha_por_entrada
    from core.modelos.flujos import buscar_esquema

    etiqueta = _etiqueta_catalogo_modo(entrada)
    modelo_id = entrada.diagrama_modelo_id or ""
    vista = st.session_state.get(_KEY_CATALOGO_VISTA)

    st.markdown(f"### {etiqueta}")

    _mostrar_ficha_catalogo(
        titulo=etiqueta,
        entrada=entrada,
        key_suffix=str(idx),
        permitir_cerrar=True,
    )
    imgs = imagenes_ficha_por_entrada(entrada)
    esquema = buscar_esquema(modelo_id) if modelo_id else None
    if imgs or esquema is not None:
        st.divider()
        _mostrar_esquema_catalogo(
            modelo_id=modelo_id, key_suffix=str(idx), entrada=entrada
        )

    if vista in ("pdf", "txt"):
        st.divider()
        st.markdown("#### Diagrama de flujo")
        _visor_diagrama_catalogo(modelo_id=modelo_id, key_suffix=str(idx))
    else:
        st.divider()
        st.button(
            "Abrir diagrama",
            key=f"pde_cat_abrir_diag_{idx}",
            on_click=_set_catalogo_vista,
            args=("pdf",),
        )


def _bloque_catalogo_modos_impacto(*, expanded: bool = True) -> None:
    """Lista de modelos en 3 columnas (ELO / ELU / ELS) + detalle al seleccionar."""
    # Same id as core.modelos.flujos.ID_DIAGRAMA_FLUJO_UNICO (aliases resolve PDF/TXT).
    # ``expanded`` se conserva por compatibilidad de llamadas; el catálogo ya no
    # usa barra plegable «Lista de modelos» (detalle inline bajo las tarjetas).
    _ = expanded
    id_diagrama_flujo_unico = "DIAGRAMA_FLUJO_UNICO"

    st.caption("Procedimiento maestro")
    idx_sel = st.session_state.get(_KEY_CATALOGO_SEL)
    _tarjeta_maestro_catalogo(seleccionado=idx_sel == _CATALOGO_SEL_MAESTRO)

    st.markdown("##### Lista de modelos")
    col_elo, col_elu, col_els = st.columns(3, gap="medium")
    columnas_ui = {
        "ELO": col_elo,
        "ELU": col_elu,
        "ELS": col_els,
    }
    for tipo, titulo_col in COLUMNAS_LISTA_MODELOS:
        with columnas_ui[tipo]:
            st.markdown(f"**{titulo_col}**")
            entradas = entradas_por_tipo_impacto(tipo)
            if not entradas:
                st.caption("Sin modelos en esta familia.")
                continue
            for entrada in entradas:
                idx = _indice_catalogo(entrada)
                if idx < 0:
                    continue
                seleccionado = idx_sel == idx
                _tarjeta_modelo_catalogo(
                    entrada,
                    idx=idx,
                    seleccionado=seleccionado,
                )

    idx_sel = st.session_state.get(_KEY_CATALOGO_SEL)
    vista = st.session_state.get(_KEY_CATALOGO_VISTA)

    if idx_sel is None:
        st.caption(
            "Selecciona un modelo para ver su ficha y el diagrama de flujo."
        )
        return

    st.divider()

    if idx_sel == _CATALOGO_SEL_MAESTRO:
        st.markdown("### Diagrama de flujo único — Procedimiento maestro")
        if vista in ("pdf", "txt"):
            _visor_diagrama_catalogo(
                modelo_id=id_diagrama_flujo_unico,
                key_suffix="maestro",
            )
        else:
            st.button(
                "Abrir diagrama",
                key="pde_cat_abrir_diag_maestro",
                on_click=_set_catalogo_vista,
                args=("pdf",),
            )
        return

    try:
        idx_sel = int(idx_sel)
    except (TypeError, ValueError):
        st.session_state.pop(_KEY_CATALOGO_SEL, None)
        return
    if idx_sel < 0 or idx_sel >= len(CATALOGO_MODOS_IMPACTO):
        st.session_state.pop(_KEY_CATALOGO_SEL, None)
        return

    _detalle_modelo_catalogo(CATALOGO_MODOS_IMPACTO[idx_sel], idx=idx_sel)


def _resultados_impactos_puerto() -> None:
    """Muestra el resumen consolidado de cada activo (CP) tras calcular."""
    resultado_puerto = st.session_state.get("resultado_calculo_puerto")
    if resultado_puerto is None:
        resultado = st.session_state.get("resultado_calculo_activo")
        if resultado is not None and resultado.ok:
            resultado_puerto = type("LegacyPuerto", (), {
                "ok": True,
                "error": "",
                "advertencias": getattr(resultado, "advertencias", []),
                "modos_sin_modelo": [],
                "cp_total": int(st.session_state.get("cp_total_activos", 1)),
                "resultados_por_activo": [resultado],
            })()
        else:
            return

    if not resultado_puerto.ok:
        st.warning(resultado_puerto.error or "Error en el cálculo.")
        return

    _mostrar_modos_sin_modelo(getattr(resultado_puerto, "modos_sin_modelo", []))

    if resultado_puerto.advertencias:
        for adv in resultado_puerto.advertencias:
            if "No hay modos de superación de umbral" in adv:
                continue
            st.warning(adv)

    cp_total = resultado_puerto.cp_total or len(resultado_puerto.resultados_por_activo)
    for resultado in resultado_puerto.resultados_por_activo:
        etiqueta_activo = resultado.activo_raw or resultado.activo
        if not resultado.ok:
            error_txt = resultado.error or "Sin resultados para este activo."
            if "No hay modos de superación de umbral" in error_txt:
                continue
            st.divider()
            st.markdown(
                f"### CP {resultado.cp_numero}/{cp_total} — {etiqueta_activo}"
            )
            st.error(error_txt)
            if resultado.advertencias:
                for adv in resultado.advertencias:
                    if "No hay modos de superación de umbral" in adv:
                        continue
                    st.warning(adv)
            continue

    resultados = [
        r for r in resultado_puerto.resultados_por_activo
        if r.ok
    ]
    if not resultados:
        return

    cp_total = resultado_puerto.cp_total or len(resultados)
    st.subheader("Activos")
    for resultado in resultados:
        iteraciones = iteraciones_desde_calculo_activo(resultado)
        fb_esperado = getattr(resultado, "resultado_francobordo", None) is not None
        fb_en_iter = any("francobordo" in it.modo_fallo.lower() for it in iteraciones)
        if fb_esperado and not fb_en_iter:
            st.warning(
                f"CP {resultado.cp_numero}/{cp_total} — "
                f"{resultado.activo_raw or resultado.activo}: "
                f"PI falta de francobordo calculado pero no aparece en la vista."
            )
        if not iteraciones:
            continue
        resumen_activo = resumen_activo_desde_calculo_activo(resultado)
        if fb_en_iter and resumen_activo is not None:
            fb_en_resumen = any(
                "francobordo" in m.lower() for m in resumen_activo.modos_fallo
            )
            if not fb_en_resumen:
                st.warning(
                    f"CP {resultado.cp_numero}/{cp_total} — "
                    f"{resultado.activo_raw or resultado.activo}: "
                    f"PI falta de francobordo no incluido en el resumen consolidado."
                )
        vista = construir_vista_resultados_activo(
            resultado,
            iteraciones=iteraciones,
            resumen_activo=resumen_activo,
            cp_numero=resultado.cp_numero,
            cp_total=cp_total,
        )
        if vista is None:
            continue
        st.divider()
        _mostrar_vista_cp_im(vista)


def _mostrar_informe_validacion_puerto(validacion: ResultadoValidacionPuerto) -> None:
    """Muestra el resumen (banner) de validacion automatica antes del calculo."""
    stats = resumen_validacion(validacion)
    n_activos = stats["activos"]
    n_errores = stats["errores"]
    n_adv = stats["advertencias"]
    n_sin_modelo = stats["modos_sin_modelo"]
    n_calc = stats["activos_calculables"]

    if n_errores == 0 and n_adv == 0:
        st.success(
            f"Validacion correcta: {n_activos} activo(s) detectado(s), "
            f"{n_calc} con al menos un modo calculable."
        )
        return

    if n_errores:
        st.warning(
            f"Validacion: {n_activos} activo(s), {n_errores} error(es), "
            f"{n_adv} aviso(s), {n_sin_modelo} modo(s) sin metodologia. "
            f"Se calculara lo que sea posible ({n_calc} activo(s) con modos validos)."
        )
    else:
        st.info(
            f"Validacion: {n_activos} activo(s), {n_adv} aviso(s), "
            f"{n_sin_modelo} modo(s) sin metodologia implementada."
        )


def _mostrar_detalle_validacion_puerto(validacion: ResultadoValidacionPuerto) -> None:
    """Expander con el detalle de avisos/errores de validacion."""
    stats = resumen_validacion(validacion)
    n_errores = stats["errores"]
    n_adv = stats["advertencias"]
    if n_errores == 0 and n_adv == 0:
        return

    with st.expander(
        f"Detalle de validacion ({n_errores} errores, {n_adv} avisos)",
        expanded=n_errores > 0,
    ):
        filas = []
        for aviso in validacion.avisos:
            filas.append({
                "Nivel": aviso.nivel,
                "Activo": aviso.activo,
                "Modo": aviso.modo_fallo or "—",
                "Variable": aviso.variable or "—",
                "Tipo": aviso.tipo_impacto or "—",
                "Input faltante": aviso.input_faltante or "—",
                "Archivo / hoja": (
                    f"{aviso.archivo}" + (f" / {aviso.hoja}" if aviso.hoja else "")
                ),
                "Mensaje": aviso.mensaje,
            })
        if filas:
            st.dataframe(
                pd.DataFrame(filas),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Sin avisos.")


def _seccion_modelos_impactos() -> None:
    """Catálogo y diagramas de modos de impacto (menú MODELOS)."""
    _cabecera_seccion("Modelos de impactos")
    _bloque_catalogo_modos_impacto(expanded=True)


def _seccion_calculo_impactos() -> None:
    """Cálculo, validación y resultados de impactos (menú RIESGO)."""
    meta_clima = fuente("clima")
    meta_cfg = fuente("config_puerto")
    try:
        _obtener_clima(_firma_datos_excel())
    except FileNotFoundError:
        st.warning(
            f"No se encontró `{nombre_archivo_display(meta_clima)}`. "
            "Necesario para calcular los modelos."
        )
        return

    config_df = None
    try:
        config_df, _ = _obtener_config_puerto(_firma_datos_excel())
    except FileNotFoundError:
        st.error(_mensaje_excel_no_encontrado(meta_cfg))

    _cabecera_seccion("Cálculo de impactos")

    if config_df is None or config_df.empty:
        st.error(_mensaje_excel_no_encontrado(meta_cfg))
        return

    _activo, activo_raw, cp_num, cp_total, fila_cfg = _selector_activo_cp(config_df)
    st.session_state.cp_numero_actual = cp_num
    st.session_state.cp_total_activos = cp_total

    pulsar, params = _bloque_calculo_activo()
    if pulsar:
        # Siempre recomputar: no reutilizar resultado_calculo_* de un filtro anterior.
        _limpiar_resultados_calculo()
        try:
            # Copia superficial: evita mutar el objeto cacheado por @st.cache_data.
            repo = copy(_obtener_repositorio(_firma_datos_excel()))
        except FileNotFoundError as exc:
            st.error(str(exc))
            return

        filtro_nf = _filtro_impactos_no_factibles_sesion()
        huella_nf = _huella_filtro_no_factibles(filtro_nf)
        validacion = validar_puerto_antes_calculo(
            repo,
            filtro_impactos_no_factibles=filtro_nf,
        )
        _mostrar_informe_validacion_puerto(validacion)
        st.session_state.ultima_validacion_puerto = validacion

        if not validacion.puede_calcular:
            st.error(
                "No se puede ejecutar el calculo: faltan archivos criticos o "
                "no hay activos en Configuracion del puerto."
            )
            _mostrar_detalle_validacion_puerto(validacion)
            return

        resultado_puerto = calcular_impactos_puerto(
            repo,
            filtro_impactos_no_factibles=filtro_nf,
        )
        st.session_state.resultado_calculo_puerto = resultado_puerto
        st.session_state._huella_filtro_nf_resultado = huella_nf
        st.session_state.cp_total_activos = resultado_puerto.cp_total
        primer_ok = next(
            (r for r in resultado_puerto.resultados_por_activo if r.ok),
            None,
        )
        st.session_state.resultado_calculo_activo = primer_ok
        st.session_state.resultado_pi = (
            primer_ok.resultado_agitacion if primer_ok else None
        )

    if pulsar:
        _mostrar_detalle_validacion_puerto(validacion)

    _resultados_impactos_puerto()


def _seccion_modelos_economicos() -> None:
    _seccion_en_desarrollo("Modelos económicos")


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def main() -> None:
    _invalidar_resultados_si_cambian_excel()
    _invalidar_resultados_si_cambia_filtro_no_factibles()
    vista = _cabecera_branding_y_menu()
    _render_vista(vista)
    mostrar_pie_branding()


if __name__ == "__main__":
    main()
