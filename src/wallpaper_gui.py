"""
4K Bing 壁纸工具 - Windows GUI 版本
使用 customtkinter 构建现代界面，PyInstaller 打包为独立 exe
"""

import os
import sys
import json
import ctypes
import re
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urljoin

import customtkinter as ctk
import PIL.Image
import PIL.ImageTk
import requests
from bs4 import BeautifulSoup

# ── 主题配置 ──────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 应用配置 ──────────────────────────────────────────────────────────────────

APP_NAME = "4K Bing 壁纸工具"
APP_VERSION = "v0.1.0"
CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "source_url": "https://peapix.com/bing",
    "save_dir": str(Path(__file__).parent.parent / "wallpapers"),
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

class WallpaperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cfg = load_config()
        self._selected_path: Path | None = None
        self._preview_photo = None
        self._preview_original: PIL.Image.Image | None = None

        # 窗口配置
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("960x640")
        self.minsize(800, 560)
        self.resizable(True, True)

        # 布局
        self.grid_rowconfigure(0, weight=0)   # 标题
        self.grid_rowconfigure(1, weight=1)   # 主内容
        self.grid_rowconfigure(2, weight=0)   # 按钮
        self.grid_rowconfigure(3, weight=0)   # 状态栏
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_main()
        self._build_buttons()
        self._build_status_bar()

        self._refresh_wallpaper_list()

        # 绑定 resize 事件，窗口大小变化时重新缩放预览图
        self.bind("<Configure>", self._on_configure)

    # ── 标题区 ──────────────────────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=72)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 0))
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="🖼️  4K Bing 壁纸工具",
            font=ctk.CTkFont(family="Microsoft YaHei", size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="每日 4K Bing 壁纸自动抓取 & 桌面设置",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13),
            text_color="gray",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    # ── 主内容区（左：列表 + 右：预览） ──────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=24, pady=8)
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=3)   # 列表占 3/5
        main.grid_columnconfigure(1, weight=2)   # 预览占 2/5

        # ── 目录选择行 ──
        dir_row = ctk.CTkFrame(main, fg_color="transparent")
        dir_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        dir_row.grid_columnconfigure(0, weight=1)

        self.dir_var = ctk.StringVar(value=self.cfg["save_dir"])

        self.dir_entry = ctk.CTkEntry(
            dir_row, textvariable=self.dir_var,
            state="readonly", height=36,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        )
        self.dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            dir_row, text="📂 选择目录", command=self._choose_dir,
            width=110, height=36, corner_radius=8,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        ).grid(row=0, column=1)

        # ── 左侧：壁纸列表卡片 ──
        list_card = ctk.CTkFrame(main, corner_radius=12)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        list_card.grid_rowconfigure(1, weight=1)
        list_card.grid_columnconfigure(0, weight=1)

        list_header = ctk.CTkFrame(list_card, fg_color="transparent", height=36)
        list_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        list_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            list_header, text="📋 已下载壁纸",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.count_label = ctk.CTkLabel(
            list_header, text="共 0 张",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="gray",
        )
        self.count_label.grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(list_card, height=1, fg_color=("gray80", "gray30")).grid(
            row=0, column=0, sticky="new", padx=12, pady=(32, 0))

        self.list_scroll = ctk.CTkScrollableFrame(list_card, corner_radius=8)
        self.list_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._list_items = []

        # ── 右侧：预览卡片 ──
        preview_card = ctk.CTkFrame(main, corner_radius=12)
        preview_card.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        preview_header = ctk.CTkFrame(preview_card, fg_color="transparent", height=36)
        preview_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            preview_header, text="👁️ 预览",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).pack(side="left")

        ctk.CTkFrame(preview_card, height=1, fg_color=("gray80", "gray30")).grid(
            row=0, column=0, sticky="new", padx=12, pady=(32, 0))

        # 预览图区域 —— 不设置任何固定尺寸，完全自适应
        self.preview_body = ctk.CTkFrame(preview_card, fg_color="transparent")
        self.preview_body.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        self.preview_body.grid_rowconfigure(0, weight=1)
        self.preview_body.grid_columnconfigure(0, weight=1)

        self.preview_label = ctk.CTkLabel(
            self.preview_body,
            text="点击壁纸\n查看预览",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13),
            text_color="gray",
            corner_radius=8,
            fg_color=("gray90", "gray20"),
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        self.preview_info = ctk.CTkLabel(
            self.preview_body, text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="gray", anchor="center",
        )
        self.preview_info.grid(row=1, column=0, pady=(8, 0))

        # ── 模式选择行 ──
        mode_row = ctk.CTkFrame(main, fg_color="transparent")
        mode_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ctk.CTkLabel(
            mode_row, text="⚙️ 设置模式",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).pack(side="left", padx=(4, 16))

        self.mode_var = ctk.StringVar(value="single")

        ctk.CTkRadioButton(
            mode_row, text="单张壁纸", variable=self.mode_var, value="single",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        ).pack(side="left", padx=(0, 20))

        ctk.CTkRadioButton(
            mode_row, text="幻灯片轮换", variable=self.mode_var, value="slideshow",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
        ).pack(side="left")

    # ── 按钮区 ───────────────────────────────────────────────────────────────

    def _build_buttons(self):
        btn_frame = ctk.CTkFrame(self, fg_color="transparent", height=52)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(4, 8))
        btn_frame.grid_propagate(False)

        for i in range(4):
            btn_frame.grid_columnconfigure(i, weight=1)

        buttons = [
            ("📥  下载今日", "#2E7D32", "#4CAF50", self._fetch_today),
            ("📦  批量下载", "#1565C0", "#1E88E5", self._fetch_batch),
            ("🖼️  设为壁纸", "#6A1B9A", "#8E24AA", self._set_wallpaper),
            ("🔄  幻灯片", "#E65100", "#F57C00", self._enable_slideshow),
        ]

        for i, (text, hover, fg, cmd) in enumerate(buttons):
            ctk.CTkButton(
                btn_frame, text=text, command=cmd,
                font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
                height=42, corner_radius=10,
                fg_color=fg, hover_color=hover,
            ).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))

    # ── 状态栏 ───────────────────────────────────────────────────────────────

    def _build_status_bar(self):
        self.status_var = ctk.StringVar(value="就绪")
        ctk.CTkLabel(
            self, textvariable=self.status_var,
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="gray", anchor="w", height=28,
        ).grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 8))

    # ── 目录选择 ─────────────────────────────────────────────────────────────

    def _choose_dir(self):
        d = filedialog.askdirectory(title="选择壁纸保存目录")
        if d:
            self.dir_var.set(d)
            self.cfg["save_dir"] = d
            save_config(self.cfg)
            self._refresh_wallpaper_list()

    # ── 壁纸列表 & 预览 ──────────────────────────────────────────────────────

    def _refresh_wallpaper_list(self):
        for item in self._list_items:
            item[0].destroy()
        self._list_items.clear()

        save_dir = Path(self.dir_var.get())
        if save_dir.is_dir():
            valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            images = sorted([f for f in save_dir.iterdir() if f.suffix.lower() in valid_ext])
            for img in images:
                size_mb = img.stat().st_size / (1024 * 1024)
                row = ctk.CTkFrame(self.list_scroll, fg_color="transparent", height=32)
                row.pack(fill="x", padx=8, pady=1)
                row.pack_propagate(False)

                lbl = ctk.CTkLabel(
                    row,
                    text=f"  {img.name}    ({size_mb:.1f} MB)",
                    font=ctk.CTkFont(family="Microsoft YaHei", size=11),
                    anchor="w", text_color=("gray20", "gray80"),
                )
                lbl.pack(fill="x", side="left", expand=True)

                for widget in (row, lbl):
                    widget.bind("<Button-1>", lambda e, p=img: self._on_select(p))

                self._list_items.append((row, lbl, img))

            count = len(images)
        else:
            count = 0

        self.count_label.configure(text=f"共 {count} 张")

    def _on_select(self, path: Path):
        """选中壁纸时更新预览"""
        self._selected_path = path

        # 高亮选中项
        for row, lbl, fp in self._list_items:
            if fp == path:
                row.configure(fg_color=("gray85", "gray25"))
                lbl.configure(text_color=("gray10", "white"))
            else:
                row.configure(fg_color="transparent")
                lbl.configure(text_color=("gray20", "gray80"))

        # 加载原始图片，保存引用以便 resize 时重新缩放
        try:
            self._preview_original = PIL.Image.open(path)
            self._render_preview()
            size_mb = path.stat().st_size / (1024 * 1024)
            w, h = self._preview_original.size
            self.preview_info.configure(
                text=f"{path.name}\n{w}×{h}  |  {size_mb:.1f} MB"
            )
        except Exception:
            self._preview_original = None
            self.preview_label.configure(text="无法预览", image="")
            self.preview_info.configure(text="")

    def _render_preview(self):
        """根据预览区实际大小缩放并显示图片"""
        if self._preview_original is None:
            return

        # 获取预览区实际可用尺寸（减去 padding）
        self.preview_body.update_idletasks()
        avail_w = self.preview_body.winfo_width() - 16
        avail_h = self.preview_body.winfo_height() - 16

        if avail_w <= 1 or avail_h <= 1:
            return  # 还没布局好，跳过

        img = self._preview_original.copy()
        img.thumbnail((avail_w, avail_h), PIL.Image.LANCZOS)
        self._preview_photo = PIL.ImageTk.PhotoImage(img)
        self.preview_label.configure(
            image=self._preview_photo, text="",
            fg_color="transparent",
        )

    def _on_configure(self, event):
        """窗口大小变化时重绘预览图"""
        # 过滤掉非窗口事件和过小的变化，避免频繁重绘
        if event.widget is self and self._preview_original is not None:
            # 用 after 做防抖，避免连续触发
            if hasattr(self, "_resize_after_id"):
                self.after_cancel(self._resize_after_id)
            self._resize_after_id = self.after(150, self._render_preview)

    # ── 状态更新 ─────────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_var.set(text)
        self.update_idletasks()

    # ── 业务逻辑 ─────────────────────────────────────────────────────────────

    def _fetch_today(self):
        def task():
            self._set_status("⏳ 正在获取今日壁纸...")
            images = fetch_bing_images(count=1)
            if not images:
                self._set_status("❌ 获取失败")
                return
            img = images[0]
            self._set_status(f"⏳ 正在下载: {img['title']}")
            save_dir = ensure_dir(self.dir_var.get())
            path = download_image(img["url"], save_dir, img.get("title", ""))
            if path:
                self.cfg["save_dir"] = str(save_dir)
                save_config(self.cfg)
                self.after(0, self._refresh_wallpaper_list)
                self._set_status(f"✅ 已下载: {img['title']}")
                if self.mode_var.get() == "single":
                    set_windows_wallpaper(str(path))
                    self._set_status(f"✅ 壁纸已设置: {img['title']}")
            else:
                self._set_status("❌ 下载失败")
        threading.Thread(target=task, daemon=True).start()

    def _fetch_batch(self):
        count = 10
        def task():
            self._set_status(f"⏳ 正在获取 {count} 张壁纸...")
            images = fetch_bing_images(count=count)
            if not images:
                self._set_status("❌ 获取失败")
                return
            save_dir = ensure_dir(self.dir_var.get())
            success = 0
            for i, img in enumerate(images):
                self._set_status(f"⏳ 下载中 ({i+1}/{len(images)}): {img['title']}")
                path = download_image(img["url"], save_dir, img.get("title", ""))
                if path:
                    success += 1
            self.cfg["save_dir"] = str(save_dir)
            save_config(self.cfg)
            self.after(0, self._refresh_wallpaper_list)
            self._set_status(f"✅ 批量下载完成: {success}/{len(images)} 张成功")
        threading.Thread(target=task, daemon=True).start()

    def _set_wallpaper(self):
        if self._selected_path is None:
            messagebox.showwarning("提示", "请先从列表中选择一张壁纸")
            return
        if set_windows_wallpaper(str(self._selected_path)):
            self._set_status(f"✅ 壁纸已设置: {self._selected_path.name}")
        else:
            self._set_status("❌ 设置失败")

    def _enable_slideshow(self):
        interval = self.cfg.get("slideshow_interval", 1)
        if enable_slideshow(self.dir_var.get(), interval):
            self._set_status(f"✅ 幻灯片已启用（每 {interval} 分钟轮换）")
        else:
            self._set_status("❌ 启用失败，请确保目录中有壁纸")


def main():
    app = WallpaperApp()
    app.mainloop()


if __name__ == "__main__":
    main()
