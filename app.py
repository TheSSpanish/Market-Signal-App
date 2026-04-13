
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

from market_signal import (
    analyze_ticker,
    allocate_capital_top,
    benchmark_for_ticker,
    format_currency,
    parse_watchlist,
    save_scan_exports,
)

APP_TITLE = "Market Signal App"
EXPORT_DIR = Path(__file__).resolve().parent / "exports"

st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown("""
<style>
/* Texto general */
html, body, [class*="css"] {
    color: #f5f5f5 !important;
}

/* Dataframe base */
[data-testid="stDataFrame"] {
    background-color: #111827 !important;
    color: #f9fafb !important;
    border-radius: 10px;
    overflow: hidden;
}

/* Cabecera tabla */
[data-testid="stDataFrame"] th {
    background-color: #111827 !important;
    color: #f9fafb !important;
    font-weight: 700 !important;
    border-bottom: 1px solid #374151 !important;
}

/* Celdas */
[data-testid="stDataFrame"] td {
    color: #f9fafb !important;
    border-color: #374151 !important;
}

/* Selectbox / inputs */
div[data-baseweb="select"] * {
    color: #f9fafb !important;
}
div[data-baseweb="select"] {
    background-color: #111827 !important;
}

/* Botones */
button {
    color: #ffffff !important;
}

/* Métricas */
[data-testid="stMetric"] {
    background-color: #111827;
    padding: 10px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title(APP_TITLE)
st.caption("Herramienta heurística de apoyo a decisión. No es asesoramiento financiero ni una garantía de resultados.")

DEFAULT_WATCHLIST = "^IBEX, ACS.MC, ACX.MC, AENA.MC, AMS.MC, ANA.MC, ANE.MC, BBVA.MC, BKT.MC, CABK.MC, CLNX.MC, COL.MC, ELE.MC, ENG.MC, FDR.MC, FER.MC, GRF.MC, IAG.MC, IBE.MC, IDR.MC, ITX.MC, LOG.MC, MAP.MC, MRL.MC, MTS.MC, NTGY.MC, PUIG.MC, RED.MC, REP.MC, ROVI.MC, SAB.MC, SAN.MC, SCYR.MC, SLR.MC, TEF.MC, UNI.MC, VIS.MC"


@st.cache_data(ttl=900, show_spinner=False)
def get_history_cached(ticker: str, period: str = "1y") -> pd.DataFrame:
    data = yf.download(
        tickers=ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna(how="all")


@st.cache_data(ttl=3600, show_spinner=False)
def get_name_cached(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker


def build_config() -> dict:
    with st.sidebar:
        st.header("Configuración")
        capital_total = st.number_input("Capital total (€)", min_value=100.0, value=10000.0, step=100.0)
        risk_pct = st.slider("Riesgo por trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
        commission_buy = st.number_input("Comisión compra (€)", min_value=0.0, value=1.0, step=0.5)
        commission_sell = st.number_input("Comisión venta (€)", min_value=0.0, value=1.0, step=0.5)
        apply_tobin = st.checkbox("Aplicar Tobin aprox. a acciones españolas (.MC)", value=True)
        tobin_rate = st.number_input("Tasa Tobin (%)", min_value=0.0, max_value=2.0, value=0.2, step=0.1)

        st.subheader("Filtros de operabilidad")
        cost_obj_max = st.number_input("Coste/obj % máx", min_value=1.0, max_value=100.0, value=35.0, step=1.0)
        cost_pos_max = st.number_input("Coste/posic % máx", min_value=0.1, max_value=10.0, value=1.5, step=0.1)
        rb_net_min = st.number_input("R/B neto mín", min_value=0.1, max_value=10.0, value=1.5, step=0.1)
        strict_mode = st.checkbox("Modo exigente", value=False)
        if strict_mode:
            cost_obj_max = 25.0
            cost_pos_max = 1.0
            rb_net_min = 2.0
            st.info("Modo exigente activo: Coste/obj 25 | Coste/posic 1.0 | R/B neto 2.0")

        st.subheader("Modo capital completo")
        capital_mode = st.checkbox("Priorizar invertir el capital del Top 1-3", value=True)
        max_positions = st.slider("Máx. posiciones para capital completo", min_value=1, max_value=3, value=2, step=1)
        st.caption("Este modo reparte el capital total entre las mejores candidatas netas, en vez de dividirlo en mini posiciones por riesgo.")

    return {
        "capital_total": capital_total,
        "risk_pct": risk_pct / 100.0,
        "commission_buy": commission_buy,
        "commission_sell": commission_sell,
        "apply_tobin": apply_tobin,
        "tobin_rate": tobin_rate / 100.0,
        "cost_obj_max_pct": cost_obj_max,
        "cost_pos_max_pct": cost_pos_max,
        "rb_net_min": rb_net_min,
        "capital_mode": capital_mode,
        "max_positions": max_positions,
    }


def status_badge(color: str, label: str) -> str:
    palette = {
        "VERDE": "#2e7d32",
        "AMARILLO": "#f9a825",
        "ROJO": "#c62828",
        "GRIS": "#6b7280",
    }
    bg = palette.get(color, "#6b7280")
    return f"<span style='background:{bg};color:white;padding:0.25rem 0.6rem;border-radius:999px;font-weight:600'>{label}</span>"


def render_detail(result: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precio actual", format_currency(result["Precio actual"]))
    c2.metric("Score", f'{result["Score"]:.2f}')
    c3.metric("Señal", result["Señal"])
    c4.markdown(status_badge(result["Semáforo"], result["Semáforo"]), unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Tendencia", result["Tendencia"])
    c6.metric("Confianza", result["Confianza"])
    c7.metric("Benchmark", result["Benchmark"])
    c8.metric("Operable neta", result["Operable neta"])

    st.write("")
    left, right = st.columns([1.2, 1])
    with left:
        metrics_df = pd.DataFrame(
            [
                ("Rel. 1m", f'{result["Rel. 1m"]:.2f}%'),
                ("Rel. 3m", f'{result["Rel. 3m"]:.2f}%'),
                ("Est. 5d", result["Est. 5d"]),
                ("Est. 20d", result["Est. 20d"]),
                ("Stop", format_currency(result["Stop"])),
                ("Objetivo", format_currency(result["Objetivo"])),
                ("Dist. stop", f'{result["Dist.stop"]:.2f}%'),
                ("Posición €", format_currency(result["Posic. €"])),
                ("Acciones estimadas", f'{result["Acciones est."]:.0f}'),
                ("Coste compra", format_currency(result["Coste compra"])),
                ("Coste venta", format_currency(result["Coste venta"])),
                ("Tobin compra", format_currency(result["Tobin compra"])),
                ("Coste total", format_currency(result["Costes"])),
                ("Pérdida máx. aprox.", format_currency(result["Pérdida máx €"])),
                ("R/B bruto", f'{result["R/B"]:.2f}'),
                ("R/B neto", f'{result["R/B neto"]:.2f}'),
                ("Benef. neto esperado", format_currency(result["Benef. neto €"])),
                ("Capital mínimo recomendado", format_currency(result["Cap.min €"])),
                ("Coste/obj %", f'{result["Coste/obj %"]:.2f}%'),
                ("Coste/posic %", f'{result["Coste/posic %"]:.2f}%'),
            ],
            columns=["Métrica", "Valor"],
        )
        st.dataframe(metrics_df, hide_index=True, use_container_width=True)
    with right:
        st.markdown("**Notas**")
        st.write(result["Notas"])
        st.caption(
            "Las estimaciones a 5 y 20 sesiones son heurísticas basadas en estructura, momentum, volatilidad y fuerza relativa."
        )


def style_scan_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def row_color(row):
        color = row["Semáforo"]
        if color == "VERDE":
            return ["background-color: #064e3b; color: #d1fae5"] * len(row)
        if color == "AMARILLO":
            return ["background-color: #78350f; color: #fef3c7"] * len(row)
        if color == "ROJO":
            return ["background-color: #7f1d1d; color: #fee2e2"] * len(row)
        return ["background-color: #1f2937; color: #e5e7eb"] * len(row)

    fmt = {
        "Precio actual": "{:,.2f}",
        "Score": "{:,.2f}",
        "Rel. 1m": "{:,.2f}%",
        "Rel. 3m": "{:,.2f}%",
        "Stop": "{:,.2f}",
        "Objetivo": "{:,.2f}",
        "Dist.stop": "{:,.2f}%",
        "R/B": "{:,.2f}",
        "R/B neto": "{:,.2f}",
        "Costes": "{:,.2f}",
        "Coste/obj %": "{:,.2f}%",
        "Coste/posic %": "{:,.2f}%",
        "Posic. €": "{:,.2f}",
        "Benef. neto €": "{:,.2f}",
        "Cap.min €": "{:,.2f}",
        "Est. 5d %": "{:,.2f}%",
        "Est. 20d %": "{:,.2f}%",
    }
    return df.style.apply(row_color, axis=1).format(fmt)


def scan_watchlist_ui(config: dict) -> None:
    st.subheader("Escáner de watchlist")
    watchlist_text = st.text_area("Tickers separados por comas", value=DEFAULT_WATCHLIST, height=110)

    c1, c2, c3 = st.columns([1, 1, 1.2])
    only_operable = c1.checkbox("Solo candidatas operables", value=False)
    only_operable_net = c2.checkbox("Solo candidatas operables netas", value=False)
    run_scan = c3.button("Escanear watchlist", type="primary", use_container_width=True)

    if run_scan:
        tickers = parse_watchlist(watchlist_text)
        if not tickers:
            st.warning("No hay tickers válidos.")
            return

        results = []
        benchmarks = {benchmark_for_ticker(t) for t in tickers}
        with st.spinner("Descargando datos y calculando señales..."):
            bench_data = {b: get_history_cached(b) for b in benchmarks}
            for ticker in tickers:
                try:
                    hist = get_history_cached(ticker)
                    result = analyze_ticker(
                        ticker=ticker,
                        hist=hist,
                        benchmark_hist=bench_data.get(benchmark_for_ticker(ticker)),
                        display_name=get_name_cached(ticker),
                        config=config,
                    )
                    if result:
                        results.append(result)
                except Exception as exc:
                    st.warning(f"{ticker}: {exc}")

        if not results:
            st.error("No se pudieron calcular resultados.")
            return

        df = pd.DataFrame(results)
        df = df.sort_values(["Score", "R/B neto", "Rel. 1m"], ascending=[False, False, False]).reset_index(drop=True)
        df.insert(0, "Ranking", range(1, len(df) + 1))

        if only_operable:
            df = df[df["Operable"] == "Sí"].copy()
        if only_operable_net:
            df = df[df["Operable neta"] == "Sí"].copy()

        if df.empty:
            st.info("Tras aplicar los filtros no quedan candidatas.")
            return

        st.session_state["last_scan_df"] = df.copy()

        top3 = df.head(3).copy()
        st.markdown("### TOP 3 DEL DÍA")
        top_cols = st.columns(min(3, len(top3)))
        for idx, (_, row) in enumerate(top3.iterrows()):
            with top_cols[idx]:
                st.markdown(status_badge(row["Semáforo"], row["Señal"]), unsafe_allow_html=True)
                st.markdown(f"**{row['Ticker']}**")
                st.write(f"Score: {row['Score']:.2f}")
                st.write(f"R/B neto: {row['R/B neto']:.2f}")
                st.write(f"Benef. neto €: {row['Benef. neto €']:.2f}")

        if st.button("Ver Top 3 del día"):
            st.dataframe(top3, hide_index=True, use_container_width=True)

        if config.get("capital_mode", False):
            alloc_df = allocate_capital_top(
                df=df,
                total_capital=float(config["capital_total"]),
                max_positions=int(config.get("max_positions", 2)),
                commission_buy=float(config["commission_buy"]),
                commission_sell=float(config["commission_sell"]),
                apply_tobin=bool(config["apply_tobin"]),
                tobin_rate=float(config["tobin_rate"]),
            )
            st.markdown("### Capital completo sugerido")
            if alloc_df.empty:
                st.info("No hay candidatas netas suficientes para repartir el capital completo con los filtros actuales.")
            else:
                total_neto_obj = float(alloc_df["Benef. neto objetivo €"].sum())
                total_neto_est5 = float(alloc_df["Benef. neto est. 5d €"].sum())
                ccap1, ccap2, ccap3 = st.columns(3)
                ccap1.metric("Capital total analizado", format_currency(float(config["capital_total"])))
                ccap2.metric("Benef. neto total al objetivo", format_currency(total_neto_obj))
                ccap3.metric("Benef. neto total est. 5d", format_currency(total_neto_est5))

                fmt_alloc = {
                    "Score": "{:,.2f}",
                    "R/B neto": "{:,.2f}",
                    "Peso %": "{:,.2f}%",
                    "Capital asignado €": "{:,.2f}",
                    "Acciones capital completo": "{:,.0f}",
                    "Posición capital completo €": "{:,.2f}",
                    "Costes capital completo €": "{:,.2f}",
                    "Benef. neto objetivo €": "{:,.2f}",
                    "Benef. neto est. 5d €": "{:,.2f}",
                    "Objetivo": "{:,.2f}",
                    "Precio actual": "{:,.2f}",
                }
                st.dataframe(alloc_df.style.format(fmt_alloc), hide_index=True, use_container_width=True)
                st.caption("Aquí el sistema deja de priorizar mini posiciones por riesgo y reparte el capital total entre las mejores 1–3 candidatas netas.")

        columns_to_show = [
            "Ranking", "Ticker", "Precio actual", "Score", "Señal", "Tendencia", "Confianza",
            "Rel. 1m", "Rel. 3m", "Est. 5d", "Est. 20d", "Stop", "Objetivo", "Dist.stop",
            "R/B", "R/B neto", "Costes", "Coste/obj %", "Coste/posic %", "Posic. €",
            "Benef. neto €", "Cap.min €", "Semáforo", "Operable", "Operable neta"
        ]
        st.dataframe(style_scan_table(df[columns_to_show]), hide_index=True, use_container_width=True)

        detail_ticker = st.selectbox(
            "Ver detalle de un ticker del último escaneo",
            options=df["Ticker"].tolist(),
            index=0,
        )
        if detail_ticker:
            detail_row = df.loc[df["Ticker"] == detail_ticker].iloc[0].to_dict()
            st.markdown(f"### Detalle de {detail_ticker}")
            render_detail(detail_row)

        csv_bytes, excel_bytes, csv_path, xlsx_path = save_scan_exports(df, EXPORT_DIR)
        d1, d2 = st.columns(2)
        d1.download_button("Descargar CSV", data=csv_bytes, file_name=Path(csv_path).name, mime="text/csv")
        d2.download_button(
            "Descargar Excel",
            data=excel_bytes,
            file_name=Path(xlsx_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption(f"También se guardaron copias locales en: {EXPORT_DIR}")


def individual_analysis_ui(config: dict) -> None:
    st.subheader("Análisis individual")
    c1, c2 = st.columns([2, 1])
    with c1:
        ticker = st.text_input("Ticker", value="VIS.MC").strip().upper()
    with c2:
        analyze_btn = st.button("Analizar ticker", type="primary", use_container_width=True)

    if analyze_btn and ticker:
        with st.spinner("Descargando datos y calculando..."):
            hist = get_history_cached(ticker)
            bench = benchmark_for_ticker(ticker)
            bench_hist = get_history_cached(bench)
            result = analyze_ticker(
                ticker=ticker,
                hist=hist,
                benchmark_hist=bench_hist,
                display_name=get_name_cached(ticker),
                config=config,
            )

        if not result:
            st.error("No se pudo calcular el análisis con los datos recibidos.")
            return

        st.markdown(f"### {result['Nombre']}")
        render_detail(result)


config = build_config()

tab1, tab2, tab3 = st.tabs(["Análisis individual", "Escáner", "Ayuda rápida"])

with tab1:
    individual_analysis_ui(config)

with tab2:
    scan_watchlist_ui(config)

with tab3:
    st.markdown(
        """
        **Cómo usarla**
        1. Ajusta capital, riesgo y costes en la barra lateral.  
        2. Escanea tu watchlist o analiza un ticker concreto.  
        3. Prioriza señales con semáforo VERDE y operabilidad neta.  
        4. Contrasta siempre con tu propio criterio.

        **Importante**
        - La app usa datos de Yahoo Finance vía `yfinance`.
        - Las estimaciones son orientativas y heurísticas.
        - El modelo está pensado para largos (compras), no para cortos.
        - Si activas **Modo capital completo**, la app prioriza repartir el capital total entre las mejores 1–3 candidatas netas, en vez de seguir el tamaño de posición clásico por riesgo.
        """
    )
