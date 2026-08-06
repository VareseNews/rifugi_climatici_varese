# Rifugi climatici in provincia di Varese

Mappa dei luoghi dove ripararsi dal caldo, alimentata dalle segnalazioni dei lettori di VareseNews.
Contiene 18 segnalazioni reali: 11 a Varese e 7 a Saronno.

## Nessun accesso ai tuoi account

Non c'è nessuna app da autorizzare e nessuno script dentro il tuo Drive. Il foglio delle segnalazioni è condiviso con link pubblico, quindi il suo contenuto è leggibile come una qualsiasi pagina web: la geocodifica avviene su GitHub, che scarica quel link e non tocca nient'altro.

L'unica condizione è che il foglio resti condiviso come **"Chiunque abbia il link: visualizzatore"**. Se lo rimetti privato la mappa non si aggiorna più, ma non si rompe: continua a mostrare l'ultimo dato pubblicato.

## Cosa c'è in questa cartella

| File | A cosa serve |
|---|---|
| `index.html` | La mappa. Legge solo `dati/rifugi.json`: non parla con Google. |
| `dati/rifugi.json` | I dati pronti, riscritti ogni ora. |
| `dati/comuni-varese.geojson` | Confini dei 135 comuni (ISTAT via openpolis, 80 KB). |
| `dati/cache-geocoding.json` | Indirizzi già risolti, per non richiederli mai due volte. |
| `scripts/aggiorna.py` | Legge il foglio, geolocalizza, riscrive `rifugi.json`. |
| `.github/workflows/aggiorna.yml` | Fa girare lo script ogni ora su GitHub. |

---

## Pubblicare su GitHub

### 1. Crea il repository

