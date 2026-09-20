import os
import sys
import tempfile
import subprocess

def install_autostart():
    # project_dir is the parent of core/
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_exe = sys.executable
    node_exe = "C:\\Program Files\\nodejs\\node.exe"

    task_name = "InfoSphere_Cyber_Wallpaper"
    
    xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>InfoSphere Cyber Live Wallpaper Engine - runs at logon silently</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT0S</Delay>
    </LogonTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>wscript.exe</Command>
      <Arguments>"{project_dir}\\launch_hidden.vbs"</Arguments>
      <WorkingDirectory>{project_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
    # Write XML using utf-16 encoding as required by schtasks
    temp_dir = tempfile.gettempdir()
    xml_path = os.path.join(temp_dir, "infosphere_task.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(xml_content)

    print(f"Project directory: {project_dir}")
    print(f"Python interpreter: {python_exe}")
    
    # Delete existing task if any
    subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)
    
    # Create the task
    r = subprocess.run(["schtasks", "/Create", "/TN", task_name, "/XML", xml_path, "/F"], capture_output=True, text=True)
    
    # Clean up
    try:
        os.remove(xml_path)
    except Exception:
        pass

    # 1. Clean up any legacy file in Startup folder
    try:
        startup_file = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "InfoSphere_Wallpaper.vbs")
        if os.path.exists(startup_file):
            os.remove(startup_file)
    except Exception:
        pass

    # 2. Register in HKCU Run registry
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "InfoSphere_Cyber_Wallpaper", 0, winreg.REG_SZ, f'wscript.exe "{project_dir}\\launch_hidden.vbs"')
        winreg.CloseKey(key)
        print("SUCCESS: Registered in HKCU Run registry key.")
    except Exception as e:
        print(f"Notice: Registry Run key registration: {e}")

    if r.returncode == 0:
        print("SUCCESS: Autostart Task Scheduler entry registered successfully!")
    return True

if __name__ == "__main__":
    install_autostart()
