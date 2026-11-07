"""Julkisten API-rajapintojen hakeminen ja aikaleimojen yhdistäminen."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

TZ = ZoneInfo('Europe/Helsinki')
LAT, LON = 61.0587, 28.1887  # Lappeenrannan keskustan likimääräiset koordinaatit


@st.cache_data(ttl=900, show_spinner=False)
def fetch_prices():
    url = 'https://porssisahkovahti.fi/api/v1/hinnat.json'
    response = requests.get(url, params={'paiva': 'huomenna'}, timeout=20)
    response.raise_for_status()
    obj = response.json()
    if obj.get('tila') == 'ei-julkaistu' or not obj.get('hinnat'):
        raise ValueError('Huomisen pörssisähkön hintoja ei ole vielä julkaistu (yleensä klo 15 jälkeen).')
    data = pd.DataFrame(obj['hinnat'])
    data['start'] = pd.to_datetime(data['alkaa'], utc=True)
    data['end'] = pd.to_datetime(data['paattyy'], utc=True)
    data['spot_price'] = pd.to_numeric(data['hinta'], errors='raise')
    data['duration'] = (data['end']-data['start']).dt.total_seconds()/3600
    if (data['duration'] <= 0).any():
        raise ValueError('Virheellinen sähkönhintajakso.')
    # Kaikki jaksojen rajat ovat vartin/tunnin tarkkuudella.
    data['time'] = data['start'].dt.floor('h')
    data['weighted_price'] = data['spot_price'] * data['duration']
    hourly = data.groupby('time', as_index=False).agg(
        weighted_price=('weighted_price', 'sum'), hours=('duration', 'sum'))
    hourly['spot_price'] = hourly['weighted_price'] / hourly['hours']
    return hourly, str(obj.get('paiva', ''))


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_weather():
    response = requests.get('https://api.open-meteo.com/v1/forecast', params={
        'latitude': LAT, 'longitude': LON, 'hourly': 'temperature_2m',
        'timezone': 'Europe/Helsinki', 'forecast_days': 3
    }, timeout=20)
    response.raise_for_status()
    hourly = response.json()['hourly']
    # Open-Meteon paikallisaikaleimat eivät sisällä UTC-offsetia.
    # Käytetään aikaleimojen paikallistusta; DST-vaihtopäivänä voidaan
    # ilmoittaa käyttäjälle, ettei yksiselitteistä yhdistämistä voi tehdä.
    local = pd.to_datetime(hourly['time'])
    try:
        aware = local.tz_localize('Europe/Helsinki', ambiguous='raise', nonexistent='raise')
    except Exception as exc:
        raise ValueError('Sääennusteen kesä-/talviaikasiirtymän aikaleimat ovat epäselviä.') from exc
    return pd.DataFrame({'time': aware.tz_convert('UTC'), 'temperature': hourly['temperature_2m']})


def tomorrow():
    return (datetime.now(TZ).date() + timedelta(days=1)).isoformat()


def load_tomorrow():
    target = tomorrow()
    prices, price_date = fetch_prices()
    if price_date and price_date != target:
        raise ValueError('Hintarajapinta palautti väärän päivän: ' + price_date)
    weather = fetch_weather()
    merged = prices.merge(weather, on='time', how='inner', validate='one_to_one')
    local_date = merged['time'].dt.tz_convert('Europe/Helsinki').dt.strftime('%Y-%m-%d')
    merged = merged.loc[local_date == target].sort_values('time').reset_index(drop=True)
    # Normaalipäivä 24 h; kesä-/talviaikapäivä 23 tai 25 h.
    start = pd.Timestamp(target, tz='Europe/Helsinki')
    end = start + pd.DateOffset(days=1)
    hours = int((end.tz_convert('UTC') - start.tz_convert('UTC')).total_seconds()/3600)
    if len(merged) != hours or not merged['hours'].between(0.999, 1.001).all():
        raise ValueError(f'Puuttuvia tai vajaita tunteja: löytyi {len(merged)}, odotettiin {hours}.')
    return merged[['time','temperature','spot_price']], target
