/* WhatsApp mirror. Dev B owns this file.
   Shows the real WhatsApp conversation (messages the Twilio webhook received
   and the replies the backend generated). The Twilio trial account can't
   deliver those replies to the phone, so this page is where they're visible.
   Read-only: polls GET /api/messages and /api/inventory. */

const API = localStorage.getItem("api") || "http://localhost:8000";
const SHOP_ID = 1;

const chat = document.getElementById("chat");
let lastId = 0;

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// Show the last 4 digits only: this page ends up in screenshots and slides.
function masked(sender) {
  const digits = (sender || "").replace(/\D/g, "");
  return digits.length >= 4 ? `+${digits.slice(0, 2)} ••••• ${digits.slice(-4)}` : "WhatsApp";
}

function timeOf(iso) {
  // created_at is UTC from SQLite's CURRENT_TIMESTAMP ("YYYY-MM-DD HH:MM:SS").
  const d = new Date(String(iso).replace(" ", "T") + "Z");
  return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function addMessage(m) {
  // direction "in" = the owner's message to the bot -> right, green.
  const side = m.direction === "in" ? "out" : "in";
  const row = document.createElement("div");
  row.className = `row ${side}`;
  row.innerHTML =
    `<div class="bubble">${escapeHtml(m.body)}` +
    `<span class="meta">${timeOf(m.created_at)}` +
    `${side === "out" ? ' <span class="tick">✓✓</span>' : ""}</span></div>`;
  chat.appendChild(row);
}

async function pollMessages() {
  try {
    const res = await fetch(`${API}/api/messages?shop_id=${SHOP_ID}&after_id=${lastId}`);
    if (!res.ok) return;
    const { messages } = await res.json();
    if (!messages.length) return;
    for (const m of messages) {
      addMessage(m);
      lastId = Math.max(lastId, m.id);
    }
    document.getElementById("who").textContent =
      `WhatsApp · ${masked(messages[messages.length - 1].sender)}`;
    chat.scrollTop = chat.scrollHeight;
    refresh();   // a message probably just changed stock
  } catch { /* backend not up yet; try again next tick */ }
}

/* ---------- live stock panel (same as the chat page) ---------- */
async function refresh() {
  try {
    const [inv, al] = await Promise.all([
      fetch(`${API}/api/inventory`).then(r => r.json()),
      fetch(`${API}/api/alerts`).then(r => r.json()),
    ]);
    renderStats(inv.items);
    renderStock(inv.items);
    renderAlerts(al.alerts);
  } catch { /* ignore */ }
}

function renderStats(items) {
  const low = items.filter(i => i.status === "low").length;
  const out = items.filter(i => i.status === "out").length;
  document.getElementById("stats").innerHTML = `
    <div class="stat"><b>${items.length}</b><span>items</span></div>
    <div class="stat low"><b>${low}</b><span>running low</span></div>
    <div class="stat out"><b>${out}</b><span>out of stock</span></div>`;
}

function renderStock(items) {
  const order = { out: 0, low: 1, ok: 2 };
  document.getElementById("stock").innerHTML = items
    .sort((a, b) => order[a.status] - order[b.status] ||
                    (a.days_of_cover ?? 999) - (b.days_of_cover ?? 999))
    .map(i => `<tr class="${i.status}">
        <td>${escapeHtml(i.name)}</td>
        <td class="num">${i.current_qty} ${escapeHtml(i.unit)}</td>
        <td class="num">${i.days_of_cover ?? "—"}</td>
        <td><span class="pill ${i.status}">${i.status}</span></td>
      </tr>`).join("");
}

function renderAlerts(alerts) {
  const el = document.getElementById("alerts");
  if (!alerts.length) { el.innerHTML =
    `<div style="color:var(--wa-muted);font-size:13px">Sab theek hai 👍</div>`; return; }
  el.innerHTML = alerts.slice(0, 4).map(a =>
    `<div class="alert"><b>${escapeHtml(a.name)}</b> — ${a.days_of_cover} din baaki.
       <br>${escapeHtml(a.message)}</div>`).join("");
}

pollMessages();
refresh();
setInterval(pollMessages, 2000);
setInterval(refresh, 15000);
