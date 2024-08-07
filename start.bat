@echo off
python.exe -m pip install --upgrade pip
pip install -r req.txt

start python generate.py
start python telegram.py
