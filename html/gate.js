/* PROTECT draft gate (Nov. 6, 2026).
 *
 * A soft gate for pages that are still under review. It keeps them out of the Pages menu and off
 * the index cards for anyone who has not signed in, and covers the page itself with a sign-in
 * screen. It is not security: GitHub Pages serves every file and the repo is public, so anyone
 * who opens the source or the repo can read a gated page. Nothing sensitive belongs here, gated
 * or not (see the NDOT rule in CLAUDE.md).
 *
 * To gate a page: add its file name to GATED and put <script src="gate.js"></script> in its head
 * (html/gate.js from the repo root). To release it: remove the name. To change the passphrase:
 * replace HASH with the SHA-256 hex of the new phrase. In any page's console:
 *   await protectGate.hash("new phrase")
 * Signing in stores the hash in localStorage, so a new passphrase signs everyone out.
 *
 * Load this synchronously in <head>, before <body>, so a gated page never flashes its content.
 */
(function () {
  "use strict";

  var GATED = [
    "baseline-assessment.html",
    "criticality-qa.html",
    "results-simple.html",
    "workshop-punchlist.html",
    "climate-data.html",
    "tahoe-precip-events.html"
  ];
  var HASH = "26a7b98d6e6ba758f8fcb9283d0a31c274d0fe6c61d9718e0294fd3a9d07ca3a";
  var KEY = "protect-gate";

  function base(href) {
    if (!href) return "";
    return href.split("/").pop().split(/[?#]/)[0];
  }
  function isGated(href) { return GATED.indexOf(base(href)) !== -1; }
  function read() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function write(v) { try { if (v === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, v); } catch (e) {} }

  var unlocked = read() === HASH;
  var here = base(location.pathname) || "index.html";
  var src = (document.currentScript && document.currentScript.getAttribute("src")) || "gate.js";
  var home = /^html\//.test(src) ? "index.html" : "../index.html";
  var locked = !unlocked && isGated(here);

  if (locked) document.documentElement.classList.add("gate-locked");

  var css = document.createElement("style");
  css.textContent =
    "html.gate-locked{overflow:hidden}" +
    "html.gate-locked body>*:not(#gate){visibility:hidden}" +
    "#gate{position:fixed;inset:0;z-index:100000;display:flex;align-items:center;justify-content:center;padding:24px;" +
    "background:#003B71;font-family:'Open Sans',Calibri,Arial,sans-serif;visibility:visible}" +
    "#gate .card{background:#fff;color:#003B71;border-radius:8px;max-width:440px;width:100%;padding:28px 28px 24px;box-shadow:0 8px 32px rgba(0,0,0,.35)}" +
    "#gate .eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#0072CE;font-weight:700;margin:0 0 6px}" +
    "#gate h2{margin:0 0 10px;font-size:22px;line-height:1.25}" +
    "#gate p{margin:0 0 16px;font-size:15px;line-height:1.5;color:#334}" +
    "#gate label{display:block;font-size:13px;font-weight:700;margin:0 0 6px}" +
    "#gate input{width:100%;box-sizing:border-box;font:inherit;font-size:15px;padding:9px 10px;border:1px solid #B4CBE8;border-radius:6px;color:#003B71}" +
    "#gate input:focus{outline:2px solid #0072CE;outline-offset:1px}" +
    "#gate .row{display:flex;align-items:center;gap:14px;margin-top:14px}" +
    "#gate button{font:inherit;font-size:15px;font-weight:700;color:#fff;background:#0072CE;border:0;border-radius:6px;padding:9px 18px;cursor:pointer}" +
    "#gate button:hover{background:#005fae}" +
    "#gate a{color:#0072CE;font-size:14px}" +
    "#gate .err{color:#9C3E27;font-size:13px;min-height:18px;margin:10px 0 0}" +
    "#gate .note{font-size:12px;color:#667;margin:18px 0 0}" +
    ".gate-hide{display:none !important}" +
    "details.pages nav.menu a[data-gated]::after{content:'draft';font-size:.68em;font-weight:700;letter-spacing:.04em;text-transform:uppercase;" +
    "margin-left:.5em;padding:1px 5px;border-radius:3px;background:#E87722;color:#fff;vertical-align:middle}";
  document.head.appendChild(css);

  function sha256(text) {
    if (!(window.crypto && crypto.subtle)) return Promise.reject(new Error("nocrypto"));
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)).then(function (buf) {
      return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
    });
  }

  function hideLinks() {
    var links = document.querySelectorAll("a[href]");
    Array.prototype.forEach.call(links, function (a) {
      if (!isGated(a.getAttribute("href"))) return;
      var inMenu = !!a.closest("details.pages nav.menu");
      if (unlocked) { if (inMenu) a.setAttribute("data-gated", ""); return; }
      if (inMenu || a.classList.contains("page-card")) a.classList.add("gate-hide");
      else if (a.closest(".checks span")) a.closest("span").classList.add("gate-hide");
    });
    // an index card grid with no visible card left, and the heading above it
    var grids = document.querySelectorAll("section.card-grid");
    Array.prototype.forEach.call(grids, function (sec) {
      if (unlocked || sec.querySelector("a.page-card:not(.gate-hide)")) return;
      sec.classList.add("gate-hide");
      var prev = sec.previousElementSibling;
      if (prev && /^H[23]$/.test(prev.tagName)) prev.classList.add("gate-hide");
    });
    // a menu group with a heading and no visible link left
    var groups = document.querySelectorAll("details.pages nav.menu .g");
    Array.prototype.forEach.call(groups, function (g) {
      if (g.querySelector("b") && !g.querySelector("a:not(.gate-hide)")) g.classList.add("gate-hide");
    });
  }

  function staffItem() {
    var menu = document.querySelector("details.pages nav.menu");
    if (!menu) return;
    var g = document.createElement("div");
    g.className = "g gate-g";
    var b = document.createElement("b"); b.textContent = "Staff";
    var a = document.createElement("a"); a.href = "#";
    if (unlocked) {
      a.textContent = "Sign out";
      a.addEventListener("click", function (e) { e.preventDefault(); write(null); location.reload(); });
    } else {
      a.textContent = "Sign in to see drafts";
      a.addEventListener("click", function (e) { e.preventDefault(); showGate(true); });
    }
    g.appendChild(b); g.appendChild(a);
    menu.appendChild(g);
  }

  function showGate(fromMenu) {
    if (document.getElementById("gate")) return;
    var wrap = document.createElement("div");
    wrap.id = "gate";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "gate-h");
    var title = fromMenu ? "Staff sign-in" : "Draft under review";
    var text = fromMenu
      ? "Sign in to see the pages that are still being reviewed. They stay hidden from everyone else."
      : "This page is not ready to share yet. Project staff can sign in to view it.";
    wrap.innerHTML =
      '<form class="card" autocomplete="off">' +
      '<p class="eyebrow">PROTECT, Connecting Tahoe</p>' +
      '<h2 id="gate-h">' + title + '</h2>' +
      '<p>' + text + '</p>' +
      '<label for="gate-pw">Staff passphrase</label>' +
      '<input id="gate-pw" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" required />' +
      '<div class="err" id="gate-err" aria-live="polite"></div>' +
      '<div class="row"><button type="submit">Sign in</button>' +
      '<a href="' + (fromMenu ? "#" : home) + '" id="gate-back">' + (fromMenu ? "Cancel" : "Back to home") + '</a></div>' +
      '<p class="note">Signing in stays on this browser until you sign out from the Pages menu.</p>' +
      '</form>';
    document.body.appendChild(wrap);
    if (fromMenu) {
      document.documentElement.classList.add("gate-locked");
      wrap.querySelector("#gate-back").addEventListener("click", function (e) {
        e.preventDefault(); wrap.remove(); document.documentElement.classList.remove("gate-locked");
      });
    }
    var pw = wrap.querySelector("#gate-pw"), err = wrap.querySelector("#gate-err");
    setTimeout(function () { pw.focus(); }, 0);
    wrap.querySelector("form").addEventListener("submit", function (e) {
      e.preventDefault();
      err.textContent = "";
      sha256(pw.value.trim()).then(function (h) {
        if (h === HASH) { write(h); location.reload(); }
        else { err.textContent = "That passphrase did not match."; pw.select(); }
      }).catch(function () {
        err.textContent = "Sign-in needs a secure connection (https or localhost).";
      });
    });
  }

  function init() {
    hideLinks();
    staffItem();
    if (locked) showGate(false);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();

  window.protectGate = { hash: sha256, gated: GATED.slice(), unlocked: unlocked };
})();
