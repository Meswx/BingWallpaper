"""
4K Bing 壁纸工具 - Windows GUI 版本
使用 tkinter 构建界面，PyInstaller 打包为独立 exe
"""

import os
import sys
import json
import ctypes
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── 配置 ──────────────────────────────────────────────────────────────────────

APP_NAME = "4K Bing 壁纸工具"
CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "source_url": "https://peapix.com/bing",
    "save_dir": str(Path(__file__).parent / "wallpapers"),
    "resolution": "3840x2160",
    "set_wallpaper": True,
    "save_wallpaper": True,
    "slideshow_interval": 1,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.bing.com/",
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")


# ── 核心功能 ──────────────────────────────────────────────────────────────────

def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_windows_wallpaper(image_path: str):
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    abs_path = str(Path(image_path).resolve())
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )
    return bool(result)


def enable_slideshow(wallpaper_dir: str, interval_minutes: int = 1):
    import winreg
    dir_path = Path(wallpaper_dir)
    if not dir_path.is_dir():
        return False
    valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = sorted([f for f in dir_path.iterdir() if f.suffix.lower() in valid_ext])
    if not images:
        return False

    abs_dir = str(dir_path.resolve())
    interval_ms = interval_minutes * 60 * 1000

    try:
        key_desktop = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key_desktop, "WallpaperStyle", 0, winreg.REG_SZ, "6")
        winreg.SetValueEx(key_desktop, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key_desktop)

        key_wall = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key_wall, "BackgroundType", 0, winreg.REG_DWORD, 2)
        winreg.SetValueEx(key_wall, "SlideshowDirectoryPath", 0, winreg.REG_SZ, abs_dir)
        winreg.SetValueEx(key_wall, "SlideshowSourceDirectoriesSet", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key_wall, "BackgroundHistoryPath", 0, winreg.REG_SZ, abs_dir)
        winreg.CloseKey(key_wall)

        key_slide = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Slideshow",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key_slide, "Interval", 0, winreg.REG_DWORD, interval_ms)
        winreg.CloseKey(key_slide)

        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(images[0].resolve()),
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
        )
        return True
    except Exception:
        return False


def fetch_bing_images(count: int = 1) -> list:
    api_url = f"https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n={count}&mkt=zh-CN"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    images = []
    for img_info in data.get("images", []):
        urlbase = img_info.get("urlbase", "")
        if not urlbase:
            continue
        uhd_url = f"https://www.bing.com{urlbase}_UHD.jpg"
        images.append({
            "url": uhd_url,
            "title": img_info.get("title", ""),
            "copyright": img_info.get("copyright", ""),
            "date": img_info.get("startdate", ""),
        })
    return images


def download_image(url: str, save_dir: Path, title: str = "") -> Path | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        ext = ext_map.get(content_type.split(";")[0].strip(), ".jpg")

        today = datetime.now().strftime("%Y-%m-%d")
        safe_title = re.sub(r'[\\/:*?"<>|#&]', '_', title)[:60] if title else ""
        suffix = f"_{safe_title}" if safe_title else ""
        filename = f"bing_wallpaper_{today}{suffix}{ext}"
        filepath = save_dir / filename

        data = resp.content
        if len(data) < 10000:
            return None
        filepath.write_bytes(data)
        return filepath
    except Exception:
        return None


# ── GUI 界面 ──────────────────────────────────────────────────────────────────

class WallpaperApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("520x480")
        self.root.resizable(False, False)
        self.cfg = load_config()

        self._build_ui()
        self._refresh_wallpaper_list()

    def _build_ui(self):
        # 标题
        title_frame = Frame(self.root, pady=10)
        title_frame.pack(fill=X)
        Label(title_frame, text=APP_NAME, font=("Microsoft YaHei", 16, "bold")).pack()
        Label(title_frame, text="每日 4K Bing 壁纸自动抓取 & 桌面设置", font=("Microsoft YaHei", 9), fg="gray").pack()

        # 主内容区
        main_frame = Frame(self.root, padx=20, pady=5)
        main_frame.pack(fill=BOTH, expand=True)

        # 壁纸目录
        dir_frame = LabelFrame(main_frame, text="壁纸保存目录", pady=5, padx=10)
        dir_frame.pack(fill=X, pady=(0, 10))

        self.dir_var = StringVar(value=self.cfg["save_dir"])
        dir_entry = Entry(dir_frame, textvariable=self.dir_var, state="readonly", width=50)
        dir_entry.pack(side=LEFT, fill=X, expand=True)

        Button(dir_frame, text="打开", command=self._open_dir, width=6).pack(side=RIGHT, padx=(5, 0))

        # 壁纸列表
        list_frame = LabelFrame(main_frame, text="已下载壁纸", pady=5, padx=10)
        list_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        self.listbox = Listbox(list_frame, height=8, font=("Consolas", 10))
        scrollbar = Scrollbar(list_frame, orient=VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 模式选择
        mode_frame = LabelFrame(main_frame, text="设置模式", pady=5, padx=10)
        mode_frame.pack(fill=X, pady=(0, 10))

        self.mode_var = StringVar(value="single")
        Radiobutton(mode_frame, text="单张壁纸", variable=self.mode_var, value="single").pack(side=LEFT, padx=(0, 20))
        Radiobutton(mode_frame, text="幻灯片轮换", variable=self.mode_var, value="slideshow").pack(side=LEFT)

        # 状态栏
        self.status_var = StringVar(value="就绪")
        status_bar = Label(self.root, textvariable=self.status_var, bd=1, relief=SUNKEN, anchor=W, padx=10)
        status_bar.pack(side=BOTTOM, fill=X)

        # 按钮区
        btn_frame = Frame(self.root, padx=20, pady=10)
        btn_frame.pack(fill=X, side=BOTTOM)

        Button(btn_frame, text="📥 下载今日壁纸", command=self._fetch_today, width=16, bg="#4CAF50", fg="white").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="📦 批量下载", command=self._fetch_batch, width=12).pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="🖼️ 设为壁纸", command=self._set_wallpaper, width=12, bg="#2196F3", fg="white").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="🔄 启用幻灯片", command=self._enable_slideshow, width=12).pack(side=LEFT)

    def _open_dir(self):
        os.startfile(self.dir_var.get())

    def _refresh_wallpaper_list(self):
        self.listbox.delete(0, END)
        save_dir = Path(self.dir_var.get())
        if save_dir.is_dir():
            valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            images = sorted([f for f in save_dir.iterdir() if f.suffix.lower() in valid_ext])
            for img in images:
                size_mb = img.stat().st_size / (1024 * 1024)
                self.listbox.insert(END, f"{img.name}  ({size_mb:.1f} MB)")
            self._set_status(f"共 {len(images)} 张壁纸")

    def _set_status(self, text: str):
        self.status_var.set(text)
        self.root.update_idletasks()

    def _fetch_today(self):
        def task():
            self._set_status("正在获取今日壁纸...")
            images = fetch_bing_images(count=1)
            if not images:
                self._set_status("❌ 获取失败")
                return
            img = images[0]
            self._set_status(f"正在下载: {img['title']}")
            save_dir = ensure_dir(self.dir_var.get())
            path = download_image(img["url"], save_dir, img.get("title", ""))
            if path:
                self.cfg["save_dir"] = str(save_dir)
                save_config(self.cfg)
                self.root.after(0, self._refresh_wallpaper_list)
                self.root.after(0, self._set_status, f"✅ 已下载: {img['title']}")
                if self.mode_var.get() == "single":
                    set_windows_wallpaper(str(path))
                    self.root.after(0, self._set_status, f"✅ 壁纸已设置: {img['title']}")
            else:
                self._set_status("❌ 下载失败")
        threading.Thread(target=task, daemon=True).start()

    def _fetch_batch(self):
        count = 10
        def task():
            self._set_status(f"正在获取 {count} 张壁纸...")
            images = fetch_bing_images(count=count)
            if not images:
                self._set_status("❌ 获取失败")
                return
            save_dir = ensure_dir(self.dir_var.get())
            success = 0
            for i, img in enumerate(images):
                self._set_status(f"下载中 ({i+1}/{len(images)}): {img['title']}")
                path = download_image(img["url"], save_dir, img.get("title", ""))
                if path:
                    success += 1
            self.cfg["save_dir"] = str(save_dir)
            save_config(self.cfg)
            self.root.after(0, self._refresh_wallpaper_list)
            self.root.after(0, self._set_status, f"✅ 批量下载完成: {success}/{len(images)} 张成功")
        threading.Thread(target=task, daemon=True).start()

    def _set_wallpaper(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先从列表中选择一张壁纸")
            return
        save_dir = Path(self.dir_var.get())
        valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        images = sorted([f for f in save_dir.iterdir() if f.suffix.lower() in valid_ext])
        idx = selection[0]
        if idx < len(images):
            path = images[idx]
            if set_windows_wallpaper(str(path)):
                self._set_status(f"✅ 壁纸已设置: {path.name}")
            else:
                self._set_status("❌ 设置失败")

    def _enable_slideshow(self):
        interval = self.cfg.get("slideshow_interval", 1)
        if enable_slideshow(self.dir_var.get(), interval):
            self._set_status(f"✅ 幻灯片已启用（每 {interval} 分钟轮换）")
        else:
            self._set_status("❌ 启用失败，请确保目录中有壁纸")


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    root = Tk()
    app = WallpaperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
