# RIEPILOGO MODIFICHE


- [x] Roberto Romano per indirizzo tecnico per macchina virtuale
- [x] Servizi informatici per casella noreply
- [x] Richiedere di accettare di nuovo le condizioni sull'utilizzo se modifichiamo il file
- [ ] Inserire nuovo Terms of use

## GENERALI
- [x] Il FLAGGED / UNSURE PARAMETERS fa cose strane, tipo mette problemi per Italian ma nella pagina Data i parametri sono tutti verdi
- [x] Forse è il caso che FLAGGED / UNSURE PARAMETERS mostri i parametri rossi, quindi anche quelli per cui manca anche una sola risposta (es. CEX per Trieste)
- [x] Rendere cliccabili i link nel menù (link circolari)
- [x] Aggiornare i nomi delle pagine (Graph -> Parameter networks, Submissions -> Saved languages, Queries -> Filters)
- [x] Aggiornare ordine nel menù User: Dashboard > Languages > Instructions > Glossary > My account
- [x] Aggiornare ordine nel menù Admin: Dashboard > Languages > Parameters > Parameter networks > Table A > Saved languages > Filters > Instructions > Glossary > My account > Accounts
- [x] Rendere cliccabile il breadcrumb

## HOW TO CITE
- [ ] Inserire la visualizzazione dei due How to cite (non modificabili) per User in una pagina "How to cite" (mentre per Admin è "How to cite (edit)")
- [ ] Descrizione di "How to cite" sx: "Unless otherwise specified in the description of each parameter, if you quote a parameter description or any parameter manifestation, please refer to:"
- [ ] Titolo di "How to cite" dx: "Language list & map", contenuto: "Guardiano, Cristina, Paola Crisma, Giuseppe Longobardi, Marco Longhin, Giovanni Battista Matteazzi, Emanuela Li Destri, Gaia Sorge (eds.). 2026. The PCM_Hub (version 1). Accessed on: XX/XX/XXXX"
- [ ] Nel "How to cite" dx il riferimento non si salva se modificato dal sito e quando si preme su "Edit reference" non compare il testo già presente 
- [ ] Aggiungere un terzo riquadro sotto agli altri e largo quanto i due sopra messi insieme visibile e modificabile solo per gli Admin, con titolo "Outputs" e descrizione "To cite any content of the PCM Hub (except for parameters and manifestations):" e contenuto/ref uguale a quello sopra a dx

## LANDING PAGE
- [ ] Praticamente rendere la pagina che ora è la homepage di Public visibile senza accesso e con pulsante di login in alto a destra (lo sapevo che finiva così)
- [ ] Come "logo" immagine di un planisfero con segnaposti in corrispondenza delle coordinate inserite, che si aggiorni sulla base delle lingue nel db. Sarebbe ideale se i colori dei segnaposto dipendessero dalla top-level family della lingua
- [ ] Togliere la colonna a sx (= per il momento tralasciamo le altre pagine) 
- [ ] Lasciamo il pulsante che riconduce alle citazioni
- [ ] Si può togliere anche la tabella a destra (magari teniamo il codice, che può essere utile in futuro)

