import arcpy
import os

#Voer hier de naam in van de Geodatabase waar de shapefiles te vinden zijn.
BRON_GDB = r"G:\civ\IGA_ATG\Producten\BGT\stages\Stage Matz Robijn\Originele shapefiles.gdb"

#Voer hier de naam in van de Geodatabase waar de outpunt komt te staan.
OUTPUT_GDB = r"G:\civ\IGA_ATG\Producten\BGT\stages\Stage Matz Robijn\Geconverteerde shapefiles.gdb"

#Voer hier de originele naam van de shapefile van [..] object in met de doelnaam en soort conversie
CONVERSIES = [
    ("Waarschuwingshek", "POLYLINE",  "POINT",   "Waarschuwingshek_punt"),
    ("Zonnepaneel",      "POLYGON",   "POINT",   "Zonnepaneel_punt"),
    ("Coupure",          "POLYLINE",  "POLYGON", "Coupure_vlak"),
    ("Pijler",           "POINT",     "POLYGON", "Pijler_vlak"),
    ("Damwand",          "POLYGON",   "POLYLINE","Damwand_lijn"),
    ("Greppel",          "POLYLINE",  "POLYGON", "Greppel_vlak"),
    ("Muur",             "POLYGON",   "POLYLINE","Muur_lijn"),
    ("Boomgroep", "POLYGON", "POINT","Boomgroep_punt"),  
]

# Voer hier de gewenste kolommen in die moeten worden overgezet in vaste volgorde (OBJECTID en SHAPE worden automatisch overgezet)
GEWENSTE_VELDEN = [
    "type",
    "type_2",
    "overigkenmerk",
    "subcat",
    "onderhouder",
    "beheerder",
    "eigenaar",
    "niveau",
    "monument",
    "datumaanleg",
    "st_length__shape_",
]

SHAPEFILE_MAP = {naam: os.path.join(BRON_GDB, naam) for naam, *_ in CONVERSIES}
SPATIAL_REF = arcpy.SpatialReference(28992)
arcpy.env.workspace = OUTPUT_GDB
arcpy.env.overwriteOutput = True

if not arcpy.Exists(BRON_GDB):
    print(f"FOUT: BRON_GDB niet gevonden: {BRON_GDB}")
elif not arcpy.Exists(OUTPUT_GDB):
    print(f"FOUT: OUTPUT_GDB niet gevonden: {OUTPUT_GDB}")
else:
    print("Configuratie geladen ✓")
    print(f"Bron GDB: {BRON_GDB}")
    print(f"Output GDB: {OUTPUT_GDB}")

def get_gewenste_velden(fc):
    bestaande_velden = {f.name.lower(): f.name for f in arcpy.ListFields(fc)}
    velden = []
    for veld in GEWENSTE_VELDEN:
        if veld.lower() in bestaande_velden:
            velden.append(bestaande_velden[veld.lower()])
    return velden

def maak_output_fc(output_pad, geom_type):
    gdb = os.path.dirname(output_pad)
    naam = os.path.basename(output_pad)
    if arcpy.Exists(output_pad):
        arcpy.management.Delete(output_pad)
        print(f"  Bestaande feature class verwijderd: {naam}")
    arcpy.management.CreateFeatureclass(gdb, naam, geom_type, spatial_reference=SPATIAL_REF)
    print(f"  Feature class aangemaakt: {naam} ({geom_type})")
    return output_pad

def kopieer_velden(bron_fc, doel_fc, velden):
    bron_velden = {f.name: f for f in arcpy.ListFields(bron_fc)}
    for veldnaam in velden:
        if veldnaam in bron_velden:
            f = bron_velden[veldnaam]
            try:
                arcpy.management.AddField(
                    doel_fc, f.name, f.type,
                    field_length=f.length if f.type in ("String", "Text") else None,
                    field_alias=f.aliasName
                )
            except Exception as e:
                print(f"    Waarschuwing bij veld '{veldnaam}': {e}")

print("Hulpfuncties geladen ✓")

