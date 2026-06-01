# J.A.R.V.I.S — ArqoAssist v7

> **Just A Rather Very Intelligent System**  
> AI Assistant berbasis suara & teks yang bisa mengontrol komputer secara realtime.  
> Dibuat oleh **Anjar** · [Arqonara](https://arqonara.com) · Indonesia

---

## ✨ Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| 🎙️ **Voice Control** | Perintah suara realtime via OpenAI Whisper |
| 🤖 **AI Agent Loop** | GPT-4o dengan multi-tool, bisa jalankan banyak langkah sekaligus |
| 🔍 **Auto App Discovery** | Temukan & buka SEMUA app tanpa whitelist — pakai Start Menu + registry |
| 🎵 **Spotify Control** | Putar lagu/playlist/artis langsung |
| ▶️ **YouTube Player** | Buka video YouTube langsung (bukan halaman search) |
| 🖥️ **UI Automation** | Ketik teks, klik, screenshot, hotkey, scroll |
| 💬 **TTS Indonesia** | Text-to-Speech suara natural Bahasa Indonesia |
| 🌙 **Dark GUI** | Interface gelap elegan berbasis Pygame |

---

## 📦 Requirements

### Python
- Python **3.10+** (disarankan 3.11 atau 3.13)

### Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**

```
openai>=1.0.0
pyaudio>=0.2.13
pyautogui>=0.9.54
psutil>=5.9.0
colorama>=0.4.6
pyperclip>=1.8.2
requests>=2.31.0
edge-tts>=7.2.8
yt-dlp
pywin32
rapidfuzz
```

> **Catatan pyaudio di Windows:**
> ```bash
> pip install pipwin && pipwin install pyaudio
> ```

---

## ⚙️ Setup

### 1. Clone / download project

```
Tes-AI-Assist/
├── jarvis.py          ← script utama
├── .env               ← API key (buat manual)
└── requirements.txt
```

### 2. Buat file `.env`

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> Dapatkan API key di: https://platform.openai.com/api-keys

### 3. Jalankan

```bash
python jarvis.py
```

---

## 🎮 Cara Pakai

### Mode Teks (ketik perintah)

Klik kolom input di bawah GUI → ketik perintah → tekan **KIRIM** atau Enter.

### Mode Suara

Klik tombol **VOICE** → bicara → JARVIS transkripsi & eksekusi otomatis.

---

## 💬 Contoh Perintah

### Buka Aplikasi
```
buka steam
buka discord ptb
buka obs
buka file explorer
buka vs code
buka laragon
```

### Media
```
putar lagu Keshi di Spotify
putar playlist lo-fi
putar video minecraft di YouTube
```

### Browser & Web
```
buka youtube.com
cari cara install docker di Google
buka github.com
```

### Kontrol Komputer
```
screenshot layar sekarang
ketikkan halo dunia
tekan ctrl+s
scroll ke bawah 5 kali
volume naik
```

### File & Sistem
```
buat file catatan.txt isinya belajar coding
jalankan perintah ipconfig
berapa RAM yang terpakai?
```

### Window Management
```
daftar semua window yang terbuka
fokuskan window Discord
lihat app yang sudah diindex JARVIS
```

---

## 🏗️ Arsitektur

```
jarvis.py
├── AppIndex Engine          ← auto-discover semua app (bukan whitelist)
│   ├── Start Menu .lnk scan
│   ├── Registry App Paths
│   ├── Registry Uninstall
│   └── fuzzy match (rapidfuzz)
├── _smart_open_app()        ← 5 strategi berlapis
│   ├── 1. Spotify handler
│   ├── 2. APP_BUILTIN (Windows built-in + URI)
│   ├── 3. AppIndex fuzzy match
│   ├── 4. shutil.which (PATH)
│   └── 5. Windows Search (jaring terakhir)
├── OpenAI Tools (GPT-4o)
│   ├── open_app, open_url, search_google
│   ├── spotify_play, youtube_play
│   ├── type_text, hotkey, mouse_click
│   ├── screenshot, scroll
│   ├── run_command, create_file, read_file
│   ├── focus_window, list_windows
│   ├── get_system_info, notify
│   └── app_cache_info
└── JarvisGUI (Pygame)
    ├── Waveform visualizer
    ├── Mission log
    └── Voice / Text toggle
```

---

## 🔧 Konfigurasi Lanjutan

Edit bagian `CONFIG` di atas `jarvis.py`:

```python
GPT_MODEL       = "gpt-4o"       # model AI
TTS_VOICE       = "id-ID-ArdiNeural"  # suara TTS
MAX_HISTORY     = 10             # memori percakapan
SAMPLE_RATE     = 16000          # kualitas rekam suara
```

### Ganti suara TTS

Suara tersedia (Microsoft Edge TTS):
- `id-ID-ArdiNeural` — pria Indonesia (default)
- `id-ID-GadisNeural` — wanita Indonesia
- `en-US-GuyNeural` — pria Inggris

---

## 🗂️ App Index Cache

JARVIS menyimpan index semua app yang ditemukan di:
```
C:\Users\<nama>\\.jarvis_app_index.json
```

Index ini otomatis di-rebuild setiap kali JARVIS dijalankan (background thread). Untuk melihat isi index:
```
ketik: lihat app yang sudah diindex
```

---

## ❓ Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `pyaudio` error install | `pip install pipwin && pipwin install pyaudio` |
| App tidak bisa dibuka | Coba "buka [nama app] via Windows Search" |
| Suara tidak keluar | Pastikan speaker aktif & volume tidak 0 |
| Whisper lambat | Gunakan `whisper-1` model (sudah default) |
| `obs64 not found` | Install OBS → index akan auto-update saat restart |
| TTS tidak jalan | `pip install edge-tts` |
| `rapidfuzz` tidak ada | `pip install rapidfuzz` (fuzzy match fallback ke difflib) |

---

## 📄 Lisensi

MIT License — bebas digunakan, dimodifikasi, dan didistribusikan.

---

<div align="center">
  <b>Dibuat dengan ❤️ oleh Anjar · Arqonara · Indonesia</b>
</div>
