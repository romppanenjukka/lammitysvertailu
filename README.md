# Lämmitysvertailu – Lappeenranta

Ensimmäinen toimiva Streamlit-versio. Vertailee huomisen vuorokauden VILP- ja pellettikustannuksia ja suosittelee vaihtoa vain, jos säästö ylittää asetetun rajan (oletus 5 €/vrk).

## Asennus Windowsissa

1. Asenna Python 3.11 tai uudempi, jos sitä ei ole.
2. Pura ZIP-kansio ja avaa komentokehote kansiossa.
3. Suorita:

```bat
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Selain avautuu osoitteeseen `http://localhost:8501`.

## Tietolähteet

- Sähkö: https://porssisahkovahti.fi/api/v1/hinnat.json?paiva=huomenna (ALV mukana)
- Sää: https://open-meteo.com/en/docs (Lappeenranta, tuntiennuste)

Huomisen sähkönhinnat julkaistaan tavallisesti noin klo 14.45. Kokeile klo 15 jälkeen.

## Laskenta ja rajoitukset

- Lämmöntarve kW = max(0, 4.5 - 0.193 * ulkolämpötila)
- Menovesi °C = 41 - 0.55 * ulkolämpötila
- COP = 4.2876 + 0.15081 * ulkolämpötila, mitatun alueen −15…+3,7 °C sisällä.
- Alle −15 °C COP on **oletus**: max(1.5, 2.02545 + 0.05*(T+15)). Ei varmennettu Toshiban suorituskykyarvo.
- Yli +3,7 °C COP-kaava on ekstrapolaatio, ja siitä näytetään varoitus.
- 3 kW sähkövastuksen tehontarve arvioidaan alustavalla 55 °C:n lämpöpumpun kapasiteettikäyrällä. Tämä ei ole tarkka laitemittaus eikä ota menoveden vaihtelua huomioon.
- Jos laskennallinen tehovaje jää vastuksen jälkeen, sovellus varoittaa. Silloin VILP-kustannus ei vastaa täyden lämmöntarpeen kattamista.
- Pelletin lämpöarvo oletus 4,8 kWh/kg, kattilan hyötysuhde 85 %.
- Sähkön hinnan lisäerät (sis. ALV): siirto 4,47, sähkövero 2,917, marginaali 0,50 snt/kWh.
- Lämmityksen katkaisulämpötilaa, käyttövettä, sulatuksia erillisenä, apusähköä, käynnistyksiä ja huoltoa ei mallinneta.
- Sovellus **ei ohjaa** lämmityslaitteita.
- Aikavyöhyke Europe/Helsinki. Kesä-/talviaikasiirtymässä säärajapinnan aikaleimat voivat olla monitulkintaisia, jolloin laskenta keskeytetään mieluummin kuin arvataan.

Laskentaa kannattaa kalibroida toteutuneilla lämmitys- ja sähkönkulutustiedoilla ennen kuin suositusta käyttää suurten kustannuspäätösten pohjana.
