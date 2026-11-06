"""把本地 HTML 报告导出成 PDF / PNG（Playwright，优先用本机的 Google Chrome）。"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from .api import WCLError

PNG_WIDTH = 1100


def export(html_path: Path, pdf: Optional[str] = None, png: Optional[str] = None) -> List[Tuple[str, str]]:
    """PDF 带附录（展开），PNG 不带附录（适合直接发图）。都强制浅色。"""
    try:
        from playwright.sync_api import Error as PWError, sync_playwright
    except ImportError:
        raise WCLError("导出 PDF/PNG 需要 Playwright：pip install playwright（本机装了 Google Chrome 就不用再下载浏览器）。") from None
    url = Path(html_path).resolve().as_uri()
    done: List[Tuple[str, str]] = []
    with sync_playwright() as p:
        browser = None
        for kw in ({"channel": "chrome"}, {}):
            try:
                browser = p.chromium.launch(**kw)
                break
            except PWError:
                continue
        if browser is None:
            raise WCLError("找不到可用的浏览器：装 Google Chrome，或运行 python3 -m playwright install chromium。")
        page = browser.new_page(viewport={"width": PNG_WIDTH, "height": 900}, device_scale_factor=2,
                                color_scheme="light")
        page.goto(url)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except PWError:
            pass  # Wowhead 悬停脚本加载不了也不影响版面
        page.evaluate("document.documentElement.classList.add('light','export')")
        if png:
            page.evaluate("document.querySelectorAll('details').forEach(d => d.style.display='none')")
            page.screenshot(path=png, full_page=True)
            done.append(("PNG", png))
            page.evaluate("document.querySelectorAll('details').forEach(d => d.style.display='')")
        if pdf:
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            page.emulate_media(media="print", color_scheme="light")
            page.pdf(path=pdf, format="A4", print_background=True,
                     margin={"top": "10mm", "bottom": "12mm", "left": "8mm", "right": "8mm"})
            done.append(("PDF", pdf))
        browser.close()
    return done
