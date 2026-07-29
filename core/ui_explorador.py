# -*- coding: utf-8 -*-
"""UI Streamlit: explorador de indicadores .mat (localizacion + mapa de calor).

Version: 2026-07-27c (escenario primero; historico sin periodo).
"""

from __future__ import annotations

from pathlib import Path

from io import BytesIO
import base64

import folium
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_folium import st_folium

from core.data_loader import cargar_lista_puertos
from core.mat_indicadores import (
    MISSING,
    PERCENTILES_UI,
    RUTA_INDICADORES_DEFAULT,
    ImpactoCargado,
    cargar_impacto,
    describir_punto_cercano,
    descubrir_impactos,
    etiqueta_impacto,
    fmt_valor,
    listar_drivers,
    nearest_port_index,
    puerto_mas_cercano,
    sample_espacial,
    tabla_indicadores_localizacion,
    valor_en_celda,
    valores_puertos_mapa,
)

CENTRO_ESPANA = [40.2, -3.5]
ZOOM_ESPANA = 6
_COLOR_BAJO = "#08306b"
_COLOR_MEDIO = "#2171b5"
_COLOR_CLARO = "#6baed6"
_COLOR_ALTO = "#deebf7"
# Escala: valor pequeno = claro, valor grande = oscuro.
ESCALA_COLORES = [_COLOR_ALTO, _COLOR_CLARO, _COLOR_MEDIO, _COLOR_BAJO]
ESCENARIO_HISTORICO = "historico"


def _tipo_es(tipo: str) -> str:
    return {
        "espacial": "mapa de calor",
        "puertos": "por puerto",
        "desconocido": "sin clasificar",
    }.get(tipo, tipo)


def _coords_puertos() -> pd.DataFrame:
    df, _info = cargar_lista_puertos()
    cols = [c for c in ("puerto", "lat", "lon") if c in df.columns]
    return df[cols].dropna(subset=["lat", "lon"]).copy()


def _hex_a_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _color_por_escala(t: float, colores: list[str] | None = None) -> tuple[int, int, int]:
    """Interpola color en [0,1] sobre la escala compartida."""
    colores = colores or ESCALA_COLORES
    rgb = [_hex_a_rgb(c) for c in colores]
    t = float(np.clip(t, 0.0, 1.0))
    if len(rgb) == 1:
        return rgb[0]
    pos = t * (len(rgb) - 1)
    i = int(np.floor(pos))
    j = min(i + 1, len(rgb) - 1)
    f = pos - i
    r = int(rgb[i][0] + (rgb[j][0] - rgb[i][0]) * f)
    g = int(rgb[i][1] + (rgb[j][1] - rgb[i][1]) * f)
    b = int(rgb[i][2] + (rgb[j][2] - rgb[i][2]) * f)
    return r, g, b


