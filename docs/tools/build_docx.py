"""Сборка главной документации в DOCX: python docs/tools/build_docx.py

Склеивает разделы docs/*.md в один файл, рисует mermaid-схемы в PNG (playwright),
подписи к рисункам берёт из alt-текста. Результат: docs/dist/documentation.docx.
Зависимости: docs/tools/requirements.txt (pip install -r ..., playwright install chromium).
"""
import re
import sys
from pathlib import Path

import pypandoc

DOCS = Path(__file__).resolve().parents[1]
DIST = DOCS / "dist"
ORDER = [
    "00-title.md", "01-audience-scenarios-boundaries.md", "02-architecture.md", "03-deployment.md",
    "04-matching.md", "05-economics.md", "06-simulation.md", "07-data.md", "08-user-guide.md",
    "09-admin-guide.md", "10-libraries-sources.md", "11-integrations.md", "12-limitations-roadmap.md",
    "appendix-A-assumptions.md", "appendix-B-data-quality.md", "appendix-V-status.md",
    "appendix-G-demo-and-check.md", "appendix-D-rules.md", "appendix-E-schema.md",
    "appendix-Zh-site-fields.md", "appendix-Z-compliance.md",
]
MERMAID = re.compile(r"```mermaid\n(.*?)```", re.S)
CAPTION = re.compile(r"^\*Рисунок [^\n]*\*\n", re.M)


def render_mermaid(blocks: list[str]) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        for i, code in enumerate(blocks, 1):
            html = ('<html><body style="background:#fff"><pre class="mermaid">' + code +
                    '</pre><script type="module">import m from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";'
                    'm.initialize({startOnLoad:false});await m.run();document.body.dataset.done="1"</script></body></html>')
            page.set_content(html)
            page.wait_for_selector("body[data-done='1']", timeout=30000)
            path = DIST / f"diagram-{i}.png"
            page.locator("svg").first.screenshot(path=str(path))
            out.append(path)
        browser.close()
    return out


def main() -> None:
    DIST.mkdir(exist_ok=True)
    parts = [(DOCS / name).read_text(encoding="utf-8") for name in ORDER]
    text = "\n\n\\newpage\n\n".join(parts)
    text = CAPTION.sub("", text)
    blocks = MERMAID.findall(text)
    try:
        images = render_mermaid(blocks) if blocks else []
        it = iter(images)
        n = [0]

        def repl(_m):
            n[0] += 1
            return f"![Рисунок: схема {n[0]}]({next(it).as_posix()})"

        text = MERMAID.sub(repl, text)
    except Exception as exc:  # без сети схемы останутся кодом
        print(f"mermaid не отрисован: {exc}", file=sys.stderr)
    src = DIST / "documentation.md"
    src.write_text(text, encoding="utf-8")
    pypandoc.convert_file(
        str(src), "docx", outputfile=str(DIST / "documentation.docx"),
        extra_args=["--toc", "--toc-depth=2", f"--resource-path={DOCS}", "--from=markdown+tex_math_dollars+pipe_tables"])
    print(DIST / "documentation.docx")


if __name__ == "__main__":
    main()
