
# Smart OS PRO Launcher

A professional Cloud-Sync Smart TV Launcher built with Python.

## Features
- **Cloud-Sync:** Syncs channel lists from Supabase on every launch.
- **Remote Control:** Real-time mobile remote control via Firebase.
- **Auto-Update System:** Notifies users when a new EXE version is available.

## Setup
1. Clone the repo: `git clone https://github.com/sarifuddinmondal/sumos.git`
2. Install requirements: `pip install -r requirements.txt`
3. Add `serviceAccountKey.json` to the root folder.
4. Run: `python main.py`

## Build EXE
```bash
pyinstaller --noconfirm --onefile --windowed --add-data "templates;templates" --add-data "static;static" --add-data "serviceAccountKey.json;." main.py
```