def lijn_naar_punt(bron_fc, output_fc):
    velden = get_gewenste_velden(bron_fc)
    maak_output_fc(output_fc, "POINT")
    kopieer_velden(bron_fc, output_fc, velden)
    count = 0
    with arcpy.da.SearchCursor(bron_fc, ["SHAPE@"] + velden) as s_cur, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"] + velden) as i_cur:
        for rij in s_cur:
            geom = rij[0]
            if geom is None:
                continue
            punt = geom.centroid
            i_cur.insertRow([arcpy.PointGeometry(punt, SPATIAL_REF)] + list(rij[1:]))
            count += 1
    print(f"  Lijn -> Punt: {count} objecten verwerkt")
    return count

def vlak_naar_punt(bron_fc, output_fc):
    velden = get_gewenste_velden(bron_fc)
    maak_output_fc(output_fc, "POINT")
    kopieer_velden(bron_fc, output_fc, velden)
    count = 0
    with arcpy.da.SearchCursor(bron_fc, ["SHAPE@"] + velden) as s_cur, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"] + velden) as i_cur:
        for rij in s_cur:
            geom = rij[0]
            if geom is None:
                continue
            punt = geom.centroid
            i_cur.insertRow([arcpy.PointGeometry(punt, SPATIAL_REF)] + list(rij[1:]))
            count += 1
    print(f"  Vlak -> Punt: {count} objecten verwerkt")
    return count

# Voer de bufferafstand in voor de grootte van het schetsvlak achter "buffer_afstand=..." voor de conversie lijn naar vlak.

def lijn_naar_vlak(bron_fc, output_fc, buffer_afstand=0.5):
    velden = get_gewenste_velden(bron_fc)
    maak_output_fc(output_fc, "POLYGON")
    kopieer_velden(bron_fc, output_fc, velden)
    geslaagd = 0
    mislukt = 0
    with arcpy.da.SearchCursor(bron_fc, ["SHAPE@"] + velden) as s_cur, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"] + velden) as i_cur:
        for rij in s_cur:
            geom = rij[0]
            if geom is None:
                mislukt += 1
                continue
            try:
                polygoon = geom.buffer(buffer_afstand)
                i_cur.insertRow([polygoon] + list(rij[1:]))
                geslaagd += 1
            except Exception as e:
                print(f"    Waarschuwing: rij overgeslagen ({e})")
                mislukt += 1
    print(f"  Lijn -> Vlak (buffer {buffer_afstand}m): {geslaagd} geslaagd, {mislukt} overgeslagen")
    return geslaagd

# Voer de bufferafstand in voor de grootte van het schetsvlak achter "buffer_afstand=..." voor de conversie punt naar vlak.

def punt_naar_vlak(bron_fc, output_fc, buffer_afstand=0.5):
    velden = get_gewenste_velden(bron_fc)
    maak_output_fc(output_fc, "POLYGON")
    kopieer_velden(bron_fc, output_fc, velden)
    count = 0
    with arcpy.da.SearchCursor(bron_fc, ["SHAPE@"] + velden) as s_cur, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"] + velden) as i_cur:
        for rij in s_cur:
            geom = rij[0]
            if geom is None:
                continue
            polygoon = geom.buffer(buffer_afstand)
            i_cur.insertRow([polygoon] + list(rij[1:]))
            count += 1
    print(f"  Punt -> Vlak (buffer {buffer_afstand}m): {count} objecten verwerkt")
    return count

def vlak_naar_lijn(bron_fc, output_fc):
    velden = get_gewenste_velden(bron_fc)
    maak_output_fc(output_fc, "POLYLINE")
    kopieer_velden(bron_fc, output_fc, velden)
    count = 0
    with arcpy.da.SearchCursor(bron_fc, ["SHAPE@"] + velden) as s_cur, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"] + velden) as i_cur:
        for rij in s_cur:
            geom = rij[0]
            if geom is None:
                continue
            lijn = geom.boundary()
            i_cur.insertRow([lijn] + list(rij[1:]))
            count += 1
    print(f"  Vlak -> Lijn: {count} objecten verwerkt")
    return count

print("Conversiefuncties geladen ✓")

import time
import sys


