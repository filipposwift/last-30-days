# Skill Review Workspace

Workspace di staging per la revisione di sicurezza di skill scaricate da GitHub, prima di caricarle su OpenClaw.

## Scopo

Ogni skill viene scaricata qui, ispezionata file per file per individuare codice malevolo o problematico, modificata se necessario, e poi caricata su GitHub per l'installazione su OpenClaw.

## Workflow

1. **Scaricare** la skill da GitHub in questo workspace
2. **Revisione sicurezza** - ispezionare OGNI file per:
   - Esecuzione di comandi shell sospetti (`exec`, `spawn`, `system`, `eval`)
   - Accesso a file system al di fuori del progetto
   - Richieste di rete a URL sconosciuti o sospetti
   - Offuscamento del codice (base64, hex encoding, string concatenation sospetta)
   - Dipendenze esterne non necessarie o sospette
   - Accesso a variabili d'ambiente sensibili (token, chiavi API, credenziali)
   - Script post-install in package.json o simili
3. **Modifiche** - apportare eventuali correzioni o personalizzazioni
4. **Caricare** su GitHub per l'installazione su OpenClaw

## Regole per Claude

- Quando viene chiesto di revisionare una skill, leggere OGNI singolo file senza eccezioni
- Segnalare qualsiasi pattern sospetto con livello di rischio (alto/medio/basso)
- Non eseguire mai codice scaricato senza averlo prima revisionato
- In caso di dubbio su un file, segnalarlo esplicitamente all'utente