## PUBLIC
- [x] Valori aggiornati per lingue, famiglie, ...
- [x] Creare la homepage sul modello di [ASJP](https://asjp.clld.org)
- [x] Pulsante di Login e poi messaggio di benvenuto personalizzato
- [x] Predisporre qualche riga per spiegare a cosa serve il sito
- [x] Predisporre modello di citazione 
- [x] Contatti a cui scrivere per proporre una collaborazione
- [x] Link cliccabili per privacy e per termini di utilizzo da accettare al primo accesso (in registrazione per public account)
- [x] Link al sito di [PCM](http://www.parametricomparison.unimore.it/site/home.html)
- [x] Modificare "How to cite": nuova pagina nel menù a sinistra

## QUESTIONS
- [ ] Se modifico una question da questa pagina poi non chiede di specificare quale è stato il cambiamento per salvare
- [x] Nuova pagina "Questions" simile a "Parameters" con pulsante Search una tabella: label | testo della  question | pulsante Edit (porta alla pagina del parametro)
- [x] Lista delle questions con lo stesso ordine dei parametri

## LISTA LINGUE
- [ ] Poter selezionare le lingue per scaricare gli esempi ecc (al momento o lingua singola o tutte le lingue)
- [x] Inserire l'attributo location in Add, Edit, visualizzabile in Lingue Data e come colonna nel file excel che si scarica con le info di tutte le lingue
- [x] Togliere l'attributo position
- [x] Inserire due nuovi attributi: Latitude e Longitude (da definire già quando si crea la lingua)
- [x] Errori "parlanti" al caricamento di un file
- [x] Equiparare Qs a QS nello script(?)
- [x] Fare in modo che se nel file excel ci sono ID delle questions che non si trovano nel database, i dati di quelle questions non vengano copiati
- [x] Verificare che il caricamento di un foglio di una lingua sovrascriva i dati precedentemente caricati per quella lingua

## LINGUE DATA
- [x] A volte il numero dell'esempio è cancellato nella cella di Example text (anche se è del tipo 1.1). A questo punto conviene che lo script non cerchi di associare l'esempio a un numero ma lo copi direttamente così com'è
- [x] Aggiungere Save e Next visibili a destra durante lo scorrimento
- [x] Problema della duplicazione delle stop-questions con label Qs
- [x] Ristrutturazione dei pulsanti  

## DEBUG PARAMETRI
- [x] Poter modificare manualmente il valore di un parametro nel final value, segnalando che è stata fatta una modifica 

## GLOSSARIO
- [x] Controllare corrispondenza tra versione online e locale
- [x] Caricare voci

## DEBUG
- [x] Warning in caso di risposte non date

## LISTA PARAMETRI
- [x] Mettere i pulsanti a destra in un'unica riga

## PARAMETERS EDIT
- [ ] Inserire uno spazio sotto a brief summary of changes in cui sono conservate tutte le descrizioni delle modifiche fatte per quel parametro
- [x] Instruction yes e no al plurale in edit question 
- [x] Inserire un nuovo attributo Level of comparison con i due valori mutualmente esclusivi Canonico e Deuterocanonico
- [x] Inserire due altre celle di testo libero una sotto l'altra intitolate "Long description" e "Explication of the implicational condition"
- [x] Inserire un bottone di download alla fine della pagina di edit del parametro per scaricare un pdf con tutte le informazioni di un parametro e delle sue questions

## TABLE A
- [?] Scaricare mappa Lorenzo e Federico
- [x] Poter cliccare sul valore di un parametro o su YES/NO di una question e visualizzare le questions e gli esempi che hanno permesso di fissare quel parametro/risposta
- [x] Poter selezionare le lingue anche per Family e per Group, oltre che per Top-level family, e i parametri per Level of Comparison
- [x] Poter selezionare singole lingue (oltre che con i filtri) e singoli parametri, tipo con checkbox vicino a ogni lingua/parametro per il download delle distanze e dei dendrogrammi
- [x] Far scaricare solo distanze Hamming e Jaccard[+] (eliminare le altre quattro)
- [x] Scaricare dendrogramma UPGMA adattando dendrogram.py (magari con lo stesso pulsante delle distanze: Export distances and dendrograms)
- [x] Scaricare una PCA 

## FILTERS
- [x] Inserire l'ordine alfabetico per la ricerca delle lingue anziché quello basato su position
- [x] Nuovi filtri: "Questions with answer YES (per language)" e "Questions with answer NO (per language)"
- [x] Quando ci sono i parametri tra i risultati poter cliccare sul label ed essere reindirizzato alla pagina di Edit del paramentro
- [x] Quando ci sono le questions per lingua poter cliccare sul label ed essere reindirizzato alla question all'interno di Lingua data