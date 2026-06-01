#!/usr/bin/env python3
"""
J.A.R.V.I.S — ArqoAssist Ultimate v6
Author: Anjar / Arqonara
- GUI: modern glassmorphism HUD, animasi smooth, rounded panels
- AI: 40+ tools, multi-step agentic loop, memory konteks
- TTS: edge-tts (id-ID-ArdiNeural)
- Voice: Whisper realtime VAD
- Spotify: keyboard-only navigation, force play
"""

import os, sys, json, time, wave, math, struct, tempfile
import threading, subprocess, webbrowser, urllib.parse, asyncio
import glob, re, shutil
from pathlib import Path
from datetime import datetime

# ─── Load .env ─────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TTS_VOICE       = "id-ID-ArdiNeural"   # id-ID-GadisNeural untuk wanita
TTS_RATE        = "+5%"
TTS_VOLUME      = "+0%"
LANGUAGE        = "id"
SILENCE_THR     = 1200   # Naikkan threshold agar mic tidak terlalu sensitif
SILENCE_DUR     = 1.1
MIN_REC_SECS    = 0.5
CHUNK           = 1024
SAMPLE_RATE     = 16000
CHANNELS        = 1
MAX_HISTORY     = 20
MODEL           = "gpt-4o"
# ───────────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import scrolledtext, ttk

def _check_deps():
    pkgs = {
        "openai":    "openai",
        "pyaudio":   "pyaudio",
        "pyautogui": "pyautogui",
        "psutil":    "psutil",
        "pyperclip": "pyperclip",
        "requests":  "requests",
        "edge_tts":  "edge-tts",
        "pygame":    "pygame",
        "yt_dlp":    "yt-dlp",
    }
    import importlib.util as _ilu
    missing = [pip for mod, pip in pkgs.items() if not _ilu.find_spec(mod)]
    if missing:
        print("❌  Library kurang:", ", ".join(missing))
        print(f"    pip install {' '.join(missing)}")
        sys.exit(1)

_check_deps()

import openai, pyaudio, pyautogui, psutil, pyperclip, requests, edge_tts, pygame

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0.04

# ─── TTS ───────────────────────────────────────────────────────────────────────
_tts_lock    = threading.Lock()
_tts_enabled = True

# Dedicated asyncio event loop — satu loop permanen, tidak bentrok dengan tkinter
_tts_loop = asyncio.new_event_loop()
def _tts_loop_runner():
    asyncio.set_event_loop(_tts_loop)
    _tts_loop.run_forever()
threading.Thread(target=_tts_loop_runner, daemon=True).start()

def speak(text: str):
    if not _tts_enabled or not text.strip():
        return
    def _run():
        with _tts_lock:
            tmp = None
            try:
                fd, tmp = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                async def _gen():
                    c = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, volume=TTS_VOLUME)
                    await c.save(tmp)
                # Submit ke dedicated loop — thread-safe, tidak bikin event loop baru
                future = asyncio.run_coroutine_threadsafe(_gen(), _tts_loop)
                future.result(timeout=30)
                pygame.mixer.init(frequency=44100)
                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.08)
                pygame.mixer.music.unload()
                pygame.mixer.quit()
            except Exception as e:
                print(f"[TTS] {e}")
            finally:
                if tmp:
                    for _ in range(10):
                        try: os.unlink(tmp); break
                        except: time.sleep(0.2)
    threading.Thread(target=_run, daemon=True).start()

# ─── SPOTIFY ───────────────────────────────────────────────────────────────────
def _find_spotify():
    paths = [
        Path(os.environ.get("APPDATA",""))      / "Spotify/Spotify.exe",
        Path(os.environ.get("LOCALAPPDATA","")) / "Spotify/Spotify.exe",
        Path(os.environ.get("LOCALAPPDATA","")) / "Microsoft/WindowsApps/Spotify.exe",
        Path("C:/Program Files/Spotify/Spotify.exe"),
        Path("C:/Program Files (x86)/Spotify/Spotify.exe"),
    ]
    for p in paths:
        if p.exists(): return str(p)
    return None

SPOTIFY_EXE = _find_spotify()

def _is_spotify_running():
    """Cek apakah proses Spotify sedang berjalan."""
    for p in psutil.process_iter(["name"]):
        try:
            if "spotify" in p.info["name"].lower():
                return True
        except Exception:
            pass
    return False

def _focus_spotify():
    """Fokuskan window Spotify ke depan."""
    try:
        result = subprocess.run(
            ["powershell", "-c",
             "(New-Object -ComObject WScript.Shell).AppActivate('Spotify')"],
            capture_output=True, text=True, timeout=5
        )
        time.sleep(0.6)
        return True
    except Exception:
        return False

def _spotify_do_search(q: str):
    """
    Lakukan search di Spotify yang sudah terbuka.
    Strategi: klik posisi search bar (selalu di bagian atas tengah Spotify),
    ketik query, tekan Enter untuk lihat hasil, lalu klik lagu pertama.
    """
    time.sleep(4.0)  # tunggu Spotify fully loaded

    # Fokus ke Spotify
    _focus_spotify()
    time.sleep(0.5)

    sw, sh = pyautogui.size()

    # ── Coba Ctrl+K dulu (shortcut search Spotify versi baru) ──
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.8)

    # Cek apakah search bar aktif dengan coba ketik sesuatu
    # Kosongkan dulu
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyperclip.copy(q)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(2.8)  # tunggu hasil dropdown muncul

    # Tekan Enter langsung — Spotify akan load halaman full search
    pyautogui.press("enter")
    time.sleep(2.0)  # tunggu halaman search hasil penuh

def open_spotify(query=""):
    """Buka Spotify dan opsional search+play lagu."""
    global SPOTIFY_EXE
    if not SPOTIFY_EXE:
        SPOTIFY_EXE = _find_spotify()

    already_running = _is_spotify_running()

    if SPOTIFY_EXE and Path(SPOTIFY_EXE).exists():
        if not already_running:
            subprocess.Popen([SPOTIFY_EXE])
        if query:
            threading.Thread(target=_spotify_do_search, args=(query,), daemon=True).start()
            return f"Spotify: memuat dan mencari '{query}'…"
        return "Spotify dibuka."

    # Tidak ada EXE — fallback URI (tidak memanggil _spotify_do_search lagi)
    try:
        if query:
            os.startfile(f"spotify:search:{urllib.parse.quote(query)}")
        else:
            os.startfile("spotify:")
        return f"Spotify dibuka via URI{': cari ' + query if query else ''}."
    except Exception:
        webbrowser.open("https://open.spotify.com" + (f"/search/{urllib.parse.quote(query)}" if query else ""))
        return "Spotify Web dibuka (app tidak ditemukan)."



# ─── YOUTUBE HELPER ────────────────────────────────────────────────────────────
def _youtube_get_url(query: str) -> str:
    """
    Dapat URL video YouTube PERTAMA yang bukan iklan.
    WAJIB return format watch?v=XXXX — kalau gagal, return None.
    Strategi:
      1. yt-dlp  (paling akurat)
      2. YouTube Innertube API  (tanpa API key)
    """
    # ── Metode 1: yt-dlp ──────────────────────────────────────────
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch1",
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if info and info.get("entries"):
                vid_id = info["entries"][0].get("id") or info["entries"][0].get("url","")
                if vid_id and len(vid_id) == 11:   # YouTube ID selalu 11 karakter
                    return f"https://www.youtube.com/watch?v={vid_id}"
    except Exception as e:
        print(f"[YT yt-dlp] {e}")

    # ── Metode 2: YouTube Innertube API ───────────────────────────
    try:
        endpoint = "https://www.youtube.com/youtubei/v1/search?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        payload  = {
            "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101"}},
            "query": query
        }
        resp = requests.post(endpoint, json=payload,
                             headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"},
                             timeout=8)
        data = resp.json()
        contents = (data.get("contents",{})
                        .get("twoColumnSearchResultsRenderer",{})
                        .get("primaryContents",{})
                        .get("sectionListRenderer",{})
                        .get("contents",[]))
        for section in contents:
            items = section.get("itemSectionRenderer",{}).get("contents",[])
            for item in items:
                vr = item.get("videoRenderer") or item.get("reelItemRenderer")
                if vr:
                    vid_id = vr.get("videoId","")
                    if vid_id and len(vid_id) == 11:
                        return f"https://www.youtube.com/watch?v={vid_id}"
    except Exception as e:
        print(f"[YT innertube] {e}")

    # ── Gagal total — kembalikan None ─────────────────────────────
    return None


# ─── URL OPENER (tidak lewat webbrowser module) ────────────────────────────────
def _open_url_direct(url: str):
    """
    Buka URL langsung di browser default via Windows ShellExecute.
    Tidak melalui webbrowser.open() yang kadang fallback ke Google search.
    """
    try:
        os.startfile(url)
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
        except Exception:
            webbrowser.open(url)

