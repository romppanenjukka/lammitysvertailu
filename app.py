from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from calculator import calculate
from data import load_day, TZ

st.set_page_config(page_title='Lämmitysvertailu – Lappeenranta', page_icon='🏠', layout='wide')
st.title('🏠 Lämmitysvertailu')
st.caption('Lappeenranta · Toshiba Estia R32 vs. TERMAX 25 · päätös koko vuorokaudelle')

with st.sidebar:
    st.header('Asetukset')
    # Valinta alustetaan kerran istuntoa kohti Suomen paikallisen kellonajan perusteella.
    # Käyttäjän käsin tekemä valinta säilyy Streamlitin uudelleenlaskennoissa.
    if 'selected_day' not in st.session_state:
        now_fi = datetime.now(TZ)
        st.session_state['selected_day'] = 'Huomenna' if now_fi.hour >= 15 else 'Tänään'
    selected_day = st.radio('Laskentapäivä', ['Tänään', 'Huomenna'], horizontal=True, key='selected_day')
    day_key = 'tanaan' if selected_day == 'Tänään' else 'huomenna'
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
    raw, date = load_day(day_key)
except Exception as exc:
    st.warning(f'En voi laskea valittua päivää ({selected_day.lower()}): {exc}')
    if day_key == 'huomenna':
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

st.subheader(f'{selected_day}: {pd.Timestamp(date).strftime("%d.%m.%Y")}')
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
# Kustannukset vasemmalla, ulkolämpötila ja sähkön spot-hinta omilla oikean puolen akseleillaan.
# Käytetään aikaleimoja x-akselilla: myös kesä-/talviaikaan siirtymisen tunnit säilyvät.
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=plot['aika'], y=plot['vilp_euro'],
                         name='VILP', mode='lines+markers',
                         line=dict(color='#1769d2'),
                         hovertemplate='%{x|%H:%M}<br>VILP: %{y:.2f} €/h<extra></extra>'),
              secondary_y=False)
fig.add_trace(go.Scatter(x=plot['aika'], y=plot['pelletti_euro'],
                         name='Pelletti', mode='lines+markers',
                         line=dict(color='#ed9b39'),
                         hovertemplate='%{x|%H:%M}<br>Pelletti: %{y:.2f} €/h<extra></extra>'),
              secondary_y=False)
fig.add_trace(go.Scatter(x=plot['aika'], y=plot['ulkolampotila'],
                         name='Ulkolämpötila', mode='lines+markers',
                         line=dict(color='#c03956', width=3, dash='dot'),
                         hovertemplate='%{x|%H:%M}<br>Ulkolämpötila: %{y:.0f} °C<extra></extra>'),
              secondary_y=True)
fig.add_trace(go.Scatter(x=plot['aika'], y=plot['spot_snt'],
                         name='Pörssisähkö', mode='lines+markers',
                         line=dict(color='#16834a', width=2, dash='dash'),
                         yaxis='y3',
                         hovertemplate='%{x|%H:%M}<br>Pörssisähkö: %{y:.2f} snt/kWh<extra></extra>'))
fig.update_layout(title='Tuntikohtaiset kustannukset, ulkolämpötila ja pörssisähkö',
                  hovermode='x unified', legend=dict(orientation='h', y=1.1),
                  margin=dict(t=95, r=135),
                  xaxis=dict(title='Kellonaika', tickformat='%H:%M', dtick=3600000),
                  yaxis3=dict(title=dict(text='Pörssisähkö (snt/kWh)', font=dict(color='#16834a')),
                              overlaying='y', side='right', anchor='free', position=1,
                              tickfont=dict(color='#16834a'), showgrid=False))
fig.update_yaxes(title_text='Lämmityskustannus (€/h)', secondary_y=False)
fig.update_yaxes(title_text='Ulkolämpötila (°C)', secondary_y=True,
                 showgrid=False, tickformat='.0f', dtick=1, automargin=True)
# Siirretään lämpötila-akselia hieman kuvaajan oikeasta reunasta vasemmalle.
fig.update_layout(yaxis2=dict(anchor='free', overlaying='y', side='right', position=0.91),
                  xaxis=dict(domain=[0, 0.91]))
st.plotly_chart(fig, use_container_width=True)

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
st.caption('Tänään-valinnassa käytetään tämän päivän ennustelämpötiloja, ei toteutuneita mittauksia. Lähteet: Pörssisähkövahti (porssisahkovahti.fi), Open-Meteo (open-meteo.com). Hinnat sisältävät ALV:n. Käyttövesi, pellettikattilan apusähkö, käynnistyshäviöt ja lämmityksen katkaisulämpötila eivät sisälly. Lämpöpumpun COP- ja kapasiteettimallit ovat alustavia.')
