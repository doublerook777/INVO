/* Dashboard. Dev B owns this file. Read-only views of /api/inventory + /api/alerts. */
const API = localStorage.getItem("api") || "http://localhost:8000";

const esc = s => String(s ?? "").replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function load() {
  let inv, al;
  try {
    [inv, al] = await Promise.all([
      fetch(`${API}/api/inventory`).then(r => r.json()),
      fetch(`${API}/api/alerts`).then(r => r.json()),
    ]);
  } catch (e) {
    document.getElementById("stock").innerHTML =
      `<tr><td colspan="5" style="color:#f87171">Backend offline — start uvicorn on :8000</td></tr>`;
    return;
  }

  const items = inv.items;
  const low = items.filter(i => i.status === "low").length;
  const out = items.filter(i => i.status === "out").length;
  const value = items.reduce((s, i) => s + i.current_qty * i.cost_per_unit, 0) / 100;

  document.getElementById("stats").innerHTML = `
    <div class="stat"><b>${items.length}</b><span>items tracked</span></div>
    <div class="stat low"><b>${low}</b><span>running low</span></div>
    <div class="stat out"><b>${out}</b><span>out of stock</span></div>
    <div class="stat"><b>₹${Math.round(value).toLocaleString("en-IN")}</b><span>stock value</span></div>`;

  document.getElementById("value").textContent =
    "₹" + Math.round(value).toLocaleString("en-IN");

  const order = { out: 0, low: 1, ok: 2 };
  document.getElementById("stock").innerHTML = items
    .sort((a, b) => order[a.status] - order[b.status] ||
                    (a.days_of_cover ?? 999) - (b.days_of_cover ?? 999))
    .map(i => `<tr class="${i.status}">
      <td>${esc(i.name)}</td>
      <td class="num">${i.current_qty} ${esc(i.unit)}</td>
      <td class="num">${i.avg_daily_sales}</td>
      <td class="num">${i.days_of_cover ?? "—"}</td>
      <td><span class="pill ${i.status}">${i.status}</span></td>
    </tr>`).join("");

  document.getElementById("alerts").innerHTML = al.alerts.length
    ? al.alerts.map(a => `<div class="alert">
        <b>${esc(a.name)}</b> — ${a.days_of_cover} din baaki<br>
        <span style="color:var(--wa-muted)">${esc(a.message)}</span></div>`).join("")
    : `<div style="color:var(--wa-muted);font-size:13px">Sab theek hai 👍</div>`;
}

load();
setInterval(load, 15000);
