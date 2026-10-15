import xml.etree.ElementTree as ET
from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent / "data"
FILTRIRANO_DIR = DATA_DIR / "filtrirano"


# Branje podatkov iz XML datotek in deserializacija v objekte

def read_vreme(pot):
    tree = ET.parse(pot)
    root = tree.getroot()

    vremena = []

    for element in root:
        temperatura = element.findtext("temperatura")
        zapis = {
            "id": element.get("id"),
            "datum": element.findtext("datum"),
            "ura": element.findtext("ura"),
            "temperatura": float(temperatura)
            if temperatura and temperatura.strip()
            else None,
        }
        vremena.append(zapis)

    return vremena


def read_cene(pot):
    tree = ET.parse(pot)
    root = tree.getroot()

    cene = []

    for element in root:
        cena = element.findtext("cenaEURKWh")
        zapis = {
            "id": element.get("id"),
            "datum": element.findtext("datum"),
            "ura": element.findtext("ura"),
            "cenaEURKWh": float(cena) if cena and cena.strip() else None,
        }
        cene.append(zapis)

    return cene


def read_poraba(pot):
    tree = ET.parse(pot)
    root = tree.getroot()

    porabe = []

    for element in root:
        poraba = element.findtext("porabaKWh")
        zapis = {
            "id": element.get("id"),
            "vremeId": element.get("vremeId"),
            "cenaId": element.get("cenaId"),
            "datum": element.findtext("datum"),
            "ura": element.findtext("ura"),
            "porabaKWh": float(poraba) if poraba and poraba.strip() else None,
        }
        porabe.append(zapis)

    return porabe


# Združevanje podatkov po ID-jih

def zdruzi_podatke(vremena, cene, porabe):
    vreme_po_id = {vreme["id"]: vreme for vreme in vremena}
    cena_po_id = {cena["id"]: cena for cena in cene}

    zdruzeni_podatki = []

    for poraba in porabe:
        vreme = vreme_po_id.get(poraba["vremeId"])
        cena = cena_po_id.get(poraba["cenaId"])

        zapis = {
            "id": poraba["id"],
            "datum": poraba["datum"],
            "ura": poraba["ura"],
            "porabaKWh": poraba["porabaKWh"],
            "temperatura": vreme["temperatura"] if vreme else None,
            "cenaEURKWh": cena["cenaEURKWh"] if cena else None,
        }

        zdruzeni_podatki.append(zapis)

    return zdruzeni_podatki


# Filtriranje podatkov

def filtriraj_podatke(podatki):
    print("\n=== FILTRIRANJE PODATKOV ===")
    print("1 - Poraba elektrike nad izbrano vrednostjo")
    print("2 - Cena elektrike nad izbrano vrednostjo")
    print("3 - Temperatura pod izbrano vrednostjo")
    print("4 - Meritve v izbranem časovnem obdobju")

    izbira = input("Izberi filter (1-4): ").strip()

    if izbira == "1":
        meja = float(input("Vnesi najmanjšo porabo v kWh: "))

        filtrirani = [
            zapis for zapis in podatki
            if zapis["porabaKWh"] > meja
        ]

    elif izbira == "2":
        meja = float(input("Vnesi najmanjšo ceno v EUR/kWh: "))

        filtrirani = [
            zapis for zapis in podatki
            if zapis["cenaEURKWh"] > meja
        ]

    elif izbira == "3":
        meja = float(input("Vnesi temperaturo v °C: "))

        filtrirani = [
            zapis for zapis in podatki
            if zapis["temperatura"] is not None
            and zapis["temperatura"] < meja
        ]

    elif izbira == "4":
        datum_od = input("Začetni datum (LLLL-MM-DD): ").strip()
        datum_do = input("Končni datum (LLLL-MM-DD): ").strip()

        if datum_od > datum_do:
            print("Napaka: začetni datum je poznejši od končnega.")
            return []

        filtrirani = [
            zapis for zapis in podatki
            if datum_od <= zapis["datum"] <= datum_do
        ]

    else:
        print("Neveljavna izbira filtra.")
        return []

    izpisi_tabelo(filtrirani)
    return filtrirani


# Formatiranje podatkov

def izpisi_tabelo(podatki):

    print(
        f"{'Datum':<12} {'Ura':<7} "
        f"{'Poraba (kWh)':>14} "
        f"{'Cena (EUR/kWh)':>17} "
        f"{'Temperatura (°C)':>19}"
    )
    print("-" * 75)

    for zapis in podatki:
        temperatura = zapis["temperatura"]

        if temperatura is None:
            temperatura_izpis = "Ni podatka"
        else:
            temperatura_izpis = f"{temperatura:.1f}"

        print(
            f"{zapis['datum']:<12} "
            f"{zapis['ura']:<7} "
            f"{zapis['porabaKWh']:>14.3f} "
            f"{zapis['cenaEURKWh']:>17.5f} "
            f"{temperatura_izpis:>19}"
        )


# Izvoz filtriranih podatkov v JSON

def izvozi_json(podatki, pot=FILTRIRANO_DIR / "filtrirano.json"):
    pot = Path(pot)
    pot.parent.mkdir(parents=True, exist_ok=True)

    with pot.open("w", encoding="utf-8") as datoteka:
        json.dump(podatki, datoteka, ensure_ascii=False, indent=2)
    print(f"Filtrirani podatki so bili izvoženi v filtrirano.json")


# Izvoz filtriranih podatkov v XML

def izvozi_xml(podatki, pot=FILTRIRANO_DIR / "filtrirano.xml"):
    pot = Path(pot)
    pot.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("meritve")

    for zapis in podatki:
        meritev = ET.SubElement(root, "meritev")

        for kljuc, vrednost in zapis.items():
            element = ET.SubElement(meritev, kljuc)

            if vrednost is None:
                element.text = ""
            else:
                element.text = str(vrednost)

    tree = ET.ElementTree(root)

    ET.indent(tree, space="    ")

    tree.write(
        pot,
        encoding="utf-8",
        xml_declaration=True
    )

    print(f"Filtrirani podatki so bili izvoženi v filtrirano.xml")


# Glavna funkcija

def main():
    vremena = read_vreme(DATA_DIR / "vreme.xml")
    cene = read_cene(DATA_DIR / "cene.xml")
    porabe = read_poraba(DATA_DIR / "poraba.xml")

    print(vremena[1])
    print(cene[1])
    print(porabe[1])

    zdruzeni_podatki = zdruzi_podatke(vremena, cene, porabe)
    print(zdruzeni_podatki[1])

    while True:
        try:
            filtrirani_podatki = filtriraj_podatke(zdruzeni_podatki)
            izvozi_json(filtrirani_podatki)
            izvozi_xml(filtrirani_podatki)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()