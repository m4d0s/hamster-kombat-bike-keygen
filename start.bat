@echo off
python.exe -m pip install --upgrade pip
pip install -r req.txt

start python main.py
timeout /t 15 /nobreak
start python solo.py

