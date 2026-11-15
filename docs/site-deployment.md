# 攻略网站发布

使用 Cloudflare Pages 免费静态托管。首页与 404 页是手写的模板，放在 `site/`（`index.html`、`404.html`、`site.css`、`site.js`）：深色主题，整页随所选专精的职业色变化，顶部是专精印章切换，下方八张副本卡片各有一幅线描纹样，卡片上的要点取自攻略 `lede` 段里的短粗体词，没有粗体短词时退回摘要。选择记在网址 `#slug` 和浏览器本地。`build_site.py` 只负责收集攻略、提取元数据，并把数据以 JSON 注入 `site/index.html`。新增职业只需在 `build_site.py` 的 `CLASSES` 中登记（名称、简称、职业色、职业色上的文字色、印章字）；新增副本的纹样在 `site/site.js` 的 `MOTIFS` 中补一幅。

生产网址：https://wcl-raider.pages.dev/
项目名称：`wcl-raider`；生产分支：`main`。

## 生成发布包

在仓库根目录运行：

```sh
python3 scripts/build_site.py
```

产物为 `dist/site/` 和 `dist/wcl-raider-site.zip`。只收集 `guides/<职业>/` 顶层的 HTML 成品和它们引用的本地图片；不会上传源材料、证据包、复盘记录或 API 凭据。旧版成品保留，通过文件名中的日期区分。

## Cloudflare 登录与首次部署

```sh
npx --yes wrangler@4.162.0 login --scopes account:read user:read pages:write
npx --yes wrangler@4.162.0 pages project create wcl-raider --production-branch main --force
npx --yes wrangler@4.162.0 pages deploy dist/site --project-name wcl-raider --branch main
```

首次登录需要账号持有人在浏览器中完成登录及授权。项目名若被占用，需要换名；以部署命令实际返回的网址为准。

当前项目已创建，无需再次运行 `project create`。Wrangler 4.162.0 对新项目默认尝试转交 Workers；首次创建时通过 `--force` 明确创建 Pages 项目，后续部署不加此标记。

也可在 Cloudflare Pages 的 Direct Upload 中上传 ZIP，ZIP 根目录包含 `index.html`。

## 更新攻略

重新运行生成命令，再运行 `pages deploy`。上传完整目录替换当前站点，不要上传整个仓库。

部署后检查首页、包含中文路径的攻略、武器战手册内的图片链接及不存在路径的 404 页面。
