"""Inline model_output.json into template.html to produce a self-contained index.html."""
from pathlib import Path

root = Path(__file__).parent
data = (root / "model_output.json").read_text()
html = (root / "template.html").read_text().replace("/*__DATA__*/null", data)
(root / "index.html").write_text(html)
print(f"wrote index.html ({len(html) / 1024:.1f} KB)")
