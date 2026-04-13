
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

import math

import numpy as np
import pandas as pd

DEFAULT_IBEX_TICKERS = ['^IBEX', 'ACS.MC', 'ACX.MC', 'AENA.MC', 'AMS.MC', 'ANA.MC', 'ANE.MC', 'BBVA.MC', 'BKT.MC', 'CABK.MC', 'CLNX.MC', 'COL.MC', 'ELE.MC', 'ENG.MC', 'FDR.MC', 'FER.MC', 'GRF.MC', 'IAG.MC', 'IBE.MC', 'IDR.MC', 'ITX.MC', 'LOG.MC', 'MAP.MC', 'MRL.MC', 'MTS.MC', 'NTGY.MC', 'PUIG.MC', 'RED.MC', 'REP.MC', 'ROVI.MC', 'SAB.MC', 'SAN.MC', 'SCYR.MC', 'SLR.MC', 'TEF.MC', 'UNI.MC', 'VIS.MC']
FILTERED_CONTINUO_TICKERS = ['CAF.MC', 'CIE.MC', 'DOM.MC', 'EBRO.MC', 'ENC.MC', 'EUSK.MC', 'LOG.MC', 'NHH.MC', 'PRM.MC', 'TLGO.MC', 'VID.MC']
DEFAULT_WATCHLIST_TEXT = '^IBEX, ACS.MC, ACX.MC, AENA.MC, AMS.MC, ANA.MC, ANE.MC, BBVA.MC, BKT.MC, CABK.MC, CLNX.MC, COL.MC, ELE.MC, ENG.MC, FDR.MC, FER.MC, GRF.MC, IAG.MC, IBE.MC, IDR.MC, ITX.MC, LOG.MC, MAP.MC, MRL.MC, MTS.MC, NTGY.MC, PUIG.MC, RED.MC, REP.MC, ROVI.MC, SAB.MC, SAN.MC, SCYR.MC, SLR.MC, TEF.MC, UNI.MC, VIS.MC, CAF.MC, CIE.MC, DOM.MC, EBRO.MC, ENC.MC, EUSK.MC, LOG.MC, NHH.MC, PRM.MC, TLGO.MC, VID.MC'