def toon_voortgang(huidig, totaal, label=""):
    """
    Print een eenvoudige voortgangsbalk in de console.
    Bijvoorbeeld: [########------------] 40% (2/5) INPUT_lijnen
    """

    breedte = 30

    fractie = huidig / totaal if totaal else 1

    aantal_blokjes = int(breedte * fractie)

    balk = (
        "#" * aantal_blokjes
        + "-" * (breedte - aantal_blokjes)
    )

    percentage = int(fractie * 100)

    regel = (
        f"\r  [{balk}] {percentage:3d}% "
        f"({huidig}/{totaal}) {label}"
    )

    # Regel opvullen met spaties zodat oude tekst
    # niet blijft doorschemeren
    sys.stdout.write(regel.ljust(90))
    sys.stdout.flush()

    if huidig >= totaal:
        print()


# Voorkomt dat geoprocessing-tools hun output automatisch
# en los (buiten de groepen) aan de kaart toevoegen
arcpy.env.addOutputsToMap = False

# ============================================================
# STAP 0: Bronlagen toevoegen aan kaart vanuit BRON_GDB
# in een groep
# ============================================================

print("=" * 60)
print("STAP 0: Bronlagen toevoegen aan kaart")
print("=" * 60)

try:
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    kaart = aprx.listMaps()[0]

    # INPUT-groep zoeken of maken
    bron_groep_naam = "INPUT - Originele lagen"
    bron_groep = None

    for laag in kaart.listLayers():
        if laag.isGroupLayer and laag.name == bron_groep_naam:
            bron_groep = laag
            break

    if bron_groep is None:
        bron_groep = kaart.createGroupLayer(bron_groep_naam)
        print(f"  Groep aangemaakt: {bron_groep_naam}")
    else:
        print(f"  Groep gevonden: {bron_groep_naam}")

    # Bronlagen toevoegen
    totaal_bronlagen = len(CONVERSIES)

    for index, (shapefile_naam, *_) in enumerate(CONVERSIES, start=1):

        bron_fc = SHAPEFILE_MAP[shapefile_naam]

        toon_voortgang(
            index,
            totaal_bronlagen,
            shapefile_naam
        )

        if not arcpy.Exists(bron_fc):
            print(
                f"  FOUT: Bronlaag niet gevonden in GDB: "
                f"{shapefile_naam}"
            )
            continue

        # Controleren of de laag al IN de INPUT-groep staat
        bestaande_input_lagen = [
            laag.name
            for laag in bron_groep.listLayers()
        ]

        if shapefile_naam in bestaande_input_lagen:
            print(
                f"  Bronlaag staat al in INPUT-groep: "
                f"{shapefile_naam}"
            )
            continue

        # Laag toevoegen aan kaart
        nieuwe_laag = kaart.addDataFromPath(bron_fc)

        # Naam vastleggen voordat de laag verwijderd wordt
        laag_naam = nieuwe_laag.name

        # Laag in INPUT-groep plaatsen
        kaart.addLayerToGroup(
            bron_groep,
            nieuwe_laag,
            "BOTTOM"
        )

        # Losse kopie buiten de groep weer verwijderen
        kaart.removeLayer(nieuwe_laag)

        print(
            f"  Bronlaag toegevoegd aan INPUT-groep: "
            f"{laag_naam}"
        )

    aprx.save()

    print("\nAlle bronlagen toegevoegd ✓")

except Exception as e:
    print(
        f"\nBronlagen konden niet worden toegevoegd: {e}"
    )

print()


# ============================================================
# STAP 1: Output GDB leegmaken
# ============================================================

print("=" * 60)
print("STAP 1: Output GDB leegmaken")
print("=" * 60)

gdb_leegmaken = input(
    "Wil je de output GDB volledig leegmaken "
    "voor je begint? Typ 'ja' of 'nee': "
).strip().lower()

