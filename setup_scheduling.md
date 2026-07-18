# NHPC Weather Warning System - Automation & Scheduling Guide

This guide explains how to set up the weather forecasting script (`update_forecasts.py`) to run automatically in the background. Since India Meteorological Department (IMD) updates its weather prediction models every 6 hours, it is recommended to run this script every 6 hours to keep the dashboard warnings live and up-to-date.

---

## 1. Manual Execution

You can update the forecast data and alerts at any time by running:
```bash
python update_forecasts.py
```
This script will:
1. Parse the powerplant coordinates from `Catchment_NHPC.KML`.
2. Fetch the latest 5-day weather data from the IMD Mausamgram API.
3. Assess meteorological risk levels (Rainfall and Wind).
4. Send Telegram, Slack, or Email alerts if alert levels change.
5. Generate `weather_forecast_summary.txt` and `forecast_data.js`.

---

## 2. Windows Automation (Task Scheduler)

Since your system is running Windows, the most reliable way to automate this is via **Windows Task Scheduler**. To run the script silently in the background every 6 hours without displaying a command window:

### Step 1: Open Task Scheduler
1. Press `Windows Key + R`, type `taskschd.msc`, and press **Enter**.
2. In the right panel under Actions, click **Create Task...** (do not use "Basic Task" as we need advanced recurrence options).

### Step 2: Configure General Settings
1. **Name**: `NHPC Weather Warning Scraper`
2. **Description**: `Fetches IMD weather forecasts, updates data, and triggers alerts for NHPC hydro power plant catchments.`
3. **Security options**: Select **Run whether user is logged on or not** (this ensures it runs even if you are locked or logged out).
4. Check **Run with highest privileges** (if you experience permissions issues).

### Step 3: Set up the 6-Hour Trigger
1. Go to the **Triggers** tab and click **New...**.
2. Under "Begin the task", select **On a schedule**.
3. Under Settings, select **Daily** and set the start time.
4. Under Advanced settings:
   - Check **Repeat task every**: Select **6 hours** from the dropdown (or type `6 hours`).
   - Set "for a duration of": Select **Indefinitely**.
   - Check **Enabled**.
5. Click **OK**.

### Step 4: Configure the Action
1. Go to the **Actions** tab and click **New...**.
2. **Action**: `Start a program`
3. **Program/script**: Input `pythonw` (Note: `pythonw` is a standard Python executable that runs scripts in the background without launching a black command prompt window. Alternatively, you can use `python`).
4. **Add arguments**: `update_forecasts.py`
5. **Start in (optional)**: `d:\bht bhayankar codin\nhpc` (or the absolute path to your workspace directory).
6. Click **OK**.

### Step 5: Save the Task
1. Click **OK** to save the task. 
2. Enter your Windows login credentials if prompted.
3. You can test it immediately by selecting the task from the **Task Scheduler Library** and clicking **Run** in the right-hand panel.

---

## 3. Alternative: Running as a Python background daemon

If you prefer to run a continuous Python script in the background while your terminal is active, you can create a simple background loop script.

Create a file named `daemon_runner.py` with:
```python
import time
import subprocess
import sys

INTERVAL = 6 * 3600  # 6 hours in seconds

print("Starting NHPC weather daemon. Checking forecasts every 6 hours...")
while True:
    try:
        print(f"Executing scraper run at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
        subprocess.run([sys.executable, "update_forecasts.py"], check=True)
    except Exception as e:
        print(f"Daemon run failed: {e}")
    
    print(f"Sleeping for 6 hours...")
    time.sleep(INTERVAL)
```
Run this script in a background terminal (e.g., using `nohup python daemon_runner.py &` or keeping the terminal open).
