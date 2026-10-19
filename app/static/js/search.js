const input = document.getElementById("q");
const results = document.getElementById("results");
const suggestList = document.getElementById("suggestions");
const RX_LABEL = (window.I18N && window.I18N.rx) || "Prescription required";
const ALT_LABEL = (window.I18N && window.I18N.alts) || "Available alternatives";
let timer;

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function statusBadge(status) {
  if (status === "in_stock") return ['in', input.dataset.in || 'In stock'];
  if (status === "low") return ['low', input.dataset.low || 'Low stock'];
  return ['out', input.dataset.out || 'Out of stock'];
}

function card(m) {
  const [cls, text] = statusBadge(m.status);
  const url = `/medicine/${m.id}`;
  const alts = (m.alternatives || []).length
    ? `<div class="alternatives"><strong>${esc(ALT_LABEL)}:</strong> ` +
      m.alternatives.map(a => `<a href="/medicine/${a.id}">${esc(a.name)}</a> (${esc(a.strength)}) - Rs ${esc(a.price)}`).join(", ") + `</div>`
    : "";
  return `
    <article class="result">
      <div>
        <h3><a href="${url}">${esc(m.name)}</a></h3>
        <div class="meta">${esc(m.generic)} &middot; ${esc(m.strength)} ${esc(m.form)} &middot; MRP Rs ${esc(m.price)}</div>
      </div>
      <div>
        <span class="badge ${cls}">${esc(text)}</span>
        ${m.requires_prescription ? `<span class="badge rx">${esc(RX_LABEL)}</span>` : ""}
      </div>
      ${alts}
    </article>`;
}

async function search() {
  const q = input.value.trim();
  if (q.length < 2) { results.innerHTML = ""; return; }
  try {
    const res = await fetch(`/api/medicines/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    results.innerHTML = data.length ? data.map(card).join("")
      : `<p>No medicine found for "${esc(q)}". Check the spelling or try the generic name.</p>`;
  } catch {
    results.innerHTML = "<p>Search is unavailable right now. Please try again shortly.</p>";
  }
}

async function suggest() {
  const q = input.value.trim();
  if (!suggestList || q.length < 2) return;
  try {
    const res = await fetch(`/api/medicines/suggest?q=${encodeURIComponent(q)}`);
    const names = await res.json();
    suggestList.innerHTML = names.map(n => `<option value="${esc(n)}">`).join("");
  } catch { /* ignore */ }
}

input.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => { search(); suggest(); }, 300);
});
document.getElementById("go").addEventListener("click", search);