def parse_watchlist(text: str) -> list[str]:
    if not text:
        return []
    seen = set()
    tickers = []
    for raw in text.replace("\n", ",").split(","):
        ticker = raw.strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def benchmark_for_ticker(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith(".MC") or t == "^IBEX":
        return "^IBEX"
    return "SPY"


def format_currency(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:,.2f} €"


def _series(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        raise ValueError(f"Falta la columna {name}")
    return pd.to_numeric(df[name], errors="coerce")


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high = _series(df, "High")
    low = _series(df, "Low")
    close = _series(df, "Close")
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def compute_macd_hist(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line


def _safe_pct(num: float, den: float) -> float:
    if den is None or den == 0 or pd.isna(den):
        return 0.0
    return float(num / den * 100.0)


def _ret(close: pd.Series, periods: int) -> float:
    if len(close) <= periods:
        return 0.0
    old = float(close.iloc[-periods - 1])
    new = float(close.iloc[-1])
    if old == 0 or np.isnan(old) or np.isnan(new):
        return 0.0
    return (new / old - 1.0) * 100.0


def _annualized_vol(returns: pd.Series) -> float:
    if len(returns.dropna()) < 20:
        return np.nan
    return float(returns.std() * np.sqrt(252) * 100.0)


def _confidence_label(score: float, agreement: int) -> str:
    mag = abs(score)
    if mag >= 7 and agreement >= 5:
        return "Alta"
    if mag >= 4 and agreement >= 3:
        return "Media"
    return "Baja"


def _direction_from_pct(pct: float) -> str:
    if pct > 1.0:
        return "SUBIDA"
    if pct < -1.0:
        return "BAJADA"
    return "LATERAL"


def _clean_price(value: float) -> float:
    if value is None or pd.isna(value) or value <= 0:
        return np.nan
    return float(value)


def _technical_snapshot(df: pd.DataFrame) -> dict:
    close = _series(df, "Close").dropna()
    volume = _series(df, "Volume").fillna(0)
    if len(close) < 210:
        raise ValueError("Histórico insuficiente (se recomiendan al menos 210 sesiones)")

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    rsi = compute_rsi(close)
    atr = compute_atr(df)
    macd_hist = compute_macd_hist(close)
    daily_ret = close.pct_change()

    latest_price = _clean_price(close.iloc[-1])
    latest_sma20 = _clean_price(sma20.iloc[-1])
    latest_sma50 = _clean_price(sma50.iloc[-1])
    latest_sma200 = _clean_price(sma200.iloc[-1])
    latest_rsi = float(rsi.iloc[-1])
    latest_atr = _clean_price(atr.iloc[-1])
    latest_macd_hist = float(macd_hist.iloc[-1])
    avg_vol20 = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else 0.0
    vol_ratio = float(volume.iloc[-1] / avg_vol20) if avg_vol20 else 1.0
    high20 = float(close.rolling(20).max().iloc[-1])
    low20 = float(close.rolling(20).min().iloc[-1])

    mom_1m = _ret(close, 21)
    mom_3m = _ret(close, 63)
    vol_annual = _annualized_vol(daily_ret)
    atr_pct = (latest_atr / latest_price * 100.0) if latest_atr and latest_price else np.nan
    avg_turnover_20 = avg_vol20 * latest_price
    avg_daily_move_pct = float(close.pct_change().abs().rolling(20).mean().iloc[-1] * 100.0) if len(close) >= 21 else np.nan

    return {
        "price": latest_price,
        "sma20": latest_sma20,
        "sma50": latest_sma50,
        "sma200": latest_sma200,
        "rsi": latest_rsi,
        "atr": latest_atr,
        "atr_pct": atr_pct,
        "macd_hist": latest_macd_hist,
        "mom_1m": mom_1m,
        "mom_3m": mom_3m,
        "vol_ratio": vol_ratio,
        "high20": high20,
        "low20": low20,
        "vol_annual": vol_annual,
        "avg_turnover_20": avg_turnover_20,
        "avg_daily_move_pct": avg_daily_move_pct,
    }


def _relative_strength(asset_hist: pd.DataFrame, bench_hist: pd.DataFrame | None) -> tuple[float, float]:
    if bench_hist is None or bench_hist.empty:
        return 0.0, 0.0
    asset_close = _series(asset_hist, "Close").dropna()
    bench_close = _series(bench_hist, "Close").dropna()
    if len(asset_close) < 70 or len(bench_close) < 70:
        return 0.0, 0.0
    rel_1m = _ret(asset_close, 21) - _ret(bench_close, 21)
    rel_3m = _ret(asset_close, 63) - _ret(bench_close, 63)
    return float(rel_1m), float(rel_3m)


def _score(snapshot: dict, rel_1m: float, rel_3m: float) -> tuple[float, list[str], int]:
    price = snapshot["price"]
    sma20 = snapshot["sma20"]
    sma50 = snapshot["sma50"]
    sma200 = snapshot["sma200"]
    rsi = snapshot["rsi"]
    macd_hist = snapshot["macd_hist"]
    vol_ratio = snapshot["vol_ratio"]
    high20 = snapshot["high20"]
    low20 = snapshot["low20"]
    atr_pct = snapshot["atr_pct"]
    vol_annual = snapshot["vol_annual"]
    mom_1m = snapshot["mom_1m"]

    score = 0.0
    notes = []
    agreement = 0

    if price > sma20:
        score += 1.0
        notes.append("Precio > SMA20")
        agreement += 1
    else:
        score -= 1.0
        notes.append("Precio < SMA20")

    if sma20 > sma50:
        score += 1.0
        notes.append("SMA20 > SMA50")
        agreement += 1
    else:
        score -= 1.0
        notes.append("SMA20 < SMA50")

    if price > sma200:
        score += 2.0
        notes.append("Precio > SMA200")
        agreement += 1
    else:
        score -= 2.0
        notes.append("Precio < SMA200")

    if macd_hist > 0:
        score += 1.0
        notes.append("MACD hist > 0")
        agreement += 1
    else:
        score -= 1.0
        notes.append("MACD hist < 0")

    if mom_1m > 5:
        score += 1.0
        notes.append("Momentum 1m > +5%")
        agreement += 1
    elif mom_1m < -5:
        score -= 1.0
        notes.append("Momentum 1m < -5%")

    if 45 <= rsi <= 65:
        score += 1.0
        notes.append("RSI sano 45-65")
        agreement += 1
    elif rsi > 72:
        score -= 1.0
        notes.append("RSI en sobrecompra")
    elif rsi < 32:
        score += 0.5
        notes.append("RSI bajo: posible rebote")

    if vol_ratio > 1.2:
        score += 0.5
        notes.append("Volumen > media 20d")
        agreement += 1

    if price >= high20 * 0.98:
        score += 0.5
        notes.append("Cerca de máximos 20d")
        agreement += 1
    elif price <= low20 * 1.02:
        score -= 0.5
        notes.append("Cerca de mínimos 20d")

    if not np.isnan(atr_pct):
        if atr_pct < 2.5:
            score += 0.5
            notes.append("Volatilidad contenida")
            agreement += 1
        elif atr_pct > 5.5:
            score -= 0.5
            notes.append("Volatilidad alta")

    if not np.isnan(vol_annual):
        if vol_annual < 25:
            score += 0.5
            notes.append("Volatilidad anual moderada")
            agreement += 1
        elif vol_annual > 45:
            score -= 0.5
            notes.append("Volatilidad anual elevada")

    if rel_1m > 0:
        score += 1.0
        notes.append("Mejor que benchmark a 1m")
        agreement += 1
    else:
        score -= 1.0
        notes.append("Peor que benchmark a 1m")

    if rel_3m > 0:
        score += 1.0
        notes.append("Mejor que benchmark a 3m")
        agreement += 1
    else:
        score -= 1.0
        notes.append("Peor que benchmark a 3m")

    return score, notes, agreement


def _trend_label(snapshot: dict) -> str:
    price = snapshot["price"]
    sma20 = snapshot["sma20"]
    sma50 = snapshot["sma50"]
    sma200 = snapshot["sma200"]

    if price > sma20 > sma50 > sma200:
        return "Alcista"
    if price < sma20 < sma50 < sma200:
        return "Bajista"
    return "Mixta"


def _signal(score: float) -> tuple[str, str]:
    if score >= 6:
        return "COMPRAR", "VERDE"
    if score >= 3:
        return "VIGILAR", "AMARILLO"
    if score > -2:
        return "NEUTRAL", "GRIS"
    if score > -5:
        return "DÉBIL / ESPERAR", "ROJO"
    return "VENDER / EVITAR", "ROJO"


def _estimations(snapshot: dict, score: float, rel_1m: float, rel_3m: float) -> dict:
    score_norm = np.clip(score / 8.0, -1.0, 1.0)
    rel_bias = np.clip((0.6 * rel_1m + 0.4 * rel_3m) / 20.0, -1.0, 1.0)
    rsi_bias = np.clip((50.0 - snapshot["rsi"]) / 50.0, -0.6, 0.6) * -0.25
    vol_penalty = np.clip((snapshot["atr_pct"] - 3.0) / 10.0, -0.5, 0.5) if not np.isnan(snapshot["atr_pct"]) else 0.0
    bias = 0.55 * score_norm + 0.35 * rel_bias + 0.10 * rsi_bias - 0.10 * vol_penalty

    est_5_pct = float(np.clip(bias * 4.5, -8.0, 8.0))
    est_20_pct = float(np.clip(bias * 10.0, -18.0, 18.0))
    price = snapshot["price"]
    est_5_price = price * (1 + est_5_pct / 100.0)
    est_20_price = price * (1 + est_20_pct / 100.0)
    return {
        "est_5_pct": est_5_pct,
        "est_20_pct": est_20_pct,
        "est_5_text": f'{_direction_from_pct(est_5_pct)} ({est_5_pct:+.2f}% | {est_5_price:.2f} €)',
        "est_20_text": f'{_direction_from_pct(est_20_pct)} ({est_20_pct:+.2f}% | {est_20_price:.2f} €)',
    }


def _position_and_costs(
    ticker: str,
    price: float,
    stop: float,
    target: float,
    config: dict,
) -> dict:
    capital_total = float(config["capital_total"])
    risk_pct = float(config["risk_pct"])
    risk_budget = capital_total * risk_pct
    commission_buy = float(config["commission_buy"])
    commission_sell = float(config["commission_sell"])
    apply_tobin = bool(config["apply_tobin"])
    tobin_rate = float(config["tobin_rate"])
    is_spanish = ticker.upper().endswith(".MC")
    tobin_amount_per_share = price * tobin_rate if apply_tobin and is_spanish else 0.0

    stop_distance = max(price - stop, 0.01)
    shares = max(math.floor(max(risk_budget - commission_buy - commission_sell, 0) / (stop_distance + tobin_amount_per_share)), 0)
    position_eur = shares * price
    tobin_buy = position_eur * tobin_rate if apply_tobin and is_spanish else 0.0
    cost_buy = commission_buy
    cost_sell = commission_sell
    total_cost = cost_buy + cost_sell + tobin_buy
    loss_no_costs = shares * stop_distance
    max_loss_with_costs = loss_no_costs + total_cost
    gross_profit = max(target - price, 0.0) * shares
    net_profit = gross_profit - total_cost

    rb_gross = gross_profit / max_loss_with_costs if max_loss_with_costs > 0 else 0.0
    rb_net = net_profit / max_loss_with_costs if max_loss_with_costs > 0 else 0.0
    dist_stop_pct = _safe_pct(price - stop, price)
    cost_obj_pct = _safe_pct(total_cost, gross_profit) if gross_profit > 0 else 999.0
    cost_pos_pct = _safe_pct(total_cost, position_eur) if position_eur > 0 else 999.0

    objective_pct = _safe_pct(target - price, price)
    cost_pos_limit = max(float(config["cost_pos_max_pct"]) / 100.0, 0.0001)
    cost_obj_limit = max(float(config["cost_obj_max_pct"]) / 100.0, 0.0001)
    capital_min_by_pos = total_cost / cost_pos_limit
    capital_min_by_obj = total_cost / max(objective_pct / 100.0 * cost_obj_limit, 0.0001)
    capital_min = max(total_cost, capital_min_by_pos, capital_min_by_obj)

    operable = (
        shares > 0
        and target > price
        and stop < price
        and rb_gross >= 2.0
    )
    operable_neta = (
        operable
        and rb_net >= float(config["rb_net_min"])
        and cost_obj_pct <= float(config["cost_obj_max_pct"])
        and cost_pos_pct <= float(config["cost_pos_max_pct"])
        and net_profit > 0
    )

    return {
        "shares": shares,
        "position_eur": position_eur,
        "cost_buy": cost_buy,
        "cost_sell": cost_sell,
        "tobin_buy": tobin_buy,
        "total_cost": total_cost,
        "max_loss_with_costs": max_loss_with_costs,
        "rb_gross": rb_gross,
        "rb_net": rb_net,
        "net_profit": net_profit,
        "capital_min": capital_min,
        "dist_stop_pct": dist_stop_pct,
        "cost_obj_pct": cost_obj_pct,
        "cost_pos_pct": cost_pos_pct,
        "operable": operable,
        "operable_neta": operable_neta,
    }





def _entry_extension_status(snapshot: dict, config: dict) -> tuple[float, bool, str]:
    price = float(snapshot["price"])
    sma20 = float(snapshot["sma20"])
    threshold_pct = float(config.get("entry_extension_max_pct", 2.0))

    if sma20 <= 0 or pd.isna(sma20):
        return 0.0, False, "No evaluable"

    ext_pct = (price / sma20 - 1.0) * 100.0
    is_extended = ext_pct > threshold_pct

    if ext_pct <= 1.0:
        label = "Buena"
    elif ext_pct <= threshold_pct:
        label = "Aceptable"
    else:
        label = "Extendida"

    return float(ext_pct), bool(is_extended), label


def _passes_universe_filters(snapshot: dict, config: dict) -> tuple[bool, list[str]]:
    reasons = []
    min_price = float(config.get("min_price_filter", 3.0))
    min_turnover = float(config.get("min_turnover_filter", 750000.0))
    max_atr_pct = float(config.get("max_atr_pct_filter", 8.0))

    price = float(snapshot["price"])
    avg_turnover_20 = float(snapshot.get("avg_turnover_20", 0.0) or 0.0)
    atr_pct = float(snapshot.get("atr_pct", np.nan))
    avg_daily_move = float(snapshot.get("avg_daily_move_pct", np.nan))

    if price < min_price:
        reasons.append(f"Precio < {min_price:.2f} €")
    if avg_turnover_20 < min_turnover:
        reasons.append(f"Liquidez media 20d < {min_turnover:,.0f} €")
    if not np.isnan(atr_pct) and atr_pct > max_atr_pct:
        reasons.append(f"ATR% > {max_atr_pct:.1f}")
    if not np.isnan(avg_daily_move) and avg_daily_move > max(max_atr_pct * 0.8, 5.5):
        reasons.append("Movimiento diario medio demasiado alto")

    return len(reasons) == 0, reasons


def analyze_ticker(
    ticker: str,
    hist: pd.DataFrame,
    benchmark_hist: pd.DataFrame | None,
    display_name: str,
    config: dict,
) -> dict | None:
    if hist is None or hist.empty:
        return None

    hist = hist.copy().dropna(how="all")
    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    snapshot = _technical_snapshot(hist)
    universe_ok, universe_filter_reasons = _passes_universe_filters(snapshot, config)
    entry_ext_pct, entry_is_extended, entry_zone = _entry_extension_status(snapshot, config)
    rel_1m, rel_3m = _relative_strength(hist, benchmark_hist)
    score, notes, agreement = _score(snapshot, rel_1m, rel_3m)
    trend = _trend_label(snapshot)
    signal, semaphore = _signal(score)
    confidence = _confidence_label(score, agreement)
    estimates = _estimations(snapshot, score, rel_1m, rel_3m)

    price = snapshot["price"]
    atr = snapshot["atr"] if not np.isnan(snapshot["atr"]) else max(price * 0.02, 0.01)
    base_stop = price - max(1.5 * atr, price * 0.025)
    stop = max(base_stop, price * 0.70, 0.01)
    stop = min(stop, price * 0.995)

    min_target = price * 1.01
    suggested_target = price + max((price - stop) * 2.2, atr * 2.0, price * 0.03)
    target = max(suggested_target, min_target)
    target = float(max(target, price + 0.01))

    costs = _position_and_costs(ticker, price, stop, target, config)

    block_extended = bool(config.get("block_extended_entries", True))
    extension_ok = (not entry_is_extended) or (not block_extended)

    costs["operable"] = bool(
        costs["operable"]
        and semaphore == "VERDE"
        and score >= 4.0
        and rel_1m > 0
        and universe_ok
        and extension_ok
    )
    costs["operable_neta"] = bool(
        costs["operable"]
        and costs["operable_neta"]
        and semaphore == "VERDE"
        and score >= 4.0
        and rel_1m > 0
        and universe_ok
        and extension_ok
    )

    if entry_is_extended:
        notes.append(f"Entrada extendida: +{entry_ext_pct:.2f}% sobre SMA20")
    notes_text = "; ".join(notes[:8])
    filter_notes = "; ".join(universe_filter_reasons) if universe_filter_reasons else "Universe OK"

    return {
        "Ticker": ticker,
        "Nombre": display_name or ticker,
        "Benchmark": benchmark_for_ticker(ticker),
        "Precio actual": float(price),
        "Score": float(score),
        "Señal": signal,
        "Tendencia": trend,
        "Confianza": confidence,
        "Rel. 1m": float(rel_1m),
        "Rel. 3m": float(rel_3m),
        "Est. 5d": estimates["est_5_text"],
        "Est. 20d": estimates["est_20_text"],
        "Est. 5d %": float(estimates["est_5_pct"]),
        "Est. 20d %": float(estimates["est_20_pct"]),
        "Stop": float(stop),
        "Objetivo": float(target),
        "Dist.stop": float(costs["dist_stop_pct"]),
        "Posic. €": float(costs["position_eur"]),
        "Acciones est.": float(costs["shares"]),
        "Coste compra": float(costs["cost_buy"]),
        "Coste venta": float(costs["cost_sell"]),
        "Tobin compra": float(costs["tobin_buy"]),
        "Costes": float(costs["total_cost"]),
        "Pérdida máx €": float(costs["max_loss_with_costs"]),
        "R/B": float(costs["rb_gross"]),
        "R/B neto": float(costs["rb_net"]),
        "Benef. neto €": float(costs["net_profit"]),
        "Cap.min €": float(costs["capital_min"]),
        "Coste/obj %": float(costs["cost_obj_pct"]),
        "Coste/posic %": float(costs["cost_pos_pct"]),
        "ATR %": float(snapshot["atr_pct"]) if not np.isnan(snapshot["atr_pct"]) else np.nan,
        "Volumen medio € 20d": float(snapshot.get("avg_turnover_20", 0.0)),
        "Mov. diario medio %": float(snapshot.get("avg_daily_move_pct", np.nan)) if not np.isnan(snapshot.get("avg_daily_move_pct", np.nan)) else np.nan,
        "Extensión % sobre SMA20": float(entry_ext_pct),
        "Zona de entrada": entry_zone,
        "Entrada extendida": "Sí" if entry_is_extended else "No",
        "Filtro universo": "Sí" if universe_ok else "No",
        "Motivo filtro": filter_notes,
        "Semáforo": semaphore,
        "Operable": "Sí" if costs["operable"] else "No",
        "Operable neta": "Sí" if costs["operable_neta"] else "No",
        "Notas": notes_text,
    }


def save_scan_exports(df: pd.DataFrame, export_dir: Path) -> tuple[bytes, bytes, str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = export_dir / f"scan_{timestamp}.csv"
    xlsx_path = export_dir / f"scan_{timestamp}.xlsx"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Scan")
        ws = writer.book["Scan"]
        ws.freeze_panes = "A2"
        for column_cells in ws.columns:
            max_len = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 12), 24)

    csv_bytes = csv_path.read_bytes()
    xlsx_bytes = xlsx_path.read_bytes()
    return csv_bytes, xlsx_bytes, str(csv_path), str(xlsx_path)


def allocate_capital_top(
    df: pd.DataFrame,
    total_capital: float,
    max_positions: int,
    commission_buy: float,
    commission_sell: float,
    apply_tobin: bool,
    tobin_rate: float,
) -> pd.DataFrame:
    if df is None or df.empty or total_capital <= 0:
        return pd.DataFrame()

    selected = df.copy()
    selected = selected[selected["Operable neta"] == "Sí"].copy()
    if selected.empty:
        return pd.DataFrame()

    selected = selected.sort_values(
        ["Score", "R/B neto", "Rel. 1m"],
        ascending=[False, False, False]
    ).head(max_positions).copy()

    raw_weights = (selected["Score"].clip(lower=0.1) * selected["R/B neto"].clip(lower=0.1)).astype(float)
    weights = raw_weights / raw_weights.sum() if raw_weights.sum() > 0 else pd.Series([1 / len(selected)] * len(selected), index=selected.index)

    rows = []
    for idx, row in selected.iterrows():
        ticker = str(row["Ticker"])
        price = float(row["Precio actual"])
        target = float(row["Objetivo"])
        est5_pct = float(row.get("Est. 5d %", 0.0))
        allocated_capital = float(total_capital * weights.loc[idx])

        shares = max(int(math.floor(allocated_capital / max(price, 0.01))), 0)
        position_eur = float(shares * price)
        is_spanish = ticker.upper().endswith(".MC")
        tobin_buy = position_eur * tobin_rate if (apply_tobin and is_spanish) else 0.0
        total_cost = float(commission_buy + commission_sell + tobin_buy)

        gross_profit_target = max(target - price, 0.0) * shares
        net_profit_target = gross_profit_target - total_cost

        est5_price = price * (1.0 + est5_pct / 100.0)
        gross_profit_est5 = max(est5_price - price, 0.0) * shares
        net_profit_est5 = gross_profit_est5 - total_cost

        rows.append({
            "Ranking capital": 0,
            "Ticker": ticker,
            "Score": float(row["Score"]),
            "R/B neto": float(row["R/B neto"]),
            "Señal": row["Señal"],
            "Peso %": float(weights.loc[idx] * 100.0),
            "Capital asignado €": allocated_capital,
            "Acciones capital completo": float(shares),
            "Posición capital completo €": position_eur,
            "Costes capital completo €": total_cost,
            "Benef. neto objetivo €": float(net_profit_target),
            "Benef. neto est. 5d €": float(net_profit_est5),
            "Precio actual": price,
            "Objetivo": target,
            "Semáforo": row["Semáforo"],
        })

    alloc_df = pd.DataFrame(rows).sort_values(
        ["Score", "R/B neto", "Benef. neto objetivo €"],
        ascending=[False, False, False]
    ).reset_index(drop=True)
    alloc_df["Ranking capital"] = range(1, len(alloc_df) + 1)
    return alloc_df
