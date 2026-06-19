Option Explicit

Dim shell
Dim command

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "H:\git\MultiScheduler"

command = "cmd.exe /c " & Chr(34) & "H:\git\MultiScheduler\run_multischeduler_scan.cmd" & Chr(34)
WScript.Quit shell.Run(command, 0, True)
