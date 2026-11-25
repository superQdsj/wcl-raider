(function () {
  "use strict";
  var root = document.documentElement;
  var $ = function (s, ctx) { return (ctx || document).querySelector(s); };
  var $$ = function (s, ctx) { return Array.from((ctx || document).querySelectorAll(s)); };
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var escReg = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); };
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var specIcon = function (name, cls) {
    return '<img class="ic' + (cls ? " " + cls : "") + '" src="/img/icons/' + esc(name) + '.jpg" alt="" width="28" height="28">';
  };
  var md = function (iso) {
    var p = String(iso).split("-");
    return p.length >= 3 ? +p[1] + "月" + +p[2] + "日" : esc(iso);
  };
  var shortMd = function (iso) {
    var p = String(iso).split("-");
    return p.length >= 3 ? +p[1] + "/" + (p[2].length < 2 ? "0" + p[2] : p[2]) : esc(iso);
  };

  var dataEl = $("#guide-data");
  if (!dataEl) {
    var saved = store.get("wr-color");
    if (saved && /^#[0-9a-f]{6}$/i.test(saved)) root.style.setProperty("--c", saved);
    return;
  }

  var data = JSON.parse(dataEl.textContent);
  var DUNGEONS = data.dungeons;
  var CLASSES = data.classes;
  var bySlug = {};
  CLASSES.forEach(function (c) { bySlug[c.slug] = c; });

  // Compute live site telemetry
  var currentCells = 0;
  var totalManuals = 0;
  var allEntries = [];
  CLASSES.forEach(function (c) {
    Object.keys(c.guides).forEach(function (dName) {
      var g = c.guides[dName];
      currentCells += 1;
      totalManuals += 1 + (g.old ? g.old.length : 0);
      var dInfo = DUNGEONS.filter(function (x) { return x.name === dName; })[0];
      allEntries.push({ cls: c, dungeon: dInfo || { name: dName, en: "", img: "altar" }, guide: g });
    });
  });

  if ($("#stat-total")) $("#stat-total").textContent = String(totalManuals);
  if ($("#stat-specs")) $("#stat-specs").textContent = String(CLASSES.length);
  if ($("#stat-dungeons")) $("#stat-dungeons").textContent = String(DUNGEONS.length);

  // ---------- Hero Interactive Showcase ----------
  var SAMPLES = [
    {
      slug: "hunter-bm",
      dungeon: "毒牙祭坛",
      label: "兽王猎人",
      note: "毒牙祭坛 · 5 场 +22～23 限时实录交叉比对",
      pins: [
        { t: "0:48", txt: "反制·嘶鸣", sub: true },
        { t: "1:52", txt: "灵龟守护", sub: false },
        { t: "4:18", txt: "优胜劣汰", sub: true },
        { t: "6:05", txt: "灵龟守护", sub: false }
      ],
      rows: [
        {
          must: true,
          mIcon: "/guides/icons/0215a087c1ad.jpg",
          mech: "三重喷吐（拉维）",
          actIcon: "/guides/icons/fc38901d4be6.jpg",
          act: "灵龟守护",
          why: "毒球飞来先散开，<b>砸脸前开龟壳直击与 10 秒跳伤全挡</b>；冷却时交优胜劣汰压前几跳。"
        },
        {
          must: true,
          mIcon: "/guides/icons/784b86cd89cd.jpg",
          mech: "刺耳嘶鸣（原始毒蛇）",
          actIcon: "/guides/icons/efba0b57fcd2.jpg",
          act: "反制射击",
          why: "恶臭喷吐断不了，反制死盯嘶鸣防全队降急速；起手可冰冻陷阱先控一只。"
        }
      ],
      barTitle: "拉维 · 三重喷吐单轮总承伤（+23 实测）",
      barDelta: "−100% 免疫",
      bars: [
        { lbl: "无减伤硬吃", cls: "raw", w: "100%", val: "直击 66万 + 跳伤 210万" },
        { lbl: "灵龟守护", cls: "imm", w: "100%", val: "0 · 整段不上身" }
      ]
    },
    {
      slug: "paladin-ret",
      dungeon: "毒牙祭坛",
      label: "惩戒圣骑士",
      note: "毒牙祭坛 · 5 场 +23 限时惩戒骑保人轴提取",
      pins: [
        { t: "0:32", txt: "圣盾+保护", sub: false },
        { t: "2:10", txt: "圣佑术", sub: true },
        { t: "5:40", txt: "自由祝福", sub: true },
        { t: "8:15", txt: "牺牲祝福", sub: false }
      ],
      rows: [
        {
          must: true,
          mIcon: "/guides/icons/f8cc2aec4f71.jpg",
          mech: "鲜血献祭（仪式首领）",
          actIcon: "/guides/icons/80d64e11d1d9.jpg",
          act: "保护祝福 给队友",
          why: "圣盾清自己身上的巨额治疗吸收盾，<b>保护祝福顺手秒清一名输出队友</b>，大幅减轻治疗刷盾压力。"
        },
        {
          must: true,
          mIcon: "/guides/icons/9c51e8a6cccc.jpg",
          mech: "切骨者飞斧（祖尔加）",
          actIcon: "/guides/icons/5111558479b0.jpg",
          act: "牺牲祝福 盯被点者",
          why: "5 秒读条看准飞斧点谁，读条中段挂牺牲，<b>首击到 7 秒无视护甲流血全程替扛 30%</b>。"
        }
      ],
      barTitle: "祖尔加 · 切骨者流血每跳承伤（+23 实测）",
      barDelta: "−39% 压血线",
      bars: [
        { lbl: "无减伤每跳", cls: "raw", w: "100%", val: "约 31 万 / 秒" },
        { lbl: "圣佑术覆盖", cls: "mit", w: "61%", val: "约 19 万 / 秒" }
      ]
    },
    {
      slug: "shaman-elemental",
      dungeon: "毒牙祭坛",
      label: "元素萨满",
      note: "毒牙祭坛 · +23 限时先知元素萨实录提取",
      pins: [
        { t: "0:28", txt: "星界转移", sub: false },
        { t: "1:15", txt: "净化骨头", sub: true },
        { t: "3:40", txt: "风剪盯断", sub: true },
        { t: "6:20", txt: "星界转移", sub: false }
      ],
      rows: [
        {
          must: true,
          mIcon: "/guides/icons/f8cc2aec4f71.jpg",
          mech: "鲜血献祭（3 秒读条）",
          actIcon: "/guides/icons/ca0443aca328.jpg",
          act: "星界转移",
          why: "读完约 2 秒后落刀，<b>卡读条末开星界顺带盖住不稳定图腾跳伤</b>；进拉维前留给首轮食腐。"
        },
        {
          must: false,
          mIcon: "/guides/icons/3105f4c8479d.jpg",
          mech: "被诅咒的骨头（路边物件）",
          actIcon: "/guides/icons/3105f4c8479d.jpg",
          act: "净化灵魂",
          why: "驱散诅咒放出阿曼尼精魂（<b>给周围敌人叠最高 5% 易伤</b>），拉维与盘蛇前顺路必驱。"
        }
      ],
      barTitle: "仪式首领 · 鲜血献祭落刀窗口（+23 实测）",
      barDelta: "−40% 减伤覆盖",
      bars: [
        { lbl: "裸吃物理落刀", cls: "raw", w: "100%", val: "全团高压 + 1分钟吸奶盾" },
        { lbl: "星界转移预开", cls: "mit", w: "60%", val: "落刀与图腾双减 40%" }
      ]
    }
  ];

  var scTabsEl = $(".sc-tabs");
  var scBodyEl = $("#sc-body");
  var scNoteEl = $("#sc-note");
  var scOpenEl = $("#sc-open");

  if (scTabsEl && scBodyEl) {
    scTabsEl.innerHTML = SAMPLES.map(function (s, idx) {
      var c = bySlug[s.slug] || CLASSES[0];
      return '<button type="button" role="tab" class="sc-tab" data-idx="' + idx + '" style="--k:' + c.color + '" aria-selected="' + (idx === 0 ? "true" : "false") + '">' +
        specIcon(c.icon, "sm") + "<span>" + esc(s.label) + "</span></button>";
    }).join("");

    var renderSample = function (idx) {
      var s = SAMPLES[idx] || SAMPLES[0];
      var c = bySlug[s.slug] || CLASSES[0];
      var scWrap = $(".showcase");
      if (scWrap) scWrap.style.setProperty("--sc-c", c.color);
      $$(".sc-tab", scTabsEl).forEach(function (btn, i) {
        btn.setAttribute("aria-selected", i === idx ? "true" : "false");
      });
      var g = c.guides && c.guides[s.dungeon];
      if (scNoteEl) scNoteEl.textContent = s.note;
      if (scOpenEl) {
        scOpenEl.href = g ? g.href : "#" + c.slug;
        scOpenEl.textContent = "阅读" + c.spec + c.cls + "完整手册 →";
      }

      var pinsHtml = s.pins.map(function (p) {
        return '<span class="sc-pin' + (p.sub ? " sub" : "") + '"><i></i>' + esc(p.t) + " " + esc(p.txt) + "</span>";
      }).join("");

      var rowsHtml = s.rows.map(function (r) {
        return '<div class="sc-row' + (r.must ? " must" : "") + '">' +
          '<div class="sc-row-top">' +
            '<span class="sc-mech"><img class="ic sm" src="' + esc(r.mIcon) + '" alt="" width="20" height="20">' +
              (r.must ? '<span class="badge-must">必做</span>' : "") + esc(r.mech) + "</span>" +
            '<span class="sc-to">→</span>' +
            '<span class="sc-chip' + (r.must ? "" : " alt") + '"><img class="ic sm" src="' + esc(r.actIcon) + '" alt="" width="20" height="20">' + esc(r.act) + "</span>" +
          "</div>" +
          '<p class="sc-why">' + r.why + "</p>" +
        "</div>";
      }).join("");

      var barsHtml = s.bars.map(function (b) {
        return '<div class="sc-bar-row"><span>' + esc(b.lbl) + '</span><div class="sc-meter"><span class="' + b.cls + '" style="width:' + b.w + '">' + esc(b.val) + "</span></div></div>";
      }).join("");

      scBodyEl.innerHTML =
        '<div class="sc-tl">' +
          '<div class="sc-tl-head"><span>01 · 单轨冷却时间轴</span><span>+23 限时实录</span></div>' +
          '<div class="sc-tl-track">' +
            '<span class="sc-seg trash">开场</span>' +
            '<span class="sc-seg boss">① 拉维</span>' +
            '<span class="sc-seg trash">进化者</span>' +
            '<span class="sc-seg boss">② 盘蛇</span>' +
            '<span class="sc-seg boss">③ 祖尔加</span>' +
          "</div>" +
          '<div class="sc-pins">' + pinsHtml + "</div>" +
        "</div>" +
        '<div class="sc-rows">' + rowsHtml + "</div>" +
        '<div class="sc-bars">' +
          '<div class="sc-bar-cap"><span>' + esc(s.barTitle) + "</span><em>" + esc(s.barDelta) + "</em></div>" +
          barsHtml +
        "</div>";
    };

    scTabsEl.addEventListener("click", function (e) {
      var btn = e.target.closest(".sc-tab");
      if (!btn) return;
      var idx = +btn.dataset.idx;
      var s = SAMPLES[idx];
      if (s && bySlug[s.slug]) root.style.setProperty("--c", bySlug[s.slug].color);
      renderSample(idx);
    });
    renderSample(0);
  }

  // ---------- Manual Hub State & Rendering ----------
  var state = {
    mode: "spec", // "spec" | "dungeon"
    role: "all",
    slug: CLASSES[0].slug,
    dungeon: DUNGEONS[0].name,
    query: ""
  };

  var roleBar = $(".role-bar");
  var specBar = $(".specs");
  var dungeonBar = $("#dungeon-tabs");
  var grid = $("#manual-grid");
  var searchInput = $("#manual-search");
  var searchClear = $("#search-clear");
  var searchStatus = $("#search-status");
  var searchCount = $("#search-count");

  // Build role filter pills
  var roles = ["all"];
  var roleCounts = { all: CLASSES.length };
  CLASSES.forEach(function (c) {
    if (roles.indexOf(c.role) === -1) roles.push(c.role);
    roleCounts[c.role] = (roleCounts[c.role] || 0) + 1;
  });
  roleBar.innerHTML = roles.map(function (r) {
    var lbl = r === "all" ? "全部专精" : r;
    return '<button type="button" class="role-pill" data-role="' + esc(r) + '" aria-pressed="' + (r === "all" ? "true" : "false") + '">' +
      esc(lbl) + "<small>" + roleCounts[r] + "</small></button>";
  }).join("");

  // Build spec selector strip
  function renderSpecTabs() {
    var visible = CLASSES.filter(function (c) { return state.role === "all" || c.role === state.role; });
    specBar.innerHTML = visible.map(function (c) {
      var done = Object.keys(c.guides).length;
      var pct = Math.round((done / DUNGEONS.length) * 100);
      return '<a class="spec" href="#' + esc(c.slug) + '" data-slug="' + esc(c.slug) + '" style="--k:' + c.color + '" aria-current="' + (c.slug === state.slug ? "true" : "false") + '">' +
        specIcon(c.icon) +
        '<span class="nm"><span class="nm-row"><b>' + esc(c.spec + c.cls) + '</b><span class="cnt">' + done + "/" + DUNGEONS.length + "</span></span>" +
        "<small>" + esc(c.role) + "</small></span>" +
        '<span class="prog" aria-hidden="true"><i style="width:' + pct + '%"></i></span></a>';
    }).join("");
  }

  // Build dungeon selector strip
  function renderDungeonTabs() {
    dungeonBar.innerHTML = DUNGEONS.map(function (d) {
      var cnt = CLASSES.filter(function (c) { return !!c.guides[d.name]; }).length;
      return '<button type="button" class="dtab" data-dungeon="' + esc(d.name) + '" aria-selected="' + (d.name === state.dungeon ? "true" : "false") + '">' +
        '<img src="/img/dungeons/' + esc(d.img) + '.jpg" alt="" width="360" height="202" loading="lazy">' +
        "<span>" + esc(d.name) + "</span>" +
        "<small>" + cnt + "/" + CLASSES.length + " 专精已出</small></button>";
    }).join("");
  }

  function highlight(text, q) {
    var str = String(text);
    var terms = String(q || "").trim().split(/\s+/).filter(Boolean);
    if (!terms.length) return esc(str);
    var re = new RegExp("(" + terms.map(escReg).join("|") + ")", "ig");
    return str.split(re).map(function (part, idx) {
      return idx % 2 === 1 ? "<mark>" + esc(part) + "</mark>" : esc(part);
    }).join("");
  }

  function dungeonCard(c, d, idx, q, showSpecTag) {
    var g = c.guides[d.name];
    var numBadge = idx !== null ? '<span class="art-pill">' + (idx < 9 ? "0" + (idx + 1) : idx + 1) + "</span>" : '<span class="art-pill">' + esc(d.name) + "</span>";
    var tierBadge = g && g.level ? '<span class="art-pill tier">' + esc(g.level) + " 实录</span>" : "";
    var art = '<div class="art"><img class="bg-art" src="/img/dungeons/' + esc(d.img) + '.jpg" alt="" width="720" height="405" loading="lazy">' +
      '<div class="art-badges">' + numBadge + tierBadge + "</div></div>";

    var specRow = showSpecTag
      ? '<div class="card-spec-row">' + specIcon(c.icon, "sm") + "<b>" + highlight(c.spec + c.cls, q) + "</b><span>" + esc(c.role) + "</span></div>"
      : "";
    var head = "<div><h3>" + highlight(d.name, q) + '</h3><p class="en">' + highlight(d.en, q) + "</p></div>";

    if (!g) {
      return '<li class="card todo" style="--card-c:' + c.color + '">' + art +
        '<div class="body">' + specRow + head + '<p class="gist">该副本的高层限时录像证据包正在采集与核对中。</p></div></li>';
    }
    var olds = (g.old || []).map(function (o) {
      return '<a class="old" href="' + o.href + '">' + md(o.date) + "旧版</a>";
    }).join("");
    return '<li class="card" style="--card-c:' + c.color + '"><a class="hit" href="' + g.href + '">' + art +
      '<div class="body">' + specRow + head + '<p class="gist">' + highlight(g.lede, q) + "</p></div></a>" +
      '<div class="meta"><span>' + md(g.date) + "更新</span>" + olds +
      '<a class="open" href="' + g.href + '" tabindex="-1" aria-hidden="true">阅读手册 →</a></div></li>';
  }

  function specForDungeonCard(c, d) {
    var g = c.guides[d.name];
    var head = '<div class="card-spec-row">' + specIcon(c.icon) +
      '<div style="min-width:0"><h3>' + esc(c.spec + c.cls) + '</h3><p class="en">' + esc(c.en) + "</p></div>" +
      "<span>" + esc(c.role) + "</span></div>";
    if (!g) {
      return '<li class="card todo" style="--card-c:' + c.color + '">' +
        '<div class="body">' + head + '<p class="gist">这个专精在「' + esc(d.name) + "」的手册还在整理。</p></div></li>";
    }
    var olds = (g.old || []).map(function (o) {
      return '<a class="old" href="' + o.href + '">' + md(o.date) + "旧版</a>";
    }).join("");
    return '<li class="card" style="--card-c:' + c.color + '"><a class="hit" href="' + g.href + '">' +
      '<div class="body">' + head + '<p class="gist">' + esc(g.lede) + "</p></div></a>" +
      '<div class="meta"><span>' + (g.level ? esc(g.level) + " · " : "") + md(g.date) + "更新</span>" + olds +
      '<a class="open" href="' + g.href + '" tabindex="-1" aria-hidden="true">打开手册 →</a></div></li>';
  }

  function renderHub() {
    var q = state.query.trim();
    var isSearching = q.length > 0;
    searchClear.hidden = !isSearching;
    searchStatus.hidden = !isSearching;

    $("#tab-mode-spec").setAttribute("aria-selected", state.mode === "spec" && !isSearching ? "true" : "false");
    $("#tab-mode-dungeon").setAttribute("aria-selected", state.mode === "dungeon" && !isSearching ? "true" : "false");

    if (isSearching) {
      $("#spec-mode-pane").hidden = true;
      $("#dungeon-mode-pane").hidden = true;
      var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
      var matches = allEntries.filter(function (item) {
        var hay = [
          item.cls.spec, item.cls.cls, item.cls.en, item.cls.role,
          item.dungeon.name, item.dungeon.en, item.guide.lede, item.guide.level || ""
        ].join(" ").toLowerCase();
        return terms.every(function (t) { return hay.indexOf(t) !== -1; });
      });
      searchCount.innerHTML = '全站搜索「<b>' + esc(q) + "</b>」：共找到 <b>" + matches.length + "</b> 篇匹配手册";
      if (!matches.length) {
        grid.innerHTML = '<li class="empty-box"><p>没有找到包含「' + esc(q) + '」的手册，试试搜副本名（如：毒牙、诸王）或技能词（如：龟壳、圣盾、星界）。</p><button type="button" class="btn-sec" id="empty-clear">清空搜索词</button></li>';
        var ec = $("#empty-clear");
        if (ec) ec.onclick = clearSearch;
      } else {
        grid.innerHTML = matches.map(function (m) {
          return dungeonCard(m.cls, m.dungeon, null, q, true);
        }).join("");
      }
      return;
    }

    if (state.mode === "dungeon") {
      $("#spec-mode-pane").hidden = true;
      $("#dungeon-mode-pane").hidden = false;
      renderDungeonTabs();
      var d = DUNGEONS.filter(function (x) { return x.name === state.dungeon; })[0] || DUNGEONS[0];
      var covered = CLASSES.filter(function (c) { return !!c.guides[d.name]; }).length;
      $("#dungeon-en-label").textContent = d.en + " · ALL SPECS";
      $("#dungeon-title-label").innerHTML = '<span class="cls">' + esc(d.name) + "</span> · 全职业应对总览";
      $("#dungeon-chips").innerHTML =
        '<span class="chip">已发布专精 <b>' + covered + " / " + CLASSES.length + "</b></span>" +
        '<span class="chip">适用场景 <b>车队排轴 / 多号速查</b></span>';
      grid.innerHTML = CLASSES.map(function (c) { return specForDungeonCard(c, d); }).join("");
      return;
    }

    // Spec mode (default)
    $("#spec-mode-pane").hidden = false;
    $("#dungeon-mode-pane").hidden = true;
    var c = bySlug[state.slug] || CLASSES[0];
    state.slug = c.slug;
    root.style.setProperty("--c", c.color);
    renderSpecTabs();

    $("#spec-banner-icon").src = "/img/icons/" + c.icon + ".jpg";
    $("#spec-en").textContent = c.en;
    $("#spec-name").innerHTML = '<span class="cls">' + esc(c.spec) + "</span>" + esc(c.cls) + " · 赛季大秘境手册";

    var gKeys = Object.keys(c.guides);
    var dates = gKeys.map(function (k) { return c.guides[k].date; }).sort();
    $("#spec-chips").innerHTML =
      '<span class="chip">定位 <b>' + esc(c.role) + "</b></span>" +
      '<span class="chip">已覆盖 <b>' + gKeys.length + " / " + DUNGEONS.length + " 本</b></span>" +
      (dates.length ? '<span class="chip">最近更新 <b>' + md(dates[dates.length - 1]) + "</b></span>" : "");

    grid.innerHTML = DUNGEONS.map(function (d, i) { return dungeonCard(c, d, i, "", false); }).join("");
    store.set("wr-class", c.slug);
    store.set("wr-color", c.color);
  }

  function clearSearch() {
    state.query = "";
    searchInput.value = "";
    renderHub();
  }

  // Event listeners for Manual Hub
  roleBar.addEventListener("click", function (e) {
    var btn = e.target.closest(".role-pill");
    if (!btn) return;
    state.role = btn.dataset.role;
    $$(".role-pill", roleBar).forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.role === state.role ? "true" : "false");
    });
    var visible = CLASSES.filter(function (c) { return state.role === "all" || c.role === state.role; });
    if (visible.length && !visible.some(function (c) { return c.slug === state.slug; })) {
      state.slug = visible[0].slug;
    }
    renderHub();
  });

  specBar.addEventListener("click", function (e) {
    var t = e.target.closest(".spec");
    if (!t) return;
    e.preventDefault();
    state.mode = "spec";
    state.slug = t.dataset.slug;
    renderHub();
    history.replaceState(null, "", "#" + state.slug);
  });

  dungeonBar.addEventListener("click", function (e) {
    var t = e.target.closest(".dtab");
    if (!t) return;
    state.mode = "dungeon";
    state.dungeon = t.dataset.dungeon;
    renderHub();
    var dObj = DUNGEONS.filter(function (x) { return x.name === state.dungeon; })[0];
    if (dObj) history.replaceState(null, "", "#dungeon-" + dObj.img);
  });

  $$(".vtab").forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.query = "";
      searchInput.value = "";
      state.mode = btn.dataset.mode;
      renderHub();
    });
  });

  searchInput.addEventListener("input", function () {
    state.query = searchInput.value;
    renderHub();
  });
  searchClear.addEventListener("click", function () {
    clearSearch();
    searchInput.focus();
  });
  $("#search-reset").addEventListener("click", clearSearch);

  var jumpSearch = $("#jump-search");
  if (jumpSearch) {
    jumpSearch.addEventListener("click", function () {
      $("#manuals").scrollIntoView({ behavior: "smooth" });
      setTimeout(function () { searchInput.focus(); }, 220);
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !/^(INPUT|TEXTAREA)$/.test((e.target && e.target.tagName) || "")) {
      e.preventDefault();
      $("#manuals").scrollIntoView({ behavior: "smooth" });
      searchInput.focus();
    } else if (e.key === "Escape" && document.activeElement === searchInput && state.query) {
      clearSearch();
    }
  });

  var ctaDungeon = $("#cta-dungeon");
  if (ctaDungeon) {
    ctaDungeon.addEventListener("click", function () {
      state.mode = "dungeon";
      state.query = "";
      searchInput.value = "";
      renderHub();
      $("#manuals").scrollIntoView({ behavior: "smooth" });
    });
  }
  var ctaSpec = $("#cta-spec");
  if (ctaSpec) {
    ctaSpec.addEventListener("click", function () {
      state.mode = "spec";
      state.query = "";
      searchInput.value = "";
      renderHub();
    });
  }

  // ---------- 03: Coverage Matrix & Recent Releases ----------
  var matrixEl = $("#coverage-matrix");
  var matrixSumEl = $("#matrix-summary");
  if (matrixEl) {
    var totalPossible = CLASSES.length * DUNGEONS.length;
    if (matrixSumEl) {
      matrixSumEl.innerHTML =
        '<span class="chip">单元覆盖率 <b>' + currentCells + " / " + totalPossible + "（" + Math.round((currentCells / totalPossible) * 100) + "%）</b></span>" +
        '<span class="chip">含历史归档 <b>' + totalManuals + " 篇 HTML</b></span>";
    }
    var thead = "<thead><tr><th>职业专精</th>" + DUNGEONS.map(function (d) {
      return '<th><a href="#dungeon-' + esc(d.img) + '" data-jump-dungeon="' + esc(d.name) + '">' + esc(d.name) + "</a></th>";
    }).join("") + "</tr></thead>";

    var tbody = "<tbody>" + CLASSES.map(function (c) {
      var done = Object.keys(c.guides).length;
      var cells = DUNGEONS.map(function (d) {
        var g = c.guides[d.name];
        if (!g) return '<td><span class="m-cell-miss" title="整理中">—</span></td>';
        return '<td><a class="m-cell-ok" style="--k:' + c.color + '" href="' + g.href + '" title="' + esc(c.spec + c.cls + " · " + d.name + "（" + md(g.date) + "更新）") + '">✓ ' + shortMd(g.date) + "</a></td>";
      }).join("");
      return "<tr style=\"--k:" + c.color + "\"><th>" +
        '<a class="m-spec-cell" href="#' + esc(c.slug) + '" data-jump-spec="' + esc(c.slug) + '">' +
        specIcon(c.icon, "sm") + "<b>" + esc(c.spec + c.cls) + "</b><small>" + done + "/" + DUNGEONS.length + "</small></a></th>" +
        cells + "</tr>";
    }).join("") + "</tbody>";

    matrixEl.innerHTML = thead + tbody;
  }

  var recentEl = $("#recent-grid");
  if (recentEl) {
    var latest = allEntries.slice().sort(function (a, b) {
      return b.guide.date.localeCompare(a.guide.date);
    }).slice(0, 6);
    recentEl.innerHTML = latest.map(function (item) {
      return '<a class="rec-item" style="--k:' + item.cls.color + '" href="' + item.guide.href + '">' +
        specIcon(item.cls.icon) +
        '<div class="rec-body">' +
          '<div class="rec-top"><span class="spec-tag">' + esc(item.cls.spec + item.cls.cls) + "</span><b>" + esc(item.dungeon.name) + "</b><time>" + md(item.guide.date) + "</time></div>" +
          '<p class="rec-gist">' + esc(item.guide.lede) + "</p>" +
        "</div></a>";
    }).join("");
  }

  // ---------- Footer Quick Links ----------
  var footSpecs = $("#foot-specs");
  if (footSpecs) {
    footSpecs.innerHTML = CLASSES.map(function (c) {
      return '<li><a href="#' + esc(c.slug) + '" data-jump-spec="' + esc(c.slug) + '">' + esc(c.spec + c.cls) + "（" + Object.keys(c.guides).length + "/" + DUNGEONS.length + "）</a></li>";
    }).join("");
  }
  var footDungeons = $("#foot-dungeons");
  if (footDungeons) {
    footDungeons.innerHTML = DUNGEONS.map(function (d) {
      return '<li><a href="#dungeon-' + esc(d.img) + '" data-jump-dungeon="' + esc(d.name) + '">' + esc(d.name) + "</a></li>";
    }).join("");
  }

  document.addEventListener("click", function (e) {
    var js = e.target.closest("[data-jump-spec]");
    if (js) {
      e.preventDefault();
      state.mode = "spec";
      state.role = "all";
      state.query = "";
      searchInput.value = "";
      state.slug = js.dataset.jumpSpec;
      $$(".role-pill", roleBar).forEach(function (b) {
        b.setAttribute("aria-pressed", b.dataset.role === "all" ? "true" : "false");
      });
      renderHub();
      history.replaceState(null, "", "#" + state.slug);
      $("#manuals").scrollIntoView({ behavior: "smooth" });
      return;
    }
    var jd = e.target.closest("[data-jump-dungeon]");
    if (jd) {
      e.preventDefault();
      state.mode = "dungeon";
      state.query = "";
      searchInput.value = "";
      state.dungeon = jd.dataset.jumpDungeon;
      renderHub();
      var dObj = DUNGEONS.filter(function (x) { return x.name === state.dungeon; })[0];
      if (dObj) history.replaceState(null, "", "#dungeon-" + dObj.img);
      $("#manuals").scrollIntoView({ behavior: "smooth" });
    }
  });

  // ---------- Hash Routing & Initial State ----------
  function applyHash(scrollOnMatch) {
    var raw = decodeURIComponent(location.hash.slice(1));
    if (raw && bySlug[raw]) {
      state.mode = "spec";
      state.role = "all";
      state.slug = raw;
      document.title = bySlug[raw].spec + bySlug[raw].cls + "｜wcl-raider 大秘境作战手册";
      renderHub();
      if (scrollOnMatch) $("#manuals").scrollIntoView();
      return;
    }
    if (raw && raw.indexOf("dungeon-") === 0) {
      var imgSlug = raw.slice(8);
      var hit = DUNGEONS.filter(function (d) { return d.img === imgSlug || d.name === imgSlug; })[0];
      if (hit) {
        state.mode = "dungeon";
        state.dungeon = hit.name;
        renderHub();
        if (scrollOnMatch) $("#manuals").scrollIntoView();
        return;
      }
    }
    var savedSlug = store.get("wr-class");
    if (savedSlug && bySlug[savedSlug]) state.slug = savedSlug;
    renderHub();
  }

  window.addEventListener("hashchange", function () { applyHash(false); });
  applyHash(true);
})();
