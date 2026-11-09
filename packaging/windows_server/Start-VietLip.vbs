Option Explicit
Dim fs, shell, root, cmd
Set fs = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
cmd = Chr(34) & root & "\runtime\pythonw.exe" & Chr(34) & " " & Chr(34) & root & "\server\desktop_launcher.py" & Chr(34)
shell.Run cmd, 1, False
