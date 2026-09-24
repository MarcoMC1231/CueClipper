Set sh = CreateObject("WScript.Shell")
sh.Run "pythonw """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\server.py""", 0, False
