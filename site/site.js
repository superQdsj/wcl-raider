(function () {
  "use strict";
  var root = document.documentElement;
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var icon = function (name) { return '<img class="ic" src="/img/icons/' + name + '.jpg" alt="" width="28" height="28">'; };
  var md = function (iso) { var p = iso.split("-"); return +p[1] + "月" + +p[2] + "日"; };

  var dataEl = $("#guide-data");
  if (!dataEl) {
    // 404 and other static pages: last chosen class color.
    var saved = store.get("wr-color");
    if (saved && /^#[0-9a-f]{6}$/i.test(saved)) root.style.setProperty("--c", saved);
    return;
  }

  var data = JSON.parse(dataEl.textContent);
  var DUNGEONS = data.dungeons;
  var bar = $(".specs"), grid = $(".grid");

  bar.innerHTML = data.classes.map(function (c) {
    return '<a class="spec" href="#' + c.slug + '" data-slug="' + c.slug + '" style="--k:' + c.color + '">' + icon(c.icon) +
      '<span class="nm"><b>' + esc(c.spec) + "</b><small>" + esc(c.cls) + "</small></span></a>";
  }).join("");
  var tabs = Array.from(bar.children);

  function card(c, d) {
    var g = c.guides[d.name];
    var art = '<div class="art"><img src="/img/dungeons/' + d.img + '.jpg" alt="" width="720" height="405" loading="lazy"></div>';
    var head = "<div><h3>" + esc(d.name) + '</h3><p class="en">' + esc(d.en) + "</p></div>";
    if (!g) {
      return '<li class="card todo">' + art + '<div class="body">' + head +
        '<p class="gist">这个副本的手册还在整理。</p></div></li>';
    }
    var olds = g.old.map(function (o) { return '<a class="old" href="' + o.href + '">' + md(o.date) + "旧版</a>"; }).join("");
    return '<li class="card"><a class="hit" href="' + g.href + '">' + art +
      '<div class="body">' + head + '<p class="gist">' + esc(g.lede) + "</p></div></a>" +
      '<div class="meta"><span>' + md(g.date) + "更新</span>" + olds +
      '<a class="open" href="' + g.href + '" tabindex="-1" aria-hidden="true">打开 →</a></div></li>';
  }

  function show(slug, push) {
    var c = data.classes.filter(function (x) { return x.slug === slug; })[0] || data.classes[0];
    var full = c.spec + c.cls;
    tabs.forEach(function (t) { t.setAttribute("aria-current", t.dataset.slug === c.slug ? "true" : "false"); });
    root.style.setProperty("--c", c.color);
    $("#spec-en").textContent = c.en;
    $("#spec-name").innerHTML = '<span class="cls">' + esc(c.spec) + "</span>" + esc(c.cls) + " 大秘境手册";
    document.title = full + "｜大秘境作战手册";

    var dates = Object.keys(c.guides).map(function (d) { return c.guides[d].date; }).sort();
    $(".chips").innerHTML = '<span class="chip">职业 <b>' + esc(c.cls) + '</b></span><span class="chip">定位 <b>' + esc(c.role) + "</b></span>" +
      (dates.length ? '<span class="chip">最近更新 <b>' + md(dates[dates.length - 1]) + "</b></span>" : "");

    grid.innerHTML = DUNGEONS.map(function (d) { return card(c, d); }).join("");

    store.set("wr-class", c.slug);
    store.set("wr-color", c.color);
    if (push) history.replaceState(null, "", "#" + c.slug);
  }

  bar.addEventListener("click", function (e) {
    var t = e.target.closest(".spec");
    if (!t) return;
    e.preventDefault();
    show(t.dataset.slug, true);
  });
  window.addEventListener("hashchange", function () { show(location.hash.slice(1), false); });

  show(location.hash.slice(1) || store.get("wr-class"), false);
})();
