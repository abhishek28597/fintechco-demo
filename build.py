"""Inline model_output.json and recession_output.json into template.html to produce a self-contained index.html."""
from pathlib import Path

root = Path(__file__).parent
html = (root / "template.html").read_text()
html = html.replace("/*__DATA__*/null", (root / "model_output.json").read_text())
html = html.replace("/*__RDATA__*/null", (root / "recession_output.json").read_text())
(root / "index.html").write_text(html)
print(f"wrote index.html ({len(html) / 1024:.1f} KB)")
