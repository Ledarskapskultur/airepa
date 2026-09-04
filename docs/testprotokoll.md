# Steg 8 – Testprotokoll

Tio testsamtal att köra själv i webbläsaren på `PUBLIC_BASE_URL`. Kryssa i,
notera avvikelser. Kör om hela listan efter varje ändring i prompten, och en
gång till per telefon när fas 2 är på plats.

Innan du börjar: ha Google Kalender och din mobil framme.

| # | Test | Så här gör du | Godkänt när |
|---|---|---|---|
| 1 | **Boka tid, allt rätt** | "Jag vill boka en tid." Välj en av tiderna, uppge namn och nummer, säg vad det gäller. | Tre tider läses upp en i taget. Bokningen syns i kalendern på rätt tid. SMS till dig **och** till uppringaren inom 10 sek. Rad i `bokningar`. |
| 2 | **Ångra, ta meddelande i stället** | Börja boka, säg sedan "nej förresten, kan du bara framföra ett meddelande?" | Byter spår utan krångel. Ingen kalenderhändelse skapas. Rad i `meddelanden`. |
| 3 | **Fråga om pris** | "Vad kostar en UGL-vecka?" | Svarar *inte* på frågan. Hänvisar till bokat samtal. |
| 4 | **Fråga om kursdatum** | "När går nästa kurs?" | Hänvisar till bokat samtal. Hittar inte på datum. |
| 5 | **Brådskande meddelande** | Lämna meddelande, säg att det är akut. | SMS till dig börjar med `BRÅDSKANDE:`. `bradskande = true` i databasen. Säger "återkommer samma dag". |
| 6 | **Fel nummer** | "Är det här bilverkstan?" | Tackar vänligt och avslutar. Ingen bokning, inget meddelande. |
| 7 | **Otydligt telefonnummer** | Säg ett nummer fel, avbryt när det upprepas: "nej, det ska vara 4 på slutet." | Läser upp numret siffra för siffra, rättar sig, bekräftar innan bokning. Rätt nummer i SMS:et. |
| 8 | **Vill prata med människa** | "Jag vill prata med Carl-Fredrik direkt." | Säger att han inte kan nås nu, erbjuder bokning eller meddelande. Lovar inte att koppla. |
| 9 | **Lång tystnad** | Svara inte på en fråga på 30 sekunder. | Avslutar samtalet efter ca 20 sekunders tystnad, utan att bli konstig. |
| 10 | **Avbryta mitt i mening** | Prata rakt in i assistentens replik. | Slutar prata direkt och lyssnar. Ingen dubbelprat. |

## Kolla efteråt

```
[ ] Alla tio samtal finns i tabellen `samtal` med transkript och sammanfattning
[ ] Utfallen stämmer ('bokning', 'meddelande', 'avbrutet')
[ ] Inga dubbelbokningar i kalendern
[ ] Alla bokade tider ligger på vardagar 08–17, svensk tid
[ ] Inget ljud finns sparat någonstans, bara text
```

## Anteckningar per körning

| Datum | Test som föll | Vad hände | Åtgärd |
|---|---|---|---|
| | | | |
