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

  if (!appointmentId || !publishableKey) {
    messageEl.textContent = "Stripe is not configured.";
    return;
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  const stripe = Stripe(publishableKey);
  let elements;

  async function init() {
    const response = await fetch(`/api/payments/${appointmentId}/create-intent/`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: "{}",
    });
    const data = await response.json();
    if (!response.ok) {
      messageEl.textContent = data.detail || "Could not start payment.";
      submitBtn.disabled = true;
      return;
    }

    elements = stripe.elements({ clientSecret: data.client_secret });
    const paymentElement = elements.create("payment");
    paymentElement.mount("#payment-element");
  }

  submitBtn.addEventListener("click", async function () {
    messageEl.textContent = "";
    submitBtn.disabled = true;
    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: window.location.origin + successUrl,
      },
    });
    if (error) {
      messageEl.textContent = error.message || "Payment failed.";
      submitBtn.disabled = false;
    }
  });

  init().catch(function (err) {
    messageEl.textContent = err.message || "Checkout failed to load.";
    submitBtn.disabled = true;
  });
})();
