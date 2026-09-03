#!/bin/bash
# Lanzador de BIMO Pro para macOS / Linux
DIR="$( cd "$(dirname "$0")" || exit; pwd )"
cd "$EIR"
echo "Iniciando BIMO Pro..."
python3 main.py || python main.py
