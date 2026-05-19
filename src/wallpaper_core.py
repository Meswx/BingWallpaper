"""
4K Bing 壁纸自动抓取 & 桌面设置工具
来源: https://peapix.com/bing + Bing 官方 API 备用
"""

import os
import sys
import json
import ctypes
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── 配置 ──────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "source_url": "https://peapix.com/bing",
    "save_dir": str(Path(__file__).parent / "wallpapers"),
    "resolution": "3840x2160",
    "set_wallpaper": True,       # True=设置单张壁纸, "slideshow"=幻灯片自动轮换
    "save_wallpaper": True,
    "slideshow_interval": 1,     # 幻灯片轮换间隔（分钟）
}

# ── 日志 ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("wallpaper")

# ── HTTP 头 ───────────────────────────────────────────────────────────────────

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

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception as e:
            log.warning("配置文件读取失败，使用默认配置: %s", e)
    return cfg


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_windows_wallpaper(image_path: str):
    """调用 Windows API 设置桌面壁纸（静态单张）"""
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    abs_path = str(Path(image_path).resolve())
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )
    if result:
        log.info("✅ 桌面壁纸已设置: %s", abs_path)
    else:
        log.error("❌ 设置壁纸失败")


def enable_slideshow(wallpaper_dir: str, interval_minutes: int = 1):
    """
    启用 Windows 幻灯片放映模式，自动轮换指定目录下的壁纸。

    关键注册表键:
      BackgroundType = 2             ← 0=图片 1=纯色 2=幻灯片 (必须!)
      SlideshowDirectoryPath         ← 幻灯片源目录
      SlideshowDirectoryPath1        ← 幻灯片源目录(加密格式)
      Interval                       ← 轮换间隔(毫秒)
      WallpaperStyle = 6             ← 填充
      TileWallpaper = 0
    """
    import winreg

    dir_path = Path(wallpaper_dir)
    if not dir_path.is_dir():
        log.error("❌ 壁纸目录不存在: %s", wallpaper_dir)
        return False

    valid_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = sorted([f for f in dir_path.iterdir() if f.suffix.lower() in valid_ext])
    if not images:
        log.warning("⚠️  目录中没有找到图片文件: %s", wallpaper_dir)
        return False

    log.info("🖼️  目录中共有 %d 张壁纸", len(images))

    abs_dir = str(dir_path.resolve())
    interval_ms = interval_minutes * 60 * 1000

    try:
        # ── 1. 壁纸显示样式 ──
        key_desktop = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key_desktop, "WallpaperStyle", 0, winreg.REG_SZ, "6")
        winreg.SetValueEx(key_desktop, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key_desktop)

        # ── 2. 幻灯片源目录 + 关键: BackgroundType = 2 ──
        key_wall = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers",
            0, winreg.KEY_SET_VALUE,
        )
        # ★ 最关键: 2 = 幻灯片模式
        winreg.SetValueEx(key_wall, "BackgroundType", 0, winreg.REG_DWORD, 2)
        winreg.SetValueEx(key_wall, "SlideshowDirectoryPath", 0, winreg.REG_SZ, abs_dir)
        winreg.SetValueEx(key_wall, "SlideshowSourceDirectoriesSet", 0, winreg.REG_DWORD, 1)
        # BackgroundHistoryPath 也设为目录
        winreg.SetValueEx(key_wall, "BackgroundHistoryPath", 0, winreg.REG_SZ, abs_dir)
        winreg.CloseKey(key_wall)

        # ── 3. 轮换间隔 ──
        key_slide = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Slideshow",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key_slide, "Interval", 0, winreg.REG_DWORD, interval_ms)
        winreg.CloseKey(key_slide)

        # ── 4. 通知 Windows 资源管理器重新加载 ──
        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02

        # 先设第一张图为当前壁纸
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(images[0].resolve()),
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
        )

        # 广播设置变更
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            "ImmersiveColorSet",
            SMTO_ABORTIFHUNG, 5000, ctypes.byref(result),
        )

        log.info("✅ 幻灯片放映已启用！")
        log.info("   BackgroundType = 2 (幻灯片模式)")
        log.info("   目录: %s", abs_dir)
        log.info("   轮换间隔: %d 分钟", interval_minutes)
        log.info("   壁纸数量: %d 张", len(images))
        return True

    except Exception as e:
        log.error("❌ 启用幻灯片放映失败: %s", e)
        return False


