from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent
app = ROOT / "app.py"
snip = ROOT / "assets" / "_build_snippet.py"

ns: dict = {}
exec(snip.read_text(encoding="utf-8"), ns)
new_methods = ns["BUILD_METHODS"]

text = app.read_text(encoding="utf-8")
start = text.index("    def _build(self) -> None:")
end = text.index("    def _row(self, parent, row, label, var, width=50, show=None) -> None:")
out = text[:start] + new_methods + "\n" + text[end:]

old_log = """    def _log(self, msg: str) -> None:
        def append() -> None:
            self.txt_log.insert(tk.END, msg + \"\\n\")
            self.txt_log.see(tk.END)

        self.after(0, append)
"""
new_log = """    def _log(self, msg: str) -> None:
        def append() -> None:
            if not hasattr(self, \"txt_log\") or self.txt_log is None:
                return
            try:
                self.txt_log.insert(tk.END, msg + \"\\n\")
                self.txt_log.see(tk.END)
            except Exception:
                pass

        self.after(0, append)
"""
if old_log in out:
    out = out.replace(old_log, new_log)
else:
    # try alternate formatting
    pass

app.write_text(out, encoding="utf-8")
ast.parse(out)
print("OK spliced", len(new_methods))
