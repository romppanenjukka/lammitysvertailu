"""Lämmityksen vertailulaskenta. Hinnat sis. ALV, yksikkö snt/kWh."""
import pandas as pd

PELLET_ENERGY = 4.8
PELLET_EFFICIENCY = 0.85


def heat_demand(temp: float) -> float:
    return max(0.0, 4.5 - 0.193 * temp)


def supply_temp(temp: float) -> float:
    return 41.0 - 0.55 * temp


def cop_estimate(temp: float) -> float:
    """Mitattuun aineistoon sovitettu malli. Alle -15 C käytetään vain oletusta."""
    if temp < -15:
        # Kylmän alueen COP ei ole mitattu: varovainen laskentaoletus.
        return max(1.5, 2.02545 + 0.05 * (temp + 15))
    return max(1.0, 4.2876 + 0.15081 * temp)


def pump_capacity(temp: float) -> float:
    """ALUSTAVA 55 C -tehokäyrä; ei varmennettu käyttäjän yksilölle."""
    anchors = [(-25, 4.23), (-20, 5.11), (-15, 5.99), (-10, 6.52), (-7, 6.83), (-2, 7.9), (2, 8.19)]
    if temp <= anchors[0][0]:
        return anchors[0][1]
    if temp >= anchors[-1][0]:
        return anchors[-1][1]
    for (t0, p0), (t1, p1) in zip(anchors, anchors[1:]):
        if t0 <= temp <= t1:
            return p0 + (p1-p0)*(temp-t0)/(t1-t0)
    raise ValueError('Invalid temperature')


def calculate(df: pd.DataFrame, pellet_price=0.38, transfer=4.47, tax=2.917,
              margin=0.50, heater_kw=3.0, use_heater=True) -> pd.DataFrame:
    rows = []
    for r in df.itertuples(index=False):
        t = float(r.temperature)
        q = heat_demand(t)
        cop = cop_estimate(t)
        capacity = pump_capacity(t) if use_heater else q
        pump_heat = min(q, capacity)
        needed_resistance = max(0.0, q - pump_heat)
        resistance = min(heater_kw, needed_resistance) if use_heater else 0.0
        deficit = max(0.0, needed_resistance-resistance)
        electricity = pump_heat/cop + resistance
        total_price = float(r.spot_price) + transfer + tax + margin
        pump_cost = electricity * total_price / 100.0
        pellet_cost = q / (PELLET_ENERGY * PELLET_EFFICIENCY) * pellet_price
        rows.append({
            'aika': r.time, 'ulkolampotila': t, 'menovesi': supply_temp(t),
            'lammontarve_kwh': q, 'cop': cop, 'spot_snt': float(r.spot_price),
            'sahko_yht_snt': total_price, 'vilp_lampo_kwh': pump_heat,
            'vastus_kwh': resistance, 'tehovaje_kwh': deficit,
            'vilp_sahko_kwh': electricity, 'vilp_euro': pump_cost,
            'pelletti_kg': q / (PELLET_ENERGY * PELLET_EFFICIENCY),
            'pelletti_euro': pellet_cost, 'epavarma': t < -15 or t > 3.7,
        })
    return pd.DataFrame(rows)
