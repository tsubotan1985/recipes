/* うちのレシピ — index filter + 印刷 + 材料チェックの記憶 */
(function () {
  "use strict";

  var q = document.getElementById("q");
  var chips = Array.from(document.querySelectorAll(".chip"));
  var cards = Array.from(document.querySelectorAll(".card"));
  var empty = document.getElementById("empty");

  function normalize(s) {
    return (s || "")
      .toLowerCase()
      .replace(/[\u30a1-\u30f6]/g, function (c) {
        return String.fromCharCode(c.charCodeAt(0) - 0x60);
      })
      .replace(/\s+/g, " ");
  }

  function apply() {
    var term = normalize(q ? q.value.trim() : "");
    var cat = "all";
    chips.forEach(function (c) {
      if (c.classList.contains("is-active")) cat = c.dataset.filter;
    });
    var shown = 0;
    cards.forEach(function (card) {
      var okCat = cat === "all" || card.dataset.cat === cat;
      var okTerm = !term || normalize(card.dataset.search).indexOf(term) !== -1;
      var on = okCat && okTerm;
      card.hidden = !on;
      if (on) shown++;
    });
    if (empty) empty.hidden = shown !== 0;
  }

  if (q) {
    q.addEventListener("input", apply);
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== q) {
        e.preventDefault();
        q.focus();
      }
    });
  }

  chips.forEach(function (c) {
    c.addEventListener("click", function () {
      chips.forEach(function (o) { o.classList.remove("is-active"); });
      c.classList.add("is-active");
      apply();
    });
  });

  if (cards.length) apply();

  Array.from(document.querySelectorAll("[data-print]")).forEach(function (b) {
    b.addEventListener("click", function () { window.print(); });
  });

  /* 材料チェック: 同じページのチェック状態を session 内で保持 */
  var boxes = Array.from(document.querySelectorAll(".ing-check"));
  if (boxes.length) {
    var key = "recipes-check:" + location.pathname;
    var saved = [];
    try { saved = JSON.parse(sessionStorage.getItem(key) || "[]"); } catch (e) { saved = []; }
    boxes.forEach(function (b, i) {
      if (saved.indexOf(i) !== -1) b.checked = true;
      b.addEventListener("change", function () {
        var state = boxes.map(function (x, j) { return x.checked ? j : -1; })
          .filter(function (j) { return j !== -1; });
        try { sessionStorage.setItem(key, JSON.stringify(state)); } catch (e) {}
      });
    });
  }
})();
