# RIEPILOGO MODIFICHE
- [ ] Roberto Romano per problemi con mail, password e https

## GENERALI

## LANDING PAGE
- [ ] È scomparsa la mappa

## PUBLIC
(ancora non so esattamente cosa sarà visualizzabile per questi utenti)

## HOW TO CITE

## LISTA LINGUE
- [ ] La mappa si scarica ma è molto sfocata
- [ ] Sostituire la stringa "family" con "subfamily" (anche nelle altre parti del sito)
- [ ] Invertire l'ordine di "group" e "historical"
- [ ] Se seleziono una certa top-level family poi si può fare che vedo solo le subfamily rilevanti e così via?
- [ ] Nei filtri mettere una checkbox che permetta ad es. di selezionare più top-level family ecc
- [ ] Dopo aver applicato i filtri, vorrebbero trovare un modo per deselezionare le lingue che non vogliono ma che sono state identificate dai filtri, es. se seleziono le lingue indoeuropee ma per qualche motivo non voglio l'italiano nella mappa e nelle distanze si dovrebbe poter deselezionare solo l'italiano e mantenere le altre indoeuropee
- [ ] Si può inserire un modo per decidere sulla base di cosa assegnare i colori nella mappa? Se per "top-level family", "subfamily", "group" oppure "historical"
- [ ] Inserire una legenda dei colori
- [ ] Sostituire "Export .xlsx" con "Export language metadata (.xlsx)"
- [ ] Sostituire "Export data (.zip)" con "Export parametric data (.zip)"
- [ ] Poter scaricare le distanze geografiche GCD (come per la mappa, se sono selezionati dei filtri dovrebbe scaricare solo le distanze delle località per cui sono state selezionate le lingue). Ti metto il file gcd.py (metto anche coord.txt solo per mostrarti come vuole formattati i dati, poi si può eliminare)
- [ ] Inserire un pulsante download con tendina come per la pagina della Table A che scarichi la mappa "Map (.png)" e le distanze geografiche GCD "Geo distances (.txt)" entrambe con il dataset intero o solo con le lingue selezionate
- [ ] Scaricare la mappa di Lorenzo e Federico (ne riparliamo prossimamente con loro)

## LINGUE DATA
- [ ] Nel foglio "Database model" dell'export aggiungere la colonna "Motivations" per le motivazioni selezionate sul sito dalla checkbox e la colonna Language_Example_Transliteration. Forse da quel foglio possiamo rimuovere le colonne Question, Question_Examples_YES e Question_Intructions_Comments visto che non sono info linguo-specifiche e teniamo quel foglio primariamente come "backup"?
- [ ] Sostituire "Download .xlsx" con "Export parametric data (.xlsx)"

## DEBUG PARAMETRI

## LISTA PARAMETRI
- [ ] È scomparso il bottone "Add a new parameter"
- [ ] Mettere in alto un bottone che permetta di scaricare un pdf con le info di tutti i parametri, tipo "Download parameters info (.pdf)" 
- [ ] Si può mettere anche un bottone che permetta di fare un 'backup' delle info di tutti i parametri (con questions ecc) come si fa per i dati delle lingue, da vedere poi nella pagina "Backup"? Se sì poi possiamo mettere un bottone "Backup" anche vicino al bottone "PDF" per farlo del singolo parametro

## PARAMETERS EDIT
- [ ] Per salvare una question mantenere il bottone che c'è adesso ma chiamarlo "Save the changes and maintain data" e aggiungere un altro bottone "Save the changes and delete the linked data (the old data will still be accessible in Old questins archive)". 
L'idea è che la modifica al testo di una question potrebbe:
    1. comunque essere coerente con i vecchi esempi raccolti oppure 
    2. far sì che i vecchi dati non vadano più bene con il nuovo testo della question. 
        -> Nel caso 2. i dati di tutte le lingue relativi a quella question dovrebbero essere rimossi ma non eliminati, ci vorrebbe una pagina che li conservasse, magari con anche la possibilità di scaricarli come xlsx. Tipo una pagina simile a "Questions" con la lista delle questions obsolete e la possibilità di scaricare i vecchi dati
- [ ] Spostare in alto a dx il download del pdf con le info del parametro "Download parameter info (.pdf)"
- [ ] Il bottone "Download PDF" nel riquadro "Brief summary of changes" potrebbe scaricare la cronologia delle modifiche
- [ ] Fare in modo che le finestre di edit delle motivazioni, di schema/type ecc si aprano come pop up e quindi non si perdano le info inserite (funziona in edit parameter ma non in edit question)

## LISTA QUESTIONS
- [ ] Aggiungere il bottone "Add a new question" sul modello di "Add a new language"
- [ ] Se modifico una question da questa pagina poi non chiede di specificare quale è stato il cambiamento per salvare

## NETWORK

## TABLE A
- [ ] Allineare i filtri delle lingue con le modifiche fatte agli stessi filtri nella pagina con la lista delle lingue

## MANTEL TEST
- [ ] Nuova pagina che permetta di selezionare lingue con gli stessi filtri che si trovano nella pagina della Table A e un bottone "Perform Mantel test and download results (.zip)" che scarichi le matrici di distanze geografiche e sintattiche (gcd.txt, hamming.txt e jaccard[+].txt) e i risultati dello script mantel.py. Lo script fa già tutte le combinazioni possibili dei file di distanze

## FILTERS

## BACKUP
- [ ] Rimuovere il backup di prova del 9 gennaio (dal sito non si riesce perché dice "No backup found with this date.")
- [ ] Poter scaricare i backup come excel con un bottone "Download full backup (.xlsx)" vicino al bottone "Open folder" e con un bottone "Download data (.xlsx)" vicino al bottone "Data" specifico per ogni lingua
- [ ] Mettere il testo della motivazione anziché il codice

## OLD QUESTIONS ARCHIVE
- [ ] Nuova pagina con la lista delle questions obsolete (strutturata tipo la pagina Questions) con pulsante "View data" (o qls di simile) che premendolo apra una pagina con tutte le risposte, esempi ecc di quella singola question per tutte le lingue. Vicino al pulsante "View data" potremmo metterne uno che permetta di scaricare i dati in formato excel

## GLOSSARIO