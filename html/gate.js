/* PROTECT draft gate (Nov. 6, 2026).
 *
 * A soft gate for pages that are still under review. It keeps them out of the Pages menu and off
 * the index cards for anyone who has not signed in, and covers the page itself with a sign-in
 * screen. A padlock button beside Pages signs in (closed lock) or out (open lock). It is not
 * security: GitHub Pages serves every file and the repo is public, so anyone who opens the source
 * or the repo can read a gated page. Nothing sensitive belongs here, gated or not (see the NDOT
 * rule in CLAUDE.md).
 *
 * To gate a page: add its file name (relative to html/) to GATED and put
 * <script src="gate.js"></script> in its head (html/gate.js from the repo root). To release it:
 * remove the name. To change the passphrase: replace HASH with the SHA-256 hex of the new phrase.
 * In any page's console:
 *   await protectGate.hash("new phrase")
 * Signing in stores the hash in localStorage, so a new passphrase signs everyone out.
 *
 * Pages are matched by full URL resolved against this script's folder, so "index.html" here is
 * html/index.html (All pages) and never the public home at the repo root.
 *
 * Load this synchronously in <head>, before <body>, so a gated page never flashes its content.
 */
(function () {
  "use strict";

  var GATED = [
    "index.html",
    "baseline-assessment.html",
    "criticality-qa.html",
    "results-simple.html",
    "workshop-punchlist.html",
    "od-services-index.html",
    "scoring-rubrics.html",
    "reference-hub.html",
    "climate-data.html",
    "historic-hazards.html",
    "tahoe-precip-events.html"
  ];
  var HASH = "26a7b98d6e6ba758f8fcb9283d0a31c274d0fe6c61d9718e0294fd3a9d07ca3a";
  var KEY = "protect-gate";
  var MAIL = "mailto:gis@trpa.gov?subject=" + encodeURIComponent("Connecting Tahoe draft pages: passphrase request") +
    "&body=" + encodeURIComponent("Hello,\n\nPlease send me the staff passphrase for the Connecting Tahoe draft pages.\n\nName:\nAgency:\nPage I was trying to open: ") +
    encodeURIComponent(location.href);

  // html/ is the folder this script lives in, whichever page loaded it
  var scriptSrc = (document.currentScript && document.currentScript.src) || new URL("gate.js", location.href).href;
  var HTML_DIR = new URL("./", scriptSrc).href;
  var home = new URL("../index.html", HTML_DIR).href;

  function norm(href) {
    var u;
    try { u = new URL(href, location.href); } catch (e) { return ""; }
    var p = u.origin + u.pathname;
    if (/\/$/.test(p)) p += "index.html";
    return p;
  }
  var gatedUrls = GATED.map(function (n) { return norm(HTML_DIR + n); });
  function isGated(href) { return gatedUrls.indexOf(norm(href)) !== -1; }
  function read() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function write(v) { try { if (v === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, v); } catch (e) {} }

  var unlocked = read() === HASH;
  var locked = !unlocked && isGated(location.href);

  if (locked) document.documentElement.classList.add("gate-locked");

  var css = document.createElement("style");
  css.textContent =
    "html.gate-locked{overflow:hidden}" +
    "html.gate-locked body>*:not(#gate){visibility:hidden}" +
    "#gate{position:fixed;inset:0;z-index:100000;display:flex;align-items:center;justify-content:center;padding:24px;" +
    "background:#003B71;font-family:'Open Sans',Calibri,Arial,sans-serif;visibility:visible}" +
    "#gate .gate-card{background:#fff;color:#003B71;border-radius:8px;max-width:440px;width:100%;padding:28px 28px 24px;box-shadow:0 8px 32px rgba(0,0,0,.35)}" +
    "#gate .gate-eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#0072CE;font-weight:700;margin:0 0 6px}" +
    "#gate h2{margin:0 0 10px;font-size:22px;line-height:1.25}" +
    "#gate p{margin:0 0 16px;font-size:15px;line-height:1.5;color:#334}" +
    "#gate label{display:block;font-size:13px;font-weight:700;margin:0 0 6px}" +
    "#gate input{width:100%;box-sizing:border-box;font:inherit;font-size:15px;padding:9px 10px;border:1px solid #B4CBE8;border-radius:6px;color:#003B71}" +
    "#gate input:focus{outline:2px solid #0072CE;outline-offset:1px}" +
    "#gate .gate-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px 14px;margin-top:14px}" +
    "#gate button{white-space:nowrap;font:inherit;font-size:15px;font-weight:700;color:#fff;background:#0072CE;border:0;border-radius:6px;padding:9px 18px;cursor:pointer}" +
    "#gate button:hover{background:#005fae}" +
    "#gate a{color:#0072CE;font-size:14px}" +
    "#gate .gate-ask{display:inline-block;white-space:nowrap;font-size:14px;font-weight:700;color:#0072CE;background:#fff;border:1px solid #0072CE;border-radius:6px;padding:8px 14px;text-decoration:none}" +
    "#gate .gate-ask:hover{background:#eef5fc}" +
    "#gate .gate-err{color:#9C3E27;font-size:13px;min-height:18px;margin:10px 0 0}" +
    "#gate .gate-note{font-size:12px;color:#667;margin:18px 0 0}" +
    ".gate-hide{display:none !important}" +
    ".gate-btn{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;" +
    "border:1px solid rgba(180,203,232,.55);border-radius:999px;background:none;color:#B4CBE8;cursor:pointer;vertical-align:middle;flex:0 0 auto}" +
    ".gate-btn:hover{background:rgba(255,255,255,.1);border-color:#fff;color:#fff}" +
    ".gate-btn.open{color:#E87722;border-color:#E87722}" +
    ".gate-btn svg{width:14px;height:14px;display:block}" +
    "details.pages nav.menu a[data-gated]::after{content:'draft';font-size:.68em;font-weight:700;letter-spacing:.04em;text-transform:uppercase;" +
    "margin-left:.5em;padding:1px 5px;border-radius:3px;background:#E87722;color:#fff;vertical-align:middle}";
  document.head.appendChild(css);

  var LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
  var UNLOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.6-1.8"/></svg>';

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
      if (inMenu || a.classList.contains("page-card") || a.classList.contains("tool")) a.classList.add("gate-hide");
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

  function lockButton() {
    var pages = document.querySelector("details.pages");
    if (!pages) return;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "gate-btn" + (unlocked ? " open" : "");
    b.innerHTML = unlocked ? UNLOCK : LOCK;
    var label = unlocked ? "Signed in: draft pages are shown. Sign out" : "Staff sign-in to see draft pages";
    b.title = label;
    b.setAttribute("aria-label", label);
    b.addEventListener("click", function () {
      if (unlocked) { write(null); location.reload(); } else showGate(true);
    });
    pages.parentNode.insertBefore(b, pages);
  }

  function showGate(fromButton) {
    if (document.getElementById("gate")) return;
    var wrap = document.createElement("div");
    wrap.id = "gate";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "gate-h");
    var title = fromButton ? "Staff sign-in" : "Draft under review";
    var text = fromButton
      ? "Sign in to see the pages that are still being reviewed. They stay hidden from everyone else."
      : "This page is not ready to share yet. Project staff can sign in to view it.";
    wrap.innerHTML =
      '<form class="gate-card" autocomplete="off">' +
      '<p class="gate-eyebrow">PROTECT, Connecting Tahoe</p>' +
      '<h2 id="gate-h">' + title + '</h2>' +
      '<p>' + text + '</p>' +
      '<label for="gate-pw">Staff passphrase</label>' +
      '<input id="gate-pw" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" required />' +
      '<div class="gate-err" id="gate-err" aria-live="polite"></div>' +
      '<div class="gate-row"><button type="submit">Sign in</button>' +
      '<a class="gate-ask" href="' + MAIL + '">Request access</a>' +
      '<a href="' + (fromButton ? "#" : home) + '" id="gate-back">' + (fromButton ? "Cancel" : "Back to home") + '</a></div>' +
      '<p class="gate-note">Signing in stays on this browser until you sign out with the lock beside Pages.</p>' +
      '</form>';
    document.body.appendChild(wrap);
    if (fromButton) {
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
    lockButton();
    if (locked) showGate(false);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();

  window.protectGate = { hash: sha256, gated: GATED.slice(), unlocked: unlocked };
})();
