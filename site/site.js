(function () {
  "use strict";
  var root = document.documentElement;
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  /* ---- sigil: an {8/3} star, one node per dungeon ---- */
  var pt = function (i, r) {
    var a = (i * 45 - 90) * Math.PI / 180;
    return [200 + r * Math.cos(a), 200 + r * Math.sin(a)];
  };
  var star = $(".sigil .star");
  if (star) {
    var order = [0, 3, 6, 1, 4, 7, 2, 5];
    var d = order.map(function (i, n) { var p = pt(i, 150); return (n ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join("") + "Z";
    var inner = [0, 2, 4, 6].map(function (i, n) { var p = pt(i, 62); return (n ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join("") + "Z";
    var nodes = "";
    for (var i = 0; i < 8; i++) { var p = pt(i, 150); nodes += '<circle class="node" data-n="' + i + '" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="6"/>'; }
    star.innerHTML = '<path d="' + d + '"/><path d="' + inner + '" style="opacity:.4"/>' + nodes;
  }

  var splitTitle = function (h, text) {
    h.innerHTML = Array.from(text).map(function (ch, i) {
      return '<span class="ch" style="--i:' + i + '">' + esc(ch) + "</span>";
    }).join("");
  };

  var dataEl = $("#guide-data");
  if (!dataEl) {
    // 404 and other static pages: borrow the last chosen class color.
    var c = store.get("wr-color");
    var on = store.get("wr-on");
    if (c && /^#[0-9a-f]{6}$/i.test(c)) root.style.setProperty("--c", c);
    if (on && /^#[0-9a-f]{6}$/i.test(on)) root.style.setProperty("--on", on);
    var h = $("h1[data-split]");
    if (h) splitTitle(h, h.textContent.trim());
    return;
  }

  /* ---- dungeon line-art motifs (viewBox 0 0 200 200) ---- */
  var rays = function () {
    var s = '<circle cx="100" cy="100" r="30"/><circle cx="100" cy="100" r="44" stroke-dasharray="2 6"/>';
    for (var i = 0; i < 16; i++) {
      var a = i * Math.PI / 8, r1 = 54, r2 = i % 2 ? 78 : 96;
      s += '<path d="M' + (100 + r1 * Math.cos(a)).toFixed(1) + " " + (100 + r1 * Math.sin(a)).toFixed(1) +
        "L" + (100 + r2 * Math.cos(a)).toFixed(1) + " " + (100 + r2 * Math.sin(a)).toFixed(1) + '"/>';
    }
    return s;
  };
  var arches = function () {
    var s = "";
    [1, .78, .58, .4, .25].forEach(function (k) {
      var w = 70 * k, top = 100 - 80 * k, b = 100 + 80 * k, m = 100 - 20 * k;
      s += '<path d="M' + (100 - w) + " " + b + "V" + m + "Q" + (100 - w) + " " + top + " 100 " + top +
        "Q" + (100 + w) + " " + top + " " + (100 + w) + " " + m + "V" + b + '"/>';
    });
    return s + '<path d="M10 180H190"/>';
  };
  var MOTIFS = {
    "夺目谷": rays(),
    "塞塔里斯神庙": '<path d="M26 172H174M42 172V146H158V172M58 146V120H142V146M76 120V94H124V120M90 94V76H110V94"/><path d="M112 14L88 50H106L90 76"/><path d="M40 64C56 44 72 70 88 52"/>',
    "密谋小径": arches(),
    "毒牙祭坛": '<path d="M24 36Q100 60 176 36"/><path d="M50 40Q58 112 86 168Q92 104 98 46"/><path d="M150 40Q142 112 114 168Q108 104 102 46"/><path d="M100 178q-7 10 0 15q7-5 0-15"/><path d="M64 70Q70 110 84 140" stroke-dasharray="2 6"/>',
    "红玉新生法池": '<path d="M100 22L132 70L100 118L68 70Z M68 70H132 M100 22V118 M84 46L116 94 M116 46L84 94" /><ellipse cx="100" cy="150" rx="86" ry="26"/><ellipse cx="100" cy="150" rx="60" ry="17"/><ellipse cx="100" cy="150" rx="34" ry="9"/>',
    "纳洛拉克的洞穴": '<path d="M14 196Q100 20 186 196"/><path d="M60 52Q96 104 76 168"/><path d="M96 40Q134 98 114 176"/><path d="M132 52Q166 104 150 160"/>',
    "虚空之痕竞技场": '<circle cx="100" cy="100" r="86"/><circle cx="100" cy="100" r="68" stroke-dasharray="3 7"/><path d="M34 100Q100 46 166 100Q100 154 34 100Z"/><circle cx="100" cy="100" r="16"/><circle cx="100" cy="100" r="4"/>',
    "诸王之眠": '<path d="M44 118V52L72 86L100 40L128 86L156 52V118Z"/><circle cx="100" cy="40" r="5"/><circle cx="44" cy="52" r="4"/><circle cx="156" cy="52" r="4"/><path d="M36 134H164M48 150H152M62 166H138"/>'
  };
  var BOOK = '<svg viewBox="0 0 48 48" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M24 12C18 8 10 8 5 10V38C10 36 18 36 24 40C30 36 38 36 43 38V10C38 8 30 8 24 12Z"/><path d="M24 12V40"/></g></svg>';

  var data = JSON.parse(dataEl.textContent);
  var DUNGEONS = data.dungeons;
  var seals = $(".seals"), grid = $(".grid"), extra = $(".extra"), h1 = $("#spec-name");
  var nodes = Array.from(document.querySelectorAll(".sigil .node"));

  var md = function (iso) { var p = iso.split("-"); return +p[1] + "月" + +p[2] + "日"; };

  seals.innerHTML = data.classes.map(function (c) {
    var n = Object.keys(c.guides).length;
    return '<a class="seal" href="#' + c.slug + '" data-slug="' + c.slug + '" style="--k:' + c.color + ";--on-k:" + c.on + '">' +
      "<b>" + esc(c.glyph) + '</b><span><span class="full">' + esc(c.name) + '</span><span class="short">' + esc(c.short) + "</span><small>" + n + " 本手册</small></span></a>";
  }).join("");
  var tabs = Array.from(seals.children);

  function tile(c, dungeon, i) {
    var g = c.guides[dungeon];
    var art = '<svg class="motif" viewBox="0 0 200 200" aria-hidden="true">' + (MOTIFS[dungeon] || "") + "</svg>";
    if (!g) {
      return '<li class="tile todo" style="--i:' + i + '" data-n="' + i + '"><div class="hit">' + art +
        "<h3>" + esc(dungeon) + '</h3><p class="when">这本还在整理</p></div></li>';
    }
    var body = g.keys.length
      ? '<ul class="keys" aria-label="要点">' + g.keys.map(function (k) { return "<li>" + esc(k) + "</li>"; }).join("") + "</ul>"
      : '<p class="gist">' + esc(g.lede) + "</p>";
    var olds = g.old.map(function (o) { return '<a class="old" href="' + o.href + '">' + md(o.date) + "旧版</a>"; }).join("");
    return '<li class="tile" style="--i:' + i + '" data-n="' + i + '"><a class="hit" href="' + g.href + '" title="' + esc(g.lede) + '">' + art +
      "<h3>" + esc(dungeon) + "</h3>" + body + '<p class="when">' + md(g.date) + "更新</p></a>" + (olds ? '<span class="olds">' + olds + "</span>" : "") + "</li>";
  }

  function show(slug, push) {
    var c = data.classes.filter(function (x) { return x.slug === slug; })[0] || data.classes[0];
    tabs.forEach(function (t) { t.setAttribute("aria-current", t.dataset.slug === c.slug ? "true" : "false"); });
    root.style.setProperty("--c", c.color);
    splitTitle(h1, c.name);
    document.title = c.name + "｜大秘境作战手册";

    var have = DUNGEONS.map(function (d) { return !!c.guides[d]; });
    var count = have.filter(Boolean).length;
    $(".tags").innerHTML = "<i>" + esc(c.family) + "</i><i>" + esc(c.role) + "</i>";
    $(".cover").innerHTML = '<span class="pips" aria-hidden="true">' +
      have.map(function (h) { return '<i class="' + (h ? "on" : "") + '"></i>'; }).join("") +
      "</span><span><b>" + count + " / " + DUNGEONS.length + "</b> 个副本已有手册</span>";
    nodes.forEach(function (n, i) { n.classList.toggle("on", have[i]); n.classList.remove("hot"); });

    extra.innerHTML = c.extras.map(function (e) {
      return '<a class="feature" href="' + e.href + '">' + BOOK + "<div><h3>" + esc(e.title) + "</h3><p>" + esc(e.lede) + "</p></div></a>";
    }).join("");
    grid.innerHTML = DUNGEONS.map(function (d, i) { return tile(c, d, i); }).join("");

    store.set("wr-class", c.slug);
    store.set("wr-color", c.color);
    store.set("wr-on", c.on);
    if (push) history.replaceState(null, "", "#" + c.slug);
  }

  seals.addEventListener("click", function (e) {
    var t = e.target.closest(".seal");
    if (!t) return;
    e.preventDefault();
    show(t.dataset.slug, true);
  });
  window.addEventListener("hashchange", function () { show(location.hash.slice(1), false); });

  // Spotlight follows the pointer; the matching point on the sigil lights up.
  grid.addEventListener("pointermove", function (e) {
    var t = e.target.closest(".tile");
    if (!t) return;
    var r = t.getBoundingClientRect();
    t.style.setProperty("--mx", (e.clientX - r.left) + "px");
    t.style.setProperty("--my", (e.clientY - r.top) + "px");
  });
  var hot = function (e) {
    var t = e.target.closest && e.target.closest(".tile");
    nodes.forEach(function (n) { n.classList.toggle("hot", !!t && n.dataset.n === t.dataset.n); });
  };
  grid.addEventListener("pointerover", hot);
  grid.addEventListener("focusin", hot);
  grid.addEventListener("pointerleave", function () { nodes.forEach(function (n) { n.classList.remove("hot"); }); });

  show(location.hash.slice(1) || store.get("wr-class"), false);
})();
