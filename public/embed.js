(function () {
  var ORIGIN = "https://calendar-book-omega.vercel.app";

  document.querySelectorAll("[data-calbook-slug]").forEach(function (el) {
    var slug = el.getAttribute("data-calbook-slug");
    if (!slug) return;

    var iframe = document.createElement("iframe");
    iframe.src = ORIGIN + "/book/" + encodeURIComponent(slug) + "?embed=true";
    iframe.style.width = "100%";
    iframe.style.height = "600px";
    iframe.style.border = "none";
    iframe.allow = "clipboard-write";
    el.appendChild(iframe);
  });

  window.addEventListener("message", function (e) {
    if (e.origin !== ORIGIN) return;
    if (e.data && e.data.type === "calbook:booked") {
      var evt = new CustomEvent("calbook:booked", { detail: e.data });
      window.dispatchEvent(evt);
    }
  });
})();
