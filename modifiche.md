# RIEPILOGO MODIFICHE

- [ ] Roberto Romano per problemi con mail e password
- [x] Richiedere di accettare di nuovo le condizioni sull'utilizzo se modifichiamo il file

## GENERALI


## LANDING PAGE
- [x] Togliere "www.parametricomparison.unimore.it" da in alto a sx

## HOW TO CITE
- [x] Togliere il box Outputs

## PUBLIC
(ancora non so esattamente cosa sarà visualizzabile per questi utenti)

## QUESTIONS
- [ ] Se modifico una question  poi non chiede di specificare quale è stato il cambiamento per salvare

## LISTA LINGUE
- [x] Inserire la mappa "interattiva" che c'è nella homepage anche in alto in questa pagina

- [x] Inserire gli stessi "Language filters" che ci sono nella pagina della Table A anche qui in alto e poterli selezionare per visualizzare solo subset di lingue

- [x] Bottone per scaricare una mappa "statica" png a partire dalle coordinate geografiche (idealmente sono stati applicati dei filtri per la visualizzazione della lista delle lingue, la mappa dovrebbe mostrare solo quelle lingue). Va bene che le località siano indicate con colori diversi a seconda della top-level family

- [ ] Bottone per scaricare le distanze geografiche GCD (come per la mappa, se sono selezionati dei filtri dovrebbe scaricare solo le distanze delle località per cui sono state selezionate le lingue). Ti metto il file gcd.py (metto anche coord.txt solo per mostrarti come vuole formattati i dati, poi si può eliminare)

- [ ] Scaricare mappa Lorenzo e Federico (ne riparliamo prossimamente con loro)

## LINGUE DATA

## DEBUG PARAMETRI

## GLOSSARIO

## DEBUG

## LISTA PARAMETRI
- [x] Inserire gli stessi "Parameter filters" che ci sono nella pagina della Table A anche qui in alto e poterli selezionare per visualizzare solo subset di parametri

## PARAMETERS EDIT
- [x] Fare in modo che se si scrive testo nel Brief summary of changes e poi si cambia pagina (es. per modificare le implicazioni di un parametro e poter disattivarne un altro), il testo precedentemente scritto rimanga e non si cancelli. 
Similmente, se modifico altri campi (es. modifico la Short description) questa dovrebbe "salvarsi" se cambio pagina, pur mantenendo il salvataggio globale del parametro con il sistema che c'è adesso

- [ ] Per salvare una question mantenere il bottone che c'è adesso ma chiamarlo "Save the changes and maintain data" e aggiungere un altro bottone "Save the changes and delete the linked data (the old data will still be accessible in ...)". 
L'idea è che la modifica al testo di una question potrebbe:
    1. comunque essere coerente con i vecchi esempi raccolti oppure 
    2. far sì che i vecchi dati non vadano più bene con il nuovo testo della question. 
        -> Nel caso 2. i dati di tutte le lingue relativi a quella question dovrebbero essere rimossi ma non eliminati, ci vorrebbe una pagina che li conservasse, magari con anche la possibilità di scaricarli come xlsx. Tipo una pagina simile a "Questions" con la lista delle questions obsolete e la possibilità di scaricare i vecchi dati

- [x] Nel download del pdf togliere le parentesi dopo il label delle question normali

## TABLE A
- [x] I filtri a volte non funzionano bene in visualizzazione e non si scaricano solo i subset selezionati (ma a volte sì ma purtroppo non sono riuscito a capire quando sì e quando no)

- [ ] Scaricare i mantel test (ti metto lo script mantel.py). Quest'analisi richiede due matrici di distanze: noi abbiamo hamming, jaccard[+] e gcd (che è quella geografica)

## FILTERS


## BACKUP
- [x] Non trovo più la pagina