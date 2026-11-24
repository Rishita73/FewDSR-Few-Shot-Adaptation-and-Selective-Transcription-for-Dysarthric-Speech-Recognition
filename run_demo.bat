@echo off
cd /d "%~dp0"
title FewDSR 40 Percent Running Module Demo
echo ========================================================
echo   FewDSR: Dysarthric Speech Recognition (40%% Demo)
echo   Rishita Bhandari (230000101080) & Radhika Negi (230000101076)
echo   UTU Dehradun - Academic Session 2026-2027
echo ========================================================
echo.
echo Launching Streamlit Interactive Dashboard on http://localhost:8501 ...
echo (No API tokens, logins, or cloud keys needed - runs 100%% offline)
echo.
python -m streamlit run app.py --server.headless=false --browser.gatherUsageStats=false
pause
