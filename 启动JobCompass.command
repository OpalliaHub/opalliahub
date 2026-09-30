#!/bin/zsh
cd "${0:A:h}"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python main.py
else
  python3 main.py
fi
