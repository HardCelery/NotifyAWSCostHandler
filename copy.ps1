Copy-Item -Path .\.env\requirements.txt .\docs
Copy-Item -Path .\src\*.py .env\Lib\site-packages\
