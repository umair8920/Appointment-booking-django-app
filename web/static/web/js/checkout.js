/**
 * Stripe Payment Element checkout (Docs/10).
 * - POST /api/payments/{appointment_id}/create-intent/ with session + CSRF
 * - confirmPayment via Stripe.js
 * - redirect to my appointments on success
 */
(function () {
  const root = document.getElementById("checkout-root");
  if (!root) return;

  const appointmentId = root.dataset.appointmentId;
  const publishableKey = root.dataset.publishableKey;
  const successUrl = root.dataset.successUrl;
  const messageEl = document.getElementById("payment-message");
  const submitBtn = document.getElementById("submit-payment");

  // Prevent paying before Elements is mounted / form is complete.
  submitBtn.disabled = true;

  if (!appointmentId || !publishableKey) {
    messageEl.textContent = "Stripe is not configured.";
    return;
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function setBusy(busy) {
    submitBtn.disabled = busy || !window.__checkoutReady;
    submitBtn.textContent = busy ? "Processing…" : "Pay now";
  }

  const stripe = Stripe(publishableKey);
  let elements = null;
  let paymentComplete = false;

  async function init() {
    messageEl.textContent = "Loading payment form…";
    const response = await fetch(`/api/payments/${appointmentId}/create-intent/`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: "{}",
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_err) {
      throw new Error("Could not start payment (invalid server response).");
    }

    if (!response.ok) {
      const detail =
        (typeof data.detail === "string" && data.detail) ||
        (data.detail && JSON.stringify(data.detail)) ||
        "Could not start payment.";
      throw new Error(detail);
    }
    if (!data.client_secret) {
      throw new Error("Payment intent missing client secret.");
    }

    elements = stripe.elements({ clientSecret: data.client_secret });
    const paymentElement = elements.create("payment");
    paymentElement.mount("#payment-element");

    paymentElement.on("ready", function () {
      messageEl.textContent = "";
      window.__checkoutReady = true;
      // Enable once mounted; tighten when Stripe reports the form complete.
      submitBtn.disabled = false;
    });

    paymentElement.on("change", function (event) {
      paymentComplete = Boolean(event.complete);
      if (event.error) {
        messageEl.textContent = event.error.message;
      } else if (!messageEl.dataset.locked) {
        messageEl.textContent = "";
      }
      if (window.__checkoutReady) {
        submitBtn.disabled = false;
      }
    });
  }

  submitBtn.addEventListener("click", async function () {
    if (!elements) {
      messageEl.textContent = "Payment form is still loading. Please wait.";
      return;
    }

    messageEl.textContent = "";
    delete messageEl.dataset.locked;
    setBusy(true);

    try {
      const { error } = await stripe.confirmPayment({
        elements: elements,
        confirmParams: {
          return_url: window.location.origin + successUrl,
        },
      });
      if (error) {
        messageEl.textContent = error.message || "Payment failed.";
        messageEl.dataset.locked = "1";
        setBusy(false);
      }
      // On success Stripe redirects; leave button disabled.
    } catch (err) {
      messageEl.textContent = (err && err.message) || "Payment failed.";
      setBusy(false);
    }
  });

  init().catch(function (err) {
    messageEl.textContent = err.message || "Checkout failed to load.";
    submitBtn.disabled = true;
    submitBtn.textContent = "Pay now";
    window.__checkoutReady = false;
  });
})();
