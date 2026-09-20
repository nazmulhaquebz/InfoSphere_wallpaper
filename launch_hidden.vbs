Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 1. Dynamically detect project directory from script location
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = projectDir

' 2. Dynamically locate Python executable (prefer pythonw for silent headless execution)
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
progFiles = WshShell.ExpandEnvironmentStrings("%ProgramFiles%")
pythonExe = ""

' Check %LOCALAPPDATA%\Programs\Python\Python*
If fso.FolderExists(localAppData & "\Programs\Python") Then
    Set pyFolder = fso.GetFolder(localAppData & "\Programs\Python")
    For Each subF In pyFolder.SubFolders
        If fso.FileExists(subF.Path & "\pythonw.exe") Then
            pythonExe = subF.Path & "\pythonw.exe"
            Exit For
        End If
    Next
End If

' Check %ProgramFiles%\Python*
If pythonExe = "" And fso.FolderExists(progFiles) Then
    Set pfFolder = fso.GetFolder(progFiles)
    For Each subF In pfFolder.SubFolders
        If InStr(1, subF.Name, "Python", 1) = 1 Then
            If fso.FileExists(subF.Path & "\pythonw.exe") Then
                pythonExe = subF.Path & "\pythonw.exe"
                Exit For
            End If
        End If
    Next
End If

' Fallback to system PATH
If pythonExe = "" Then
    pythonExe = "pythonw.exe"
End If

' 3. Initial delay at Windows boot to let Windows Explorer and desktop shell initialize
WScript.Sleep 1500

' 4. Launch Python Telemetry Engine in background (window style 0 = hidden)
WshShell.Run Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & projectDir & "\main.py" & Chr(34), 0, False

' 5. Pause to allow Python to write initial snapshot
WScript.Sleep 1500

' 6. Launch Go Live Wallpaper Engine (WebView2 behind desktop icons)
wallpaperExe = projectDir & "\infosphere_wallpaper.exe"
If fso.FileExists(wallpaperExe) Then
    WshShell.Run Chr(34) & wallpaperExe & Chr(34), 1, False
End If
