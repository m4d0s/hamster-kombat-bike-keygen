@echo off
python.exe -m pip install --upgrade pip
pip install -r req.txt

start solo.py
start python telegram.py
