
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

from market_signal import (
    DEFAULT_IBEX_TICKERS,
    FILTERED_CONTINUO_TICKERS,
    DEFAULT_WATCHLIST_TEXT,
    allocate_capital_top,
    analyze_ticker,
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
html, body, [class*="css"] {
    color: #f5f5f5 !important;
}
[data-testid="stDataFrame"] {
    background-color: #111827 !important;
    color: #f9fafb !important;
    border-radius: 10px;
    overflow: hidden;
}
[data-testid="stDataFrame"] th {
    background-color: #111827 !important;
    color: #f9fafb !important;
    font-weight: 700 !important;
    border-bottom: 1px solid #374151 !important;
}
[data-testid="stDataFrame"] td {
    color: #f9fafb !important;
    border-color: #374151 !important;
}
button {
    color: #ffffff !important;
}
[data-testid="stMetric"] {
    background-color: #111827;
    padding: 10px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title(APP_TITLE)
st.caption("Herramienta heurística de apoyo a decisión. No es asesoramiento financiero ni una garantía de resultados.")

DEFAULT_WATCHLIST = DEFAULT_WATCHLIST_TEXT


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


def build_watchlist_from_presets(include_ibex: bool, include_continuo: bool, custom_text: str) -> str:
    tickers = []
    if include_ibex:
        tickers.extend(DEFAULT_IBEX_TICKERS)
    if include_continuo:
        tickers.extend(FILTERED_CONTINUO_TICKERS)
    tickers.extend(parse_watchlist(custom_text))
    return ", ".join(parse_watchlist(", ".join(tickers)))



def build_config() -> dict:
    with st.sidebar:
        st.header("Configuración")
        capital_total = st.number_input("Capital total (€)", min_value=100.0, value=3000.0, step=100.0)
        risk_pct = st.slider("Riesgo por trade (%)", min_value=0.1, max_value=5.0, value=1.5, step=0.1)

        st.subheader("Modo capital completo")
        capital_mode = st.checkbox("Priorizar invertir el capital del Top 1-3", value=True)
        max_positions = st.slider("Máx. posiciones para capital completo", min_value=1, max_value=3, value=2, step=1)
        st.caption("Si está activado, la salida principal se centra en las mejores 1–3 ideas y reparte ahí el capital.")

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

        st.subheader("Universo")
        include_ibex = st.checkbox("Incluir IBEX", value=True)
        include_continuo = st.checkbox("Incluir continuo filtrado", value=True)
        min_price_filter = st.number_input("Precio mínimo (€)", min_value=0.1, max_value=100.0, value=3.0, step=0.5)
        min_turnover_filter = st.number_input("Liquidez media mínima 20d (€)", min_value=10000.0, max_value=50000000.0, value=750000.0, step=50000.0)
        max_atr_pct_filter = st.number_input("ATR % máximo", min_value=2.0, max_value=20.0, value=8.0, step=0.5)

    return {
        "capital_total": capital_total,
        "risk_pct": risk_pct / 100.0,
        "capital_mode": capital_mode,
        "max_positions": max_positions,
        "commission_buy": commission_buy,
        "commission_sell": commission_sell,
        "apply_tobin": apply_tobin,
        "tobin_rate": tobin_rate / 100.0,
        "cost_obj_max_pct": cost_obj_max,
        "cost_pos_max_pct": cost_pos_max,
        "rb_net_min": rb_net_min,
        "include_ibex": include_ibex,
        "include_continuo": include_continuo,
        "min_price_filter": min_price_filter,
        "min_turnover_filter": min_turnover_filter,
        "max_atr_pct_filter": max_atr_pct_filter,
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
                ("ATR %", f'{result["ATR %"]:.2f}%'),
                ("Volumen medio € 20d", format_currency(result["Volumen medio € 20d"])),
                ("Mov. diario medio %", f'{result["Mov. diario medio %"]:.2f}%'),
                ("Filtro universo", result["Filtro universo"]),
                ("Motivo filtro", result["Motivo filtro"]),
            ],
            columns=["Métrica", "Valor"],
        )
        st.dataframe(metrics_df, hide_index=True, use_container_width=True)
    with right:
        st.markdown("**Notas**")
        st.write(result["Notas"])
        st.caption("Las estimaciones a 5 y 20 sesiones son heurísticas basadas en estructura, momentum, volatilidad y fuerza relativa.")


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
        "ATR %": "{:,.2f}%",
        "Volumen medio € 20d": "{:,.0f}",
        "Mov. diario medio %": "{:,.2f}%",
    }
    return df.style.apply(row_color, axis=1).format(fmt)