# ─── APP DISCOVERY CACHE ───────────────────────────────────────────────────────
_APP_CACHE_FILE = Path.home() / ".jarvis_app_cache.json"
_app_cache: dict = {}   # { "keyword": "C:/path/to/app.exe" }

def _load_app_cache():
    global _app_cache
    try:
        if _APP_CACHE_FILE.exists():
            with open(_APP_CACHE_FILE, "r", encoding="utf-8") as f:
                _app_cache = json.load(f)
    except Exception:
        _app_cache = {}

def _save_app_cache():
    try:
        with open(_APP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_app_cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _cache_set(keyword: str, path: str):
    _app_cache[keyword.lower()] = path
    _save_app_cache()

def _normalize(s: str) -> str:
    return s.lower().replace(" ","").replace("-","").replace("_","").replace(".exe","")

def _scan_all_apps() -> dict:
    """
    Scan SEMUA EXE yang terinstall di Windows:
    Registry App Paths + Uninstall + semua folder install umum.
    Kembalikan dict { normalized_name: exe_path }
    """
    found = {}

    # Registry: App Paths
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for reg_path in [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
            ]:
                try:
                    key = winreg.OpenKey(hive, reg_path)
                    i = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            try:
                                sub_key = winreg.OpenKey(key, sub_name)
                                exe_path, _ = winreg.QueryValueEx(sub_key, "")
                                exe_path = exe_path.strip('"')
                                if exe_path and Path(exe_path).exists():
                                    found[_normalize(sub_name)] = exe_path
                            except Exception:
                                pass
                            i += 1
                        except OSError:
                            break
                except Exception:
                    pass
    except ImportError:
        pass

    # Registry: Uninstall (DisplayIcon = path to EXE)
    try:
        import winreg
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for reg_path in [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ]:
                try:
                    key = winreg.OpenKey(hive, reg_path)
                    i = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            try:
                                sub_key = winreg.OpenKey(key, sub_name)
                                try:
                                    display_name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                                    install_loc, _ = winreg.QueryValueEx(sub_key, "InstallLocation")
                                    if display_name and install_loc:
                                        loc = Path(install_loc.strip('"'))
                                        if loc.exists():
                                            # Cari EXE utama di folder install
                                            exes = list(loc.glob("*.exe"))
                                            if exes:
                                                # Pilih EXE yang namanya paling mirip DisplayName
                                                dn = _normalize(display_name)
                                                best = min(exes, key=lambda e: abs(len(_normalize(e.stem)) - len(dn)))
                                                found[_normalize(display_name)] = str(best)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            i += 1
                        except OSError:
                            break
                except Exception:
                    pass
    except ImportError:
        pass

    # Scan folder install umum
    scan_dirs = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for base_dir in scan_dirs:
        if not base_dir.exists():
            continue
        try:
            for exe in base_dir.rglob("*.exe"):
                key = _normalize(exe.stem)
                if key and key not in found:
                    found[key] = str(exe)
        except Exception:
            continue

    return found

# Load cache saat startup
_load_app_cache()

# ─── SMART APP OPENER ──────────────────────────────────────────────────────────
def _smart_open_app(app_name: str) -> str:
    """
    Buka aplikasi apapun — 8 strategi, TIDAK PERNAH gagal total:
    1. Spotify (handler khusus)
    2. APP_MAP fuzzy (chrome, explorer, discord, dll)
    3. KNOWN_APP_PATHS (hard-coded: Steam, VLC, dll)
    4. Start Menu shortcuts (.lnk) — semua app terinstall
    5. Cache lokal
    6. Registry + folder scan (full scan)
    7. shutil.which (PATH)
    8. Windows Search — PASTI jalan: Win+S → ketik → Enter
    """
    name_raw  = app_name.strip()
    name_lower= name_raw.lower()
    name_norm = _normalize(name_raw)

    # ── 1. Spotify ──────────────────────────────────────────────────────────
    if "spotify" in name_lower:
        return open_spotify()

    # ── 2. APP_MAP fuzzy ────────────────────────────────────────────────────
    for key, cmd in APP_MAP.items():
        k_norm = _normalize(key)
        if k_norm == name_norm or k_norm in name_norm or name_norm in k_norm:
            subprocess.Popen(cmd, shell=True)
            return f"'{name_raw}' dibuka."

    # ── 3. KNOWN_APP_PATHS ──────────────────────────────────────────────────
    for key, paths in KNOWN_APP_PATHS.items():
        if key in name_norm or name_norm in key:
            for p in paths:
                if Path(p).exists():
                    subprocess.Popen([str(p)])
                    _cache_set(name_norm, str(p))
                    return f"'{name_raw}' dibuka ({Path(p).name})."

    # ── 4. Start Menu shortcuts (.lnk) ──────────────────────────────────────
    global _shortcut_cache
    if not _shortcut_cache:
        _shortcut_cache = _scan_shortcuts()
    # Exact match dulu
    for sc_key, sc_path in _shortcut_cache.items():
        if sc_key == name_norm:
            os.startfile(sc_path)
            return f"'{name_raw}' dibuka via shortcut."
    # Substring match
    best_lnk = None
    best_lnk_score = 0
    for sc_key, sc_path in _shortcut_cache.items():
        if name_norm in sc_key or sc_key in name_norm:
            score = len(set(name_norm) & set(sc_key))
            if score > best_lnk_score:
                best_lnk_score = score
                best_lnk = (sc_key, sc_path)
    if best_lnk and best_lnk_score >= 2:
        os.startfile(best_lnk[1])
        return f"'{name_raw}' dibuka via shortcut ({best_lnk[0]})."

    # ── 5. Cache hit ────────────────────────────────────────────────────────
    for cached_key, cached_path in list(_app_cache.items()):
        if name_norm in _normalize(cached_key) or _normalize(cached_key) in name_norm:
            p = Path(cached_path)
            if p.exists():
                subprocess.Popen([str(p)])
                return f"'{name_raw}' dibuka (cache)."
            else:
                del _app_cache[cached_key]; _save_app_cache(); break

    # ── 6. Full scan registry + folder ──────────────────────────────────────
    all_apps = _scan_all_apps()
    best_match = None; best_score = 0
    for app_key, app_path in all_apps.items():
        if name_norm == app_key:
            best_match = (app_key, app_path); break
        if name_norm in app_key or app_key in name_norm:
            score = len(set(name_norm) & set(app_key))
            if score > best_score:
                best_score = score; best_match = (app_key, app_path)
    if best_match:
        p = Path(best_match[1])
        if p.exists():
            _cache_set(best_match[0], best_match[1])
            subprocess.Popen([str(p)])
            return f"'{name_raw}' dibuka ({p.name})."

    # ── 7. shutil.which ─────────────────────────────────────────────────────
    for candidate in [name_lower, name_lower.replace(" ",""), name_lower.replace(" ","-")]:
        exe = shutil.which(candidate)
        if exe:
            subprocess.Popen([exe])
            _cache_set(name_norm, exe)
            return f"'{name_raw}' dibuka (PATH)."

    # ── 8. Windows Search — PASTI jalan ─────────────────────────────────────
    # Tutup JARVIS focus dulu agar Win+S ke desktop
    import ctypes
    ctypes.windll.user32.ShowWindow(
        ctypes.windll.user32.GetForegroundWindow(), 6)  # SW_MINIMIZE
    time.sleep(0.3)
    pyautogui.hotkey("win", "s")
    time.sleep(0.8)
    pyperclip.copy(name_raw)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.5)
    pyautogui.press("enter")
    return f"'{name_raw}' dibuka via Windows Search."