if gdb_leegmaken == "ja":

    arcpy.env.workspace = OUTPUT_GDB

    # Alle feature classes verzamelen, ook die binnen
    # feature datasets staan (ListFeatureClasses alleen
    # ziet de root van de GDB, dus we lopen ook de
    # datasets langs)
    alle_fc = []

    # Feature classes los in de root van de GDB
    for fc in arcpy.ListFeatureClasses() or []:
        alle_fc.append(fc)

    # Feature classes binnen feature datasets
    for dataset in arcpy.ListDatasets(feature_type="Feature") or []:

        arcpy.env.workspace = os.path.join(OUTPUT_GDB, dataset)

        for fc in arcpy.ListFeatureClasses() or []:
            alle_fc.append(
                os.path.join(dataset, fc)
            )

        arcpy.env.workspace = OUTPUT_GDB

    if alle_fc:

        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            kaart = aprx.listMaps()[0]

            # Alleen lagen uit de OUTPUT-groep verwijderen
            output_groep_naam = "OUTPUT - Geconverteerde lagen"

            output_groep = None

            for laag in kaart.listLayers():
                if (
                    laag.isGroupLayer
                    and laag.name == output_groep_naam
                ):
                    output_groep = laag
                    break

            if output_groep is not None:

                for laag in output_groep.listLayers():

                    kaart.removeLayer(laag)

                    print(
                        f"  Laag verwijderd uit OUTPUT-groep: "
                        f"{laag.name}"
                    )

            aprx.save()

        except Exception as e:
            print(
                f"  Waarschuwing bij verwijderen uit kaart: "
                f"{e}"
            )

        # Feature classes uit OUTPUT GDB verwijderen,
        # elke verwijdering apart controleren
        aantal_verwijderd = 0

        for fc in alle_fc:

            fc_pad = os.path.join(OUTPUT_GDB, fc)

            try:
                arcpy.management.Delete(fc_pad)

                # Controleren of hij echt weg is
                if not arcpy.Exists(fc_pad):
                    print(
                        f"  ✓ Verwijderd uit GDB: {fc}"
                    )
                    aantal_verwijderd += 1
                else:
                    print(
                        f"  ✗ LET OP: {fc} bestaat nog "
                        f"na Delete-aanroep "
                        f"(mogelijk locked door open sessie)"
                    )

            except Exception as e:
                print(
                    f"  ✗ FOUT bij verwijderen van {fc}: {e}"
                )

        print(
            f"\nOutput GDB geleegd "
            f"({aantal_verwijderd}/{len(alle_fc)} "
            f"feature classes daadwerkelijk verwijderd) ✓"
        )

        print(
            "  Zie je de wijziging niet in het Catalog-paneel? "
            "Klik rechts op de GDB en kies 'Refresh'."
        )

    else:
        print("  Output GDB was al leeg.")

else:
    print(
        "  Output GDB niet geleegd, "
        "doorgaan met bestaande inhoud."
    )

print()


# ============================================================
# STAP 2: Controleer op bestaande lagen en vraag bevestiging
# ============================================================

print("=" * 60)
print("STAP 2: Controleer bestaande lagen")
print("=" * 60)

al_bestaand = []

for _, _, _, output_naam in CONVERSIES:

    output_fc = os.path.join(
        OUTPUT_GDB,
        output_naam
    )

    if arcpy.Exists(output_fc):
        al_bestaand.append(output_naam)


if al_bestaand:

    print("De volgende lagen bestaan al:")

    for naam in al_bestaand:
        print(f"  - {naam}")

    bevestiging = input(
        "\nWil je deze lagen overschrijven? "
        "Typ 'ja' om door te gaan of 'nee' om te stoppen: "
    ).strip().lower()

    if bevestiging != "ja":

        print(
            "Script gestopt. "
            "Geen lagen overschreven."
        )

        raise SystemExit

else:

    print(
        "Geen bestaande lagen gevonden, "
        "direct doorgaan."
    )

print()


# ============================================================
# STAP 3: Conversie uitvoeren
# ============================================================

start_tijd = time.time()
totaal_objecten = 0

print("=" * 60)
print("STAP 3: BGT Geometrieconversie gestart")
print("=" * 60)


totaal_conversies = len(CONVERSIES)

