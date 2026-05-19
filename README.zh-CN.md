# 🖼️ 4K Bing 壁纸工具

[English](README.md) | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

自动抓取每日 Bing 4K 壁纸，支持**单张设置**和**幻灯片自动轮换**，内置 GUI 界面，开箱即用。

## 功能特性

- 🌐 **双源抓取** — peapix.com 优先，Bing 官方 API 自动备用
- 🖼️ **真 4K UHD** — 使用 Bing `_UHD.jpg` 原图（3-5MB+）
- 🔄 **幻灯片放映** — 自动轮换壁纸目录中的所有图片
- 💻 **GUI 界面** — 基于 tkinter，无需命令行
- 📦 **独立 exe** — 可打包为单文件，无需 Python 环境

## 快速开始

### 方式一：直接运行 exe

从 [Releases](https://github.com/Meswx/BingWallpaper/releases) 下载最新版 `BingWallpaper.exe`，双击运行。

### 方式二：从源码运行

```bash
git clone https://github.com/Meswx/BingWallpaper.git
cd BingWallpaper
pip install -r requirements.txt
python src/wallpaper_gui.py
```

### 方式三：命令行

```bash
# 下载今日壁纸
python src/wallpaper_core.py

# 批量下载 10 张
python src/wallpaper_core.py --fetch 10

# 定时模式（每天 09:00 自动更新）
python src/wallpaper_core.py --schedule
```

## 界面预览

```
┌────────────────────────────────────────────┐
│         🖼️ 4K Bing 壁纸工具                │
│     每日 4K Bing 壁纸自动抓取 & 桌面设置      │
├────────────────────────────────────────────┤
│ 壁纸保存目录: D:\BingWallpaper\wallpapers   │
│                              [打开]         │
├────────────────────────────────────────────┤
│ 已下载壁纸                                 │
│ ┌──────────────────────────────────────┐   │
│ │ bing_wallpaper_2026-05-19_xxx.jpg    │   │
│ │ bing_wallpaper_2026-05-18_xxx.jpg    │   │
│ │ ...                                  │   │
│ └──────────────────────────────────────┘   │
├────────────────────────────────────────────┤
│ 设置模式: ◉ 单张壁纸  ○ 幻灯片轮换          │
├────────────────────────────────────────────┤
│ [📥 下载今日] [📦 批量下载] [🖼️ 设为壁纸] [🔄 幻灯片] │
└────────────────────────────────────────────┘
```

## 安装

### 下载

你可以下载源码自行编译，或从 [Releases](https://github.com/Meswx/BingWallpaper/releases) 页面下载已编译版本。

### 打包 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "BingWallpaper" src/wallpaper_gui.py
```

生成的 exe 在 `dist/BingWallpaper.exe`。

## 配置 (config.json)

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

| 配置项 | 说明 |
|--------|------|
| `set_wallpaper` | `true`=单张壁纸, `"slideshow"`=幻灯片轮换 |
| `save_dir` | 壁纸保存目录 |
| `slideshow_interval` | 幻灯片轮换间隔（分钟） |

## 技术细节

### 4K UHD 获取原理

Bing 图片 URL 获取高分辨率有两种方式：

| 方式 | URL 示例 | 文件大小 | 画质 |
|------|----------|----------|------|
| 动态缩放参数 | `?w=3840&h=2160` | ~464KB | 一般 |
| **UHD 原图** ✅ | `_UHD.jpg` 后缀 | **3-5MB+** | **最佳** |

本工具使用 `_UHD.jpg` 后缀获取真正的 4K 原图。

### Windows 幻灯片实现

通过修改注册表实现，和 Windows 自带幻灯片放映效果一致：

- `HKCU\Control Panel\Desktop` → 壁纸样式（填充）
- `HKCU\...\Explorer\Wallpapers` → `BackgroundType=2`（幻灯片模式）
- `HKCU\...\Explorer\Slideshow` → 轮换间隔

## 项目结构

```
BingWallpaper/
├── src/
│   ├── wallpaper_gui.py      # GUI 主程序
│   └── wallpaper_core.py     # 核心逻辑（命令行）
├── dist/
│   └── BingWallpaper.exe     # 打包后的独立程序
├── config.json               # 配置文件
├── requirements.txt          # Python 依赖
├── LICENSE                   # MIT 开源协议
├── README.md                 # 英文版文档
├── README.zh-CN.md           # 中文版文档
└── .github/
    └── workflows/            # GitHub Actions 自动化
```

## 开发与构建

### 开发

- 安装 [Python 3.10+](https://www.python.org/)
- 运行 `pip install -r requirements.txt` 安装依赖
- 运行 `python src/wallpaper_gui.py` 启动 GUI
- 运行 `python src/wallpaper_core.py` 使用命令行

### 打包

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "BingWallpaper" src/wallpaper_gui.py
```

打包后的文件在 `./dist` 目录。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

[MIT](LICENSE) © 2026
