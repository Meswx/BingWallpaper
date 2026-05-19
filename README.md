# 🖼️ 4K Bing Wallpaper Tool

[English](README.md) | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

Automatically fetch daily Bing 4K wallpapers and set them as your desktop background. Supports **single wallpaper** and **slideshow** modes. Built-in GUI, ready to use out of the box.

## Features

- 🌐 **Dual-source fetching** — peapix.com as primary, Bing official API as fallback
- 🖼️ **True 4K UHD** — uses Bing `_UHD.jpg` original image (3-5MB+)
- 🔄 **Slideshow** — auto-rotate all wallpapers in your local directory
- 💻 **GUI interface** — built with tkinter, no command line needed
- 📦 **Standalone exe** — can be packaged into a single file, no Python required

## Quick Start

### Option 1: Download the exe

Download the latest `BingWallpaper.exe` from [Releases](https://github.com/Meswx/BingWallpaper/releases) and run it.

### Option 2: Run from source

```bash
git clone https://github.com/Meswx/BingWallpaper.git
cd BingWallpaper
pip install -r requirements.txt
python src/wallpaper_gui.py
```

### Option 3: Command line

```bash
# Download today's wallpaper
python src/wallpaper_core.py

# Batch download 10 wallpapers
python src/wallpaper_core.py --fetch 10

# Scheduled mode (auto-update every day at 09:00)
python src/wallpaper_core.py --schedule
```

## Screenshot

```
┌────────────────────────────────────────────┐
│         🖼️ 4K Bing Wallpaper Tool          │
│     Daily 4K Bing Wallpaper & Desktop      │
├────────────────────────────────────────────┤
│ Wallpaper Directory: D:\Claude Code\wallpapers │
│                              [Open]        │
├────────────────────────────────────────────┤
│ Downloaded Wallpapers                      │
│ ┌──────────────────────────────────────┐   │
│ │ bing_wallpaper_2026-05-19_xxx.jpg    │   │
│ │ bing_wallpaper_2026-05-18_xxx.jpg    │   │
│ │ ...                                  │   │
│ └──────────────────────────────────────┘   │
├────────────────────────────────────────────┤
│ Mode: ○ Single Wallpaper  ○ Slideshow      │
├────────────────────────────────────────────┤
│ [📥 Fetch Today] [📦 Batch] [🖼️ Set] [🔄 Slideshow] │
└────────────────────────────────────────────┘
```

## Install

### Download

You can download the source code and build it yourself, or download the built version from the [Releases](https://github.com/Meswx/BingWallpaper/releases) page.

### Build the exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "BingWallpaper" src/wallpaper_gui.py
```

The output exe will be at `dist/BingWallpaper.exe`.

## Configuration (config.json)

```json
{
    "source_url": "https://peapix.com/bing",
    "save_dir": "D:/BingWallpaper/wallpapers",
    "resolution": "3840x2160",
    "set_wallpaper": true,
    "save_wallpaper": true,
    "slideshow_interval": 1
}
```

| Option | Description |
|--------|-------------|
| `set_wallpaper` | `true` = single wallpaper, `"slideshow"` = auto-rotate |
| `save_dir` | Directory to save wallpapers |
| `slideshow_interval` | Slideshow rotation interval (minutes) |

## How It Works

### True 4K UHD

Bing image URLs support two approaches for high resolution:

| Method | URL Example | File Size | Quality |
|--------|-------------|-----------|---------|
| Resize parameter | `?w=3840&h=2160` | ~464KB | Average |
| **UHD original** ✅ | `_UHD.jpg` suffix | **3-5MB+** | **Best** |

This tool uses the `_UHD.jpg` suffix to get the true 4K original image.

### Windows Slideshow

Implemented via Windows registry, consistent with the built-in Windows slideshow experience:

- `HKCU\Control Panel\Desktop` → Wallpaper style (fill)
- `HKCU\...\Explorer\Wallpapers` → `BackgroundType=2` (slideshow mode)
- `HKCU\...\Explorer\Slideshow` → Rotation interval

## Project Structure

```
BingWallpaper/
├── src/
│   ├── wallpaper_gui.py      # GUI application
│   └── wallpaper_core.py     # Core logic (CLI)
├── dist/
│   └── BingWallpaper.exe     # Packaged standalone program
├── config.json               # Configuration file
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT License
├── README.md                 # This file
└── .github/
    └── workflows/            # GitHub Actions CI
```

## Develop and Build

### Development

- Install [Python 3.10+](https://www.python.org/)
- Run `pip install -r requirements.txt` to install dependencies
- Run `python src/wallpaper_gui.py` to start the GUI
- Run `python src/wallpaper_core.py` to use the CLI

### Build and Package

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "BingWallpaper" src/wallpaper_gui.py
```

The packaged file will be in the `./dist` folder.

## Contributing

Issues and Pull Requests are welcome!

## License

[MIT](LICENSE) © 2026
