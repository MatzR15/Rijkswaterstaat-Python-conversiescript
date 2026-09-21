import arcpy
import os
import time
import sys

# ─── PADEN ────────────────────────────────────────────────────
# GDB waar de bronlagen in staan
EXTRACTIE_GDB    = r"M:\IVRINext\Backup\eengis\eengis_eengis.gdb"

# Feature Dataset binnen de GDB waar de bronlagen uit worden gehaald
FEATURE_DATASET  = "EENGIS_DATA"

# GDB waar de geëxtraheerde losse feature classes naartoe worden geschreven
BRON_GDB         = r"G:\civ\IGA_ATG\Producten\BGT\stages\Stage Matz Robijn\Originele shapefiles.gdb"

# GDB waar de geconverteerde feature classes komen te staan
OUTPUT_GDB       = r"G:\civ\IGA_ATG\Producten\BGT\stages\Stage Matz Robijn\Geconverteerde shapefiles.gdb"

# ─── GEWENSTE VELDEN ──────────────────────────────────────────
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

# ─── OBJECT DEFINITIES ────────────────────────────────────────
# Formaat: "Objectnaam": ("Laagnaam_in_FEATURE_DATASET", "Veldnaam", "Brongeometrie", "Doelgeometrie", "Outputnaam")
OBJECT_DEFINITIES = {
    "Waarschuwingshek": ("lMeubilair",              "type", "POLYLINE",  "POINT",   "Waarschuwingshek_punt"),
    "Zonnepaneel":      ("vMeubilairEnVoorziening", "type", "POLYGON",   "POINT",   "Zonnepaneel_punt"),
    "Coupure":          ("lKunstwerk",              "type", "POLYLINE",  "POLYGON", "Coupure_vlak"),
    "Pijler":           ("pKunstwerkdeel",          "type", "POINT",     "POLYGON", "Pijler_vlak"),
    "Damwand":          ("vKunstwerkdeel",          "type", "POLYGON",   "POLYLINE","Damwand_lijn"),
    "Greppel":          ("lWater",                  "type", "POLYLINE",  "POLYGON", "Greppel_vlak"),
    "Muur":             ("vKunstwerkdeel",          "type", "POLYGON",   "POLYLINE","Muur_lijn"),
    # Voeg hier nieuwe objecten toe
}

# Leesbare omschrijving van conversiesoorten
CONVERSIE_OMSCHRIJVING = {
    "POLYLINE_naar_POINT":   "lijn naar punt",
    "POLYGON_naar_POINT":    "vlak naar punt",
    "POLYLINE_naar_POLYGON": "lijn naar vlak",
    "POINT_naar_POLYGON":    "punt naar vlak",
    "POLYGON_naar_POLYLINE": "vlak naar lijn",
}

SPATIAL_REF = arcpy.SpatialReference(28992)
arcpy.env.overwriteOutput  = True
arcpy.env.addOutputsToMap  = False

# GDB validatie
fout = False
for label, pad in [("EXTRACTIE_GDB", EXTRACTIE_GDB), ("BRON_GDB", BRON_GDB), ("OUTPUT_GDB", OUTPUT_GDB)]:
    if not arcpy.Exists(pad):
        print(f"FOUT: {label} niet gevonden: {pad}")
        fout = True

if not fout:
    print("Configuratie geladen ✓")
    print(f"  Extractie GDB    : {EXTRACTIE_GDB}")
    print(f"  Feature Dataset  : {FEATURE_DATASET}")
    print(f"  Bron GDB         : {BRON_GDB}")
    print(f"  Output GDB       : {OUTPUT_GDB}")

# ─── VELDEN ───────────────────────────────────────────────────

def get_gewenste_velden(fc):
    bestaande_velden = {f.name.lower(): f.name for f in arcpy.ListFields(fc)}
    return [bestaande_velden[v.lower()] for v in GEWENSTE_VELDEN if v.lower() in bestaande_velden]

def maak_output_fc(output_pad, geom_type):
    naam = os.path.basename(output_pad)
    if arcpy.Exists(output_pad):
        arcpy.management.Delete(output_pad)
        print(f"  Bestaande feature class verwijderd: {naam}")
    arcpy.management.CreateFeatureclass(os.path.dirname(output_pad), naam, geom_type, spatial_reference=SPATIAL_REF)
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

# ─── VOORTGANGSBALK ───────────────────────────────────────────

