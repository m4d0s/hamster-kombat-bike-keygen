@echo off
python.exe -m pip install --upgrade pip
pip install -r req.txt

start python telegram.py
@REM timeout /t 15 /nobreak
@REM start python solo.py

