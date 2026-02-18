# RIEPILOGO MODIFICHE

- [ ] Roberto Romano per indirizzo tecnico per macchina virtuale
- [ ] Servizi informatici per casella noreply

## GENERALI
- [ ] "Instructions" al plurale in edit question
- [x] Rendere cliccabili i link nel menù (link circolari)
- [x] Aggiornare i nomi delle pagine (Graph -> Parameter networks, Submissions -> Saved languages, Queries -> Filters)
- [x] Aggiornare ordine nel menù User: Dashboard > Languages > Instructions > Glossary > My account
- [x] Aggiornare ordine nel menù Admin: Dashboard > Languages > Parameters > Parameter networks > Table A > Saved languages > Filters > Instructions > Glossary > My account > Accounts
- [x] Rendere cliccabile il breadcrumb

## HOMEPAGE
- [x] Creare la homepage sul modello di [ASJP](https://asjp.clld.org)
- [x] Pulsante di Login e poi messaggio di benvenuto personalizzato
- [x] Predisporre qualche riga per spiegare a cosa serve il sito
- [x] Predisporre modello di citazione 
- [x] Contatti a cui scrivere per proporre una collaborazione
- [x] Link cliccabili per privacy e per termini di utilizzo da accettare al primo accesso (in registrazione per public account)
- [x] Info lingue e famiglie (si possono aggiornare automaticamente?)
- [x] Link al sito di [PCM](http://www.parametricomparison.unimore.it/site/home.html)

## QUESTIONS
- [x] Nuova pagina "Questions" simile a "Parameters" con pulsante Search una tabella: label | testo della  question | pulsante Edit (porta alla pagina del parametro)
- [x] Lista delle questions con lo stesso ordine dei parametri

## LISTA LINGUE
- [ ] Togliere l'attributo position (non serve più)
- [ ] Inserire due nuovi attributi: Latitude e Longitude (da definire già quando si crea la lingua) ?? obbligatori o no ??
- [x] Errori "parlanti" al caricamento di un file(?) 
- [x] Equiparare Qs a QS nello script(?)
- [x] Fare in modo che se nel file excel ci sono ID delle questions che non si trovano nel database, i dati di quelle questions non vengano copiati
- [x] **RISOLTO**: Verificare che il caricamento di un foglio di una lingua sovrascriva i dati precedentemente caricati per quella lingua
  - **Problema**: Il secondo upload non eliminava le risposte vecchie, causando inconsistenze
  - **Soluzione**: Implementato "replace all" - tutti i dati vengono eliminati e ricreati da zero

## LINGUE DATA
- [x] A volte il Number degli esempi non aumenta progressivamente (a volte rimane uguale, a volte salta dei numeri)
- [x] A volte il numero dell'esempio è cancellato nella cella di Example text (anche se è del tipo 1.1). A questo punto conviene che lo script non cerchi di associare l'esempio a un numero ma lo copi direttamente così com'è
- [x] Aggiungere Save e Next visibili a destra durante lo scorrimento
- [x] Problema della duplicazione delle stop-questions con label Qs
- [x] Ristrutturazione dei pulsanti  

## DEBUG PARAMETRI
- [!!] Poter modificare manualmente il valore di un parametro nel final value, segnalando che è stata fatta una modifica 

## GLOSSARIO
- [x] Caricare voci

## DEBUG
- [ ] Warning in caso di risposte non date

## PARAMETERS EDIT
- [x] Inserire un nuovo attributo Level of comparison con i due valori mutualmente esclusivi Canonico e Deuterocanonico
- [ ] Inserire due altre celle di testo libero una sotto l'altra intitolate "Long description" e "Explication of the implicational condition(s)"
- [ ] Inserire un bottone di download alla fine della pagina di edit del parametro per scaricare un pdf con tutte le informazioni di un parametro e delle sue questions

## TABLE A
- [x] Poter cliccare sul valore di un parametro o su YES/NO di una question e visualizzare le questions e gli esempi che hanno permesso di fissare quel parametro/risposta (solo se si riesce) 
- [x] Poter selezionare le lingue anche per Family e per Group, oltre che per Top-level family, e i parametri per Level of Comparison
- [x] Poter selezionare singole lingue (oltre che con i filtri) e singoli parametri, tipo con checkbox vicino a ogni lingua/parametro per il download delle distanze e dei dendrogrammi
- [x] Far scaricare solo distanze Hamming e Jaccard[+] (eliminare le altre quattro)
- [x] Scaricare dendrogramma UPGMA adattando dendrogram.py (magari con lo stesso pulsante delle distanze: Export distances and dendrograms)
- [ ] Scaricare una PCA 
- [ ] Scaricare una mappa 

## FILTERS
- [x] Inserire l'ordine alfabetico per la ricerca delle lingue anziché quello basato su position
- [x] Nuovi filtri: "Questions with answer YES (per language)" e "Questions with answer NO (per language)"
- [x] Quando ci sono i parametri tra i risultati poter cliccare sul label ed essere reindirizzato alla pagina di Edit del paramentro
- [x] Quando ci sono le questions per lingua poter cliccare sul label ed essere reindirizzato alla question all'interno di Lingua data
