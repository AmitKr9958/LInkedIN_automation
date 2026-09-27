Option Explicit

Dim shell, fso, base, runner, cmd, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
runner = fso.BuildPath(base, "run-agent.ps1")
shell.CurrentDirectory = base
cmd = "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & runner & """"
exitCode = shell.Run(cmd, 0, True)
WScript.Quit exitCode
