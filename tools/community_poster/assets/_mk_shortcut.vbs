Set sh = CreateObject("WScript.Shell")
Set sc = sh.CreateShortcut("C:\\Users\\hysoo\\Desktop\\ReachKit.lnk")
sc.TargetPath = "C:\\Users\\hysoo\\projects\\RoadLog\\tools\\community_poster\\ReachKit.bat"
sc.WorkingDirectory = "C:\\Users\\hysoo\\projects\\RoadLog\\tools\\community_poster"
sc.Description = "ReachKit"
sc.IconLocation = "C:\\Users\\hysoo\\projects\\RoadLog\\tools\\community_poster\\assets\\icon.ico,0"
sc.Save
