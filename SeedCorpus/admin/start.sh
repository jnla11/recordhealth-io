#!/bin/bash
cd "$(dirname "$0")"
echo "Starting ADI Console at http://localhost:8080/adi-console.html"
open "http://localhost:8080/adi-console.html"
python3 -m http.server 8080
