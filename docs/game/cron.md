# Cron Job - Periodické úlohy ve ForrestHubu (experimentální)

Ve ForrestHubu můžete vytvářet cron joby, což jsou skripty, které se spouštějí automaticky v pravidelných intervalech. Tyto úlohy jsou užitečné pro úkoly, které je třeba provádět opakovaně, jako kontrola skóre, globální zvyšování herní obtížnosti, či odesílání pravidelných oznámení hráčům.

## Jak fungují cron joby
Cron joby jsou umístěny v souboru `cron.<interval-seconds>.js` ve složce vaší hry (např. `games/<your-game>/cron.30.js`). Tento skript se spouští každých `N` sekund a může obsahovat jakýkoli JavaScriptový kód (bez async + await), který potřebujete pro správu vaší hry. Měla by být dostupné ořezané API prostředí ForrestHubu, což znamená, že můžete přistupovat k databázím, uživatelským datům a dalším funkcím platformy.
Ve složce vaší hry můžete mít více cron jobů s různými intervaly, například `cron.10.js` pro úlohy spouštěné každých 10 sekund a `cron.60.js` pro úlohy spouštěné každou minutu. Ale také například `cron.300.js` pro úlohy spouštěné každých 5 minut. Kratší intervaly než 1 sekundu nejsou podporovány a pravděpodobně by ani nebylo možné je spolehlivě dodržet. Vykonávání cron jobů může být ovlivněno zatížením serveru a dalšími faktory, takže není zaručeno, že se úloha spustí přesně v daném intervalu, ale vždy se spustí a vykoná celý skript. Cron job je aktivní pouze tehdy, pokud běží hra. Během pozastavení hry se cron joby nespouštějí.

## Příklad cron jobu
Zde je jednoduchý příklad cron jobu, který se spouští každých 12 sekund a zvyšuje hodnotu proměnné


`cron.12.js`:
```js
const forrestHubLib = ForrestHubLib.getInstance();
let proj = ENV.FH_GAME_NAME || "global";

// increment a counter
let ticks = forrestHubLib.dbVarGetKey("ticks", proj) || 0;
forrestHubLib.dbVarSetKey("ticks", ticks + 1, proj);

// add a chat message
forrestHubLib.dbArrayAddRecord("chatMessages", { text: `tick #${ticks + 1}`, time: new Date().toISOString() }, proj);
```

Pokud narazíte na problém s cron joby, prosíme o nahlášení chyby na [GitHub Issues](https://github.com/Helceletka/ForrestHub/issues).