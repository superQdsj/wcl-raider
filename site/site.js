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
  var slot = function (icon, cls) {
    return '<span class="slot' + (cls ? " " + cls : "") + '"><img src="/img/icons/' + icon + '.jpg" alt="" width="56" height="56"></span>';
  };

  /* ---- the backdrop: two layers that crossfade ---- */
  var scenes = Array.from(document.querySelectorAll(".scene"));
  var front = 0, shown = null;
  function scene(img) {
    if (!scenes.length || img === shown) return;
    shown = img;
    var next = scenes[1 - front];
    next.style.backgroundImage = 'url("/img/dungeons/' + img + '.jpg")';
    var flip = function () { scenes[front].classList.remove("on"); next.classList.add("on"); front = 1 - front; };
    var pre = new Image();
    pre.onload = pre.onerror = function () { if (shown === img) flip(); };
    pre.src = "/img/dungeons/" + img + ".jpg";
  }

  var splitTitle = function (h, text) {
    h.innerHTML = Array.from(text).map(function (ch, i) {
      return '<span class="ch" style="--i:' + i + '">' + esc(ch) + "</span>";
    }).join("");
  };

  var dataEl = $("#guide-data");
  if (!dataEl) {
    // 404 and other static pages: a dark dungeon behind, last chosen class color.
    var c = store.get("wr-color");
    if (c && /^#[0-9a-f]{6}$/i.test(c)) root.style.setProperty("--c", c);
    scene(document.body.dataset.scene || "kingsrest");
    return;
  }

  var data = JSON.parse(dataEl.textContent);
  var DUNGEONS = data.dungeons;
  var bar = $(".specbar"), grid = $(".grid"), extra = $(".extra"), h1 = $("#spec-name");
  var nowZh = $(".now .zh"), nowEn = $(".now .en");
  var md = function (iso) { var p = iso.split("-"); return +p[1] + "月" + +p[2] + "日"; };
  var base = null; // the dungeon the page rests on for the current spec

  bar.innerHTML = data.classes.map(function (c) {
    var n = Object.keys(c.guides).length;
    return '<a class="spec" href="#' + c.slug + '" data-slug="' + c.slug + '" style="--k:' + c.color + '">' + slot(c.icon) +
      '<span><span class="full">' + esc(c.name) + '</span><span class="short">' + esc(c.short) + "</span><small>" + n + " 本</small></span></a>";
  }).join("");
  var tabs = Array.from(bar.children);

  function card(c, d, i) {
    var g = c.guides[d.name];
    var art = '<img class="art" src="/img/dungeons/' + d.img + '-s.jpg" alt="" loading="' + (i < 4 ? "eager" : "lazy") + '">';
    var head = "<h3>" + esc(d.name) + '</h3><p class="en">' + esc(d.en) + "</p>";
    if (!g) {
      return '<li class="card todo" data-i="' + i + '"><div class="hit">' + art + '<div class="body">' + head +
        '<p class="when">这本还在整理</p></div></div></li>';
    }
    var body = g.keys.length
      ? '<ul class="keys" aria-label="要点">' + g.keys.map(function (k) { return "<li>" + esc(k) + "</li>"; }).join("") + "</ul>"
      : '<p class="gist">' + esc(g.lede) + "</p>";
    var olds = g.old.map(function (o) { return '<a class="old" href="' + o.href + '">' + md(o.date) + "旧版</a>"; }).join("");
    return '<li class="card" data-i="' + i + '"><a class="hit" href="' + g.href + '" title="' + esc(g.lede) + '">' + art +
      '<div class="body">' + head + body + '<p class="when">' + md(g.date) + "更新</p></div></a>" +
      (olds ? '<span class="olds">' + olds + "</span>" : "") + "</li>";
  }

  function rest(d) {
    scene(d.img);
    nowZh.textContent = d.name;
    nowEn.textContent = d.en;
  }

  function show(slug, push) {
    var c = data.classes.filter(function (x) { return x.slug === slug; })[0] || data.classes[0];
    tabs.forEach(function (t) { t.setAttribute("aria-current", t.dataset.slug === c.slug ? "true" : "false"); });
    root.style.setProperty("--c", c.color);
    splitTitle(h1, c.name);
    document.title = c.name + "｜大秘境作战手册";

    var have = DUNGEONS.map(function (d) { return !!c.guides[d.name]; });
    var count = have.filter(Boolean).length;
    $(".family").innerHTML = "<i>" + esc(c.family) + "</i><i>" + esc(c.role) + "</i>";
    $(".cover").innerHTML = '<span class="pips" aria-hidden="true">' +
      have.map(function (h) { return '<i class="' + (h ? "on" : "") + '"></i>'; }).join("") +
      "</span><span><b>" + count + " / " + DUNGEONS.length + "</b> 个副本已有手册</span>";

    extra.innerHTML = c.extras.map(function (e) {
      return '<a class="feature" href="' + e.href + '">' + slot("inv_misc_book_09") + "<div><h3>" + esc(e.title) + "</h3><p>" + esc(e.lede) + "</p></div></a>";
    }).join("");
    grid.innerHTML = DUNGEONS.map(function (d, i) { return card(c, d, i); }).join("");

    // Rest on the most recently updated guide of this spec.
    var latest = DUNGEONS.filter(function (d) { return c.guides[d.name]; })
      .sort(function (a, b) { return c.guides[b.name].date.localeCompare(c.guides[a.name].date); })[0];
    base = latest || DUNGEONS[0];
    rest(base);

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

  // Point at a dungeon and the whole page becomes that dungeon.
  var timer;
  var aim = function (e) {
    var t = e.target.closest && e.target.closest(".card");
    if (!t) return;
    clearTimeout(timer);
    timer = setTimeout(function () { rest(DUNGEONS[+t.dataset.i]); }, 120);
  };
  grid.addEventListener("pointerover", aim);
  grid.addEventListener("focusin", aim);
  grid.addEventListener("pointerleave", function () { clearTimeout(timer); timer = setTimeout(function () { rest(base); }, 400); });

  show(location.hash.slice(1) || store.get("wr-class"), false);
})();
