from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import streamlit as st
from calculator import calculate
from data import load_tomorrow, TZ

st.set_page_config(page_title='Lämmitysvertailu – Lappeenranta', page_icon='🏠', layout='wide')
st.title('🏠 Huomisen lämmitysvertailu')
st.caption('Lappeenranta · Toshiba Estia R32 vs. TERMAX 25 · päätös koko vuorokaudelle')

with st.sidebar:
    st.header('Asetukset')
    current = st.radio('Nykyinen lämmitysmuoto', ['VILP', 'Pelletti'], index=0)
    threshold = st.number_input('Vaihdon vähimmäissäästö €/vrk', min_value=0.0, value=5.0, step=0.5)
    pellet_price = st.number_input('Pelletti €/kg', min_value=0.0, value=0.38, step=0.01)
    transfer = st.number_input('Siirto snt/kWh (sis. ALV)', value=4.47, step=0.01)
    tax = st.number_input('Sähkövero snt/kWh (sis. ALV)', value=2.917, step=0.001, format='%.3f')
    margin = st.number_input('Marginaali snt/kWh (sis. ALV)', value=0.50, step=0.01)
    st.divider()
    use_heater = st.checkbox('Mallinna 3 kW lisävastus (alustava tehomalli)', value=True)
    st.caption('Tehokäyrä on alustava 55 °C:n arvio. VILP:n COP alle −15 °C on oletus, ei mitattu arvo.')
    if st.button('Päivitä rajapintatiedot'):
        from data import fetch_prices, fetch_weather
        fetch_prices.clear()
        fetch_weather.clear()
        st.rerun()

try:
    raw, date = load_tomorrow()
except (ValueError, KeyError, TypeError, OSError, Exception) as exc:
    st.warning(f'En voi vielä laskea huomista: {exc}')
    st.info('Huomisen sähkönhinnat julkaistaan yleensä noin klo 14.45 Suomen aikaa. Kokeile uudelleen klo 15 jälkeen.')
    st.stop()

results = calculate(raw, pellet_price=pellet_price, transfer=transfer,
                    tax=tax, margin=margin, use_heater=use_heater)
pump_total = results['vilp_euro'].sum()
pellet_total = results['pelletti_euro'].sum()
current_cost = pump_total if current == 'VILP' else pellet_total
other_cost = pellet_total if current == 'VILP' else pump_total
saving = current_cost - other_cost
uncertain = results['epavarma'].any()
deficit = results['tehovaje_kwh'].sum()

st.subheader(f'Ennuste {pd.Timestamp(date).strftime("%d.%m.%Y")}')
c1,c2,c3,c4 = st.columns(4)
c1.metric('VILP koko vuorokausi', f'{pump_total:.2f} €')
c2.metric('Pelletti koko vuorokausi', f'{pellet_total:.2f} €')
c3.metric('Säästö vaihtamalla', f'{saving:.2f} €')
c4.metric('Lämmöntarve', f'{results["lammontarve_kwh"].sum():.1f} kWh')

if deficit > 0.01:
    st.error(f'⚠️ Mallinnettu VILP + 3 kW vastus ei kata kaikkea lämmöntarvetta ({deficit:.1f} kWh/vuorokausi). VILP:n kustannus ei ole täysin vertailukelpoinen.')
if uncertain:
    st.warning('⚠️ Ennusteessa on lämpötiloja mitatun COP-alueen (−15…+3,7 °C) ulkopuolella. Tulokset ovat suuntaa-antavia.')

if deficit > 0.01 or (uncertain and saving >= threshold):
    st.info('**Suositus: tarkista laskenta ennen lämmitysmuodon vaihtoa.** Teho- tai COP-oletus on epävarma.')
elif saving >= threshold:
    st.success(f'**Suositus: vaihda lämmitysmuotoon {"pelletti" if current == "VILP" else "VILP"}.** Arvioitu säästö {saving:.2f} € ylittää {threshold:.2f} € rajan.')
else:
    st.info(f'**Suositus: jatka nykyisellä lämmitysmuodolla ({current}).** Vaihdon arvioitu säästö {saving:.2f} € ei ylitä {threshold:.2f} € rajaa.')

plot = results.copy()
plot['kellonaika'] = plot['aika'].dt.tz_convert(TZ).dt.strftime('%H:%M')
long = plot.melt(id_vars=['kellonaika'], value_vars=['vilp_euro','pelletti_euro'],
                 var_name='Lämmitysmuoto', value_name='€/h')
long['Lämmitysmuoto'] = long['Lämmitysmuoto'].map({'vilp_euro':'VILP','pelletti_euro':'Pelletti'})
st.plotly_chart(px.line(long, x='kellonaika', y='€/h', color='Lämmitysmuoto', markers=True,
                        title='Tuntikohtaiset kustannukset'), use_container_width=True)

show = plot.rename(columns={
    'kellonaika':'Kello', 'ulkolampotila':'Ulko °C', 'menovesi':'Menovesi °C',
    'lammontarve_kwh':'Lämmöntarve kWh', 'cop':'COP', 'spot_snt':'Pörssihinta snt/kWh',
    'sahko_yht_snt':'Sähkön kokonaishinta snt/kWh', 'vastus_kwh':'Vastus kWh',
    'tehovaje_kwh':'Tehovaje kWh', 'vilp_euro':'VILP €', 'pelletti_euro':'Pelletti €',
})
cols = ['Kello','Ulko °C','Menovesi °C','Lämmöntarve kWh','COP',
        'Pörssihinta snt/kWh','Sähkön kokonaishinta snt/kWh','Vastus kWh',
        'Tehovaje kWh','VILP €','Pelletti €']
st.dataframe(show[cols].round(2), use_container_width=True, hide_index=True)
st.download_button('Lataa tuntitiedot CSV', data=show[cols].to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig'),
                   file_name=f'lammitysvertailu_{date}.csv', mime='text/csv')
st.caption('Lähteet: Pörssisähkövahti (porssisahkovahti.fi), Open-Meteo (open-meteo.com). Hinnat sisältävät ALV:n. Käyttövesi, pellettikattilan apusähkö, käynnistyshäviöt ja lämmityksen katkaisulämpötila eivät sisälly. Lämpöpumpun COP- ja kapasiteettimallit ovat alustavia.')
