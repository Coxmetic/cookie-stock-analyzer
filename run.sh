#!/bin/bash
cd "$(dirname "$0")"

echo "starter server på http://localhost:8080"
echo "lad dette vindue stå åbent ellers stopper serveren"

# åbn browser efter 1.5 sek så flask når at starte
(sleep 1.5 && open http://localhost:8080) &

python3 app.py
