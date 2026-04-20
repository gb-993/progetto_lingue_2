# RIEPILOGO MODIFICHE
- [ ] Roberto Romano per problemi con mail e password

## GENERALI

## LANDING PAGE

## HOW TO CITE

## PUBLIC
(ancora non so esattamente cosa sarà visualizzabile per questi utenti)

## QUESTIONS
- [ ] Se modifico una question poi non chiede di specificare quale è stato il cambiamento per salvare

## LISTA LINGUE
- [ ] Far sì che anche il bottone "Export .xlsx" scarichi solo le info delle lingue selezionate (come fa Export selected (N) (.zip))

- [ ] Se premo su "Download Map (.png)" non mi scarica la mappa

- [ ] Bottone per scaricare le distanze geografiche GCD (come per la mappa, se sono selezionati dei filtri dovrebbe scaricare solo le distanze delle località per cui sono state selezionate le lingue). Ti metto il file gcd.py (metto anche coord.txt solo per mostrarti come vuole formattati i dati, poi si può eliminare)

- [ ] Scaricare mappa Lorenzo e Federico (ne riparliamo prossimamente con loro)

## LINGUE DATA
- [ ] Nel foglio "Database model" dell'export aggiungere la colonna "Motivations" per le motivazioni selezionate sul sito dalla checkbox e la colonna Language_Example_Transliteration. Forse da quel foglio possiamo rimuovere le colonne Question, Question_Examples_YES e Question_Intructions_Comments visto che non sono info linguo-specifiche e teniamo quel foglio primariamente come "backup"?

## DEBUG PARAMETRI

## GLOSSARIO

## LISTA PARAMETRI

## PARAMETERS EDIT
- [ ] Per salvare una question mantenere il bottone che c'è adesso ma chiamarlo "Save the changes and maintain data" e aggiungere un altro bottone "Save the changes and delete the linked data (the old data will still be accessible in ...)". 
L'idea è che la modifica al testo di una question potrebbe:
    1. comunque essere coerente con i vecchi esempi raccolti oppure 
    2. far sì che i vecchi dati non vadano più bene con il nuovo testo della question. 
        -> Nel caso 2. i dati di tutte le lingue relativi a quella question dovrebbero essere rimossi ma non eliminati, ci vorrebbe una pagina che li conservasse, magari con anche la possibilità di scaricarli come xlsx. Tipo una pagina simile a "Questions" con la lista delle questions obsolete e la possibilità di scaricare i vecchi dati

- [ ] Il download del pdf non restituisce l'alfabeto greco (tipo in FGK_Qc)

## TABLE A
- [ ] Scaricare i mantel test (ti metto lo script mantel.py). Quest'analisi richiede due matrici di distanze: noi abbiamo hamming, jaccard[+] e gcd (che è quella geografica)

## FILTERS

## BACKUP
