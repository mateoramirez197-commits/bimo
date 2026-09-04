import sys
import os
import time
import threading
import customtkinter as ctk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.desktop_floating_widget import DesktopFloatingWidget

def check_parent_alive(parent_pid, root):
    if not parent_pid:
        return
    import ctypes
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    while True:
        time.sleep(1.5)
        try:
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(parent_pid))
            if not handle:
                break
            exit_code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            if exit_code.value != STILL_ACTIVE:
                break
        except Exception:
            break

    try:
        root.after(0, root.destroy)
    except Exception:
        pass
    os._exit(0)

def main():
    parent_pid = None
    if '--parent-pid' in sys.argv:
        try:
            idx = sys.argv.index('--parent-pid')
            parent_pid = int(sys.argv[idx + 1])
        except Exception:
            pass

    ctk.set_appearance_mode('Dark')
    root = ctk.CTk()
    root.withdraw()

    widget = DesktopFloatingWidget(master_app=None)

    if parent_pid:
        t = threading.Thread(target=check_parent_alive, args=(parent_pid, root), daemon=True)
        t.start()

    try:
        root.mainloop()
    except Exception:
        pass

if __name__ == '__main__':
    main()