1. Su [github.com](https://github.com), **+** in alto a destra → **New repository**.
2. **Repository name**: `rifugi-climatici-varese`, minuscolo e senza spazi. Finisce nell'indirizzo pubblico.
3. Scegli **Public**: con un repository privato GitHub Pages non funziona sul piano gratuito.
4. Non spuntare nulla in *Initialize this repository*. **Create repository**.

### 2. Carica i file

Clicca **uploading an existing file**, poi trascina dalla cartella `RifugiClimaticiVarese`:

- il file **`index.html`**
- le cartelle **`dati`**, **`scripts`** e **`.github`** — trascina le cartelle intere, non i file sciolti, altrimenti si perdono i percorsi

Se il Finder non ti mostra `.github` perché inizia con un punto, premi <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>.</kbd> per rendere visibili i file nascosti.

In fondo, **Commit changes**. Controlla che nell'elenco compaiano `dati/`, `scripts/` e `.github/` come cartelle.

### 3. Accendi GitHub Pages

**Settings** → menu di sinistra, **Pages** → *Source*: **Deploy from a branch**, ramo **main**, cartella **/ (root)** → **Save**.

Dopo due o tre minuti la mappa è online su `https://TUONOME.github.io/rifugi-climatici-varese/`.

### 4. Dai al robot il permesso di scrivere

Serve perché l'aggiornamento orario possa ripubblicare i dati.

**Settings** → **Actions** → **General** → in fondo, *Workflow permissions*: scegli **Read and write permissions** → **Save**.

### 5. Prova subito l'aggiornamento

Tab **Actions** → nella colonna di sinistra **Aggiorna la mappa** → pulsante **Run workflow** → **Run workflow**.

Dopo un minuto compare una riga verde. Se è rossa, aprila e leggi l'errore: quasi sempre è il permesso del passaggio 4, oppure il foglio non più condiviso.

Da qui in avanti gira da solo ogni ora.

### 6. Metti la mappa nell'articolo

```html
<iframe src="https://TUONOME.github.io/rifugi-climatici-varese/"
        width="100%" height="900" style="border:0" loading="lazy"
        title="Mappa dei rifugi climatici in provincia di Varese"></iframe>
```

L'altezza è fissa perché il contenuto non cresce più con le segnalazioni: 600 px se li prende la mappa, il resto sono testata, filtri e piè di pagina. Se la vuoi più compatta, in `index.html` cerca `#contenitore-mappa` e abbassa i 600 px — ma non sotto i 590, perché lì la provincia non entra più e la mappa scende di un livello di zoom rimpicciolendosi di colpo.

---

## Come si aggiorna

Ogni ora GitHub scarica il foglio, geolocalizza **solo gli indirizzi mai visti** e riscrive `dati/rifugi.json`. Se non è cambiato niente non pubblica nulla. La pagina rilegge il file ogni ora, e anche quando torni sulla scheda del browser dopo più di un'ora.

In pratica: la segnalazione arriva, e nel giro di un'ora è sulla mappa senza che nessuno tocchi niente.

Il geocoder è Nominatim, di OpenStreetMap. Grazie alla cache in `dati/cache-geocoding.json` ogni indirizzo viene chiesto una volta sola: a regime le richieste sono zero, e c'è un tetto di 40 nuovi indirizzi per esecuzione per non fare raffiche.

## Aggiungi la colonna `PUBBLICA` prima di lanciare l'articolo

Adesso non c'è, quindi **ogni riga del foglio finisce online**. Aggiungi una colonna `PUBBLICA` e scrivi `SI` solo nelle righe verificate: da quel momento la mappa mostra soltanto quelle. È l'unica difesa contro una segnalazione sbagliata o in malafede che arrivi mentre nessuno guarda.

## Correggere un punto finito nel posto sbagliato

Aggiungi al foglio due colonne `lat` e `lon` e scrivici le coordinate giuste: **hanno la precedenza su tutto** e non vengono mai sovrascritte. Per farlo, apri Google Maps, clicca col destro sul punto esatto e copia i due numeri.

## Cosa fa lo script con i dati grezzi

I lettori scrivono come capita, e il foglio lo rispecchia. La pulizia avviene prima della pubblicazione, senza toccare il foglio:

- `varese` → **Varese**, riportato al nome ISTAT ufficiale. Senza questo il confine del comune non si accenderebbe.
- `pagamento` e `a pagamento` → **A pagamento**, altrimenti sarebbero due categorie diverse nel filtro.
- `giardini estensi` → **Giardini estensi**, solo la prima lettera. Volutamente non "Giardini Estensi": su nomi come "villa Mylius" un maiuscolo automatico farebbe danni.

Le colonne vengono riconosciute dal testo per esteso delle domande (`Nome del luogo da segnalare`, `È naturale o climatizzato?`…): se rinomini una domanda continua a funzionare, purché il senso resti riconoscibile.

## Cosa manca al form, se vuoi migliorarlo

- **Comune come menu a tendina** invece che a testo libero. È la modifica più utile: oggi arriva `varese` minuscolo, domani può arrivare `Busto A.` che nessun geocoder trova. L'elenco dei 135 comuni si ricava da `dati/comuni-varese.geojson`.
- **Orari di apertura**: manca del tutto, ed è ciò che serve di più a chi cerca riparo alle tre del pomeriggio. Il popup ha già lo spazio pronto.
- **Link Google Maps del luogo**, facoltativo: chi lo compila dà la posizione esatta e salta la geocodifica. Lo script lo riconosce già, inclusi i link brevi `maps.app.goo.gl`.
- La domanda *"È un luogo pubblico o privato?"* ha 18 risposte su 18 uguali: come filtro non serve, l'ho lasciata solo nel popup.

## Costi

Zero. Google Form e Sheet, GitHub Pages, GitHub Actions (gratuito e illimitato sui repository pubblici), Leaflet, Nominatim e i confini ISTAT non costano niente e non richiedono carta di credito.

L'unica voce che può diventare a pagamento sono le **tessere cartografiche**, le immagini di sfondo della mappa. Lo sfondo attuale (CARTO) è gratuito per qualche migliaio di visite al mese. Se un articolo va molto forte e la mappa rallenta o mostra riquadri grigi, si passa a un piano da circa 20-30 € al mese: in `index.html` cerca `TILE_URL` e sostituisci la riga con quella del nuovo fornitore, per esempio MapTiler. È una modifica di trenta secondi.
