(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Read owner_id from URL  (?owner_id=xxx)
  // ---------------------------------------------------------------------------
  const params = new URLSearchParams(window.location.search);
  const OWNER_ID = params.get("owner_id") || "";

  // ---------------------------------------------------------------------------
  // DOM refs
  // ---------------------------------------------------------------------------
  const datePicker = document.getElementById("datePicker");
  const stepSlots = document.getElementById("stepSlots");
  const slotsGrid = document.getElementById("slotsGrid");
  const slotsLoading = document.getElementById("slotsLoading");
  const noSlots = document.getElementById("noSlots");
  const stepForm = document.getElementById("stepForm");
  const stepConfirm = document.getElementById("stepConfirm");
  const bookBtn = document.getElementById("bookBtn");
  const customerName = document.getElementById("customerName");
  const customerEmail = document.getElementById("customerEmail");
  const confirmDetails = document.getElementById("confirmDetails");
  const errorMsg = document.getElementById("errorMsg");
  const ownerInfo = document.getElementById("ownerInfo");

  let selectedSlot = null;

  // Warn if no owner_id in URL
  if (!OWNER_ID) {
    showError("Missing owner_id in URL. Use ?owner_id=YOUR_UUID");
    datePicker.disabled = true;
  }

  // Set date picker min to today
  const today = new Date();
  datePicker.min = formatDate(today);
  datePicker.value = formatDate(today);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Fetch available slots
  // ---------------------------------------------------------------------------
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
      const res = await fetch(
        `/api/availability?owner_id=${encodeURIComponent(OWNER_ID)}&date=${date}`
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Error ${res.status}`);
      }
      const data = await res.json();
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

  // ---------------------------------------------------------------------------
  // Render slot buttons
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Book
  // ---------------------------------------------------------------------------
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
          owner_id: OWNER_ID,
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

  // ---------------------------------------------------------------------------
  // Confirmation
  // ---------------------------------------------------------------------------
  function showConfirmation(event) {
    document.getElementById("stepDate").classList.add("hidden");
    stepSlots.classList.add("hidden");
    stepForm.classList.add("hidden");
    stepConfirm.classList.remove("hidden");

    confirmDetails.innerHTML =
      '<div class="detail-row"><span class="detail-label">Date</span><span>' +
      datePicker.value +
      "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Time</span><span>' +
      unixToLocal(event.start_time) +
      " &ndash; " +
      unixToLocal(event.end_time) +
      "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Name</span><span>' +
      escapeHtml(event.customer_name) +
      "</span></div>" +
      '<div class="detail-row"><span class="detail-label">Email</span><span>' +
      escapeHtml(event.customer_email) +
      "</span></div>";
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // ---------------------------------------------------------------------------
  // Event listeners
  // ---------------------------------------------------------------------------
  datePicker.addEventListener("change", function () {
    if (datePicker.value) {
      fetchSlots(datePicker.value);
    }
  });

  bookBtn.addEventListener("click", bookSlot);

  // Auto-load today's slots if owner_id is present
  if (OWNER_ID && datePicker.value) {
    fetchSlots(datePicker.value);
  }
})();
