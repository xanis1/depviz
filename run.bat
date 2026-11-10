@echo off
setlocal
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
if /i "%~1"=="test" goto run_tests
python -m depviz %*
exit /b %ERRORLEVEL%

:run_tests
cd /d "%~dp0"
python -m unittest discover -s tests -t . -v
exit /b %ERRORLEVEL%
