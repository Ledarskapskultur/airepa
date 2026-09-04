"""Ren logik för att räkna ut lediga tider. Inga API-anrop här."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.preferences import matchar_onskemal
from app.swedish import tid_text


@dataclass(frozen=True)
class Slot:
    start: datetime  # tidszonsmedveten, Europe/Stockholm

    @property
    def id(self) -> str:
        return self.start.strftime("%Y-%m-%dT%H:%M")

    @property
    def text(self) -> str:
        return tid_text(self.start)

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text}


@dataclass(frozen=True)
class Busy:
    """En upptagen period i kalendern."""

    start: datetime
    end: datetime


def nasta_arbetsdag(fran: date) -> date:
    """Första vardagen efter `fran`."""
    d = fran + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def kandidattider(
    dag: date,
    tz,
    *,
    start_hour: int,
    end_hour: int,
    meeting_minutes: int,
) -> list[datetime]:
    """Alla möjliga starttider en given dag, var 30:e minut."""
    if dag.weekday() >= 5:
        return []
    tider: list[datetime] = []
    t = datetime(dag.year, dag.month, dag.day, start_hour, 0, tzinfo=tz)
    slut = datetime(dag.year, dag.month, dag.day, end_hour, 0, tzinfo=tz)
    while t + timedelta(minutes=meeting_minutes) <= slut:
        tider.append(t)
        t += timedelta(minutes=30)
    return tider


def ar_ledig(
    start: datetime,
    upptaget: list[Busy],
    *,
    meeting_minutes: int,
    buffer_minutes: int,
) -> bool:
    """Ledig om inget möte krockar med tiden plus buffert före och efter."""
    fran = start - timedelta(minutes=buffer_minutes)
    till = start + timedelta(minutes=meeting_minutes + buffer_minutes)
    return not any(b.start < till and b.end > fran for b in upptaget)


def berakna_lediga_tider(
    nu: datetime,
    upptaget: list[Busy],
    blockerade_dagar: set[date],
    *,
    tz,
    onskad_period: str = "",
    start_hour: int = 8,
    end_hour: int = 17,
    meeting_minutes: int = 30,
    buffer_minutes: int = 15,
    max_days_ahead: int = 14,
    max_slots: int = 3,
    max_per_dag: int = 2,
) -> list[Slot]:
    """Upp till `max_slots` lediga tider, tidigast nästa arbetsdag.

    Önskemål filtrerar i första hand. Räcker inte de matchande tiderna fylls
    listan på med de tidigaste övriga, så att uppringaren alltid får förslag.
    """
    forsta = nasta_arbetsdag(nu.date())
    sista = nu.date() + timedelta(days=max_days_ahead)

    lediga: list[Slot] = []
    dag = forsta
    while dag <= sista:
        if dag not in blockerade_dagar:
            for start in kandidattider(
                dag, tz, start_hour=start_hour, end_hour=end_hour,
                meeting_minutes=meeting_minutes,
            ):
                if ar_ledig(
                    start, upptaget,
                    meeting_minutes=meeting_minutes, buffer_minutes=buffer_minutes,
                ):
                    lediga.append(Slot(start))
        dag += timedelta(days=1)

    onskade = [s for s in lediga if matchar_onskemal(s.start, onskad_period, nu.date())]
    ovriga = [s for s in lediga if s not in onskade]

    # Sprid ut förslagen över flera dagar när det går, men aldrig på bekostnad
    # av önskemålet: hellre tre tider samma dag än en tid som inte passar.
    valda = _valj(onskade, [], max_slots, max_per_dag)
    valda = _valj(onskade, valda, max_slots, max_per_dag=max_slots)
    valda = _valj(ovriga, valda, max_slots, max_per_dag)
    valda = _valj(ovriga, valda, max_slots, max_per_dag=max_slots)

    return sorted(valda, key=lambda s: s.start)[:max_slots]


def _valj(kalla: list[Slot], valda: list[Slot], max_slots: int, max_per_dag: int) -> list[Slot]:
    """Fyller på `valda` från `kalla` utan att bryta mot spridningsregeln."""
    valda = list(valda)
    per_dag: dict[date, int] = {}
    for slot in valda:
        d = slot.start.date()
        per_dag[d] = per_dag.get(d, 0) + 1
    for slot in kalla:
        if len(valda) >= max_slots:
            break
        d = slot.start.date()
        if slot in valda or per_dag.get(d, 0) >= max_per_dag:
            continue
        valda.append(slot)
        per_dag[d] = per_dag.get(d, 0) + 1
    return valda
