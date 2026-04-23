#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "  🍪  Cookie Clicker Stock Analyzer"
echo "  ──────────────────────────────────"
echo "  Starting server on http://localhost:8080"
echo "  Keep this window OPEN — closing it stops the server."
echo ""

# Open browser after 1.5 seconds (gives Flask time to start)
(sleep 1.5 && open http://localhost:8080) &

python3 app.py
