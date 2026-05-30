import subprocess, sys, os

# 先启动 GUI（后台）
gui_proc = subprocess.Popen(
    [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'src', 'wallpaper_gui.py')],
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
)

import time
time.sleep(3)  # 等窗口加载

# 用 pyautogui 截图
try:
    import pyautogui
    import win32gui, win32con

    def enum_windows_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if 'Bing' in title or 'Wallpaper' in title or '4K' in title:
                results.append((hwnd, title))

    results = []
    win32gui.EnumWindows(enum_windows_callback, results)

    if results:
        hwnd, title = results[0]
        # 将窗口置顶
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)

        # 获取窗口位置
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect
        w, h = x2 - x, y2 - y

        # 截取窗口区域
        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        save_path = os.path.join(os.path.dirname(__file__), '..', 'screenshots', 'BingWallpaper_run.png')
        screenshot.save(save_path)
        print(f'OK: {save_path} ({w}x{h})')
    else:
        print('ERROR: window not found')

    gui_proc.terminate()

except ImportError:
    print('ERROR: pip install pyautogui pywin32')
    gui_proc.terminate()
