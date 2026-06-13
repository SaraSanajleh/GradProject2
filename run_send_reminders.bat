@echo off
cd /d "%~dp0"
REM تشغيل إرسال التذكيرات (للاستخدام من Task Scheduler أو يدوياً)
REM تأكد أن السيرفر يعمل على http://127.0.0.1:8000
set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" (
    echo ERROR: .venv not found. Run the project once to create it.
    exit /b 1
)
"%PYTHON%" send_reminders_daily.py
exit /b %ERRORLEVEL%