def download_image(url: str, save_dir: Path, title: str = "") -> Path | None:
    """下载图片到本地"""
    try:
        log.info("📥 下载: %s", url[:120])
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

        if filepath.exists():
            log.info("⏭️  文件已存在，跳过: %s", filename)
            return filepath

        data = resp.content
        if len(data) < 10000:
            log.warning("⚠️  文件太小 (%d bytes)，可能不是有效图片", len(data))
            return None

        filepath.write_bytes(data)
        size_mb = len(data) / (1024 * 1024)
        log.info("✅ 已保存: %s (%.1f MB)", filename, size_mb)
        return filepath

    except requests.RequestException as e:
        log.error("❌ 下载失败: %s - %s", url[:80], e)
        return None


# ── 方案 A: peapix.com 抓取 ──────────────────────────────────────────────────

BING_CDN_PATTERNS = [
    r"tse\d+-mm\.bing\.net",
    r"tse\d+-mm\.cn\.net\.net",
    r"img\.peapix\.com",
    r"s[12]\.peapix\.com",
    r"\.bing\.com",
    r"\.bing\.net",
]

UHD_MARKERS = ["_UHD", "3840x2160", "4K", "_4K", "UHD"]


def is_bing_image_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return any(re.search(p, lower) for p in BING_CDN_PATTERNS)


def to_uhd_url(url: str) -> str:
    """
    将 Bing 图片 URL 转换为 UHD (4K) 版本。
    关键发现: Bing 的 _UHD.jpg 后缀提供真正的 4K 原图 (3-5MB)
    """
    # 如果已经是 UHD，直接返回
    if "_uhd" in url.lower():
        return url

    # 替换 _1920x1080.jpg -> _UHD.jpg
    url = re.sub(r'_\d+x\d+\.(jpg|jpeg)', r'_UHD.\1', url, flags=re.I)

    # 如果文件名中没有分辨率后缀，添加 _UHD
    if "_UHD" not in url and re.search(r'\.(jpg|jpeg)(\?|$)', url, re.I):
        url = re.sub(r'(\.(jpg|jpeg))', r'_UHD\1', url, flags=re.I)

    return url


def fetch_peapix() -> dict | None:
    """从 peapix.com/bing 抓取壁纸"""
    url = "https://peapix.com/bing"
    log.info("🌐 请求 peapix.com/bing ...")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as e:
        log.warning("peapix.com 请求失败: %s", e)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    images = []
    seen = set()

    # 策略 1: <img> 标签
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src", "")
        src = urljoin(url, src)
        if is_bing_image_url(src) and src not in seen:
            seen.add(src)
            title = img.get("alt", "") or img.get("title", "")
            images.append({"url": src, "title": title})

    # 策略 2: <a> 链接到图片
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        if re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', href, re.I) and is_bing_image_url(href):
            if href not in seen:
                seen.add(href)
                images.append({"url": href, "title": a.get_text(strip=True) or a.get("title", "")})

    # 策略 3: og:image 元标签
    og_image = soup.find("meta", property="og:image")
    if og_image:
        img_url = og_image.get("content", "")
        if img_url and img_url not in seen:
            images.insert(0, {"url": img_url, "title": ""})

    # 策略 4: 从页面文本提取 Bing 图片 URL
    text = str(soup)
    for m in re.findall(r'https?://[^\s<>"\']*bing\.net[^\s<>"\']*\.jpg[^\s<>"\']*', text):
        clean = m.rstrip(".,;:!?)'\"")
        if clean not in seen and is_bing_image_url(clean):
            seen.add(clean)
            images.append({"url": clean, "title": ""})

    if not images:
        log.warning("peapix.com 未找到壁纸图片")
        return None

    log.info("🔍 peapix 找到 %d 个候选", len(images))

    # 优先选 UHD，否则转 UHD
    for img in images:
        if any(m.lower() in img["url"].lower() for m in UHD_MARKERS):
            img["url"] = to_uhd_url(img["url"])
            return img

    best = images[0]
    best["url"] = to_uhd_url(best["url"])
    return best


# ── 方案 B: Bing 官方 API ────────────────────────────────────────────────────

