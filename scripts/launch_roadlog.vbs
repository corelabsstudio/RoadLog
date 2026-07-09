' 로드로그(RoadLog) 런처 — 서버 기동 후 브라우저 열기
Option Explicit

Dim sh, fso, root, venvPy, url, port, cmd, http, ok, i
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
venvPy = root & "\.venv\Scripts\python.exe"
url = "http://127.0.0.1:8501/"
port = "8501"

If Not fso.FileExists(venvPy) Then
  MsgBox "Python 가상환경을 찾을 수 없습니다." & vbCrLf & venvPy, vbCritical, "로드로그"
  WScript.Quit 1
End If

' 이미 서버가 떠 있는지 확인
ok = False
On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.Open "GET", url, False
http.setRequestHeader "Cache-Control", "no-cache"
http.Send
If Err.Number = 0 Then
  If http.Status >= 200 And http.Status < 500 Then ok = True
End If
Err.Clear
On Error GoTo 0

If Not ok Then
  ' 백그라운드로 FastAPI 서버 시작 (창 숨김)
  cmd = """" & venvPy & """ -m uvicorn server:app --host 127.0.0.1 --port " & port
  sh.CurrentDirectory = root
  sh.Run cmd, 0, False

  ' 기동 대기 (최대 ~20초)
  For i = 1 To 40
    WScript.Sleep 500
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", url, False
    http.Send
    If Err.Number = 0 Then
      If http.Status >= 200 And http.Status < 500 Then
        ok = True
        Exit For
      End If
    End If
    Err.Clear
    On Error GoTo 0
  Next
End If

' 기본 브라우저로 열기
sh.Run url, 1, False