for volgnummer, (
    shapefile_naam,
    bron_type,
    doel_type,
    output_naam
) in enumerate(CONVERSIES, start=1):

    bron_fc = SHAPEFILE_MAP[shapefile_naam]

    output_fc = os.path.join(
        OUTPUT_GDB,
        output_naam
    )

    print(
        f"\n[{shapefile_naam}] "
        f"{bron_type} -> {doel_type}"
    )

    if not arcpy.Exists(bron_fc):

        print(
            f"  FOUT: Bronbestand niet gevonden: "
            f"{bron_fc}"
        )

        continue

    gevonden_velden = get_gewenste_velden(bron_fc)

    print(
        f"  Velden gevonden: "
        f"{gevonden_velden}"
    )

    aantal = 0

    sleutel = (
        f"{bron_type}_naar_{doel_type}"
    )

    if sleutel == "POLYLINE_naar_POINT":

        aantal = lijn_naar_punt(
            bron_fc,
            output_fc
        )

    elif sleutel == "POLYGON_naar_POINT":

        aantal = vlak_naar_punt(
            bron_fc,
            output_fc
        )

    elif sleutel == "POLYLINE_naar_POLYGON":

        aantal = lijn_naar_vlak(
            bron_fc,
            output_fc,
            buffer_afstand=0.5
        )

    elif sleutel == "POINT_naar_POLYGON":

        aantal = punt_naar_vlak(
            bron_fc,
            output_fc,
            buffer_afstand=0.5
        )

    elif sleutel == "POLYGON_naar_POLYLINE":

        aantal = vlak_naar_lijn(
            bron_fc,
            output_fc
        )

    totaal_objecten += aantal

    toon_voortgang(
        volgnummer,
        totaal_conversies,
        output_naam
    )


# ============================================================
# STAP 4: Outputlagen toevoegen aan kaart in een groep
# ============================================================

print("\n" + "=" * 60)
print("STAP 4: Outputlagen toevoegen aan kaart")
print("=" * 60)

try:

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    kaart = aprx.listMaps()[0]

    # OUTPUT-groep zoeken of maken
    output_groep_naam = "OUTPUT - Geconverteerde lagen"

    output_groep = None

    for laag in kaart.listLayers():

        if (
            laag.isGroupLayer
            and laag.name == output_groep_naam
        ):

            output_groep = laag
            break

    if output_groep is None:

        output_groep = kaart.createGroupLayer(
            output_groep_naam
        )

        print(
            f"  Groep aangemaakt: "
            f"{output_groep_naam}"
        )

    else:

        print(
            f"  Groep gevonden: "
            f"{output_groep_naam}"
        )

    # Outputlagen toevoegen
    totaal_outputlagen = len(CONVERSIES)

    for index, (_, _, _, output_naam) in enumerate(CONVERSIES, start=1):

        output_fc = os.path.join(
            OUTPUT_GDB,
            output_naam
        )

        toon_voortgang(
            index,
            totaal_outputlagen,
            output_naam
        )

        if not arcpy.Exists(output_fc):

            print(
                f"  FOUT: Output niet gevonden: "
                f"{output_fc}"
            )

            continue

        # Controleren of laag al in OUTPUT-groep staat
        bestaande_output_lagen = [
            laag.name
            for laag in output_groep.listLayers()
        ]

        if output_naam in bestaande_output_lagen:

            print(
                f"  Laag staat al in OUTPUT-groep: "
                f"{output_naam}"
            )

            continue

        # Laag toevoegen aan kaart
        nieuwe_output_laag = kaart.addDataFromPath(
            output_fc
        )

        # Naam vastleggen voordat de laag verwijderd wordt
        output_laag_naam = nieuwe_output_laag.name

        # Laag in OUTPUT-groep plaatsen
        kaart.addLayerToGroup(
            output_groep,
            nieuwe_output_laag,
            "BOTTOM"
        )

        # Losse kopie buiten de groep weer verwijderen
        kaart.removeLayer(nieuwe_output_laag)

        print(
            f"  ✓ Laag toegevoegd aan OUTPUT-groep: "
            f"{output_laag_naam}"
        )

    aprx.save()

    print("\nKaart bijgewerkt ✓")

except Exception as e:

    print(
        f"\nLagen konden niet automatisch "
        f"worden toegevoegd: {e}"
    )


print("\n" + "=" * 60)
print("Conversie voltooid!")
print(
    f"Totaal aantal verwerkte objecten: "
    f"{totaal_objecten}"
)
print("=" * 60)


# ============================================================
# STAP 5: Tijdmeting
# ============================================================

eind_tijd = time.time()

verschil = (
    eind_tijd - start_tijd
)

minuten = int(
    verschil // 60
)

seconden = int(
    verschil % 60
)

print(
    f"\nTotale uitvoertijd: "
    f"{minuten} minuten en "
    f"{seconden} seconden"
)