def toon_voortgang(huidig, totaal, label=""):
    breedte        = 30
    fractie        = huidig / totaal if totaal else 1
    aantal_blokjes = int(breedte * fractie)
    balk           = "#" * aantal_blokjes + "-" * (breedte - aantal_blokjes)
    percentage     = int(fractie * 100)
    sys.stdout.write(f"\r  [{balk}] {percentage:3d}% ({huidig}/{totaal}) {label}".ljust(90))
    sys.stdout.flush()
    if huidig >= totaal:
        print()

# ─── CONVERSIEFUNCTIES ────────────────────────────────────────

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
            i_cur.insertRow([arcpy.PointGeometry(geom.centroid, SPATIAL_REF)] + list(rij[1:]))
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
            i_cur.insertRow([arcpy.PointGeometry(geom.centroid, SPATIAL_REF)] + list(rij[1:]))
            count += 1
    print(f"  Vlak -> Punt: {count} objecten verwerkt")
    return count

def lijn_naar_vlak(bron_fc, output_fc, buffer_afstand=0.5):
    velden = get_gewenste_velden(bron_fc)

    # Tijdelijke buffer met FLAT uiteindes
    temp_fc = os.path.join(os.path.dirname(output_fc), "temp_buffer")
    if arcpy.Exists(temp_fc):
        arcpy.management.Delete(temp_fc)

    arcpy.analysis.Buffer(
        in_features=bron_fc,
        out_feature_class=temp_fc,
        buffer_distance_or_field=f"{buffer_afstand} Meters",
        line_end_type="FLAT"
    )

    # Maak de echte output aan en kopieer velden
    maak_output_fc(output_fc, "POLYGON")
    kopieer_velden(bron_fc, output_fc, velden)

    # Kopieer geometrie en attribuutvelden van temp naar output
    geslaagd = 0
    mislukt  = 0
    with arcpy.da.SearchCursor(temp_fc, ["SHAPE@"] + velden) as s_cur, \
         arcpy.da.InsertCursor(output_fc, ["SHAPE@"] + velden) as i_cur:
        for rij in s_cur:
            geom = rij[0]
            if geom is None:
                mislukt += 1
                continue
            try:
                i_cur.insertRow([geom] + list(rij[1:]))
                geslaagd += 1
            except Exception as e:
                print(f"    Waarschuwing: rij overgeslagen ({e})")
                mislukt += 1

    arcpy.management.Delete(temp_fc)
    print(f"  Lijn -> Vlak FLAT (buffer {buffer_afstand}m): {geslaagd} geslaagd, {mislukt} overgeslagen")
    return geslaagd

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
            i_cur.insertRow([geom.buffer(buffer_afstand)] + list(rij[1:]))
            count += 1
    print(f"  Punt -> Vlak (buffer {buffer_afstand}m): {count} objecten verwerkt")
    return count

def vlak_naar_lijn(bron_fc, output_fc):
    # Extensie uitchecken
    if arcpy.CheckExtension("Foundation") == "Available":
        arcpy.CheckOutExtension("Foundation")
    else:
        print("  FOUT: Production Mapping extensie niet beschikbaar.")
        return 0

    try:
        # Verwijder output als die al bestaat
        if arcpy.Exists(output_fc):
            arcpy.management.Delete(output_fc)
            print(f"  Bestaande feature class verwijderd: {os.path.basename(output_fc)}")

        # Maak centerline met de Polygon To Centerline tool
        arcpy.topographic.PolygonToCenterline(
            in_features=bron_fc,
            out_feature_class=output_fc
        )
        print(f"  Centerlines aangemaakt: {os.path.basename(output_fc)}")

        # Haal het aantal centerlines op
        count = int(arcpy.management.GetCount(output_fc)[0])

        # Join de attribuutvelden van de bronlaag naar de centerlines
        fid_veld = f"FID_{os.path.basename(bron_fc)}"
        gewenste_velden = get_gewenste_velden(bron_fc)

        if gewenste_velden:
            arcpy.management.JoinField(
                in_data=output_fc,
                in_field=fid_veld,
                join_table=bron_fc,
                join_field="OBJECTID",
                fields=gewenste_velden
            )
            print(f"  Attribuutvelden gejoind: {gewenste_velden}")

        print(f"  Vlak -> Centerline: {count} centerlines aangemaakt")
        return count

    except Exception as e:
        print(f"  FOUT bij aanmaken centerlines: {e}")
        return 0

    finally:
        # Extensie altijd weer inchecken
        arcpy.CheckInExtension("Foundation")