def scan_watchlist_ui(config: dict) -> None:
    st.subheader("Escáner de watchlist")

    watchlist_text = st.text_area(
        "Watchlist extra (además del IBEX / continuo filtrado que marques)",
        value="",
        height=90,
        help="Aquí puedes añadir tickers extra separados por comas. El universo principal se controla desde la barra lateral.",
    )

    built_watchlist = build_watchlist_from_presets(
        include_ibex=bool(config.get("include_ibex", True)),
        include_continuo=bool(config.get("include_continuo", True)),
        custom_text=watchlist_text,
    )
    st.caption(f"Universo activo: {built_watchlist}")

    c1, c2, c3 = st.columns([1, 1, 1.2])
    only_operable = c1.checkbox("Solo candidatas operables", value=False)
    only_operable_net = c2.checkbox("Solo candidatas operables netas", value=True)
    run_scan = c3.button("Escanear watchlist", type="primary", use_container_width=True)

    if run_scan:
        tickers = parse_watchlist(built_watchlist)
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

        df_all = pd.DataFrame(results)
        df_all = df_all.sort_values(["Score", "R/B neto", "Rel. 1m"], ascending=[False, False, False]).reset_index(drop=True)

        filtered_out = df_all[df_all["Filtro universo"] == "No"].copy()
        df = df_all[df_all["Filtro universo"] == "Sí"].copy()
        df.insert(0, "Ranking", range(1, len(df) + 1))

        if only_operable:
            df = df[df["Operable"] == "Sí"].copy()
        if only_operable_net:
            df = df[df["Operable neta"] == "Sí"].copy()

        if df.empty:
            st.info("Tras aplicar los filtros no quedan candidatas.")
            if not filtered_out.empty:
                st.markdown("#### Valores descartados por filtro de universo")
                st.dataframe(
                    filtered_out[["Ticker", "Precio actual", "Volumen medio € 20d", "ATR %", "Motivo filtro"]].head(15),
                    hide_index=True,
                    use_container_width=True,
                )
            return

        st.session_state["last_scan_df"] = df.copy()

        top3 = df.head(3).copy()
        st.markdown("### TOP 3 DEL DÍA" if not config.get("capital_mode", False) else "### TOP 3 BASE (antes del reparto de capital)")
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

        alloc_df = None
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
                st.caption("Aquí el sistema reparte el capital total entre las mejores 1–3 candidatas netas y la salida principal se centra en ellas.")

        columns_to_show = [
            "Ranking", "Ticker", "Precio actual", "Score", "Señal", "Tendencia", "Confianza",
            "Rel. 1m", "Rel. 3m", "Est. 5d", "Est. 20d", "Stop", "Objetivo", "Dist.stop",
            "R/B", "R/B neto", "Costes", "Coste/obj %", "Coste/posic %", "Posic. €",
            "Benef. neto €", "Cap.min €", "ATR %", "Volumen medio € 20d", "Mov. diario medio %",
            "Semáforo", "Operable", "Operable neta"
        ]

        if config.get("capital_mode", False) and alloc_df is not None and not alloc_df.empty:
            selected_tickers = alloc_df["Ticker"].tolist()
            df_main = df[df["Ticker"].isin(selected_tickers)].copy()
            df_main = df_main.sort_values(["Score", "R/B neto", "Rel. 1m"], ascending=[False, False, False]).reset_index(drop=True)
            df_main.insert(0, "Ranking visible", range(1, len(df_main) + 1))
            st.markdown("### Resumen de las posiciones elegidas")
            st.dataframe(style_scan_table(df_main[columns_to_show]), hide_index=True, use_container_width=True)
        else:
            st.dataframe(style_scan_table(df[columns_to_show]), hide_index=True, use_container_width=True)

        if not filtered_out.empty:
            with st.expander("Ver valores descartados por filtro de universo"):
                st.dataframe(
                    filtered_out[["Ticker", "Precio actual", "Volumen medio € 20d", "ATR %", "Mov. diario medio %", "Motivo filtro"]],
                    hide_index=True,
                    use_container_width=True,
                )

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
    ticker = st.text_input("Ticker", value="IBE.MC").strip().upper()
    analyze_button = st.button("Analizar ticker")

    if analyze_button and ticker:
        with st.spinner("Calculando análisis..."):
            hist = get_history_cached(ticker)
            bench = get_history_cached(benchmark_for_ticker(ticker))
            result = analyze_ticker(
                ticker=ticker,
                hist=hist,
                benchmark_hist=bench,
                display_name=get_name_cached(ticker),
                config=config,
            )
        if not result:
            st.error("No se pudo analizar el ticker.")
            return

        st.markdown(f"### {result['Ticker']} — {result['Nombre']}")
        render_detail(result)


def quick_help_ui() -> None:
    st.subheader("Ayuda rápida")
    st.markdown(
        """
        **Importante**
        - La app usa datos de Yahoo Finance vía `yfinance`.
        - Las estimaciones son orientativas y heurísticas.
        - El modelo está pensado para largos (compras), no para cortos.
        - Ahora puedes mezclar IBEX + continuo filtrado.
        - El filtro de universo intenta evitar chicharros mediante precio mínimo, liquidez mínima y ATR % máximo.
        - El modo capital completo reparte el capital total entre las mejores 1–3 candidatas netas.
        """
    )


def main() -> None:
    config = build_config()
    t1, t2, t3 = st.tabs(["Análisis individual", "Escáner", "Ayuda rápida"])
    with t1:
        individual_analysis_ui(config)
    with t2:
        scan_watchlist_ui(config)
    with t3:
        quick_help_ui()


if __name__ == "__main__":
    main()
