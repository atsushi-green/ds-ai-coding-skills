/* 診断図ギャラリーの挙動: テーマ切替・目次の追従・図の拡大・判定での絞り込み */
(function () {
  "use strict";

  var root = document.documentElement;

  /* ---------------------------------------------------------- テーマ --- */
  // localStorage はプライベートウィンドウ等で例外を投げるので毎回 try で包む
  function readStored(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function writeStored(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* 保存できなくても動作は変えない */ }
  }

  var themeBtn = document.querySelector("[data-theme-toggle]");

  function currentTheme() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function applyTheme(theme) {
    root.dataset.theme = theme;
    if (themeBtn) {
      themeBtn.setAttribute("aria-label", theme === "dark" ? "ライトテーマに切り替える" : "ダークテーマに切り替える");
      themeBtn.querySelector("[data-theme-icon]").textContent = theme === "dark" ? "☀" : "☾";
    }
  }
  applyTheme(currentTheme());
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      writeStored("gallery-theme", next);
    });
  }

  /* ------------------------------------------------ サイドバー（狭幅） --- */
  var sidebar = document.querySelector("[data-sidebar]");
  var scrim = document.querySelector("[data-scrim]");
  var navBtn = document.querySelector("[data-nav-toggle]");

  function closeNav() {
    if (!sidebar) return;
    sidebar.classList.remove("is-open");
    if (scrim) scrim.classList.remove("is-open");
    if (navBtn) navBtn.setAttribute("aria-expanded", "false");
  }
  if (navBtn && sidebar) {
    navBtn.addEventListener("click", function () {
      var open = sidebar.classList.toggle("is-open");
      if (scrim) scrim.classList.toggle("is-open", open);
      navBtn.setAttribute("aria-expanded", String(open));
    });
  }
  if (scrim) scrim.addEventListener("click", closeNav);
  // 目次から飛んだら閉じる
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  tocLinks.forEach(function (a) { a.addEventListener("click", closeNav); });

  /* -------------------------------------------------- 目次の現在地表示 --- */
  var targets = tocLinks
    .map(function (a) {
      var id = a.getAttribute("href");
      return id && id.charAt(0) === "#" ? document.getElementById(id.slice(1)) : null;
    })
    .filter(Boolean);

  if (targets.length && "IntersectionObserver" in window) {
    var visible = new Set();
    var spy = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        });
        // 画面内にある見出しのうち、文書順で最初のものを現在地とする
        var activeId = null;
        for (var i = 0; i < targets.length; i++) {
          if (visible.has(targets[i].id)) { activeId = targets[i].id; break; }
        }
        tocLinks.forEach(function (a) {
          a.classList.toggle("is-active", a.getAttribute("href") === "#" + activeId);
        });
      },
      { rootMargin: "-84px 0px -62% 0px", threshold: 0 }
    );
    targets.forEach(function (t) { spy.observe(t); });
  }

  /* ------------------------------------------------------- 図の拡大 --- */
  var lightbox = document.querySelector("[data-lightbox]");
  var lbImg = lightbox && lightbox.querySelector("[data-lightbox-img]");
  var lbCap = lightbox && lightbox.querySelector("[data-lightbox-cap]");
  var lbLink = lightbox && lightbox.querySelector("[data-lightbox-link]");
  var lastFocused = null;

  function openLightbox(frame) {
    if (!lightbox) return;
    var img = frame.querySelector("img");
    var src = frame.getAttribute("href") || img.getAttribute("src");
    lastFocused = frame;
    lbImg.setAttribute("src", src);
    lbImg.setAttribute("alt", img.getAttribute("alt") || "");
    lbCap.textContent = frame.getAttribute("data-caption") || img.getAttribute("alt") || "";
    lbLink.setAttribute("href", src);
    lightbox.classList.add("is-open");
    document.body.classList.add("is-locked");
    lightbox.querySelector("[data-lightbox-close]").focus();
  }
  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove("is-open");
    document.body.classList.remove("is-locked");
    lbImg.removeAttribute("src");
    if (lastFocused) { lastFocused.focus(); lastFocused = null; }
  }

  document.querySelectorAll("[data-figure]").forEach(function (frame) {
    frame.addEventListener("click", function (ev) {
      ev.preventDefault();
      openLightbox(frame);
    });
  });

  if (lightbox) {
    lightbox.addEventListener("click", function (ev) {
      // 画像そのもの・原寸リンク以外をクリックしたら閉じる
      if (ev.target.closest("[data-lightbox-img], [data-lightbox-link]")) return;
      closeLightbox();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && lightbox.classList.contains("is-open")) closeLightbox();
    });
  }

  /* ----------------------------------------------- 判定での絞り込み --- */
  var methods = Array.prototype.slice.call(document.querySelectorAll("[data-method]"));
  var chips = Array.prototype.slice.call(document.querySelectorAll("[data-filter]"));
  var countEl = document.querySelector("[data-filter-count]");

  function applyFilter(mode) {
    var shown = 0;
    methods.forEach(function (el) {
      var hit = mode === "all" || el.dataset.verdicts.indexOf(mode) !== -1;
      el.classList.toggle("is-dimmed", !hit);
      if (hit) shown += 1;
    });
    // 手法が 1 つも残らない skill セクションごと隠す
    document.querySelectorAll("[data-skill]").forEach(function (section) {
      var any = section.querySelector("[data-method]:not(.is-dimmed)");
      section.style.display = any ? "" : "none";
    });
    chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.filter === mode)); });
    if (countEl) countEl.textContent = shown + " / " + methods.length + " 手法を表示";
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () { applyFilter(chip.dataset.filter); });
  });
  if (chips.length) applyFilter("all");
})();
