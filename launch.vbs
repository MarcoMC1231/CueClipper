Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pidFile   = scriptDir & "\server.pid"

' Kill previous instance if PID file exists
If fso.FileExists(pidFile) Then
  On Error Resume Next
  Set f = fso.OpenTextFile(pidFile, 1)
  oldPid = Trim(f.ReadLine())
  f.Close
  If oldPid <> "" Then
    sh.Run "taskkill /F /PID " & oldPid, 0, True
    WScript.Sleep 400
  End If
  fso.DeleteFile pidFile
  On Error GoTo 0
End If

' Start server (opens browser automatically via webbrowser.open in Python)
sh.Run "pythonw """ & scriptDir & "\server.py""", 0, False
