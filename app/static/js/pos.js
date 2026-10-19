const csrf = document.body.dataset.csrf;
const lookupInput = document.getElementById("lookup");
const lookupResults = document.getElementById("lookup-results");
const cartBody = document.getElementById("cart-body");
const cartEmpty = document.getElementById("cart-empty");
const totalEl = document.getElementById("total");
const rxBox = document.getElementById("rx-box");
const rxOk = document.getElementById("rx-ok");
const msg = document.getElementById("pos-msg");
let cart = [];           // {id, name, price, qty, rx}
let lookupTimer;

function esc(s) { const d = document.createElement("div"); d.textContent = s ?? ""; return d.innerHTML; }
function money(n) { return "Rs " + Number(n).toFixed(2); }

function renderCart() {
  cartBody.innerHTML = cart.map((it, idx) => `
    <tr><td>${esc(it.name)}${it.rx ? ' <span class="badge rx">Rx</span>' : ""}</td>
      <td>${money(it.price)}</td>
      <td><input type="number" min="1" value="${it.qty}" data-idx="${idx}" class="qty-input" style="width:4rem"></td>
      <td>${money(it.price * it.qty)}</td>
      <td><button class="linkbtn" data-remove="${idx}">remove</button></td></tr>`).join("");
  cartEmpty.hidden = cart.length > 0;
  const total = cart.reduce((s, it) => s + it.price * it.qty, 0);
  const discount = Number(document.getElementById("discount").value || 0);
  totalEl.textContent = money(total * (1 - discount / 100));
  rxBox.hidden = !cart.some(it => it.rx);
  cartBody.querySelectorAll(".qty-input").forEach(inp => inp.addEventListener("change", e => {
    const i = Number(e.target.dataset.idx);
    cart[i].qty = Math.max(1, Number(e.target.value) || 1);
    renderCart();
  }));
  cartBody.querySelectorAll("[data-remove]").forEach(btn => btn.addEventListener("click", e => {
    cart.splice(Number(e.target.dataset.remove), 1);
    renderCart();
  }));
}

async function runLookup() {
  const q = lookupInput.value.trim();
  if (q.length < 2) { lookupResults.innerHTML = ""; return; }
  const res = await fetch(`/pharmacist/lookup?q=${encodeURIComponent(q)}`);
  const items = await res.json();
  lookupResults.innerHTML = items.map(m => `
    <button type="button" class="pick" data-id="${m.id}" data-name="${esc(m.name)}" data-price="${m.price}" data-rx="${m.rx}">
      ${esc(m.name)} - Rs ${m.price} (avail. ${m.qty})</button>`).join("") || "<p class='empty'>No match.</p>";
  lookupResults.querySelectorAll(".pick").forEach(btn => btn.addEventListener("click", () => {
    const id = Number(btn.dataset.id);
    const existing = cart.find(it => it.id === id);
    if (existing) existing.qty += 1;
    else cart.push({ id, name: btn.dataset.name, price: Number(btn.dataset.price), qty: 1, rx: btn.dataset.rx === "true" });
    lookupInput.value = ""; lookupResults.innerHTML = "";
    renderCart();
  }));
}

lookupInput.addEventListener("input", () => { clearTimeout(lookupTimer); lookupTimer = setTimeout(runLookup, 250); });
document.getElementById("discount").addEventListener("input", renderCart);

document.getElementById("checkout").addEventListener("click", async () => {
  if (!cart.length) return;
  msg.hidden = true;
  const payload = {
    items: cart.map(it => ({ medicine_id: it.id, quantity: it.qty })),
    customer_id: document.getElementById("customer").value || null,
    payment_mode: document.getElementById("payment").value,
    discount_pct: document.getElementById("discount").value,
    rx_verified: !rxBox.hidden && rxOk.checked,
    doctor_name: document.getElementById("doctor").value,
    doctor_reg: document.getElementById("doctor-reg").value,
  };
  if (!rxBox.hidden && !rxOk.checked) {
    msg.hidden = false; msg.className = "flash error";
    msg.textContent = "Tick 'I have checked a valid prescription' before billing Rx items.";
    return;
  }
  const res = await post("/pharmacist/pos/checkout", payload);
  const data = await res.json();
  if (data.ok) { window.location.href = data.url; return; }
  if (data.needs_ack) {
    const text = data.warnings.map(w => w.message).join(" | ");
    if (confirm("Safety warning:\n" + text + "\n\nBill anyway?")) {
      payload.acknowledge = true;
      const res2 = await post("/pharmacist/pos/checkout", payload);
      const data2 = await res2.json();
      if (data2.ok) { window.location.href = data2.url; return; }
      showError(data2.error || "Could not complete the sale.");
    }
    return;
  }
  showError(data.error || "Could not complete the sale.");
});

function showError(text) {
  msg.hidden = false; msg.className = "flash error"; msg.textContent = text;
}

async function post(url, payload) {
  return fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify(payload) });
}

renderCart();