print("Hulp- en conversiefuncties geladen ✓")

def zoek_object(invoer):
    if invoer in OBJECT_DEFINITIES:
        return invoer
    return next((k for k in OBJECT_DEFINITIES if k.lower() == invoer.lower()), None)

def toon_beschikbare_objecten():
    print("\nBeschikbare objecten:")
    for naam in sorted(OBJECT_DEFINITIES.keys()):
        defn    = OBJECT_DEFINITIES[naam]
        sleutel = f"{defn[2]}_naar_{defn[3]}"
        print(f"  - {naam} ({CONVERSIE_OMSCHRIJVING.get(sleutel, 'onbekend')})")
    print()

def exporteer_object(object_naam):
    """Exporteert object vanuit FEATURE_DATASET naar BRON_GDB."""
    laag_naam, veld_naam, _, _, _ = OBJECT_DEFINITIES[object_naam]
    bron_laag = os.path.join(EXTRACTIE_GDB, FEATURE_DATASET, laag_naam)
    bron_fc   = os.path.join(BRON_GDB, object_naam)

    if not arcpy.Exists(bron_laag):
        print(f"  FOUT: Bronlaag '{laag_naam}' niet gevonden in {FEATURE_DATASET}.")
        return False, 0
    try:
        arcpy.conversion.ExportFeatures(
            in_features=bron_laag,
            out_features=bron_fc,
            where_clause=f"{veld_naam} = '{object_naam}'"
        )
        count = int(arcpy.management.GetCount(bron_fc)[0])
        if count == 0:
            print(f"  FOUT: Geen objecten gevonden met {veld_naam} = '{object_naam}'.")
            return False, 0
        return True, count
    except Exception as e:
        print(f"  FOUT bij exporteren: {e}")
        return False, 0

def kies_objecten():
    gekozen = []
    toon_beschikbare_objecten()

    print("Opties:")
    print("  - Typ de naam van een object om het te selecteren")
    print("  - Typ 'ALLES' om alle objecten in één keer te converteren")
    print()

    invoer = input("Welk object wilt u converteren? Typ de naam in of typ 'ALLES': ").strip()

    # Optie: alles selecteren
    if invoer.upper() == "ALLES":
        print("\nAlle objecten geselecteerd. Exporteren naar BRON_GDB...")
        for object_naam in OBJECT_DEFINITIES.keys():
            print(f"\nExporteren: {object_naam}...")
            succes, count = exporteer_object(object_naam)
            if succes:
                _, _, bron_type, doel_type, output_naam = OBJECT_DEFINITIES[object_naam]
                sleutel = f"{bron_type}_naar_{doel_type}"
                omschr  = CONVERSIE_OMSCHRIJVING.get(sleutel, "onbekend")
                gekozen.append((object_naam, bron_type, doel_type, output_naam, omschr, count))
                print(f"  ✓ {count} objecten gevonden en opgeslagen in BRON_GDB.")
            else:
                print(f"  '{object_naam}' wordt niet toegevoegd.")
        return gekozen

    # Optie: losse objecten kiezen
    while True:
        gevonden = zoek_object(invoer)
        if not gevonden:
            print(f"\n  Object '{invoer}' niet gevonden. Controleer de spelling.\n")
        elif gevonden in [o[0] for o in gekozen]:
            print(f"\n  '{gevonden}' staat al in de selectie.\n")
        else:
            print(f"\nObject '{gevonden}' gevonden. Exporteren naar BRON_GDB...")
            succes, count = exporteer_object(gevonden)
            if succes:
                _, _, bron_type, doel_type, output_naam = OBJECT_DEFINITIES[gevonden]
                sleutel = f"{bron_type}_naar_{doel_type}"
                omschr  = CONVERSIE_OMSCHRIJVING.get(sleutel, "onbekend")
                gekozen.append((gevonden, bron_type, doel_type, output_naam, omschr, count))
                print(f"  ✓ {count} objecten gevonden en opgeslagen in BRON_GDB.")
            else:
                print(f"  '{gevonden}' wordt niet toegevoegd.")

        print(f"\nHuidige selectie: {[o[0] for o in gekozen]}")
        if input("Wilt u nog een object toevoegen? Typ 'ja' of 'nee': ").strip().lower() != "ja":
            break
        invoer = input("Welk object wilt u converteren? Typ de naam in of typ 'ALLES': ").strip()
        if invoer.upper() == "ALLES":
            print("\nAlle objecten worden toegevoegd...")
            for object_naam in OBJECT_DEFINITIES.keys():
                if object_naam not in [o[0] for o in gekozen]:
                    succes, count = exporteer_object(object_naam)
                    if succes:
                        _, _, bron_type, doel_type, output_naam = OBJECT_DEFINITIES[object_naam]
                        sleutel = f"{bron_type}_naar_{doel_type}"
                        omschr  = CONVERSIE_OMSCHRIJVING.get(sleutel, "onbekend")
                        gekozen.append((object_naam, bron_type, doel_type, output_naam, omschr, count))
                        print(f"  ✓ {object_naam}: {count} objecten toegevoegd.")
            break

    return gekozen