def _color_valor(v: float, vmin: float, vmax: float) -> str:
    if not np.isfinite(v) or vmax <= vmin:
        return "#6b7280"
    t = float(np.clip((v - vmin) / (vmax - vmin), 0.0, 1.0))
    r, g, b = _color_por_escala(t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _capa_raster_valores(
    lat: np.ndarray,
    lon: np.ndarray,
    valores: np.ndarray,
    *,
    vmin: float,
    vmax: float,
) -> folium.raster_layers.ImageOverlay | None:
    """Imagen coloreada segun el valor real (misma escala que la leyenda)."""
    grid = np.asarray(valores, dtype=float)
    la = np.asarray(lat, dtype=float)
    lo = np.asarray(lon, dtype=float)
    if grid.ndim != 2 or grid.shape != la.shape or grid.shape != lo.shape:
        return None

    mask = np.isfinite(grid) & np.isfinite(la) & np.isfinite(lo)
    if not mask.any():
        return None

    denom = vmax - vmin if vmax > vmin else 1.0
    t = np.zeros(grid.shape, dtype=float)
    t[mask] = np.clip((grid[mask] - vmin) / denom, 0.0, 1.0)
    lut = np.array(
        [_color_por_escala(i / 255.0) for i in range(256)], dtype=np.uint8
    )
    idx = np.round(t * 255).astype(np.int32)
    idx = np.clip(idx, 0, 255)
    rgb = lut[idx]
    alpha = np.where(mask, 200, 0).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])

    # PNG: fila 0 = arriba. Si lat crece hacia abajo en el array, voltear.
    lat_row0 = float(np.nanmean(la[0, :]))
    lat_row_last = float(np.nanmean(la[-1, :]))
    if lat_row0 < lat_row_last:
        rgba = np.flipud(rgba)

    img = Image.fromarray(rgba, mode="RGBA")
    max_side = 640
    if max(img.size) > max_side:
        img = img.resize(
            (
                max(1, int(img.width * max_side / max(img.size))),
                max(1, int(img.height * max_side / max(img.size))),
            ),
            Image.Resampling.BILINEAR,
        )

    buf = BytesIO()
    img.save(buf, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    south = float(np.nanmin(la))
    north = float(np.nanmax(la))
    west = float(np.nanmin(lo))
    east = float(np.nanmax(lo))
    return folium.raster_layers.ImageOverlay(
        image=uri,
        bounds=[[south, west], [north, east]],
        opacity=0.85,
        interactive=False,
        cross_origin=False,
        zindex=1,
    )


def _mapa_base(centro=None, zoom: int | None = None) -> folium.Map:
    return folium.Map(
        location=centro or CENTRO_ESPANA,
        zoom_start=zoom or ZOOM_ESPANA,
        tiles="CartoDB positron",
        control_scale=True,
    )


def _anadir_marcador(mapa: folium.Map, lat: float, lon: float, popup: str = "") -> None:
    folium.Marker(
        location=[lat, lon],
        popup=popup or f"{lat:.3f}, {lon:.3f}",
        icon=folium.Icon(color="blue", icon="map-marker", prefix="fa"),
    ).add_to(mapa)


def _mostrar_escala_streamlit(
    *,
    vmin: float,
    vmax: float,
    titulo: str,
    colores: list[str] | None = None,
) -> None:
    """Escala de colores debajo del mapa (misma que el raster)."""
    colores = colores or ESCALA_COLORES
    gradiente = ", ".join(colores)
    st.markdown(
        f"""
<div style="margin-top: -0.4rem; margin-bottom: 0.6rem;">
  <div style="font-size: 0.85rem; font-weight: 600; margin-bottom: 0.25rem;">{titulo}</div>
  <div style="height: 16px; border-radius: 4px; border: 1px solid #94a3b8;
       background: linear-gradient(to right, {gradiente});"></div>
  <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #334155;">
    <span>{vmin:.4g}</span><span>{vmax:.4g}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _etiqueta_escenario(esc: str) -> str:
    clave = str(esc).strip().lower().replace("-", "").replace(".", "").replace(" ", "")
    if clave in {"historico", "baseline", "hist"}:
        return "Historico"
    if "245" in clave:
        return "SSP2-4.5"
    if "585" in clave:
        return "SSP5-8.5"
    return str(esc)


def _opciones_escenario(escenarios_mat: list[str]) -> list[tuple[str, str]]:
    """Historico + SSPs del .mat (ssp245 / ssp585)."""
    ops: list[tuple[str, str]] = [(ESCENARIO_HISTORICO, "Historico")]
    vistos = {ESCENARIO_HISTORICO}
    for e in escenarios_mat:
        eid = str(e).strip().lower()
        if not eid or eid in vistos:
            continue
        vistos.add(eid)
        ops.append((eid, _etiqueta_escenario(eid)))
    if len(ops) == 1:
        ops.append(("ssp245", "SSP2-4.5"))
        ops.append(("ssp585", "SSP5-8.5"))
    return ops


def _opciones_periodo(centros: list[int]) -> list[tuple[str, int]]:
    """Solo horizontes futuros 2030-2100. Sin historico."""
    ops: list[tuple[str, int]] = []
    for i, y in enumerate(centros):
        year = int(y)
        if 2030 <= year <= 2100:
            ops.append((str(year), i))
    return ops


def _indice_escenario_mat(escenario: str, escenarios_mat: list[str]) -> int:
    if not escenarios_mat:
        return 0
    lower = [e.lower() for e in escenarios_mat]
    if escenario.lower() in lower:
        return lower.index(escenario.lower())
    if escenario.lower() == "ssp585" and len(escenarios_mat) > 1:
        return 1
    return 0


def _resolver_seleccion_escenario_periodo(
    escenarios_mat: list[str],
    centros: list[int],
    *,
    key_esc: str = "viz_esc",
    key_per: str = "viz_periodo",
) -> tuple[str, int | None, int, str]:
    """Primero escenario; periodo solo si no es historico."""
    esc_ops = _opciones_escenario(escenarios_mat)
    ids = [e[0] for e in esc_ops]
    labels = {e[0]: e[1] for e in esc_ops}

    escenario = st.selectbox(
        "Escenario",
        options=ids,
        format_func=lambda x: labels.get(x, x),
        key=key_esc,
    )

    if escenario == ESCENARIO_HISTORICO:
        st.selectbox(
            "Periodo",
            options=["(no aplica)"],
            key=f"{key_per}_hist",
            disabled=True,
            help="El escenario Historico no tiene ano de periodo; usa la linea base.",
        )
        return escenario, None, 0, "Historico"

    per_ops = _opciones_periodo(centros)
    esc_idx = _indice_escenario_mat(escenario, escenarios_mat)
    if not per_ops:
        st.selectbox(
            "Periodo",
            options=["-"],
            key=f"{key_per}_empty",
            disabled=True,
        )
        return escenario, None, esc_idx, labels.get(escenario, escenario)

    periodo_label = st.selectbox(
        "Periodo",
        options=[p[0] for p in per_ops],
        key=key_per,
        help="Horizontes futuros del archivo (2030-2100).",
    )
    periodo_idx = next(p[1] for p in per_ops if p[0] == periodo_label)
    etiqueta = f"{labels.get(escenario, escenario)} / {periodo_label}"
    return escenario, periodo_idx, esc_idx, etiqueta


def _consumir_clic_pendiente() -> None:
    pendiente = st.session_state.pop("_pending_map_click", None)
    if not pendiente:
        return
    lat_c, lon_c = pendiente
    st.session_state["exp_lat"] = float(lat_c)
    st.session_state["exp_lon"] = float(lon_c)
    st.session_state["exp_mostrar_tabla"] = True


def _aplicar_clic_mapa(map_state: dict | None, *, estado_key: str = "_exp_last_click") -> bool:
    if not map_state:
        return False
    click = map_state.get("last_clicked")
    if not click or "lat" not in click or "lng" not in click:
        return False
    lat_c = round(float(click["lat"]), 4)
    lon_c = round(float(click["lng"]), 4)
    actual = (lat_c, lon_c)
    if st.session_state.get(estado_key) == actual:
        return False
    st.session_state[estado_key] = actual
    st.session_state["_pending_map_click"] = actual
    return True


def _cargar_seleccion(infos, driver_ids: list[str]) -> list[ImpactoCargado]:
    cargados: list[ImpactoCargado] = []
    for info in infos:
        if info.driver_id not in driver_ids:
            continue
        if info.n_con_datos == 0:
            continue
        try:
            cargados.append(cargar_impacto(str(info.ruta.resolve())))
        except Exception as exc:  # noqa: BLE001
            st.warning(f"No se pudo leer `{info.ruta.name}`: {exc}")
    return cargados


def _tab_localizacion(infos, drivers, coords: pd.DataFrame) -> None:
    col_side, col_map = st.columns([1.05, 2.2], gap="medium")

    with col_side:
        st.markdown("##### Localizacion")
        st.caption("Haz clic en el mapa para cambiar el punto.")

        busqueda = st.text_input(
            "Buscar puerto",
            placeholder="p. ej.: Santander",
            key="exp_busqueda",
        )
        if busqueda and not coords.empty:
            mask = coords["puerto"].astype(str).str.contains(
                busqueda, case=False, na=False
            )
            hits = coords.loc[mask]
            if not hits.empty:
                elegido = st.selectbox(
                    "Coincidencias",
                    options=hits.index.tolist(),
                    format_func=lambda i: str(hits.loc[i, "puerto"]),
                    key="exp_hit",
                )
                if st.button("Ir al puerto", key="exp_ir_puerto"):
                    st.session_state["_pending_map_click"] = (
                        round(float(hits.loc[elegido, "lat"]), 4),
                        round(float(hits.loc[elegido, "lon"]), 4),
                    )
                    st.session_state.pop("_exp_last_click", None)
                    st.rerun()
            else:
                st.caption("Sin coincidencias en la lista de puertos.")

        c1, c2 = st.columns(2)
        with c1:
            lat = st.number_input("Latitud", format="%.4f", key="exp_lat")
        with c2:
            lon = st.number_input("Longitud", format="%.4f", key="exp_lon")

        st.markdown("##### Variable / driver")
        driver_labels = {d: lab for d, lab in drivers}
        opciones = list(driver_labels.keys())
        con_datos = {i.driver_id for i in infos if i.n_con_datos > 0}
        default = [d for d in opciones if d in con_datos] or (
            opciones[:1] if opciones else []
        )

        driver_sel = (
            st.selectbox(
                "Driver climatico",
                options=opciones,
                index=(
                    opciones.index(default[0])
                    if default and default[0] in opciones
                    else 0
                ),
                format_func=lambda d: driver_labels.get(d, d),
                key="exp_driver_sel",
            )
            if opciones
            else None
        )

        incluir_todos = st.checkbox(
            "Incluir todos los drivers con datos",
            value=False,
            key="exp_drv_all",
        )
        if incluir_todos:
            seleccionados = [d for d in opciones if d in con_datos] or list(opciones)
        elif driver_sel:
            seleccionados = [driver_sel]
        else:
            seleccionados = []

        impactos_driver = [
            i for i in infos if i.driver_id in seleccionados and i.n_con_datos > 0
        ]
        if impactos_driver:
            st.caption(
                "Indicadores del driver: "
                + ", ".join(etiqueta_impacto(i.impacto_id) for i in impactos_driver)
            )

    cargados = _cargar_seleccion(infos, seleccionados)

    with col_map:
        lat = float(st.session_state["exp_lat"])
        lon = float(st.session_state["exp_lon"])
        mapa = _mapa_base(centro=[lat, lon], zoom=6)
        _anadir_marcador(mapa, lat, lon, f"{lat:.4f}, {lon:.4f}")

        cerca = puerto_mas_cercano(lat, lon, coords)
        if cerca:
            nom, la, lo, dist = cerca
            folium.CircleMarker(
                location=[la, lo],
                radius=8,
                color="#2563eb",
                fill=True,
                fill_color="#60a5fa",
                fill_opacity=0.9,
                popup=f"{nom}<br>{dist:.1f} km",
            ).add_to(mapa)

        for _, row in coords.iterrows():
            folium.CircleMarker(
                location=[float(row["lat"]), float(row["lon"])],
                radius=3,
                color="#94a3b8",
                fill=True,
                fill_opacity=0.55,
                popup=str(row["puerto"]),
            ).add_to(mapa)

        map_state = st_folium(
            mapa,
            width=None,
            height=520,
            key="exp_map_loc",
            returned_objects=["last_clicked"],
        )
        if _aplicar_clic_mapa(map_state):
            st.rerun()

        st.caption(
            f"Punto seleccionado: **{lat:.4f}**, **{lon:.4f}**. "
            "Al hacer clic se actualizan los indicadores del driver elegido "
            "en el punto de datos mas cercano."
        )

    lat = float(st.session_state["exp_lat"])
    lon = float(st.session_state["exp_lon"])
    st.markdown("##### Indicadores en el punto mas cercano")

    if cerca:
        st.info(
            f"Puerto de referencia mas cercano al clic: **{cerca[0]}** "
            f"({cerca[3]:.1f} km)."
        )

    if not seleccionados:
        st.warning("Selecciona un driver climatico.")
        return

    if not cargados:
        st.info(
            "No hay archivos `.mat` para este driver todavia. "
            f"Los valores ausentes se muestran como `{MISSING}`."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Indicador": driver_labels.get(d, d),
                        "Percentil": "P50",
                        "Historico": MISSING,
                    }
                    for d in seleccionados
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        return

    detalles = []
    for imp in cargados:
        meta = describir_punto_cercano(imp, lat, lon, coords)
        etiqueta = meta.get("etiqueta") or MISSING
        dist = meta.get("distancia_km")
        dist_txt = f"{dist:.1f} km" if isinstance(dist, (int, float)) else MISSING
        detalles.append(
            {
                "Indicador": (
                    f"{imp.info.driver_label} - {etiqueta_impacto(imp.info.impacto_id)}"
                ),
                "Punto de datos": etiqueta,
                "Distancia": dist_txt,
            }
        )
    st.dataframe(pd.DataFrame(detalles), use_container_width=True, hide_index=True)

    df = tabla_indicadores_localizacion(
        cargados,
        lat=lat,
        lon=lon,
        coords_puertos=coords,
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        "Valores del indicador en el punto/puerto mas cercano. "
        f"Si falta el dato se muestra `{MISSING}`."
    )


def _tab_visualizador(infos, drivers, coords: pd.DataFrame) -> None:
    col_side, col_map = st.columns([1.05, 2.2], gap="medium")

    with col_side:
        st.markdown("##### Variable climatica")
        driver_ids = [d for d, _ in drivers]
        con_datos = {i.driver_id for i in infos if i.n_con_datos > 0}
        idx_default = next(
            (i for i, d in enumerate(driver_ids) if d in con_datos), 0
        )
        driver = (
            st.selectbox(
                "Driver climatico",
                options=driver_ids,
                index=idx_default if driver_ids else 0,
                format_func=lambda d: dict(drivers).get(d, d),
                key="viz_driver",
            )
            if driver_ids
            else None
        )

        impactos_driver = [i for i in infos if i.driver_id == driver]
        cargado = None
        if not impactos_driver:
            st.info("Este driver aun no tiene archivos `.mat`.")
        else:
            impacto_id = st.selectbox(
                "Variable / impacto",
                options=[i.impacto_id for i in impactos_driver],
                format_func=lambda x: (
                    f"{etiqueta_impacto(x)} "
                    f"({_tipo_es(next(i.tipo for i in impactos_driver if i.impacto_id == x))})"
                ),
                key="viz_impacto",
            )
            info = next(i for i in impactos_driver if i.impacto_id == impacto_id)
            try:
                cargado = cargar_impacto(str(info.ruta.resolve()))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Error al leer el archivo: {exc}")

        centros: list[int] = []
        escenarios: list[str] = []
        if cargado:
            centros = list(cargado.centros)
            escenarios = list(cargado.escenarios)
            if not centros and cargado.series_puerto:
                centros = list(cargado.series_puerto[0].centros)
            if not escenarios and cargado.series_puerto:
                escenarios = list(cargado.series_puerto[0].escenarios)
            if not centros and cargado.campos_espaciales:
                centros = list(cargado.campos_espaciales[0].centros)
            if not escenarios and cargado.campos_espaciales:
                escenarios = list(cargado.campos_espaciales[0].escenarios)

        _escenario, periodo_idx, esc_idx, etiqueta_filtro = (
            _resolver_seleccion_escenario_periodo(escenarios, centros)
        )

        percentil = st.selectbox(
            "Percentil",
            options=list(PERCENTILES_UI),
            key="viz_perc",
            help=(
                "Los archivos actuales no incluyen dimension de percentil; "
                f"si no hay dato se muestra {MISSING}."
            ),
        )

        ocultar = st.checkbox("Ocultar capas en el mapa", value=False, key="viz_hide")

        lat = float(st.session_state.get("exp_lat", 43.439))
        lon = float(st.session_state.get("exp_lon", -3.792))
        st.markdown("##### Localizacion proxima a:")
        st.caption(f"Clic en el mapa para fijar: **{lat:.3f} lat / {lon:.3f} lon**")

    with col_map:
        mapa = _mapa_base(centro=[lat, lon], zoom=7)
        titulo_leyenda = "Valor"
        vmin = vmax = None

        if cargado and not ocultar:
            if cargado.campos_espaciales:
                campo = cargado.campos_espaciales[0]
                if percentil == "P50":
                    if periodo_idx is None:
                        grid = np.asarray(campo.baseline, dtype=float)
                    else:
                        try:
                            grid = np.asarray(
                                campo.proyecciones[periodo_idx, esc_idx], dtype=float
                            )
                        except Exception:
                            grid = np.array([])
                    if grid.size and grid.shape == campo.lat.shape:
                        fin = grid[np.isfinite(grid)]
                        if fin.size:
                            vmin = float(fin.min())
                            vmax = float(fin.max())
                            capa = _capa_raster_valores(
                                campo.lat,
                                campo.lon,
                                grid,
                                vmin=vmin,
                                vmax=vmax,
                            )
                            if capa is not None:
                                capa.add_to(mapa)
                            mapa.fit_bounds(
                                [
                                    [
                                        float(np.nanmin(campo.lat)),
                                        float(np.nanmin(campo.lon)),
                                    ],
                                    [
                                        float(np.nanmax(campo.lat)),
                                        float(np.nanmax(campo.lon)),
                                    ],
                                ]
                            )
                            titulo_leyenda = (
                                f"{etiqueta_impacto(cargado.info.impacto_id)} "
                                f"({etiqueta_filtro})"
                            )
            elif cargado.series_puerto:
                df_pts = valores_puertos_mapa(
                    cargado.series_puerto,
                    coords,
                    periodo=periodo_idx,
                    escenario_idx=esc_idx,
                )
                if percentil != "P50":
                    df_pts = df_pts.copy()
                    df_pts["valor"] = np.nan
                vals = df_pts["valor"].dropna()
                if not vals.empty:
                    vmin, vmax = float(vals.min()), float(vals.max())
                for _, row in df_pts.iterrows():
                    v = row["valor"]
                    color = (
                        _color_valor(float(v), vmin or 0.0, vmax or 1.0)
                        if v is not None and np.isfinite(v)
                        else "#cbd5e1"
                    )
                    texto = fmt_valor(v) if percentil == "P50" else MISSING
                    folium.CircleMarker(
                        location=[float(row["lat"]), float(row["lon"])],
                        radius=9,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.85,
                        popup=f"{row['puerto']}<br>Valor: {texto}",
                    ).add_to(mapa)
                titulo_leyenda = (
                    f"{etiqueta_impacto(cargado.info.impacto_id)} "
                    f"({etiqueta_filtro})"
                )

        _anadir_marcador(mapa, lat, lon)

        hay_escala = (
            vmin is not None
            and vmax is not None
            and np.isfinite(vmin)
            and np.isfinite(vmax)
        )
        # Una sola escala abajo del mapa (coincide con colores del raster).
        map_state = st_folium(
            mapa,
            width=None,
            height=560,
            key="exp_map_viz",
            returned_objects=["last_clicked"],
        )
        if hay_escala:
            _mostrar_escala_streamlit(
                vmin=float(vmin),
                vmax=float(vmax),
                titulo=titulo_leyenda,
            )
        if _aplicar_clic_mapa(map_state, estado_key="_viz_last_click"):
            st.rerun()

        st.markdown("##### Valor en el punto seleccionado")
        lat = float(st.session_state.get("exp_lat", lat))
        lon = float(st.session_state.get("exp_lon", lon))
        if not cargado or percentil != "P50":
            st.write(MISSING)
        elif cargado.campos_espaciales:
            campo = cargado.campos_espaciales[0]
            meta = describir_punto_cercano(cargado, lat, lon, coords)
            ij = sample_espacial(campo, lat, lon)
            if ij is None:
                st.write(MISSING)
            else:
                f, c = ij
                v = valor_en_celda(
                    campo, f, c, periodo=periodo_idx, escenario_idx=esc_idx
                )
                etiqueta = meta.get("etiqueta") or "celda"
                dist = meta.get("distancia_km")
                dist_txt = f" ({dist:.1f} km)" if isinstance(dist, (int, float)) else ""
                st.write(f"{etiqueta}{dist_txt}: **{fmt_valor(v)}**")
        elif cargado.series_puerto:
            idx = nearest_port_index(cargado.series_puerto, lat, lon, coords)
            if idx is None:
                st.write(MISSING)
            else:
                s = cargado.series_puerto[idx]
                meta = describir_punto_cercano(cargado, lat, lon, coords)
                dist = meta.get("distancia_km")
                dist_txt = f" ({dist:.1f} km)" if isinstance(dist, (int, float)) else ""
                if periodo_idx is None:
                    st.write(f"{s.puerto}{dist_txt}: **{fmt_valor(s.baseline)}**")
                else:
                    try:
                        v = float(s.proyecciones[periodo_idx, esc_idx])
                    except Exception:
                        v = None
                    st.write(f"{s.puerto}{dist_txt}: **{fmt_valor(v)}**")
        else:
            st.write(MISSING)


def render_explorador_indicadores(raiz: Path | None = None) -> None:
    if "exp_lat" not in st.session_state:
        st.session_state["exp_lat"] = 43.439
    if "exp_lon" not in st.session_state:
        st.session_state["exp_lon"] = -3.792
    _consumir_clic_pendiente()

    raiz = Path(raiz or RUTA_INDICADORES_DEFAULT)
    st.subheader("Explorador de indicadores climaticos")
    st.caption(f"Fuente de datos: `{raiz}`")

    if not raiz.is_dir():
        st.error(
            "No se encuentra la carpeta de indicadores. "
            "Crea la carpeta `indicadores/` en la raiz del proyecto "
            "o define la variable de entorno `PDE_INDICADORES_PATH`."
        )
        return

    infos = descubrir_impactos(raiz)
    drivers = listar_drivers(raiz)
    coords = _coords_puertos()

    if not infos:
        st.warning(
            "No hay archivos `.mat` en las carpetas de variables. "
            "Cuando se anadan (Impacto_1 / Impacto_11, ...), apareceran aqui. "
            f"Carpetas detectadas: {', '.join(d for d, _ in drivers) or 'ninguna'}."
        )

    tab_loc, tab_mapa = st.tabs(
        ["Explorador de localizacion", "Visualizador de mapa"]
    )
    with tab_loc:
        _tab_localizacion(infos, drivers, coords)
    with tab_mapa:
        _tab_visualizador(infos, drivers, coords)