# ─── APP MAP ───────────────────────────────────────────────────────────────────
# Keyword aliases → command. Satu app bisa punya banyak alias.
APP_MAP = {
    # ── Browser (pasti di PATH setelah install) ──
    "chrome":               "start chrome",
    "google chrome":        "start chrome",
    "firefox":              "start firefox",
    "edge":                 "start msedge",
    "microsoft edge":       "start msedge",
    # ── Windows built-in (100% ada di PATH) ──
    "explorer":             "start explorer",
    "file explorer":        "start explorer",
    "file manager":         "start explorer",
    "files":                "start explorer",
    "this pc":              "start explorer",
    "folder":               "start explorer",
    "notepad":              "start notepad",
    "calc":                 "start calc",
    "calculator":           "start calc",
    "kalkulator":           "start calc",
    "paint":                "start mspaint",
    "mspaint":              "start mspaint",
    "cmd":                  "start cmd",
    "command prompt":       "start cmd",
    "terminal":             "start cmd",
    "powershell":           "start powershell",
    "task manager":         "start taskmgr",
    "taskmgr":              "start taskmgr",
    "regedit":              "start regedit",
    "registry":             "start regedit",
    "msconfig":             "start msconfig",
    "device manager":       "start devmgmt.msc",
    "disk management":      "start diskmgmt.msc",
    "services":             "start services.msc",
    # ── Dev (hanya kalau di PATH) ──
    "vscode":               "start code",
    "vs code":              "start code",
    "visual studio code":   "start code",
    "code":                 "start code",
    # ── Office (kalau terinstall via installer resmi) ──
    "word":                 "start winword",
    "excel":                "start excel",
    "powerpoint":           "start powerpnt",
    "outlook":              "start outlook",
    # ── Windows apps (URI scheme — tidak butuh PATH) ──
    "settings":             "start ms-settings:",
    "pengaturan":           "start ms-settings:",
    "snipping tool":        "start ms-screenclip:",
    "snip":                 "start ms-screenclip:",
    "kamera":               "start microsoft.windows.camera:",
    "camera":               "start microsoft.windows.camera:",
    "store":                "start ms-windows-store:",
    "windows store":        "start ms-windows-store:",
    "maps":                 "start bingmaps:",
    "mail":                 "start outlookmail:",
    "email":                "start outlookmail:",
    "calendar":             "start outlookcal:",
    "clock":                "start ms-clock:",
    "weather":              "start bingweather:",
    "sticky notes":         "start ms-stickynotes:",
    "photos":               "start ms-photos:",
    "media player":         "start wmplayer",
    # ── Communication via URI (tidak butuh PATH) ──
    "whatsapp":             'start "" "whatsapp:"',
    "discord":              'start "" "discord:"',
    "telegram":             'start "" "tg:"',
}

# Hard-coded path untuk app populer yang tidak ada di PATH Windows
def _build_known_paths() -> dict:
    """
    Hard-coded paths + glob untuk app yang tidak ada di PATH.
    Pakai glob agar bisa handle versi yang berubah (app-1.0.9182, app-1.0.9200, dll).
    """
    pf   = Path(os.environ.get("PROGRAMFILES",      "C:/Program Files"))
    pf86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
    lapp = Path(os.environ.get("LOCALAPPDATA",       "C:/Users/User/AppData/Local"))
    app  = Path(os.environ.get("APPDATA",            "C:/Users/User/AppData/Roaming"))

    def glob_first(base: Path, pattern: str):
        """Cari file dengan glob, return list path yang exist."""
        try:
            return sorted(base.glob(pattern), reverse=True)  # versi terbaru dulu
        except Exception:
            return []

    known = {
        # ── Gaming ──────────────────────────────────────────────────────────
        "steam": (
            [pf86/"Steam/Steam.exe", pf/"Steam/Steam.exe"] +
            glob_first(Path("C:/"), "Program Files*/Steam/Steam.exe")
        ),
        "epicgames": (
            glob_first(pf,   "Epic Games/Launcher/Portal/Binaries/Win*/EpicGamesLauncher.exe") +
            glob_first(pf86, "Epic Games/Launcher/Portal/Binaries/Win*/EpicGamesLauncher.exe")
        ),
        "epic": [],  # akan diisi dari epicgames
        "battlenet": [pf86/"Battle.net/Battle.net.exe", pf/"Battle.net/Battle.net.exe"],
        "minecraft": (
            [pf86/"Minecraft Launcher/MinecraftLauncher.exe"] +
            glob_first(lapp, "Packages/Microsoft.4297127D64EC6_8wekyb3d8bbwe/LocalCache/Local/runtime/**/javaw.exe")
        ),
        "riotclient": (
            glob_first(pf,   "Riot Games/Riot Client/RiotClientServices.exe") +
            glob_first(pf86, "Riot Games/Riot Client/RiotClientServices.exe")
        ),
        "valorant":         [],  # sama dengan riotclient
        "lol":              [],  # sama dengan riotclient
        "leagueoflegends":  [],  # sama dengan riotclient

        # ── Media ────────────────────────────────────────────────────────────
        "vlc": [pf/"VideoLAN/VLC/vlc.exe", pf86/"VideoLAN/VLC/vlc.exe"],
        "obs": (
            glob_first(pf,   "obs-studio/bin/64bit/obs64.exe") +
            glob_first(pf,   "OBS Studio/bin/64bit/obs64.exe") +
            glob_first(pf86, "obs-studio/bin/64bit/obs64.exe") +
            [pf/"obs-studio/bin/64bit/obs64.exe",
             pf/"OBS Studio/bin/64bit/obs64.exe",
             pf86/"obs-studio/bin/64bit/obs64.exe"]
        ),
        "obsstudio":        [],  # alias obs

        # ── Communication ────────────────────────────────────────────────────
        "discordptb": (
            glob_first(lapp, "DiscordPTB/app-*/DiscordPTB.exe") +
            [lapp/"DiscordPTB/Update.exe"]
        ),
        "ptb":              [],  # alias discordptb
        "discordcanary": (
            glob_first(lapp, "DiscordCanary/app-*/DiscordCanary.exe") +
            [lapp/"DiscordCanary/Update.exe"]
        ),
        "telegram":         [app/"Telegram Desktop/Telegram.exe"] + glob_first(lapp, "Programs/Telegram Desktop/Telegram.exe"),
        "whatsapp":         [lapp/"WhatsApp/WhatsApp.exe", app/"WhatsApp/WhatsApp.exe"],
        "zoom":             [app/"Zoom/bin/Zoom.exe", pf/"Zoom/bin/Zoom.exe"],
        "signal":           glob_first(lapp, "Programs/signal-desktop/Signal.exe"),
        "slack":            glob_first(lapp, "Programs/slack/slack.exe"),
        "teams":            glob_first(lapp, "Microsoft/Teams/current/Teams.exe"),

        # ── Dev Tools ────────────────────────────────────────────────────────
        "vscode":           [lapp/"Programs/Microsoft VS Code/Code.exe", pf/"Microsoft VS Code/Code.exe"],
        "cursor":           glob_first(lapp, "Programs/cursor/Cursor.exe") + glob_first(lapp, "cursor/Cursor.exe"),
        "androidstudio":    glob_first(pf, "Android/Android Studio/bin/studio64.exe"),
        "postman":          glob_first(lapp, "Postman/Postman.exe"),
        "insomnia":         glob_first(lapp, "Programs/insomnia/Insomnia.exe"),
        "dbeaver":          [pf/"DBeaver/dbeaver.exe", pf86/"DBeaver/dbeaver.exe"],
        "heidisql":         [pf/"HeidiSQL/heidisql.exe", pf86/"HeidiSQL/heidisql.exe"],
        "figma":            glob_first(lapp, "Figma/Figma.exe"),
        "notion":           glob_first(lapp, "Programs/Notion/Notion.exe"),
        "gitkraken":        glob_first(lapp, "gitkraken/app-*/GitKraken.exe"),
        "tabby":            glob_first(lapp, "Programs/tabby/Tabby.exe"),
        "warp":             glob_first(lapp, "Programs/warp/Warp.exe"),

        # ── Server/Dev Local ─────────────────────────────────────────────────
        "xampp":            [Path("C:/xampp/xampp-control.exe")],
        "laragon":          [Path("C:/laragon/laragon.exe")],
        "wampserver":       [Path("C:/wamp64/wampmanager.exe"), Path("C:/wamp/wampmanager.exe")],

        # ── Utilities ────────────────────────────────────────────────────────
        "winrar":           [pf/"WinRAR/WinRAR.exe", pf86/"WinRAR/WinRAR.exe"],
        "7zip":             [pf/"7-Zip/7zFM.exe", pf86/"7-Zip/7zFM.exe"],
        "notepadpp":        [pf/"Notepad++/notepad++.exe", pf86/"Notepad++/notepad++.exe"],
        "itunes":           [pf/"iTunes/iTunes.exe", pf86/"iTunes/iTunes.exe"],
        "spotify":          [app/"Spotify/Spotify.exe"],
    }

    # Isi alias yang kosong
    known["epic"]           = known["epicgames"]
    known["obsstudio"]      = known["obs"]
    known["ptb"]            = known["discordptb"]
    known["valorant"]       = known["riotclient"]
    known["lol"]            = known["riotclient"]
    known["leagueoflegends"]= known["riotclient"]

    return known

KNOWN_APP_PATHS = _build_known_paths()

