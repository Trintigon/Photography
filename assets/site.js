/* Shared by index.html and biweekly.html. The two pages do not carry the same
   furniture, so anything page-specific is guarded rather than assumed. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  /* ---------- header state ---------- */
  var header = $("header");
  var onScroll = function () {
    header.classList.toggle("is-stuck", window.scrollY > 40);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- mobile menu ---------- */
  var burger = $("burger");
  var nav = $("nav");
  var closeMenu = function () {
    document.body.classList.remove("menu-open");
    burger.setAttribute("aria-expanded", "false");
  };
  burger.addEventListener("click", function () {
    var open = document.body.classList.toggle("menu-open");
    burger.setAttribute("aria-expanded", String(open));
  });
  nav.addEventListener("click", function (e) {
    if (e.target.tagName === "A") closeMenu();
  });

  /* ---------- scroll reveal ---------- */
  var revealables = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    revealables.forEach(function (el) { io.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add("is-in"); });
  }

  /* ---------- gallery filtering (front page only) ---------- */
  var grids = Array.prototype.slice.call(document.querySelectorAll(".grid"));
  var tiles = Array.prototype.slice.call(document.querySelectorAll(".tile"));
  var filters = $("filters");
  if (filters) filters.addEventListener("click", function (e) {
    var btn = e.target.closest("button");
    if (!btn) return;
    var cat = btn.dataset.filter;

    this.querySelectorAll("button").forEach(function (b) {
      b.classList.toggle("is-active", b === btn);
    });

    grids.forEach(function (grid) {
      grid.classList.toggle("is-hidden", cat !== "all" && grid.dataset.group !== cat);
    });
  });

  /* ---------- lightbox ---------- */
  var lb = $("lightbox");
  var lbImg = $("lbImg");
  var lbCount = $("lbCount");
  var lbCap = $("lbCap");
  var index = 0;

  var visible = function () {
    return tiles.filter(function (t) {
      var g = t.closest(".grid");
      return !(g && g.classList.contains("is-hidden"));
    });
  };

  var show = function (i) {
    var list = visible();
    if (!list.length) return;
    index = (i + list.length) % list.length;
    var src = list[index].querySelector("img");
    lbImg.src = src.src;
    lbImg.alt = src.alt;
    var fc = list[index].querySelector("figcaption");
    lbCap.innerHTML = fc ? fc.innerHTML : "";
    lbCount.textContent = ("0" + (index + 1)).slice(-2) + " / " + ("0" + list.length).slice(-2);
  };

  var open = function (tile) {
    show(visible().indexOf(tile));
    lb.classList.add("is-open");
    document.body.classList.add("lb-open");
    document.body.style.overflow = "hidden";
  };

  var close = function () {
    lb.classList.remove("is-open");
    document.body.classList.remove("lb-open");
    document.body.style.overflow = "";
  };

  tiles.forEach(function (tile) {
    tile.addEventListener("click", function () { open(tile); });
    tile.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(tile); }
    });
  });

  $("lbClose").addEventListener("click", close);
  $("lbPrev").addEventListener("click", function () { show(index - 1); });
  $("lbNext").addEventListener("click", function () { show(index + 1); });
  lb.addEventListener("click", function (e) { if (e.target === lb) close(); });

  document.addEventListener("keydown", function (e) {
    if (!lb.classList.contains("is-open")) return;
    if (e.key === "Escape") close();
    if (e.key === "ArrowLeft") show(index - 1);
    if (e.key === "ArrowRight") show(index + 1);
  });

  /* ---------- contact form, front page only (no backend: opens mail client) ---------- */
  var form = $("form");
  if (form) form.addEventListener("submit", function (e) {
    e.preventDefault();
    var f = this.elements;
    var name = f.name.value.trim();
    var email = f.email.value.trim();
    var message = f.message.value.trim();

    window.location.href =
      "mailto:trintigon@gmail.com" +
      "?subject=" + encodeURIComponent("Enquiry from " + name) +
      "&body=" + encodeURIComponent(message + "\n\n" + name + " — " + email);

    $("note").textContent = "Opening your mail app…";
  });

  /* ---------- footer year ---------- */
  $("year").textContent = new Date().getFullYear();
})();