def fetch_bing_api(count: int = 1) -> list[dict]:
    """
    通过 Bing HPImageArchive API 获取壁纸列表，并转换为 UHD 分辨率。
    API: https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n={count}&mkt=zh-CN
    UHD 技巧: urlbase + '_UHD.jpg' 获取真正的 4K 原图
    """
    api_url = f"https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n={count}&mkt=zh-CN"
    log.info("🔄 通过 Bing API 获取 %d 张壁纸...", count)

    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error("Bing API 请求失败: %s", e)
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

    log.info("🏆 Bing API 返回 %d 张 UHD 壁纸", len(images))
    return images


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run(fetch_count: int = 1):
    """
    主运行函数。
    fetch_count=1: 下载当日壁纸（默认）
    fetch_count>1: 批量下载最近 N 天的壁纸
    """
    cfg = load_config()
    save_dir = ensure_dir(cfg["save_dir"])

    log.info("=" * 60)
    log.info("🖼️  4K Bing 壁纸抓取工具启动")
    log.info("📂 保存目录: %s", save_dir)
    if fetch_count > 1:
        log.info("📦 批量下载模式: 最近 %d 天", fetch_count)
    log.info("=" * 60)

    downloaded_paths = []

    # === 批量下载模式 (N > 1) ===
    if fetch_count > 1:
        images = fetch_bing_api(count=fetch_count)
        for img in images:
            log.info("─" * 40)
            log.info("📝 %s | %s", img.get("date", ""), img.get("title", ""))
            if img.get("copyright"):
                log.info("©  %s", img["copyright"][:100])
            if cfg["save_wallpaper"]:
                path = download_image(img["url"], save_dir, img.get("title", ""))
                if path:
                    downloaded_paths.append(path)

        log.info("═" * 60)
        log.info("📊 批量下载完成: %d/%d 张成功", len(downloaded_paths), len(images))

        # 批量下载后默认启用幻灯片
        if downloaded_paths:
            if cfg.get("set_wallpaper") == "slideshow":
                log.info("🔄 启用幻灯片放映模式...")
                enable_slideshow(str(save_dir), cfg.get("slideshow_interval", 1))
            elif cfg.get("set_wallpaper"):
                # 设置最新的一张
                set_windows_wallpaper(str(downloaded_paths[0]))

        return downloaded_paths

    # === 单张模式 (默认) ===
    downloaded_path = None

    # 方案 A: peapix.com
    result = fetch_peapix()
    if result:
        if cfg["save_wallpaper"]:
            downloaded_path = download_image(result["url"], save_dir, result.get("title", ""))

    # 方案 B: Bing API (备用)
    if downloaded_path is None:
        log.info("🔄 切换到 Bing API 备用方案...")
        images = fetch_bing_api(count=1)
        if images:
            result = images[0]
            if result.get("copyright"):
                log.info("©  %s", result["copyright"][:100])
            if cfg["save_wallpaper"]:
                downloaded_path = download_image(result["url"], save_dir, result.get("title", ""))

    # 设置壁纸
    if cfg.get("set_wallpaper") == "slideshow":
        log.info("🔄 启用幻灯片放映模式...")
        enable_slideshow(str(save_dir), cfg.get("slideshow_interval", 1))
    elif downloaded_path and cfg.get("set_wallpaper"):
        set_windows_wallpaper(str(downloaded_path))

    if downloaded_path:
        log.info("🎉 完成！壁纸: %s", downloaded_path)
    else:
        log.error("❌ 所有方案均未能获取壁纸")

    return [downloaded_path] if downloaded_path else []


# ── 定时模式 ──────────────────────────────────────────────────────────────────

def run_scheduled():
    """每天定时执行"""
    import schedule
    import time

    run()

    schedule.every().day.at("09:00").do(run)
    log.info("⏰ 已设置每天 09:00 自动更新壁纸 (Ctrl+C 退出)")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("👋 已退出定时模式")


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--schedule" in sys.argv:
        run_scheduled()
    else:
        # 解析 --fetch N 参数
        count = 1
        for i, arg in enumerate(sys.argv):
            if arg == "--fetch" and i + 1 < len(sys.argv):
                try:
                    count = int(sys.argv[i + 1])
                except ValueError:
                    pass
        run(fetch_count=count)
