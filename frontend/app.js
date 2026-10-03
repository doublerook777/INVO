/* StockSaathi chat UI. Dev B owns this file.
   Talks to POST /api/chat -- see docs/api-contract.md. */

const API = localStorage.getItem("api") || "http://localhost:8000";
const SENDER = "web-demo";

const chat   = document.getElementById("chat");
const input  = document.getElementById("input");
const sendEl = document.getElementById("send");
const micEl  = document.getElementById("mic");
const fileEl = document.getElementById("audiofile");

const now = () =>
  new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function scroll() { chat.scrollTop = chat.scrollHeight; }

function bubble(side, html, { ticks = false } = {}) {
  const row = document.createElement("div");
  row.className = `row ${side}`;
  row.innerHTML =
    `<div class="bubble">${html}` +
    `<span class="meta">${now()}${ticks ? ' <span class="tick">✓✓</span>' : ""}</span>` +
    `</div>`;
  chat.appendChild(row);
  scroll();
  return row;
}

/* A voice note bubble, so the screenshot shows WhatsApp's real affordance
   rather than just typed text. */
function voiceBubble(seconds = 4) {
  const bars = Array.from({ length: 26 },
    () => `<i style="height:${4 + Math.random() * 16}px"></i>`).join("");
  return bubble("out",
    `<div class="voice"><span class="play">▶</span>
       <span class="wave">${bars}</span>
       <span style="font-size:11px">0:0${seconds}</span></div>`,
    { ticks: true });
}

function transcriptLine(text) {
  const d = document.createElement("div");
  d.className = "transcript";
  d.textContent = `🎙 "${text}"`;
  chat.appendChild(d);
  scroll();
}

function typing() {
  const row = document.createElement("div");
  row.className = "row in";
  row.innerHTML = `<div class="bubble typing">typing…</div>`;
  chat.appendChild(row);
  scroll();
  return row;
}

function receipt(actions) {
  if (!actions || !actions.length) return "";
  const rows = actions.map(a => {
    const sign = a.type === "stock_in" ? "+" : "−";
    const rate = a.cost_per_unit ? ` · ₹${(a.cost_per_unit / 100).toFixed(0)}` : "";
    return `<div><span>${a.sku_name}</span>
              <span>${sign}${a.qty} ${a.unit}${rate}</span></div>`;
  }).join("");
  return `<div class="receipt">${rows}</div>`;
}

function optionButtons(options) {
  if (!options || !options.length) return "";
  const b = options.map(o =>
    `<button data-value="${o.value}">${o.label}</button>`).join("");
  return `<div class="opts">${b}</div>`;
}

async function send(text, audioBlob) {
  if (audioBlob) voiceBubble();
  else if (text) bubble("out", escapeHtml(text), { ticks: true });

  input.value = "";
  const t = typing();

  const body = new FormData();
  body.append("sender", SENDER);
  if (text) body.append("text", text);
  if (audioBlob) body.append("audio", audioBlob, "note.webm");

  let data;
  try {
    const res = await fetch(`${API}/api/chat`, { method: "POST", body });
    data = await res.json();
  } catch (err) {
    t.remove();
    bubble("in", `<span style="color:#f87171">Backend offline — ${escapeHtml(String(err))}</span>`);
    return;
  }
  t.remove();

  if (data.error) { bubble("in", `<span style="color:#f87171">${escapeHtml(data.error)}</span>`); return; }
  if (data.transcript) transcriptLine(data.transcript);

  const row = bubble("in",
    escapeHtml(data.reply) + receipt(data.actions) + optionButtons(data.options));

  row.querySelectorAll(".opts button").forEach(btn => {
    btn.onclick = () => {
      row.querySelector(".opts").remove();
      send(btn.dataset.value === "new" ? "haan" : btn.textContent);
    };
  });

  refresh();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------- live stock panel ---------- */
async function refresh() {
  try {
    const [inv, al] = await Promise.all([
      fetch(`${API}/api/inventory`).then(r => r.json()),
      fetch(`${API}/api/alerts`).then(r => r.json()),
    ]);
    renderStats(inv.items);
    renderStock(inv.items);
    renderAlerts(al.alerts);
  } catch { /* backend not up yet; the chat still works on its own */ }
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
    .slice(0, 14)
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

/* ---------- voice recording ---------- */
let recorder, chunks = [];
micEl.onclick = async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    micEl.textContent = "🎙";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = e => chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      send(null, new Blob(chunks, { type: "audio/webm" }));
    };
    recorder.start();
    micEl.textContent = "⏹";
  } catch {
    fileEl.click();   // no mic permission -> let them upload a clip instead
  }
};
fileEl.onchange = e => e.target.files[0] && send(null, e.target.files[0]);

/* ---------- demo shortcuts ---------- */
const DEMO = [
  "aaj bees Parle-G aaye, aur paanch kilo aata, aata ka rate badh gaya - chhiyalis rupaye",
  "do amul aaye",
  "das maggi bik gaye",
  "do peti coke aaye",
];
document.getElementById("chips").innerHTML =
  DEMO.map((d, i) => `<button data-i="${i}">${d.slice(0, 34)}…</button>`).join("");
document.getElementById("chips").onclick = e => {
  const i = e.target.dataset?.i;
  if (i !== undefined) { input.value = DEMO[i]; input.focus(); }
};

sendEl.onclick = () => input.value.trim() && send(input.value.trim());
input.onkeydown = e => {
  if (e.key === "Enter" && input.value.trim()) send(input.value.trim());
};

bubble("in", "Namaste! 🙏 Stock aaye ya jaaye, bas mujhe bol dijiye.\n" +
             "Jaise: <i>\"bees Parle-G aaye\"</i>");
refresh();
setInterval(refresh, 15000);
