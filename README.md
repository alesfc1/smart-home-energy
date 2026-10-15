#  Smart Home Energy - Pametni energetski svetovalec

Sistem za analizo porabe električne energije in pripravo priporočil za učinkovitejšo rabo energije.

## Opis projekta

Smart Home Energy je aplikacija, namenjena analizi porabe električne energije v gospodinjstvu.

Sistem uporablja zgodovinske podatke o:
- porabi električne energije,
- ceni električne energije,
- vremenskih razmerah.

Zgodovinske podatke sistem analizira in jih primerja z aktualnimi vremenskimi podatki ter cenami električne energije. Na podlagi podobnih zgodovinskih razmer lahko sistem oceni pričakovano porabo in uporabniku pripravi priporočila za zmanjšanje porabe in stroškov.

Glavni cilj projekta je uporabniku poleg pregleda zgodovinskih podatkov ponuditi tudi uporabne informacije o tem, kdaj in kako lahko učinkoviteje uporablja električno energijo.

## Načrtovane funkcionalnosti

- prikaz zgodovinske porabe električne energije,
- prikaz cen električne energije,
- prikaz vremenskih podatkov,
- primerjava porabe, vremena in cen,
- analiza vzorcev porabe,
- ocena porabe na podlagi podobnih zgodovinskih razmer,
- izračun ocenjenih stroškov,
- priprava priporočil za zmanjšanje porabe in stroškov,
- vizualizacija podatkov v obliki grafov in preglednic.

## Viri podatkov

### Zenodo

Za zgodovinske podatke o porabi električne energije se uporablja javno dostopen podatkovni vir Zenodo.

Podatki vsebujejo meritve porabe električne energije gospodinjstva v 15-minutnih intervalih.

### Open-Meteo

Open-Meteo se uporablja za pridobivanje zgodovinskih in napovednih podatkov o temperaturi ozračja.

### Electricity Maps

Electricity Maps se uporablja za pridobivanje podatkov o ceni električne energije.

### Zagon aplikacije

Iz korenske mape projekta zaženemo program iz terminala z ukazom:

```powershell
.\.venv\Scripts\python.exe .\src\smart_home_energy\naloga1\main.py
```

### Naloga 1

Program prebere podatke iz XML-datotek v `src/smart_home_energy/naloga1/data/`, prikaže uporabniku
naslednje možnosti filtriranja:
- Poraba elektrike nad izbrano vrednostjo
- Cena elektrike nad izbrano vrednostjo
- Temperatura pod izbrano vrednostjo
- Meritve v izbranem časovnem obdobju

Po vnešenih kriterijih se podatki prikažejo v konzoli v obliki tabele in rezultati shranijo v JSON in XML datoteki:

```text
src/smart_home_energy/naloga1/data/filtrirano/filtrirano.json
src/smart_home_energy/naloga1/data/filtrirano/filtrirano.xml
```

Trenutno shranjeni rezultati vsebujejo vse meritve, pri katerih je temperatura nižja od −7 °C.


