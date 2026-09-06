# UGL-landningssidan

Ligger i `web/ugl/index.html`, en enda självbärande fil (ingen byggkedja, inga beroenden
utöver Google Fonts). Serveras av samma FastAPI-app som assistenten, på `/ugl/`.

```bash
uv run uvicorn app.main:app --reload   # → http://localhost:8000/ugl/
```

Ska den ligga på ledarskapskultur.se i stället: kopiera filen rakt av. Enda sak att
ändra är knappen "Boka ett samtal", som pekar på `/` (assistenten på den här servern).

## Fyll i innan publicering

Sök på `FYLL I` i filen. Det gäller:

| Var | Vad |
|---|---|
| Hero, nedre raden | Nästa kursstart |
| Sektion 06, Röster | Två platshållarcitat, byt mot riktiga och godkända |
| Sektion 07, Datum | Datum, ort, platsstatus och pris (`00 000 kr`) |
| Sektion 09 + sidfot | Mejladress |
| JSON-LD längst ned | Samma datum, ort och pris som i tabellen |

Platshållarcitaten är skrivna som exempel på tonläge, inte som riktiga omdömen. De måste
bytas ut innan sidan går live.

## Färg och form

Sidan använder den femfärgspalett som togs fram för sidan:

| Hex | Roll |
|---|---|
| `#123D35` | Mörk yta: hero, avslut, sidfot |
| `#F4F0E7` | Sidans bakgrund |
| `#B89A62` | Mässing. Accent: knapp, hero-cirkel, linjer |
| `#9AAA96` | Salvia. Lugn accent och sektionsbakgrund |
| `#252A28` | Brödtext, och text på mässingsknappen |

Tre toner är härledda ur paletten, av kontrastskäl: mässing mot papper ger bara 2,4:1 och
salvia 2,2:1, vilket är för svagt för brödtext och etiketter (kravet är 4,5:1). Därför
finns `--massing-mork #7A6130` för länkar och handling på ljus botten (5,2:1),
`--massing-ljus #CDB584` för liten text på mörk botten (6,0:1) och
`--salvia-mork #5E6B5A` för etiketter på papper (5,0:1). Grundfärgerna används
oförändrade på ytor och i stora element.

Rollfördelning: mässing är alltid handling eller accent, salvia alltid lugn och
navigering, petrol alltid avsändare och mörk yta. Max en knappfärg per vy, mässing på
mörk botten, textlänkar i mörk mässing på ljus botten.

Observera att paletten avviker från hex-koderna i varumärkesguiden (petrol `#013E37`,
guld `#FFEFB3`, ockra `#B9843C`, salvia `#6E7F5C`, papper `#FDF9F0`). Ska sidan och
guiden gå ihop behöver en av dem uppdateras.

Typografin följer guiden: Lora i rubriker, Poppins versaler i etiketter och knappar,
Inter som brödtext (webbersättning för Carlito). Sessionstemat
`SAMSPEL → INSIKT → LEDARSKAP` sitter under kickern i hero, enligt regeln om tre ord från
konkret handling till abstrakt resultat.

Ingen ikon på sidan, enligt regeln om att `L`-märket inte läggs på försättsblad som
standard. Inga foton, eftersom varje foto måste duotone-behandlas först. Vill du ha ett
porträtt eller kursmiljöbild senare är hero-cirkeln platsen: lägg bilden i cirkeln,
gråskala plus petrol via `mix-blend-mode: color`.

## Det tekniska

- Strukturerad data för `Course` och `FAQPage`, så att både Google och AI-sökningar kan
  beskriva kursen rätt. Måste uppdateras när datum och pris ändras.
- Rörelse: enbart en diskret intoning vid scroll, avstängd helt vid
  `prefers-reduced-motion`, med en tidsutlöst reserv som visar allt efter fyra sekunder
  om observern skulle strula.
- Tillgänglighet: hoppa-till-innehållet-länk, synlig fokusmarkering, frågorna är
  `<details>` (fungerar utan JavaScript), brödtext 17 till 18px, all text över 4,5:1.
- Fast CTA-list i mobil som glider in först när hero passerats.
- Inga bilder, inga ramverk. Sidan väger under 40 kB plus typsnitten.
