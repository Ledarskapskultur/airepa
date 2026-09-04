from datetime import datetime

from app.swedish import datum_text, klockslag_text, normalisera_telefon, tid_text


def test_hela_timmar_sags_med_siffra():
    assert klockslag_text(datetime(2026, 9, 8, 10, 0)) == "klockan 10"
    assert klockslag_text(datetime(2026, 9, 9, 9, 0)) == "klockan 9"
    assert klockslag_text(datetime(2026, 9, 9, 13, 0)) == "klockan 1"


def test_halvtimmar_sags_som_halv_nasta_timme():
    assert klockslag_text(datetime(2026, 9, 8, 14, 30)) == "klockan halv tre"
    assert klockslag_text(datetime(2026, 9, 8, 8, 30)) == "klockan halv nio"
    assert klockslag_text(datetime(2026, 9, 8, 11, 30)) == "klockan halv tolv"


def test_kvartar():
    assert klockslag_text(datetime(2026, 9, 8, 9, 15)) == "klockan kvart över nio"
    assert klockslag_text(datetime(2026, 9, 8, 9, 45)) == "klockan kvart i tio"


def test_datum_pa_svenska():
    assert datum_text(datetime(2026, 9, 8)) == "tisdag 8 september"
    assert datum_text(datetime(2026, 1, 5)) == "måndag 5 januari"


def test_hela_tiden_ihop():
    assert tid_text(datetime(2026, 9, 8, 14, 30)) == "tisdag 8 september klockan halv tre"


def test_telefonnummer_blir_plus46():
    assert normalisera_telefon("070-123 45 67") == "+46701234567"
    assert normalisera_telefon("0701234567") == "+46701234567"
    assert normalisera_telefon("+46 70 123 45 67") == "+46701234567"
    assert normalisera_telefon("0046701234567") == "+46701234567"
    assert normalisera_telefon("46701234567") == "+46701234567"
    assert normalisera_telefon("") == ""
