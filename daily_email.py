"""Lähetä huomisen neutraali lämmityskustannusvertailu Gmail SMTP:llä."""
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage

import numpy as np

from calculator import calculate
from data import load_day

APP_URL = 'https://lammitysvertailu.streamlit.app'


def build_report():
    raw, day = load_day('huomenna')
    result = calculate(raw, pellet_price=0.38, transfer=4.47, tax=2.917,
                       margin=0.50, use_heater=True)

    vilp = float(result['vilp_euro'].sum())
    pelletti = float(result['pelletti_euro'].sum())

    # Johdetaan sähkönkulutus tuntikustannuksista ja kokonaishinnasta.
    # Tarkistetaan nollahinnat ja puuttuvat arvot, jotta tulos ei vääristy.
    hinta = result['sahko_yht_snt']
    if not np.isfinite(hinta.to_numpy(dtype=float)).all() or (hinta == 0).any():
        raise ValueError('VILP:n sähkönkulutusta ei voida laskea: sähkön kokonaishinnassa on nolla tai virheellinen arvo.')
    vilp_kwh = float(result['vilp_sahko_kwh'].sum())
    if not np.isfinite(vilp_kwh):
        raise ValueError('VILP:n sähkönkulutuksen tulos ei ole kelvollinen.')

    difference = abs(vilp - pelletti)
    if difference < 0.005:
        verdict = 'Lämmitysmuotojen kustannukset ovat käytännössä samat.'
    else:
        verdict = ('VILP' if vilp < pelletti else 'Pelletti') + ' on laskennallisesti halvempi.'

    warnings = []
    deficit = float(result['tehovaje_kwh'].sum())
    if deficit > 0.01:
        warnings.append(f'VAROITUS: VILP:n mallinnettu tehovaje on {deficit:.1f} kWh; VILP:n kustannus ei kata koko lämmöntarvetta.')
    if bool(result['epavarma'].any()):
        warnings.append('HUOM: Osa lämpötiloista on mitatun COP-alueen ulkopuolella; arvio on epävarma.')

    date_str = datetime.fromisoformat(str(day)).strftime('%d.%m.%Y')
    subject = f'Lämmitysvertailu {date_str} – {verdict}'
    body = '\n'.join([
        f'HUOMISEN LÄMMITYSVERTAILU – {date_str}',
        '', verdict, '',
        f'VILP:       {vilp:.2f} €/vrk',
        f'Pelletti:   {pelletti:.2f} €/vrk',
        f'Kustannusero: {difference:.2f} €/vrk',
        f'Lämmöntarve: {result["lammontarve_kwh"].sum():.1f} kWh/vrk',
        f'VILP:n sähkönkulutus: {vilp_kwh:.1f} kWh/vrk',
        '', *warnings, '',
        'Vertailu on laskennallinen, ei lämmitystavan vaihtosuositus.',
        'Pellettihinta 0,38 €/kg, hyötysuhde 85 %; siirto 4,47, sähkövero 2,917 ja marginaali 0,50 snt/kWh.',
        'VILP:n teho- ja COP-mallit ovat alustavia. Käyttöveden lämmitystä ja käynnistyshäviöitä ei ole huomioitu.',
        '', f'Sovellus: {APP_URL}',
    ])
    return subject, body


def main():
    sender = os.environ['GMAIL_ADDRESS']
    recipient = os.environ['MAIL_TO']
    password = os.environ['GMAIL_APP_PASSWORD']

    subject, body = build_report()
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content(body)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print('Sähköposti lähetetty. Aihe:', subject)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Päivittäinen sähköposti epäonnistui: {exc}', file=sys.stderr)
        sys.exit(1)
