#!/usr/bin/env bash
# Script per avviare la UI del CRM di Melania Nutrizionista

cd "$(dirname "$0")"

echo "========================================================"
echo " Avvio CRM Melania Nutrizionista (Catania Leads)"
echo " Server locale: http://localhost:8000"
echo " Premi Ctrl+C per fermare."
echo "========================================================"

# Apri automaticamente il browser dopo 1 secondo in background
(sleep 1 && open "http://localhost:8000") &

# Avvia il server Python nativo a zero dipendenze
python3 crm_app.py
