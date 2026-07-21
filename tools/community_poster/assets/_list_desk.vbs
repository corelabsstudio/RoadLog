Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
desk = sh.SpecialFolders("Desktop")
WScript.Echo "DESK=" & desk
For Each f In fso.GetFolder(desk).Files
  ext = LCase(fso.GetExtensionName(f.Name))
  If ext = "lnk" Or ext = "bat" Or ext = "url" Then
    WScript.Echo "FILE=" & f.Name
    If ext = "lnk" Then
      On Error Resume Next
      Set sc = sh.CreateShortcut(f.Path)
      WScript.Echo "  TARGET=" & sc.TargetPath
      WScript.Echo "  ARGS=" & sc.Arguments
      WScript.Echo "  WORK=" & sc.WorkingDirectory
      On Error GoTo 0
    End If
  End If
Next
