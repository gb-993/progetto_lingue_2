# RIEPILOGO MODIFICHE

- [ ] Roberto Romano per indirizzo tecnico per macchina virtuale
- [ ] Servizi informatici per casella noreply

## GENERALI
- [x] Verificare che "instructions" sia sempre al plurale
- [ ] Rendere cliccabili i link nel menù (link circolari)
- [ ] Aggiornare i nomi delle pagine (Graph -> Parameter networks, Submissions -> Saved languages, Queries -> Filters)
- [ ] Aggiornare ordine nel menù User: Dashboard > Languages > Instructions > Glossary > My account
- [ ] Aggiornare ordine nel menù Admin: Dashboard > Languages > Parameters > Parameter networks > Table A > Saved languages > Filters > Instructions > Glossary > My account > Accounts

## HOMEPAGE
- [ ] Creare la homepage sul modello di [ASJP](https://asjp.clld.org)
- [ ] Pulsante di Login e poi messaggio di benvenuto personalizzato
- [ ] Predisporre qualche riga per spiegare a cosa serve il sito
- [ ] Predisporre modello di citazione
- [ ] Contatti a cui scrivere per proporre una collaborazione
- [ ] Link cliccabili per privacy e per termini di utilizzo da accettare al primo accesso
- [ ] Info lingue e famiglie (si possono aggiornare automaticamente?)
- [ ] Link al sito di [PCM](http://www.parametricomparison.unimore.it/site/home.html)

## LISTA LINGUE
- [ ] Togliere l'attributo position (non serve più)
- [ ] Inserire due nuovi attributi: Latitude e Longitude (da definire già quando si crea la lingua)

## LINGUE DATA
- [ ] A volte il Number degli esempi non aumenta progressivamente (a volte rimane uguale, a volte salta dei numeri)
- [ ] A volte il numero dell'esempio è cancellato nella cella di Example text (anche se è del tipo 1.1). A questo punto conviene che lo script non cerchi di associare l'esempio a un numero ma lo copi direttamente così com'è
- [ ] Aggiungere Save e Next visibili a destra durante lo scorrimento
- [ ] Problema della duplicazione delle stop-questions con label Qs
- [ ] Ristrutturazione dei pulsanti in alto

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
