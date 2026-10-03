/* Invo chat UI. Dev B owns this file.
   Talks to POST /api/chat -- see docs/api-contract.md. */

const API = localStorage.getItem("api") || "http://localhost:8000";
const SHOP_ID = 1;

// Per-tab sender id. One shared "web-demo" meant two open tabs could consume
// each other's pending clarifying question -- each tab needs its own identity.
const SENDER = (() => {
  let id = sessionStorage.getItem("invo_sender");
  if (!id) {
    id = "web-" + Math.random().toString(36).slice(2, 10);
    sessionStorage.setItem("invo_sender", id);
  }
  return id;
})();

const chat   = document.getElementById("chat");
const input  = document.getElementById("input");
const sendEl = document.getElementById("send");
const micEl  = document.getElementById("mic");
const fileEl = document.getElementById("audiofile");
const attachEl = document.getElementById("attach");
const imageEl  = document.getElementById("imagefile");

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

/* A photo bubble for a supplier bill, so the screenshot shows the input. */
function imageBubble(file) {
  const url = URL.createObjectURL(file);
  const row = bubble("out", `<img class="photo" src="${url}" alt="bill">`, { ticks: true });
  row.querySelector("img").onload = () => { scroll(); };
  return row;
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
    return `<div><span>${escapeHtml(a.sku_name)}</span>
              <span>${sign}${escapeHtml(String(a.qty))} ${escapeHtml(a.unit)}${rate}</span></div>`;
  }).join("");
  return `<div class="receipt">${rows}</div>`;
}

function optionButtons(options) {
  if (!options || !options.length) return "";
  const b = options.map(o =>
    `<button data-value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</button>`).join("");
  return `<div class="opts">${b}</div>`;
}

// Guards against overlapping requests: sending twice fast, or tapping an
// option while a request is still pending, used to interleave bubbles and
// race the pending-question state on the backend.
let inFlight = false;

// `label` is what the user sees in their own bubble when the sent text is a
// machine value (an option tap sends `sku:12`, but the bubble should read as
// the item name they tapped).
async function send(text, audioBlob, label, imageFile) {
  if (inFlight) return;
  inFlight = true;
  sendEl.disabled = micEl.disabled = attachEl.disabled = input.disabled = true;

  try {
    if (audioBlob) voiceBubble();
    else if (imageFile) imageBubble(imageFile);
    else if (text) bubble("out", escapeHtml(label || text), { ticks: true });

    input.value = "";
    const t = typing();

    const body = new FormData();
    body.append("shop_id", SHOP_ID);
    body.append("sender", SENDER);
    if (text) body.append("text", text);
    if (audioBlob) body.append("audio", audioBlob, "note.webm");
    if (imageFile) body.append("image", imageFile, imageFile.name || "bill.jpg");

    let res;
    try {
      res = await fetch(`${API}/api/chat`, { method: "POST", body });
    } catch (err) {
      t.remove();
      bubble("in", `<span style="color:#f87171">Backend offline — ${escapeHtml(String(err))}</span>`);
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch {
      t.remove();
      bubble("in", `<span style="color:#f87171">Server error (HTTP ${res.status}), no readable response</span>`);
      return;
    }
    t.remove();

    if (!res.ok || data.error) {
      bubble("in", `<span style="color:#f87171">Error ${res.status}: ${escapeHtml(data.error || res.statusText)}</span>`);
      return;
    }
    if (data.transcript) transcriptLine(data.transcript);

    const row = bubble("in",
      escapeHtml(data.reply) + receipt(data.actions) + optionButtons(data.options));

    row.querySelectorAll(".opts button").forEach(btn => {
      btn.onclick = () => {
        row.querySelector(".opts").remove();
        send(btn.dataset.value, undefined, btn.textContent);
      };
    });

    refresh();
  } finally {
    inFlight = false;
    sendEl.disabled = micEl.disabled = attachEl.disabled = input.disabled = false;
  }
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

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    bubble("in", `<span style="color:#f87171">Mic access nahi mila. File chuniye.</span>`);
    fileEl.click();   // no mic permission -> let them upload a clip instead
    return;
  }

  try {
    recorder = new MediaRecorder(stream);
  } catch (err) {
    stream.getTracks().forEach(t => t.stop());   // never got to onstop -- stop it here
    bubble("in", `<span style="color:#f87171">Recording start nahi hui: ${escapeHtml(String(err))}</span>`);
    fileEl.click();
    return;
  }

  chunks = [];
  recorder.ondataavailable = e => chunks.push(e.data);
  recorder.onstop = () => {
    stream.getTracks().forEach(t => t.stop());
    send(null, new Blob(chunks, { type: "audio/webm" }));
  };
  recorder.start();
  micEl.textContent = "⏹";
};
fileEl.onchange = e => e.target.files[0] && send(null, e.target.files[0]);

/* ---------- bill photo ---------- */
attachEl.onclick = () => imageEl.click();
imageEl.onchange = e => {
  const f = e.target.files[0];
  e.target.value = "";   // so picking the same file twice still fires
  if (f) send(null, undefined, undefined, f);
};

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
