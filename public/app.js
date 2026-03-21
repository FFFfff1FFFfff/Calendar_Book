(function () {
  "use strict";

  // Read slug from URL path: /book/<slug>
  var pathParts = window.location.pathname.split("/");
  var SLUG = (pathParts[1] === "book" && pathParts[2]) ? pathParts[2] : "";

  var datePicker = document.getElementById("datePicker");
  var stepSlots = document.getElementById("stepSlots");
  var slotsGrid = document.getElementById("slotsGrid");
  var slotsLoading = document.getElementById("slotsLoading");
  var noSlots = document.getElementById("noSlots");
  var stepForm = document.getElementById("stepForm");
  var stepConfirm = document.getElementById("stepConfirm");
  var bookBtn = document.getElementById("bookBtn");
  var customerName = document.getElementById("customerName");
  var customerEmail = document.getElementById("customerEmail");
  var confirmDetails = document.getElementById("confirmDetails");
  var errorMsg = document.getElementById("errorMsg");
  var ownerInfo = document.getElementById("ownerInfo");

  var selectedSlot = null;

  if (!SLUG) {
    showError("Invalid booking link.");
    datePicker.disabled = true;
    return;
  }

  var today = new Date();
  datePicker.min = formatDate(today);
  datePicker.value = formatDate(today);

  function formatDate(d) {
    return d.toISOString().split("T")[0];
  }

  function unixToLocal(unix) {
    return new Date(unix * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove("hidden");
  }

  function hideError() {
    errorMsg.classList.add("hidden");
  }

  async function fetchSlots(date) {
    hideError();
    stepSlots.classList.remove("hidden");
    stepForm.classList.add("hidden");
    stepConfirm.classList.add("hidden");
    slotsGrid.innerHTML = "";
    noSlots.classList.add("hidden");
    slotsLoading.classList.remove("hidden");
    selectedSlot = null;
    bookBtn.disabled = true;

    try {
      var res = await fetch(
        "/api/availability?slug=" + encodeURIComponent(SLUG) + "&date=" + date
      );
      if (!res.ok) {
        var body = await res.json().catch(function () { return {}; });
        throw new Error(body.detail || "Error " + res.status);
      }
      var data = await res.json();
      slotsLoading.classList.add("hidden");
      if (data.owner_email && ownerInfo) {
        ownerInfo.textContent = "Booking with " + data.owner_email;
      }
      renderSlots(data.slots || []);
    } catch (err) {
      slotsLoading.classList.add("hidden");
      showError(err.message);
    }
  }

  function renderSlots(slots) {
    slotsGrid.innerHTML = "";
    if (slots.length === 0) {
      noSlots.classList.remove("hidden");
      return;
    }
    slots.forEach(function (slot) {
      var btn = document.createElement("button");
      btn.className = "slot-btn";
      btn.textContent = unixToLocal(slot.start_time);
      btn.addEventListener("click", function () {
        document.querySelectorAll(".slot-btn.selected").forEach(function (el) {
          el.classList.remove("selected");
        });
        btn.classList.add("selected");
        selectedSlot = slot;
        stepForm.classList.remove("hidden");
        bookBtn.disabled = false;
      });
      slotsGrid.appendChild(btn);
    });
  }

  async function bookSlot() {
    hideError();
    if (!selectedSlot || !customerName.value.trim() || !customerEmail.value.trim()) {
      showError("Please fill in all fields.");
      return;
    }

    bookBtn.disabled = true;
    bookBtn.innerHTML = '<span class="spinner"></span> Booking&hellip;';

    try {
      var res = await fetch("/api/book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug: SLUG,
          start_time: selectedSlot.start_time,
          end_time: selectedSlot.end_time,
          customer_name: customerName.value.trim(),
          customer_email: customerEmail.value.trim(),
        }),
      });
      if (!res.ok) {
        var body = await res.json().catch(function () { return {}; });
        throw new Error(body.detail || "Booking failed");
      }
      var data = await res.json();
      showConfirmation(data);
    } catch (err) {
      showError(err.message);
      bookBtn.disabled = false;
      bookBtn.textContent = "Confirm Booking";
    }
  }

  function showConfirmation(event) {
    document.getElementById("stepDate").classList.add("hidden");
    stepSlots.classList.add("hidden");
    stepForm.classList.add("hidden");
    stepConfirm.classList.remove("hidden");

    if (window.parent !== window) {
      window.parent.postMessage({ type: "calbook:booked", detail: event }, "*");
    }

    confirmDetails.innerHTML =
      '<div class="detail-row"><span class="detail-label">Date</span><span>' +
      datePicker.value + "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Time</span><span>' +
      unixToLocal(event.start_time) + " &ndash; " + unixToLocal(event.end_time) +
      "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Name</span><span>' +
      escapeHtml(event.customer_name) + "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Email</span><span>' +
      escapeHtml(event.customer_email) + "</span></div>";
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  datePicker.addEventListener("change", function () {
    if (datePicker.value) fetchSlots(datePicker.value);
  });

  bookBtn.addEventListener("click", bookSlot);

  if (SLUG && datePicker.value) {
    fetchSlots(datePicker.value);
  }
})();