def toon_bevestiging(gekozen):
    print(f"\n{'=' * 60}")
    if len(gekozen) == 1:
        obj      = gekozen[0]
        antwoord = input(
            f"Weet u zeker dat u het object '{obj[0]}' wilt converteren?\n"
            f"Het object wordt geconverteerd van {obj[4]}.\n"
            f"Typ 'ja' of 'nee': "
        ).strip().lower()
    else:
        print(f"Weet u zeker dat u de volgende {len(gekozen)} objecten wilt converteren?")
        for obj in gekozen:
            print(f"  - {obj[0]}: {obj[4]} ({obj[5]} objecten gevonden)")
        antwoord = input("\nTyp 'ja' of 'nee': ").strip().lower()
    return antwoord == "ja"

print("Menufuncties geladen ✓")

def run():
    print("=" * 60)
    print("BGT Conversiescript V2 — Interactief menu")
    print("=" * 60)

    doorgaan = True
    while doorgaan:

        # Objecten kiezen
        gekozen = kies_objecten()
        if not gekozen:
            print("\nGeen objecten geselecteerd. Script gestopt.")
            break

        # Bevestiging
        if not toon_bevestiging(gekozen):
            print("\nScript gestopt.")
            break

        conversies = [(o[0], o[1], o[2], o[3]) for o in gekozen]

        # Stap 0: Bronlagen toevoegen aan kaart
        print("\n" + "=" * 60)
        print("STAP 0: Bronlagen toevoegen aan kaart")
        print("=" * 60)
        try:
            aprx      = arcpy.mp.ArcGISProject("CURRENT")
            kaart     = aprx.listMaps()[0]
            bron_groep = None
            for laag in kaart.listLayers():
                if laag.isGroupLayer and laag.name == "INPUT - Originele lagen":
                    bron_groep = laag
                    break
            if bron_groep is None:
                bron_groep = kaart.createGroupLayer("INPUT - Originele lagen")
            for object_naam, *_ in gekozen:
                bron_fc = os.path.join(BRON_GDB, object_naam)
                if object_naam not in [l.name for l in bron_groep.listLayers()]:
                    nieuwe_laag = kaart.addDataFromPath(bron_fc)
                    kaart.addLayerToGroup(bron_groep, nieuwe_laag, "BOTTOM")
                    kaart.removeLayer(nieuwe_laag)
                    print(f"  ✓ Bronlaag toegevoegd: {object_naam}")
                else:
                    print(f"  Bronlaag staat al in kaart: {object_naam}")
            aprx.save()
        except Exception as e:
            print(f"  Waarschuwing: bronlagen konden niet worden toegevoegd: {e}")

        # Stap 1: Output GDB leegmaken
        print("\n" + "=" * 60)
        print("STAP 1: Output GDB leegmaken")
        print("=" * 60)
        if input("Wilt u de output GDB volledig leegmaken? Typ 'ja' of 'nee': ").strip().lower() == "ja":
            arcpy.env.workspace = OUTPUT_GDB
            alle_fc = arcpy.ListFeatureClasses()
            if alle_fc:
                try:
                    aprx  = arcpy.mp.ArcGISProject("CURRENT")
                    kaart = aprx.listMaps()[0]
                    for laag in kaart.listLayers():
                        if laag.name in alle_fc:
                            kaart.removeLayer(laag)
                    aprx.save()
                except Exception as e:
                    print(f"  Waarschuwing: {e}")
                for fc in alle_fc:
                    arcpy.management.Delete(os.path.join(OUTPUT_GDB, fc))
                    print(f"  Verwijderd: {fc}")
                print(f"\n  Output GDB geleegd ({len(alle_fc)} feature classes) ✓")
            else:
                print("  Output GDB was al leeg.")
        else:
            print("  Output GDB niet geleegd.")

        # Stap 2: Bestaande lagen controleren
        print("\n" + "=" * 60)
        print("STAP 2: Controleer bestaande lagen")
        print("=" * 60)
        al_bestaand = [o for _, _, _, o in conversies if arcpy.Exists(os.path.join(OUTPUT_GDB, o))]
        if al_bestaand:
            print("De volgende lagen bestaan al:")
            for naam in al_bestaand:
                print(f"  - {naam}")
            if input("\nWilt u deze overschrijven? Typ 'ja' of 'nee': ").strip().lower() != "ja":
                print("Script gestopt.")
                break
        else:
            print("Geen bestaande lagen gevonden, direct doorgaan.")

        # Stap 3: Conversies uitvoeren
        start_tijd      = time.time()
        totaal_objecten = 0
        print("\n" + "=" * 60)
        print("STAP 3: BGT Geometrieconversie gestart")
        print("=" * 60)

        for volgnummer, (shapefile_naam, bron_type, doel_type, output_naam) in enumerate(conversies, start=1):
            bron_fc   = os.path.join(BRON_GDB, shapefile_naam)
            output_fc = os.path.join(OUTPUT_GDB, output_naam)
            print(f"\n[{shapefile_naam}] {bron_type} -> {doel_type}")
            if not arcpy.Exists(bron_fc):
                print(f"  FOUT: Bronbestand niet gevonden: {bron_fc}")
                continue
            print(f"  Velden gevonden: {get_gewenste_velden(bron_fc)}")
            sleutel = f"{bron_type}_naar_{doel_type}"
            aantal  = 0
            if sleutel == "POLYLINE_naar_POINT":
                aantal = lijn_naar_punt(bron_fc, output_fc)
            elif sleutel == "POLYGON_naar_POINT":
                aantal = vlak_naar_punt(bron_fc, output_fc)
            elif sleutel == "POLYLINE_naar_POLYGON":
                aantal = lijn_naar_vlak(bron_fc, output_fc, buffer_afstand=0.5)
            elif sleutel == "POINT_naar_POLYGON":
                aantal = punt_naar_vlak(bron_fc, output_fc, buffer_afstand=0.5)
            elif sleutel == "POLYGON_naar_POLYLINE":
                aantal = vlak_naar_lijn(bron_fc, output_fc)
            totaal_objecten += aantal
            toon_voortgang(volgnummer, len(conversies), output_naam)

        print("\n" + "=" * 60)
        print(f"Conversie voltooid! Totaal verwerkt: {totaal_objecten} objecten")
        print("=" * 60)

        # Stap 4: Outputlagen toevoegen aan kaart
        print("\n" + "=" * 60)
        print("STAP 4: Outputlagen toevoegen aan kaart")
        print("=" * 60)
        try:
            aprx         = arcpy.mp.ArcGISProject("CURRENT")
            kaart        = aprx.listMaps()[0]
            output_groep = None
            for laag in kaart.listLayers():
                if laag.isGroupLayer and laag.name == "OUTPUT - Geconverteerde lagen":
                    output_groep = laag
                    break
            if output_groep is None:
                output_groep = kaart.createGroupLayer("OUTPUT - Geconverteerde lagen")
            for _, _, _, output_naam in conversies:
                output_fc = os.path.join(OUTPUT_GDB, output_naam)
                if output_naam not in [l.name for l in output_groep.listLayers()]:
                    nieuwe_laag = kaart.addDataFromPath(output_fc)
                    kaart.addLayerToGroup(output_groep, nieuwe_laag, "BOTTOM")
                    kaart.removeLayer(nieuwe_laag)
                    print(f"  ✓ Laag toegevoegd: {output_naam}")
                else:
                    print(f"  Laag staat al in kaart: {output_naam}")
            aprx.save()
            print("\nKaart bijgewerkt ✓")
        except Exception as e:
            print(f"\nLagen konden niet worden toegevoegd: {e}")

        # Stap 5: Tijdmeting
        verschil = time.time() - start_tijd
        print(f"\nTotale uitvoertijd: {int(verschil // 60)} minuten en {int(verschil % 60)} seconden")

        # Opnieuw starten?
        print("\n" + "=" * 60)
        if input("Wilt u nog een object converteren? Typ 'ja' of 'nee': ").strip().lower() != "ja":
            doorgaan = False
            print("\nConversie afgerond.")

run()