# ─── SHORTCUT (.lnk) SCANNER ───────────────────────────────────────────────────
def _scan_shortcuts() -> dict:
    """
    Scan semua shortcut .lnk di Start Menu Windows.
    Ini adalah cara paling reliable untuk menemukan SEMUA app terinstall
    termasuk Discord PTB, game launcher, tools — apapun yang ada di Start Menu.
    Return: { normalized_name: lnk_path }
    """
    found = {}
    start_menu_dirs = [
        Path(os.environ.get("APPDATA",""))  / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA","C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    for base in start_menu_dirs:
        if not base.exists():
            continue
        try:
            for lnk in base.rglob("*.lnk"):
                key = _normalize(lnk.stem)
                if key and key not in found:
                    found[key] = str(lnk)
        except Exception:
            continue
    return found

_shortcut_cache: dict = {}

def _load_shortcut_cache():
    global _shortcut_cache
    _shortcut_cache = _scan_shortcuts()

# Load di background agar tidak delay startup
threading.Thread(target=_load_shortcut_cache, daemon=True).start()

# ─── TOOLS DEFINITION ──────────────────────────────────────────────────────────
TOOLS = [
  {"type":"function","function":{
    "name":"spotify_play",
    "description":"Buka Spotify dan putar lagu/artis yang diminta.",
    "parameters":{"type":"object","properties":{"query":{"type":"string"}}}}},
  {"type":"function","function":{
    "name":"youtube_play",
    "description":"Cari dan putar video/lagu di YouTube.",
    "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
  {"type":"function","function":{
    "name":"open_app",
    "description":"Buka aplikasi: chrome, firefox, edge, notepad, vscode, cmd, powershell, explorer, calculator, paint, word, excel, powerpoint, task manager, whatsapp, discord, telegram, vlc, steam, obs, settings, snipping tool, camera, store, maps, mail, spotify, minecraft.",
    "parameters":{"type":"object","properties":{"app":{"type":"string"}},"required":["app"]}}},
  {"type":"function","function":{
    "name":"open_url",
    "description":"Buka website/URL di browser.",
    "parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
  {"type":"function","function":{
    "name":"search_google",
    "description":"Cari sesuatu di Google.",
    "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
  {"type":"function","function":{
    "name":"search_youtube",
    "description":"Buka halaman hasil pencarian YouTube (tanpa auto-play).",
    "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
  {"type":"function","function":{
    "name":"type_text",
    "description":"Ketikkan teks ke aplikasi aktif.",
    "parameters":{"type":"object","properties":{"text":{"type":"string"},"press_enter":{"type":"boolean"}},"required":["text"]}}},
  {"type":"function","function":{
    "name":"press_key",
    "description":"Tekan tombol keyboard, contoh: ctrl+c, alt+tab, win+d, f5, escape, ctrl+shift+esc.",
    "parameters":{"type":"object","properties":{"keys":{"type":"string"}},"required":["keys"]}}},
  {"type":"function","function":{
    "name":"click",
    "description":"Klik di koordinat layar x,y.",
    "parameters":{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"},"button":{"type":"string","description":"left, right, double"}},"required":["x","y"]}}},
  {"type":"function","function":{
    "name":"scroll",
    "description":"Scroll halaman.",
    "parameters":{"type":"object","properties":{"direction":{"type":"string","description":"up atau down"},"amount":{"type":"integer"}},"required":["direction"]}}},
  {"type":"function","function":{
    "name":"screenshot",
    "description":"Ambil screenshot dan simpan ke Desktop.",
    "parameters":{"type":"object","properties":{"filename":{"type":"string"}}}}},
  {"type":"function","function":{
    "name":"run_cmd",
    "description":"Jalankan perintah Command Prompt. show_window=true untuk buka terminal baru.",
    "parameters":{"type":"object","properties":{"command":{"type":"string"},"show_window":{"type":"boolean"}},"required":["command"]}}},
  {"type":"function","function":{
    "name":"run_powershell",
    "description":"Jalankan perintah PowerShell.",
    "parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
  {"type":"function","function":{
    "name":"run_python",
    "description":"Jalankan kode Python dan kembalikan hasilnya.",
    "parameters":{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]}}},
  {"type":"function","function":{
    "name":"read_file",
    "description":"Baca isi file teks.",
    "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
  {"type":"function","function":{
    "name":"write_file",
    "description":"Tulis atau buat file teks.",
    "parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"},"append":{"type":"boolean"}},"required":["path","content"]}}},
  {"type":"function","function":{
    "name":"list_dir",
    "description":"Tampilkan isi folder.",
    "parameters":{"type":"object","properties":{"path":{"type":"string"}}}}},
  {"type":"function","function":{
    "name":"system_info",
    "description":"Info sistem: cpu, ram, disk, battery, network, processes, atau all.",
    "parameters":{"type":"object","properties":{"type":{"type":"string"}}}}},
  {"type":"function","function":{
    "name":"kill_process",
    "description":"Hentikan proses berdasarkan nama, contoh: chrome.exe",
    "parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
  {"type":"function","function":{
    "name":"clipboard",
    "description":"Operasi clipboard: get atau set.",
    "parameters":{"type":"object","properties":{"action":{"type":"string"},"text":{"type":"string"}},"required":["action"]}}},
  {"type":"function","function":{
    "name":"volume",
    "description":"Atur volume: up, down, mute, unmute, set (level 0-100).",
    "parameters":{"type":"object","properties":{"action":{"type":"string"},"level":{"type":"integer"},"steps":{"type":"integer"}},"required":["action"]}}},
  {"type":"function","function":{
    "name":"media_control",
    "description":"Kontrol media: play_pause, next, previous, stop.",
    "parameters":{"type":"object","properties":{"action":{"type":"string"}},"required":["action"]}}},
  {"type":"function","function":{
    "name":"window_control",
    "description":"Kontrol jendela aktif: minimize, maximize, close, fullscreen, restore, switch (alt+tab).",
    "parameters":{"type":"object","properties":{"action":{"type":"string"}},"required":["action"]}}},
  {"type":"function","function":{
    "name":"brightness",
    "description":"Atur kecerahan layar 0-100.",
    "parameters":{"type":"object","properties":{"level":{"type":"integer"}},"required":["level"]}}},
  {"type":"function","function":{
    "name":"get_weather",
    "description":"Cek cuaca kota.",
    "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}},
  {"type":"function","function":{
    "name":"get_time",
    "description":"Dapatkan waktu dan tanggal sekarang.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{
    "name":"set_reminder",
    "description":"Buat pengingat popup dalam X menit.",
    "parameters":{"type":"object","properties":{"message":{"type":"string"},"minutes":{"type":"number"}},"required":["message","minutes"]}}},
  {"type":"function","function":{
    "name":"lock_screen",
    "description":"Kunci layar.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{
    "name":"shutdown_restart",
    "description":"Shutdown atau restart komputer.",
    "parameters":{"type":"object","properties":{"action":{"type":"string","description":"shutdown atau restart"},"delay":{"type":"integer","description":"detik"}},"required":["action"]}}},
  {"type":"function","function":{
    "name":"screen_size",
    "description":"Dapatkan resolusi layar.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{
    "name":"move_mouse",
    "description":"Pindahkan kursor ke koordinat x,y.",
    "parameters":{"type":"object","properties":{"x":{"type":"integer"},"y":{"type":"integer"}},"required":["x","y"]}}},
  {"type":"function","function":{
    "name":"ip_info",
    "description":"Dapatkan info IP publik dan lokasi.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{
    "name":"download_file",
    "description":"Download file dari URL ke folder lokal.",
    "parameters":{"type":"object","properties":{"url":{"type":"string"},"save_path":{"type":"string"}},"required":["url"]}}},
  {"type":"function","function":{
    "name":"create_folder",
    "description":"Buat folder baru.",
    "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
  {"type":"function","function":{
    "name":"search_files",
    "description":"Cari file berdasarkan nama/pattern di folder.",
    "parameters":{"type":"object","properties":{"pattern":{"type":"string"},"folder":{"type":"string"}},"required":["pattern"]}}},
  {"type":"function","function":{
    "name":"get_clipboard_image",
    "description":"Simpan gambar dari clipboard ke file.",
    "parameters":{"type":"object","properties":{"save_path":{"type":"string"}}}}},
  {"type":"function","function":{
    "name":"get_battery",
    "description":"Cek status baterai.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{
    "name":"notify",
    "description":"Tampilkan notifikasi popup Windows.",
    "parameters":{"type":"object","properties":{"title":{"type":"string"},"message":{"type":"string"}},"required":["title","message"]}}},
  {"type":"function","function":{
    "name":"focus_window",
    "description":"Fokuskan / bawa ke depan window aplikasi berdasarkan nama, contoh: 'Chrome', 'Notepad', 'Discord'.",
    "parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
  {"type":"function","function":{
    "name":"list_windows",
    "description":"Tampilkan semua window yang sedang terbuka.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{
    "name":"app_cache_info",
    "description":"Tampilkan info cache aplikasi yang sudah diindex JARVIS.",
    "parameters":{"type":"object","properties":{}}}},
]

# ─── TOOL EXECUTOR ─────────────────────────────────────────────────────────────
def _exec(name: str, args: dict) -> str:
    try:
        # ── Media ──────────────────────────────────────────────────────────────
        if name == "spotify_play":
            return open_spotify(args.get("query",""))

        if name == "youtube_play":
            q = args["query"]
            video_url = _youtube_get_url(q)
            if not video_url:
                # Fallback: buka halaman search YouTube — bukan Google
                video_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}"
            _open_url_direct(video_url)
            label = "langsung" if "watch?v=" in video_url else "halaman search"
            return f"YouTube: membuka '{q}' ({label})."

        if name == "search_youtube":
            q = args["query"]
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}")
            return f"YouTube: hasil pencarian '{q}' dibuka."

        # ── App & Web ──────────────────────────────────────────────────────────
        if name == "open_app":
            return _smart_open_app(args["app"])

        if name == "open_url":
            url = args["url"]
            if not url.startswith("http"): url = "https://" + url
            _open_url_direct(url)
            return f"URL dibuka: {url}"

        if name == "search_google":
            webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(args['query'])}")
            return f"Google: '{args['query']}'"

        # ── Keyboard & Mouse ───────────────────────────────────────────────────
        if name == "type_text":
            time.sleep(0.25)
            pyperclip.copy(args["text"])
            pyautogui.hotkey("ctrl","v")
            if args.get("press_enter"): time.sleep(0.1); pyautogui.press("enter")
            return "Teks diketik."

        if name == "press_key":
            k = args["keys"].lower().replace(" ","")
            parts = k.split("+")
            if len(parts) > 1: pyautogui.hotkey(*parts)
            else: pyautogui.press(k)
            return f"Tombol '{args['keys']}' ditekan."

        if name == "click":
            x, y = args["x"], args["y"]
            btn = args.get("button","left")
            pyautogui.moveTo(x, y, duration=0.15)
            if btn == "double":   pyautogui.doubleClick()
            elif btn == "right":  pyautogui.rightClick()
            else:                 pyautogui.click()
            return f"Klik ({x},{y})."

        if name == "scroll":
            amt = args.get("amount", 5)
            pyautogui.scroll(amt * 120 if args["direction"]=="up" else -amt * 120)
            return f"Scroll {args['direction']}."

        if name == "move_mouse":
            pyautogui.moveTo(args["x"], args["y"], duration=0.2)
            return f"Mouse pindah ke ({args['x']},{args['y']})."

        if name == "screen_size":
            w,h = pyautogui.size()
            return f"Resolusi: {w}×{h}"

        # ── Screenshot ────────────────────────────────────────────────────────
        if name == "screenshot":
            fn = args.get("filename", f"ss_{int(time.time())}.png")
            p = Path.home()/"Desktop"/fn
            pyautogui.screenshot().save(str(p))
            return f"Screenshot disimpan: {p}"

        # ── CMD / PowerShell / Python ─────────────────────────────────────────
        if name == "run_cmd":
            if args.get("show_window"):
                subprocess.Popen(f'start cmd /k "{args["command"]}"', shell=True)
                return "CMD dibuka."
            r = subprocess.run(args["command"], shell=True, capture_output=True, text=True, timeout=30)
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip()[:2000] or "(no output)"

        if name == "run_powershell":
            r = subprocess.run(["powershell","-Command",args["command"]],
                               capture_output=True, text=True, timeout=30)
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip()[:2000] or "(no output)"

        if name == "run_python":
            import io, contextlib
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    exec(args["code"], {})
            except Exception as e:
                buf.write(f"\nError: {e}")
            return buf.getvalue()[:2000] or "(no output)"

        # ── File System ───────────────────────────────────────────────────────
        if name == "read_file":
            p = Path(args["path"])
            return p.read_text(encoding="utf-8",errors="ignore")[:3000] if p.exists() else "File tidak ditemukan."

        if name == "write_file":
            p = Path(args["path"]); p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a" if args.get("append") else "w", encoding="utf-8") as f:
                f.write(args["content"])
            return f"File ditulis: {p}"

        if name == "list_dir":
            p = Path(args.get("path", str(Path.home()/"Desktop")))
            if not p.exists(): return "Folder tidak ditemukan."
            items = sorted(p.iterdir(), key=lambda x:(not x.is_dir(), x.name.lower()))
            return "\n".join(("📁 " if i.is_dir() else "📄 ")+i.name for i in items[:60])

        if name == "create_folder":
            p = Path(args["path"]); p.mkdir(parents=True, exist_ok=True)
            return f"Folder dibuat: {p}"

        if name == "search_files":
            folder = Path(args.get("folder", str(Path.home())))
            pattern = args["pattern"]
            results = list(folder.rglob(pattern))[:40]
            return "\n".join(str(r) for r in results) if results else "Tidak ditemukan."

        if name == "download_file":
            save = args.get("save_path", str(Path.home()/"Downloads"/Path(args["url"]).name))
            r = requests.get(args["url"], timeout=30, stream=True)
            with open(save, "wb") as f:
                for chunk in r.iter_content(8192): f.write(chunk)
            return f"Didownload: {save}"

        # ── System ────────────────────────────────────────────────────────────
        if name == "system_info":
            t = args.get("type","all")
            info = {}
            if t in ("cpu","all"):
                info["CPU"] = f"{psutil.cpu_percent(1):.1f}% | {psutil.cpu_count()} cores | {psutil.cpu_freq().current:.0f} MHz"
            if t in ("ram","all"):
                m = psutil.virtual_memory()
                info["RAM"] = f"{m.percent:.1f}% | {m.used//1024**2} MB / {m.total//1024**2} MB"
            if t in ("disk","all"):
                d = psutil.disk_usage("/")
                info["Disk C:"] = f"{d.percent:.1f}% | {d.used//1024**3} GB / {d.total//1024**3} GB"
            if t in ("battery","all"):
                b = psutil.sensors_battery()
                info["Baterai"] = f"{b.percent:.0f}% {'⚡ mengisi' if b.power_plugged else '🔋 baterai'}" if b else "N/A"
            if t in ("network","all"):
                n = psutil.net_io_counters()
                info["Network"] = f"↑ {n.bytes_sent//1024**2} MB  ↓ {n.bytes_recv//1024**2} MB"
            if t in ("processes",):
                procs = sorted([(p.info["name"],p.info["pid"],p.info["memory_info"].rss//1024//1024)
                                for p in psutil.process_iter(["name","pid","memory_info"])
                                if p.info.get("memory_info")], key=lambda x:-x[2])[:20]
                return "\n".join(f"{n:30s} PID:{pid:6d}  {m:4d} MB" for n,pid,m in procs)
            return json.dumps(info, ensure_ascii=False, indent=2)

        if name == "get_battery":
            b = psutil.sensors_battery()
            if not b: return "Info baterai tidak tersedia."
            return f"Baterai: {b.percent:.0f}% | {'Mengisi daya ⚡' if b.power_plugged else 'Menggunakan baterai 🔋'} | Sisa: {int(b.secsleft//60) if b.secsleft>0 else '?'} menit"

        if name == "kill_process":
            n = args["name"]
            if not n.endswith(".exe"): n += ".exe"
            r = subprocess.run(f"taskkill /f /im {n}", shell=True, capture_output=True, text=True)
            return (r.stdout or r.stderr).strip()

        if name == "ip_info":
            r = requests.get("https://ipinfo.io/json", timeout=8)
            d = r.json()
            return f"IP: {d.get('ip')} | Kota: {d.get('city')} | Negara: {d.get('country')} | ISP: {d.get('org')}"

        # ── Clipboard ─────────────────────────────────────────────────────────
        if name == "clipboard":
            if args["action"] == "get":
                return pyperclip.paste()[:1000] or "Clipboard kosong."
            pyperclip.copy(args.get("text",""))
            return "Clipboard diisi."

        if name == "get_clipboard_image":
            save = args.get("save_path", str(Path.home()/"Desktop"/"clipboard_img.png"))
            r = subprocess.run(
                ["powershell","-c","Add-Type -Assembly 'System.Windows.Forms'; "
                 f"[System.Windows.Forms.Clipboard]::GetImage().Save('{save}')"],
                capture_output=True, timeout=8)
            return f"Gambar clipboard disimpan: {save}"

        # ── Audio / Media ─────────────────────────────────────────────────────
        if name == "volume":
            act = args["action"].lower()
            steps = args.get("steps",3)
            if act == "up":
                for _ in range(steps): pyautogui.press("volumeup")
            elif act == "down":
                for _ in range(steps): pyautogui.press("volumedown")
            elif act in ("mute","unmute"): pyautogui.press("volumemute")
            elif act == "set":
                level = max(0,min(100,args.get("level",50)))
                ps = (f"$obj = New-Object -ComObject WScript.Shell; "
                      f"1..50 | %{{ $obj.SendKeys([char]174) }}; "
                      f"1..{level//2} | %{{ $obj.SendKeys([char]175) }}")
                subprocess.run(["powershell","-c",ps], capture_output=True)
            return f"Volume {act}."

        if name == "media_control":
            km = {"play_pause":"playpause","next":"nexttrack","previous":"prevtrack","stop":"stop"}
            pyautogui.press(km.get(args["action"],"playpause"))
            return f"Media: {args['action']}."

        # ── Window ────────────────────────────────────────────────────────────
        if name == "window_control":
            act = args["action"].lower()
            {
             "minimize":   lambda: pyautogui.hotkey("win","down"),
             "maximize":   lambda: pyautogui.hotkey("win","up"),
             "close":      lambda: pyautogui.hotkey("alt","f4"),
             "fullscreen": lambda: pyautogui.press("f11"),
             "restore":    lambda: pyautogui.hotkey("win","down"),
             "switch":     lambda: pyautogui.hotkey("alt","tab"),
            }.get(act, lambda: None)()
            return f"Window {act}."

        # ── Utilities ─────────────────────────────────────────────────────────
        if name == "brightness":
            lv = max(0,min(100,args["level"]))
            subprocess.run(["powershell","-c",
                f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                f".WmiSetBrightness(1,{lv})"], capture_output=True, timeout=8)
            return f"Kecerahan: {lv}%."

        if name == "get_weather":
            r = requests.get(f"https://wttr.in/{urllib.parse.quote(args['city'])}?format=3", timeout=8)
            return r.text.strip() if r.ok else "Gagal mengambil data cuaca."

        if name == "get_time":
            now = datetime.now()
            return f"{now.strftime('%A, %d %B %Y')} — pukul {now.strftime('%H:%M:%S')} WIB"

        if name == "set_reminder":
            msg, mins = args["message"], float(args["minutes"])
            def _r():
                time.sleep(mins*60)
                subprocess.Popen(["powershell","-c",
                    f'Add-Type -AssemblyName PresentationFramework; '
                    f'[System.Windows.MessageBox]::Show("{msg}","JARVIS · Reminder","OK","Information")'])
            threading.Thread(target=_r, daemon=True).start()
            return f"Reminder '{msg}' dalam {mins} menit."

        if name == "lock_screen":
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return "Layar dikunci."

        if name == "shutdown_restart":
            act = args["action"].lower(); delay = args.get("delay",30)
            subprocess.Popen(f"shutdown /{act[0]} /t {delay}", shell=True)
            return f"{act.capitalize()} dalam {delay} detik."

        if name == "notify":
            title = args["title"]; msg = args["message"]
            subprocess.Popen(["powershell","-c",
                f'Add-Type -AssemblyName PresentationFramework; '
                f'[System.Windows.MessageBox]::Show("{msg}","{title}","OK","Information")'])
            return f"Notifikasi: {title}"

        # ── UI Automation ─────────────────────────────────────────────────────
        if name == "focus_window":
            return _focus_window_by_name(args["name"])

        if name == "list_windows":
            return _list_open_windows()

        if name == "app_cache_info":
            return _app_cache_info()

        return f"[unknown tool: {name}]"
    except Exception as e:
        return f"[ERROR {name}]: {e}"


# ─── UI AUTOMATION HELPERS ─────────────────────────────────────────────────────
def _list_open_windows() -> str:
    """Daftar semua window yang terbuka saat ini."""
    try:
        import ctypes
        import ctypes.wintypes
        EnumWindows        = ctypes.windll.user32.EnumWindows
        GetWindowTextW     = ctypes.windll.user32.GetWindowTextW
        IsWindowVisible    = ctypes.windll.user32.IsWindowVisible
        GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW

        windows = []
        def callback(hwnd, _):
            if IsWindowVisible(hwnd):
                length = GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title:
                        windows.append(title)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        EnumWindows(WNDENUMPROC(callback), 0)
        if windows:
            return "Window terbuka:\n" + "\n".join(f"  • {w}" for w in windows[:40])
        return "Tidak ada window terdeteksi."
    except Exception as e:
        # Fallback PowerShell
        try:
            r = subprocess.run(
                ["powershell", "-c",
                 "Get-Process | Where-Object {$_.MainWindowTitle} | "
                 "Select-Object -ExpandProperty MainWindowTitle"],
                capture_output=True, text=True, timeout=8
            )
            return "Window terbuka:\n" + r.stdout.strip()
        except Exception:
            return f"[list_windows error] {e}"

def _focus_window_by_name(name: str) -> str:
    """Fokuskan window berdasarkan partial name match."""
    name_lower = name.lower()

    # Coba win32gui dulu (pywin32)
    try:
        import win32gui, win32con
        def callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if name_lower in title.lower():
                    result.append(hwnd)
            return True
        found_hwnds = []
        win32gui.EnumWindows(callback, found_hwnds)
        if found_hwnds:
            hwnd = found_hwnds[0]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return f"Window '{name}' difokuskan."
        return f"Window '{name}' tidak ditemukan."
    except ImportError:
        pass
    except Exception as e:
        print(f"[focus win32gui] {e}")

    # Fallback PowerShell AppActivate
    try:
        result = subprocess.run(
            ["powershell", "-c",
             f"(New-Object -ComObject WScript.Shell).AppActivate('{name}')"],
            capture_output=True, text=True, timeout=5
        )
        time.sleep(0.4)
        return f"Window '{name}' difokuskan (PowerShell)."
    except Exception as e:
        return f"[focus_window error] {e}"

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""Kamu adalah J.A.R.V.I.S v7 (Just A Rather Very Intelligent System) — asisten AI personal milik Tuan Anjar, developer muda dari Arqonara, Indonesia. Kamu bisa membuka SEMUA aplikasi di komputer (Steam, game, tools, browser, editor, dll), memutar YouTube tanpa iklan, dan mengontrol window yang sedang terbuka.

KEPRIBADIAN & GAYA:
• Profesional, tegas, sedikit formal — seperti asisten eksekutif kelas satu
• Singkat dan efisien, tidak bertele-tele
• Sebut user "Tuan" atau "Tuan Anjar"
• Percaya diri dan proaktif — eksekusi tanpa meminta izin berulang

ATURAN EKSEKUSI (KRITIS — TIDAK BOLEH DILANGGAR):
1. SELALU gunakan tool yang tepat — jangan hanya jawab teks jika ada tool yang bisa melakukannya
2. "putar/play X di spotify" → spotify_play
3. "putar/play X di youtube" atau tanpa platform → youtube_play
4. "buka [app/nama apapun]" → WAJIB gunakan open_app, JANGAN TANYA apakah yakin
5. "buka situs/web" → open_url
6. "cari X" tanpa platform → search_google
7. Setelah tool selesai, konfirmasi singkat 1 kalimat
8. Untuk tugas kompleks, jalankan beberapa tool secara berurutan tanpa menunggu konfirmasi
9. Jangan sebut nama tool/fungsi dalam jawaban ke user
10. Jika input ambigu, pilih interpretasi paling masuk akal dan LANGSUNG eksekusi
11. DILARANG KERAS: jangan pernah tanya "apakah Anda ingin membuka X?" — langsung buka saja
12. "buka [apapun]" selalu → open_app, termasuk nama game, PTB, canary, atau varian apapun
13. Jika app tidak ditemukan di cache, sistem akan otomatis cari via Windows Search — TETAP eksekusi
14. TIDAK PERLU konfirmasi user untuk membuka aplikasi apapun

SAAT INI: {datetime.now().strftime('%A, %d %B %Y — %H:%M WIB')}
SISTEM: Windows | Spotify: {"terdeteksi ✓" if SPOTIFY_EXE else "fallback mode"}
"""

history = []

# ─── GUI ───────────────────────────────────────────────────────────────────────
class JarvisGUI:
    # ── Color Palette ──────────────────────────────────────────────────────────
    BG          = "#08090d"
    BG2         = "#0c0e14"
    PANEL       = "#0f1117"
    PANEL2      = "#12141c"
    BORDER      = "#1a1d28"
    BORDER2     = "#222638"
    BORDER_GLOW = "#2a3050"
    CYAN        = "#4fc3f7"
    CYAN2       = "#29b6f6"
    CYAN_DIM    = "#1a4a6b"
    CYAN_GLOW   = "#0d2d42"
    PURPLE      = "#ce93d8"
    PURPLE2     = "#ba68c8"
    GOLD        = "#ffd54f"
    GOLD2       = "#ffca28"
    RED         = "#ef5350"
    GREEN       = "#66bb6a"
    TEXT        = "#b0bec5"
    TEXT2       = "#546e7a"
    TEXT3       = "#2d3d48"
    WHITE       = "#eceff1"

    def __init__(self):
        if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-GANTI"):
            raise ValueError("Isi OPENAI_API_KEY di file .env terlebih dahulu!")
        self.client   = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.muted    = False
        self.busy     = False
        self.tts_on   = True
        self.recording= False
        self._wave    = [2.0] * 80
        self._phase   = 0.0
        self._pulse   = 0.0
        self._build()

    def _build(self):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S  ·  ArqoAssist")
        self.root.geometry("1100x780")
        self.root.configure(bg=self.BG)
        self.root.minsize(840, 600)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # Rounded window effect (Windows 11)
        try:
            import ctypes
            val = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.windll.user32.GetParent(self.root.winfo_id()),
                33,
                ctypes.byref(val),
                ctypes.sizeof(val)
            )
        except Exception:
            pass

        self._setup_styles()
        self._make_ui()
        self._start_listener()
        self._tick()
        self.root.mainloop()

    def _setup_styles(self):
        st = ttk.Style()
        st.theme_use("clam")

    # ── UI Layout ──────────────────────────────────────────────────────────────
    def _make_ui(self):
        r = self.root

        # Top glow line
        tk.Frame(r, bg=self.CYAN, height=1).pack(fill="x")
        tk.Frame(r, bg=self.CYAN_GLOW, height=2).pack(fill="x")
        tk.Frame(r, bg=self.BG2, height=1).pack(fill="x")

        # ── HEADER ────────────────────────────────────────────────────────────
        hdr = tk.Frame(r, bg=self.BG2)
        hdr.pack(fill="x", padx=0, pady=0)

        left = tk.Frame(hdr, bg=self.BG2)
        left.pack(side="left", padx=32, pady=18)

        # Logo row
        logo_row = tk.Frame(left, bg=self.BG2)
        logo_row.pack(anchor="w")

        # Glowing dot
        tk.Label(logo_row, text="◉ ", fg=self.CYAN, bg=self.BG2,
                 font=("Segoe UI", 18)).pack(side="left", pady=(2,0))

        tk.Label(logo_row, text="J.A.R.V.I.S",
                 fg=self.CYAN, bg=self.BG2,
                 font=("Segoe UI", 24, "bold")).pack(side="left")

        tk.Label(left, text="JUST A RATHER VERY INTELLIGENT SYSTEM   ·   ARQONARA  v6.0",
                 fg=self.TEXT3, bg=self.BG2,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(3,0))

        # Right controls
        ctrl = tk.Frame(hdr, bg=self.BG2)
        ctrl.pack(side="right", padx=32, pady=18)

        # TTS toggle
        self.tts_btn = tk.Button(
            ctrl, text="🔊 VOICE",
            command=self._toggle_tts,
            bg=self.CYAN_GLOW, fg=self.CYAN,
            activebackground=self.CYAN_DIM,
            activeforeground=self.CYAN,
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=14, pady=7, cursor="hand2"
        )
        self.tts_btn.pack(side="right", padx=(8,0))

        # Status pill
        self.pill = tk.Frame(ctrl, bg=self.PANEL2,
                              highlightbackground=self.BORDER_GLOW,
                              highlightthickness=1)
        self.pill.pack(side="right")

        self._dot = tk.Label(self.pill, text="◉",
                             fg=self.CYAN, bg=self.PANEL2,
                             font=("Segoe UI", 11))
        self._dot.pack(side="left", padx=(12,4), pady=9)

        self._stlbl = tk.Label(self.pill, text="ONLINE",
                               fg=self.CYAN, bg=self.PANEL2,
                               font=("Segoe UI", 9, "bold"), padx=4)
        self._stlbl.pack(side="left", padx=(0,14))

        # ── SEPARATOR ─────────────────────────────────────────────────────────
        tk.Frame(r, bg=self.BORDER, height=1).pack(fill="x")
        # Accent line center
        sep2 = tk.Frame(r, bg=self.BG2)
        sep2.pack(fill="x")
        tk.Frame(sep2, bg=self.CYAN, height=1).pack(fill="x", padx=180)
        tk.Frame(r, bg=self.BORDER, height=1).pack(fill="x")

        # ── WAVEFORM ──────────────────────────────────────────────────────────
        wave_container = tk.Frame(r, bg=self.BG2)
        wave_container.pack(fill="x", padx=0, pady=0)

        self.canvas = tk.Canvas(wave_container, height=72,
                                bg=self.BG2, highlightthickness=0)
        self.canvas.pack(fill="x", padx=30, pady=(10,8))

        self._bars = []
        for i in range(80):
            b = self.canvas.create_rectangle(0,36,8,36, fill=self.CYAN_DIM, outline="")
            self._bars.append(b)

        # ── CHAT ──────────────────────────────────────────────────────────────
        tk.Frame(r, bg=self.BORDER, height=1).pack(fill="x", padx=30)

        chat_wrap = tk.Frame(r, bg=self.PANEL,
                              highlightbackground=self.BORDER2,
                              highlightthickness=1)
        chat_wrap.pack(fill="both", expand=True, padx=30, pady=(10,6))

        # Chat topbar
        ctop = tk.Frame(chat_wrap, bg=self.BG2)
        ctop.pack(fill="x")
        tk.Label(ctop, text="  ▸  MISSION LOG",
                 fg=self.TEXT3, bg=self.BG2,
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=5)
        self._clr_btn = tk.Button(ctop, text="CLEAR  ×",
                                   command=self._clear,
                                   bg=self.BG2, fg=self.TEXT3,
                                   activebackground=self.PANEL,
                                   relief="flat", bd=0,
                                   font=("Segoe UI", 8),
                                   padx=12, pady=5, cursor="hand2")
        self._clr_btn.pack(side="right")
        tk.Frame(chat_wrap, bg=self.BORDER, height=1).pack(fill="x")

        self.chat = scrolledtext.ScrolledText(
            chat_wrap, wrap=tk.WORD,
            bg=self.PANEL, fg=self.TEXT,
            font=("Consolas", 10),
            insertbackground=self.CYAN,
            relief="flat", bd=0,
            padx=20, pady=16,
            selectbackground=self.PANEL2,
        )
        self.chat.pack(fill="both", expand=True)

        # Tags
        self.chat.tag_config("ts",      foreground=self.TEXT3,   font=("Consolas",8))
        self.chat.tag_config("anjar",   foreground=self.CYAN,    font=("Segoe UI",10,"bold"))
        self.chat.tag_config("jarvis",  foreground=self.PURPLE,  font=("Segoe UI",10,"bold"))
        self.chat.tag_config("body",    foreground=self.TEXT,    font=("Consolas",10))
        self.chat.tag_config("action",  foreground=self.GOLD,    font=("Consolas",9))
        self.chat.tag_config("sys",     foreground=self.GREEN,   font=("Consolas",8))
        self.chat.tag_config("err",     foreground=self.RED,     font=("Consolas",9))
        self.chat.tag_config("divider", foreground=self.TEXT3,   font=("Consolas",8))
        self.chat.config(state="disabled")

        # ── INPUT BAR ─────────────────────────────────────────────────────────
        tk.Frame(r, bg=self.BORDER, height=1).pack(fill="x", padx=30, pady=(0,4))

        bar = tk.Frame(r, bg=self.BG)
        bar.pack(fill="x", padx=30, pady=(0,18))

        # Mic
        self.mic_btn = tk.Button(
            bar, text="  🎙  ",
            command=self._toggle_mic,
            bg=self.CYAN_GLOW, fg=self.CYAN,
            activebackground=self.CYAN_DIM,
            relief="flat", bd=0,
            highlightbackground=self.CYAN,
            highlightthickness=1,
            font=("Segoe UI", 13),
            padx=8, pady=9, cursor="hand2"
        )
        self.mic_btn.pack(side="left")

        # Entry wrapper
        self.ef = tk.Frame(bar, bg=self.PANEL2,
                            highlightbackground=self.BORDER2,
                            highlightcolor=self.CYAN,
                            highlightthickness=1)
        self.ef.pack(side="left", fill="x", expand=True, padx=(10,8))

        tk.Label(self.ef, text=" ❯❯ ",
                 fg=self.CYAN2, bg=self.PANEL2,
                 font=("Consolas", 11, "bold")).pack(side="left")

        self.entry = tk.Entry(
            self.ef,
            bg=self.PANEL2, fg=self.WHITE,
            insertbackground=self.CYAN,
            relief="flat", bd=0,
            font=("Segoe UI", 11)
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=11, padx=(0,12))
        self.entry.bind("<Return>", self._send)
        self.entry.bind("<FocusIn>",  lambda e: self.ef.config(highlightbackground=self.CYAN))
        self.entry.bind("<FocusOut>", lambda e: self.ef.config(highlightbackground=self.BORDER2))
        self.entry.focus()

        # Send
        tk.Button(
            bar, text="  KIRIM  ",
            command=self._send,
            bg=self.CYAN2, fg=self.BG,
            activebackground=self.CYAN,
            activeforeground=self.BG,
            relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"),
            padx=20, pady=10, cursor="hand2"
        ).pack(side="right")

        # Bottom glow
        tk.Frame(r, bg=self.CYAN_GLOW, height=2).pack(fill="x", side="bottom")
        tk.Frame(r, bg=self.CYAN, height=1).pack(fill="x", side="bottom")

        # Boot messages
        self._sys(f"JARVIS v5  ·  Model: {MODEL}  ·  TTS: {TTS_VOICE}")
        self._sys(f"Spotify: {SPOTIFY_EXE or 'fallback URI mode'}")
        self._log("JARVIS", "Sistem aktif. Selamat datang, Tuan Anjar. Siap menerima perintah.", "jarvis")

    # ── Chat helpers ───────────────────────────────────────────────────────────
    def _log(self, label, msg, tag):
        ts = datetime.now().strftime("%H:%M:%S")
        def _do():
            self.chat.config(state="normal")
            self.chat.insert("end", f" {ts}  ", "ts")
            self.chat.insert("end", f"[{label}]  ", tag)
            self.chat.insert("end", f"{msg}\n", "body")
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _do)

    def _action(self, msg):
        def _do():
            self.chat.config(state="normal")
            self.chat.insert("end", f"         ⚡  {msg}\n", "action")
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _do)

    def _sys(self, msg):
        def _do():
            self.chat.config(state="normal")
            self.chat.insert("end", f"  ▸  {msg}\n", "sys")
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _do)

    def _err(self, msg):
        def _do():
            self.chat.config(state="normal")
            self.chat.insert("end", f"  ✕  {msg}\n", "err")
            self.chat.see("end")
            self.chat.config(state="disabled")
        self.root.after(0, _do)

    def _clear(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0","end")
        self.chat.config(state="disabled")
        history.clear()
        self._sys("Log dibersihkan.")

    # ── Status ─────────────────────────────────────────────────────────────────
    def _status(self, text, color):
        self.root.after(0, lambda: [
            self._dot.config(fg=color),
            self._stlbl.config(text=text, fg=color)
        ])

    # ── Toggle ─────────────────────────────────────────────────────────────────
    def _toggle_mic(self):
        self.muted = not self.muted
        if self.muted:
            self.mic_btn.config(fg=self.RED, highlightbackground=self.RED)
            self._status("MIC OFF", self.RED)
        else:
            self.mic_btn.config(fg=self.CYAN, highlightbackground=self.CYAN)
            self._status("ONLINE", self.CYAN)

    def _toggle_tts(self):
        global _tts_enabled
        self.tts_on = not self.tts_on
        _tts_enabled = self.tts_on
        if self.tts_on:
            self.tts_btn.config(fg=self.CYAN, bg=self.CYAN_GLOW, text="🔊 VOICE")
        else:
            self.tts_btn.config(fg=self.TEXT2, bg=self.PANEL, text="🔇 VOICE")
        self._sys(f"TTS voice {'aktif' if self.tts_on else 'nonaktif'}.")

    # ── Animation tick ─────────────────────────────────────────────────────────
    def _tick(self):
        self._phase  += 0.08
        self._pulse  += 0.12

        w = self.canvas.winfo_width() or 1040
        n = len(self._bars)
        bw = (w - 60) / n

        if   self.muted:     col = self.TEXT3
        elif self.busy:      col = self.PURPLE2
        elif self.recording: col = self.RED
        else:                col = self.CYAN2

        # Idle ambient wave
        if not self.recording and not self.busy and not self.muted:
            for i in range(n):
                v = (2.5
                     + 2.0 * math.sin(self._phase * 1.1 + i * 0.20)
                     + 1.0 * math.sin(self._phase * 2.3 + i * 0.45))
                self._wave[i] = self._wave[i] * 0.85 + max(1, v) * 0.15

        for i, bar in enumerate(self._bars):
            x = 30 + i * bw
            h = max(1.5, self._wave[i])
            cy = 36
            self.canvas.coords(bar, x, cy - h, x + max(bw - 1.5, 2), cy + h)
            # Edge fade
            edge = abs(i - n//2) / (n//2)
            alpha = max(0.2, 1.0 - edge * 0.55)
            self.canvas.itemconfig(bar, fill=col)

        self.root.after(30, self._tick)

    def _wave_push(self, rms):
        h = max(2, min(32, rms / 45))
        self._wave.pop(0); self._wave.append(h)

    # ── Audio VAD ──────────────────────────────────────────────────────────────
    @staticmethod
    def _rms(data):
        cnt = len(data)//2
        if not cnt: return 0
        return math.sqrt(sum(s*s for s in struct.unpack(f"{cnt}h", data)) / cnt)

    def _save_wav(self, frames):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        pa = pyaudio.PyAudio()
        with wave.open(path,"wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))
        pa.terminate()
        return path

    def _transcribe(self, path):
        with open(path,"rb") as f:
            r = self.client.audio.transcriptions.create(
                model="gpt-4o-transcribe", file=f, language=LANGUAGE)
        for _ in range(8):
            try: os.unlink(path); break
            except: time.sleep(0.2)
        return r.text.strip()

    def _start_listener(self):
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        try:
            pa = pyaudio.PyAudio()
            st = pa.open(format=pyaudio.paInt16, channels=CHANNELS,
                         rate=SAMPLE_RATE, input=True,
                         frames_per_buffer=CHUNK)
            frames, speaking, sil_t, start_t = [], False, None, 0
            while True:
                data = st.read(CHUNK, exception_on_overflow=False)
                if self.muted or self.busy:
                    time.sleep(0.01); continue
                rms = self._rms(data)
                self._wave_push(rms)
                if rms > SILENCE_THR:
                    if not speaking:
                        speaking = True; self.recording = True
                        frames = []; start_t = time.time()
                        self._status("● REC", self.RED)
                    frames.append(data); sil_t = None
                else:
                    if speaking:
                        frames.append(data)
                        if sil_t is None: sil_t = time.time()
                        elif time.time() - sil_t >= SILENCE_DUR:
                            speaking = False; self.recording = False
                            if time.time() - start_t >= MIN_REC_SECS:
                                self._status("◌ PROC", self.GOLD)
                                cp = frames[:]
                                threading.Thread(
                                    target=self._handle_voice,
                                    args=(cp,), daemon=True
                                ).start()
                            else:
                                self._status("ONLINE", self.CYAN)
                            frames = []; sil_t = None
        except Exception as e:
            self._err(f"Listener error: {e}")

    def _handle_voice(self, frames):
        try:
            self.busy = True
            path = self._save_wav(frames)
            text = self._transcribe(path)
            if text:
                self._log("ANJAR", text, "anjar")
                self._run_ai(text)
            else:
                self.busy = False
                self._status("ONLINE", self.CYAN)
        except Exception as e:
            self._err(f"Voice: {e}")
            self.busy = False
            self._status("ONLINE", self.CYAN)

    # ── Send (text) ────────────────────────────────────────────────────────────
    def _send(self, e=None):
        text = self.entry.get().strip()
        if not text: return
        self.entry.delete(0,"end")
        self._log("ANJAR", text, "anjar")
        threading.Thread(target=self._run_ai, args=(text,), daemon=True).start()

    # ── AI Agent Loop ──────────────────────────────────────────────────────────
    def _run_ai(self, text: str):
        try:
            self.busy = True
            self._status("◌ THINKING", self.PURPLE)
            history.append({"role":"user","content":text})
            msgs = [{"role":"system","content":SYSTEM_PROMPT}] + history[-MAX_HISTORY:]

            for _ in range(16):
                resp = self.client.chat.completions.create(
                    model=MODEL,
                    messages=msgs,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.15,
                    max_tokens=1024,
                )
                msg = resp.choices[0].message
                msgs.append(msg)

                if not msg.tool_calls:
                    reply = msg.content or "Siap, Tuan."
                    history.append({"role":"assistant","content":reply})
                    self._log("JARVIS", reply, "jarvis")
                    if self.tts_on: speak(reply)
                    break

                self._status("⚡ EXEC", self.GOLD)
                for tc in msg.tool_calls:
                    fn  = tc.function.name
                    fag = json.loads(tc.function.arguments)
                    self._action(f"{fn}  {json.dumps(fag, ensure_ascii=False)[:80]}")
                    result = _exec(fn, fag)
                    msgs.append({
                        "role":"tool",
                        "tool_call_id": tc.id,
                        "content": str(result)
                    })

        except Exception as e:
            self._err(f"AI: {e}")
        finally:
            self.busy = False
            self._status("ONLINE", self.CYAN)

    # ── Quit ───────────────────────────────────────────────────────────────────
    def _quit(self):
        try: self.root.destroy()
        except: pass

# ─── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-GANTI"):
        print("=" * 60)
        print("  ERROR: OPENAI_API_KEY belum diisi!")
        print("  Buat file .env di folder yang sama:")
        print("  OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxx")
        print("=" * 60)
        sys.exit(1)
    JarvisGUI()
