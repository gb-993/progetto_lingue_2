# RIEPILOGO MODIFICHE

- [ ] Roberto Romano per indirizzo tecnico per macchina virtuale
- [ ] Servizi informatici per casella noreply

## GENERALI
- [x] Verificare che "instructions" sia sempre al plurale
- [ ] Rendere cliccabili i link nel menù (link circolari)
- [ ] Aggiornare i nomi delle pagine (Graph -> Parameter networks, Submissions -> Saved languages, Queries -> Filters)
- [ ] Aggiornare ordine nel menù User: Dashboard > Languages > Instructions > Glossary > My account
- [ ] Aggiornare ordine nel menù Admin: Dashboard > Languages > Parameters > Parameter networks > Table A > Saved languages > Filters > Instructions > Glossary > My account > Accounts
- [ ] Rendere cliccabile il breadcrumb

## HOMEPAGE
- [ ] Creare la homepage sul modello di [ASJP](https://asjp.clld.org)
- [ ] Pulsante di Login e poi messaggio di benvenuto personalizzato
- [ ] Predisporre qualche riga per spiegare a cosa serve il sito
- [ ] Predisporre modello di citazione
- [ ] Contatti a cui scrivere per proporre una collaborazione
- [ ] Link cliccabili per privacy e per termini di utilizzo da accettare al primo accesso
- [ ] Info lingue e famiglie (si possono aggiornare automaticamente?)
- [ ] Link al sito di [PCM](http://www.parametricomparison.unimore.it/site/home.html)

## QUESTIONS
- [ ] Nuova pagina "Questions" simile a "Parameters" con pulsante Search una tabella: label | testo della  question | pulsante Edit (porta alla pagina del parametro)
- [ ] Lista delle questions con lo stesso ordine dei parametri

## LISTA LINGUE
- [ ] Togliere l'attributo position (non serve più)
- [ ] Inserire due nuovi attributi: Latitude e Longitude (da definire già quando si crea la lingua)
- [ ] Errori "parlanti" al caricamento di un file(?)
- [ ] Equiparare Qs a QS nello script(?)
- [ ] Fare in modo che se nel file excel ci sono ID delle questions che non si trovano nel database, i dati di quelle questions non vengano copiati
- [ ] Verificare che il caricamento di un foglio di una lingua sovrascriva i dati precedentemente caricati per quella lingua

## LINGUE DATA
- [ ] A volte il Number degli esempi non aumenta progressivamente (a volte rimane uguale, a volte salta dei numeri)
- [ ] A volte il numero dell'esempio è cancellato nella cella di Example text (anche se è del tipo 1.1). A questo punto conviene che lo script non cerchi di associare l'esempio a un numero ma lo copi direttamente così com'è
- [ ] Aggiungere Save e Next visibili a destra durante lo scorrimento
- [ ] Problema della duplicazione delle stop-questions con label Qs
- [ ] Ristrutturazione dei pulsanti in alto

## DEBUG PARAMETRI
- [ ] Poter modificare manualmente il valore di un parametro nel final value, segnalando che è stata fatta una modifica

## GLOSSARIO
- [ ] Caricare voci

## DEBUG
- [ ] Warning in caso di risposte non date

## PARAMETERS
- [ ] Inserire un nuovo attributo Level of comparison con i due valori mutualmente esclusivi Canonico e Deuterocanonico

## TABLE A
- [ ] Togliere dallo script che genera le distanze quelle che trasformano gli 0 in -
- [ ] Poter cliccare sul valore di un parametro o su YES/NO di una question e visualizzare le questions e gli esempi che hanno permesso di fissare quel parametro/risposta (solo se si riesce)
- [ ] Poter selezionare le lingue anche per Family e per Group, oltre che per Top-level family, e i parametri per Level of Comparison
- [ ] Poter selezionare singole lingue (oltre che con i filtri) e singoli parametri, tipo con checkbox vicino a ogni lingua/parametro per il download delle distanze e dei dendrogrammi
- [ ] Far scaricare solo distanze Hamming e Jaccard[+] (eliminare le altre quattro)
- [ ] Scaricare dendrogramma UPGMA adattando dendrogram.py (magari con lo stesso pulsante delle distanze: Export distances and dendrograms)

## FILTERS
- [ ] Inserire l'ordine alfabetico per la ricerca delle lingue anziché quello basato su position
- [ ] Nuovi filtri: "Questions with answer YES (per language)" e "Questions with answer NO (per language)"
- [ ] Quando ci sono i parametri tra i risultati poter cliccare sul label ed essere reindirizzato alla pagina di Edit del paramentro
- [ ] Quando ci sono le questions per lingua poter cliccare sul label ed essere reindirizzato alla question all'interno di Lingua data
