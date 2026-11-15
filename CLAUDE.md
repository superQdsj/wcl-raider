# wcl-raider

## 攻略 HTML：节省上下文

成品页 `guides/<职业>/*.html` 和 `dist/` 是构建产物，**任何情况下都不要整份读取**。

- **改文字，有 `sources/` 的攻略**：改源文件（通常是 `body.part`、`head.part` 或 `src.html`），再跑同目录的 `build.py` 重新生成。
- **改文字，没有源文件的攻略**（神圣骑士全部，武器战大部分）：先用 grep 定位行号，输出要截短（例如 `grep -n 关键词 文件 | cut -c1-200`），再只读或只替换那几行。
- 不要读 `sources/*/icons.json`（几十 KB 的 base64）和 `dist/`。

## 图标

图标是共享文件 `guides/icons/<sha1 前 12 位>.jpg`，页面用相对路径引用，不内嵌 base64。
`build.py` 末尾会调用 `guides/tools/icons.py` 的 `externalize(out)`，自动把内嵌图标换成文件链接。
手写或别处拼出来的页面，跑一次 `python3 guides/tools/icons.py <页面>` 即可。
`scripts/build_site.py` 允许页面引用 `guides/icons/` 下的图片，并会一起发布。
