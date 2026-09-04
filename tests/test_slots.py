from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.slots import Busy, berakna_lediga_tider, kandidattider, nasta_arbetsdag

TZ = ZoneInfo("Europe/Stockholm")


def dt(dag: int, timme: int, minut: int = 0, manad: int = 9) -> datetime:
    return datetime(2026, manad, dag, timme, minut, tzinfo=TZ)


def lediga(nu, upptaget=None, blockerade=None, **kw):
    return berakna_lediga_tider(
        nu, upptaget or [], blockerade or set(), tz=TZ, **kw
    )


# -- nästa arbetsdag --------------------------------------------------------

def test_fredag_ger_mandag():
    # 2026-09-04 är en fredag.
    assert nasta_arbetsdag(date(2026, 9, 4)) == date(2026, 9, 7)


def test_vanlig_dag_ger_nasta_dag():
    assert nasta_arbetsdag(date(2026, 9, 7)) == date(2026, 9, 8)


# -- kandidattider ----------------------------------------------------------

def test_kandidater_ligger_inom_arbetsdagen():
    tider = kandidattider(
        date(2026, 9, 8), TZ, start_hour=8, end_hour=17, meeting_minutes=30
    )
    assert tider[0].hour == 8 and tider[0].minute == 0
    # Sista mötet börjar 16:30 så att det slutar 17:00.
    assert tider[-1].hour == 16 and tider[-1].minute == 30
    assert len(tider) == 18


def test_helg_ger_inga_kandidater():
    assert kandidattider(
        date(2026, 9, 5), TZ, start_hour=8, end_hour=17, meeting_minutes=30
    ) == []


# -- lediga tider -----------------------------------------------------------

def test_tom_kalender_ger_tre_tider_fran_nasta_arbetsdag():
    tider = lediga(dt(4, 12))
    assert len(tider) == 3
    assert tider[0].id == "2026-09-07T08:00"
    # Högst två per dag, så tredje tiden hamnar på nästa dag.
    assert tider[2].start.date() == date(2026, 9, 8)


def test_ingen_tid_samma_dag():
    tider = lediga(dt(7, 8))
    assert all(t.start.date() > date(2026, 9, 7) for t in tider)


def test_mote_blockerar_med_buffert_fore_och_efter():
    # Möte 09:00–10:00 blockerar 08:30 (slutar 09:00, ingen buffert) och 10:00.
    upptaget = [Busy(dt(7, 9), dt(7, 10))]
    ider = {t.id for t in lediga(dt(4, 12), upptaget, max_slots=20, max_per_dag=20)}
    assert "2026-09-07T08:00" in ider
    assert "2026-09-07T08:30" not in ider
    assert "2026-09-07T09:00" not in ider
    assert "2026-09-07T10:00" not in ider
    assert "2026-09-07T10:30" in ider


def test_heldagshandelse_blockerar_hela_dagen():
    tider = lediga(dt(4, 12), blockerade={date(2026, 9, 7)})
    assert all(t.start.date() != date(2026, 9, 7) for t in tider)
    assert tider[0].start.date() == date(2026, 9, 8)


def test_langst_fjorton_dagar_fram():
    # Allt blockerat utom en dag långt fram i tiden.
    blockerade = {date(2026, 9, 4) + timedelta(days=i) for i in range(1, 40)}
    assert lediga(dt(4, 12), blockerade=blockerade) == []


def test_helger_hoppas_over():
    tider = lediga(
        dt(4, 12),
        blockerade={date(2026, 9, 7)},
        max_slots=20,
        max_per_dag=20,
    )
    assert all(t.start.weekday() < 5 for t in tider)


def test_id_och_text_foljer_kravspecen():
    tid = lediga(dt(4, 12))[0]
    assert tid.id == "2026-09-07T08:00"
    assert tid.text == "måndag 7 september klockan 8"
    assert tid.as_dict() == {"id": tid.id, "text": tid.text}


# -- önskemål ---------------------------------------------------------------

def test_onskemal_eftermiddag():
    tider = lediga(dt(4, 12), onskad_period="helst på eftermiddagen")
    assert all(t.start.hour >= 12 for t in tider)


def test_onskemal_formiddag():
    tider = lediga(dt(4, 12), onskad_period="på förmiddagen tack")
    assert all(t.start.hour < 12 for t in tider)


def test_onskemal_nasta_vecka():
    # Fredag 4 sept är vecka 36, så nästa vecka är 7–13 september.
    tider = lediga(dt(4, 12), onskad_period="gärna i nästa vecka")
    assert tider
    assert all(date(2026, 9, 7) <= t.start.date() <= date(2026, 9, 13) for t in tider)


def test_onskemal_nasta_vecka_mitt_i_veckan():
    # Måndag 7 sept är vecka 37, så nästa vecka är 14–20 september.
    tider = lediga(dt(7, 12), onskad_period="nästa vecka funkar bäst")
    assert tider
    assert all(date(2026, 9, 14) <= t.start.date() <= date(2026, 9, 20) for t in tider)


def test_onskemal_imorgon():
    tider = lediga(dt(7, 12), onskad_period="imorgon om det går")
    assert all(t.start.date() == date(2026, 9, 8) for t in tider)


def test_onskemal_veckodag():
    tider = lediga(dt(4, 12), onskad_period="passar det på en onsdag?")
    assert all(t.start.weekday() == 2 for t in tider)


def test_omojligt_onskemal_ger_andra_tider_anda():
    # Ingen tid kan vara både förmiddag och eftermiddag – vi svarar ändå.
    tider = lediga(dt(4, 12), onskad_period="förmiddag eller egentligen eftermiddag")
    assert len(tider) == 3


def test_tomt_onskemal_ger_tidigaste_tiderna():
    assert lediga(dt(4, 12), onskad_period="")[0].id == "2026-09-07T08:00"


def test_sa_snart_som_mojligt_filtrerar_inte_bort_allt():
    tider = lediga(dt(4, 12), onskad_period="så snart som möjligt")
    assert len(tider) == 3
    assert tider[0].id == "2026-09-07T08:00"
