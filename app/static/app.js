// ===== Insta Post Auto — front (vanilla JS, mobile-first) =====
const $ = (sel, el = document) => el.querySelector(sel);
const view = $("#view");
const brandSelect = $("#brandSelect");

const state = { brands: [], products: [], currentBrand: null, tab: "generate" };

// ---- helpers réseau ----
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || JSON.stringify(j); } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}
const getJSON = (p) => api(p);
const postJSON = (p, body) =>
  api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const patchJSON = (p, body) =>
  api(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const postForm = (p, fd) => api(p, { method: "POST", body: fd });
const del = (p) => api(p, { method: "DELETE" });

// ---- UI feedback ----
let toastTimer;
function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast " + kind; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3200);
}
function loader(on, text = "Chargement…") {
  $("#loaderText").textContent = text;
  $("#loader").hidden = !on;
}
const mediaUrl = (p) => (p ? `/static/${p.replace(/^static\//, "")}` : "");

// ---- bootstrap ----
async function init() {
  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );
  brandSelect.addEventListener("change", () => {
    state.currentBrand = state.brands.find((b) => b.id == brandSelect.value) || null;
    render();
  });
  await loadBrands();
  render();
}

async function loadBrands() {
  state.brands = await getJSON("/api/brands");
  brandSelect.innerHTML =
    state.brands.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("") ||
    `<option value="">— aucune marque —</option>`;
  if (state.brands.length) {
    if (!state.currentBrand || !state.brands.find((b) => b.id === state.currentBrand.id))
      state.currentBrand = state.brands[0];
    brandSelect.value = state.currentBrand.id;
  } else {
    state.currentBrand = null;
  }
}

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  render();
}

function render() {
  const map = { brands: renderBrands, products: renderProducts, generate: renderGenerate,
                library: renderLibrary, schedule: renderSchedule };
  (map[state.tab] || renderGenerate)();
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// =====================================================================
//  MARQUE
// =====================================================================
function renderBrands() {
  const b = state.currentBrand;
  view.innerHTML = `
    <h2 class="section-title">🏷️ Marque & charte</h2>
    <div class="card">
      <label>Nom de la marque</label>
      <input id="bName" value="${esc(b?.name || "")}" placeholder="Ex : MedSkin Precision" />
      <div class="color-swatches">
        <div class="color-field"><label>Primaire</label><input type="color" id="cPrim" value="${b?.primary_color || "#111111"}"></div>
        <div class="color-field"><label>Secondaire</label><input type="color" id="cSec" value="${b?.secondary_color || "#ffffff"}"></div>
        <div class="color-field"><label>Accent</label><input type="color" id="cAcc" value="${b?.accent_color || "#ff4d6d"}"></div>
      </div>
      <label>Ton de voix</label>
      <input id="bTone" value="${esc(b?.tone_of_voice || "")}" placeholder="Ex : expert, rassurant, premium" />
      <label>Audience cible</label>
      <input id="bAud" value="${esc(b?.target_audience || "")}" placeholder="Ex : femmes 30-50, soin de la peau" />
      <label>Hashtags par défaut</label>
      <input id="bTags" value="${esc(b?.default_hashtags || "")}" placeholder="#skincare #beauty" />
      <label>Brand guidelines (texte)</label>
      <textarea id="bGuide" placeholder="Colle ici ta charte, ou importe un PDF ci-dessous">${esc(b?.guidelines || "")}</textarea>
      <button class="btn-primary" id="saveBrand" style="margin-top:14px">${b ? "💾 Enregistrer" : "➕ Créer la marque"}</button>
    </div>
    ${b ? brandAssetsCard(b) : `<p class="muted">Crée d'abord la marque pour ajouter logos, image et PDF.</p>`}
  `;

  $("#saveBrand").onclick = saveBrand;
  if (b) bindAssetHandlers(b);
}

function brandAssetsCard(b) {
  const logos = (b.logos || []).map((p) => `
    <div class="logo-item">
      <img src="${mediaUrl(p)}" class="${p === b.logo_path ? "primary" : ""}"
           title="Cliquer pour définir comme principal" data-logo="${esc(p)}">
    </div>`).join("");
  return `
    <div class="card">
      <h3 style="margin-top:0">Logos PNG</h3>
      <p class="muted">Ajoute tes logos individuellement. Clique sur un logo pour le définir comme principal (encadré rose).</p>
      <div class="logo-strip" id="logoStrip">${logos || '<span class="muted">Aucun logo</span>'}</div>
      <label>Ajouter des logos (PNG, multiple)</label>
      <input type="file" id="logoInput" accept="image/png,image/*" multiple>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Image de marque (fond)</h3>
      ${b.brand_image_path ? `<img src="${mediaUrl(b.brand_image_path)}" style="width:100%;border-radius:12px;margin-bottom:10px">` : ""}
      <input type="file" id="brandImgInput" accept="image/*">
    </div>
    <div class="card">
      <h3 style="margin-top:0">Brand guidelines (PDF)</h3>
      <p class="muted">${b.guidelines_pdf_path ? "✅ PDF importé — texte ajouté aux guidelines." : "Importe un PDF, le texte est extrait automatiquement."}</p>
      <input type="file" id="pdfInput" accept="application/pdf">
    </div>`;
}

async function saveBrand() {
  const payload = {
    name: $("#bName").value.trim(),
    primary_color: $("#cPrim").value, secondary_color: $("#cSec").value, accent_color: $("#cAcc").value,
    tone_of_voice: $("#bTone").value, target_audience: $("#bAud").value,
    default_hashtags: $("#bTags").value, guidelines: $("#bGuide").value,
  };
  if (!payload.name) return toast("Donne un nom à la marque", "error");
  loader(true, "Enregistrement…");
  try {
    if (state.currentBrand) await patchJSON(`/api/brands/${state.currentBrand.id}`, payload);
    else await postJSON("/api/brands", payload);
    await loadBrands(); toast("Marque enregistrée", "ok"); render();
  } catch (e) { toast(e.message, "error"); } finally { loader(false); }
}

function bindAssetHandlers(b) {
  $("#logoInput").onchange = async (e) => {
    const fd = new FormData();
    [...e.target.files].forEach((f) => fd.append("files", f));
    await uploadAsset(`/api/brands/${b.id}/logos`, fd, "Logos ajoutés");
  };
  $("#brandImgInput").onchange = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    await uploadAsset(`/api/brands/${b.id}/brand-image`, fd, "Image enregistrée");
  };
  $("#pdfInput").onchange = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    await uploadAsset(`/api/brands/${b.id}/guidelines-pdf`, fd, "PDF importé & texte extrait");
  };
  document.querySelectorAll("#logoStrip img[data-logo]").forEach((img) => {
    img.onclick = async () => {
      const fd = new FormData(); fd.append("path", img.dataset.logo);
      await uploadAsset(`/api/brands/${b.id}/primary-logo`, fd, "Logo principal défini");
    };
  });
}

async function uploadAsset(url, fd, okMsg) {
  loader(true, "Envoi…");
  try { await postForm(url, fd); await loadBrands(); toast(okMsg, "ok"); render(); }
  catch (e) { toast(e.message, "error"); } finally { loader(false); }
}

// =====================================================================
//  PRODUITS
// =====================================================================
async function renderProducts() {
  if (!requireBrand()) return;
  const products = await getJSON(`/api/products?brand_id=${state.currentBrand.id}`);
  state.products = products;
  view.innerHTML = `
    <h2 class="section-title">📦 Produits (mockups)</h2>
    <div class="card">
      <p class="muted">Ajoute un produit avec ses dimensions réelles (en mm) — les mockups respecteront ses proportions L × H.</p>
      <label>Nom du produit</label><input id="pName" placeholder="Ex : Sérum 30ml">
      <label>Description</label><input id="pDesc" placeholder="Optionnel">
      <div class="row">
        <div><label>Largeur (mm)</label><input id="pW" type="number" inputmode="decimal" placeholder="40"></div>
        <div><label>Hauteur (mm)</label><input id="pH" type="number" inputmode="decimal" placeholder="110"></div>
      </div>
      <label>Image du produit (PNG détouré conseillé)</label>
      <input type="file" id="pImg" accept="image/*">
      <button class="btn-primary" id="addProduct" style="margin-top:14px">➕ Ajouter le produit</button>
    </div>
    <div class="grid">
      ${products.map(productCard).join("") || `<p class="empty">Aucun produit.</p>`}
    </div>`;
  $("#addProduct").onclick = addProduct;
  products.forEach((p) => {
    const btn = $(`#delProd${p.id}`); if (btn) btn.onclick = () => removeProduct(p.id);
  });
}

function productCard(p) {
  const ratio = p.width_mm && p.height_mm ? `${p.width_mm}×${p.height_mm} mm` : "ratio image";
  return `<div class="card">
    ${p.image_path ? `<img src="${mediaUrl(p.image_path)}" class="thumb" style="object-fit:contain;background:#fff">` : ""}
    <div class="hook">${esc(p.name)}</div>
    <span class="pill">${ratio}</span>
    <p class="caption">${esc(p.description || "")}</p>
    <div class="card-actions"><button class="btn-danger btn-sm" id="delProd${p.id}">🗑️ Supprimer</button></div>
  </div>`;
}

async function addProduct() {
  if (!$("#pName").value.trim()) return toast("Nom requis", "error");
  const fd = new FormData();
  fd.append("brand_id", state.currentBrand.id);
  fd.append("name", $("#pName").value.trim());
  fd.append("description", $("#pDesc").value);
  if ($("#pW").value) fd.append("width_mm", $("#pW").value);
  if ($("#pH").value) fd.append("height_mm", $("#pH").value);
  if ($("#pImg").files[0]) fd.append("file", $("#pImg").files[0]);
  loader(true, "Ajout du produit…");
  try { await postForm("/api/products", fd); toast("Produit ajouté", "ok"); render(); }
  catch (e) { toast(e.message, "error"); } finally { loader(false); }
}
async function removeProduct(id) {
  if (!confirm("Supprimer ce produit ?")) return;
  await del(`/api/products/${id}`); toast("Supprimé", "ok"); render();
}

// =====================================================================
//  GÉNÉRER
// =====================================================================
async function renderGenerate() {
  if (!requireBrand()) return;
  state.products = await getJSON(`/api/products?brand_id=${state.currentBrand.id}`);
  view.innerHTML = `
    <h2 class="section-title">✨ Générer du contenu</h2>
    <div class="card">
      <p class="muted" style="margin-top:0">
        <b style="color:var(--text)">Étape 1</b> — génère d'abord les hooks qui convertissent
        (ex : « Tu perds chaque jour 1000 CHF… »). <b style="color:var(--text)">Étape 2</b> —
        depuis la bibliothèque, tu génères l'image à partir du hook choisi.
      </p>
      <div class="seg" id="fmtSeg">
        <button data-fmt="post" class="active">📷 Post</button>
        <button data-fmt="carousel">🎠 Carousel</button>
        <button data-fmt="story">📲 Story</button>
      </div>
      <label>Brief / sujet du contenu</label>
      <textarea id="gPrompt" placeholder="Ex : promouvoir notre nouveau sérum anti-âge, bénéfices et routine"></textarea>
      <div class="row">
        <div><label>Nb de hooks</label><input id="gVar" type="number" inputmode="numeric" value="10" min="1" max="30"></div>
        <div><label>Produit (mockup)</label>
          <select id="gProduct"><option value="">— aucun —</option>
            ${state.products.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}
          </select>
        </div>
      </div>
      <button class="btn-primary" id="genBtn" style="margin-top:16px">🎯 Générer les hooks qui convertissent</button>
      <p class="muted" style="margin-top:10px">Chaque hook utilise un angle d'attaque différent (pain point, curiosité, preuve sociale, FOMO…).</p>
    </div>`;
  let fmt = "post";
  document.querySelectorAll("#fmtSeg button").forEach((btn) =>
    (btn.onclick = () => {
      fmt = btn.dataset.fmt;
      document.querySelectorAll("#fmtSeg button").forEach((b) => b.classList.toggle("active", b === btn));
    })
  );
  $("#genBtn").onclick = () => generate(fmt);
}

async function generate(fmt) {
  const prompt = $("#gPrompt").value.trim();
  if (!prompt) return toast("Décris le contenu à générer", "error");
  const body = {
    brand_id: state.currentBrand.id, prompt, format: fmt,
    variations: parseInt($("#gVar").value) || 10,
    auto_compose: false, // étape 1 : hooks seuls
    product_id: $("#gProduct").value ? parseInt($("#gProduct").value) : null,
  };
  loader(true, "Génération des hooks (Claude)…");
  try {
    const items = await postJSON("/api/content/generate", body);
    toast(`${items.length} hooks générés — choisis-en un et génère l'image`, "ok");
    switchTab("library");
  } catch (e) { toast(e.message, "error"); } finally { loader(false); }
}

// =====================================================================
//  BIBLIOTHÈQUE
// =====================================================================
async function renderLibrary() {
  if (!requireBrand()) return;
  const items = await getJSON(`/api/content?brand_id=${state.currentBrand.id}`);
  view.innerHTML = `
    <h2 class="section-title">🗂️ Bibliothèque <span class="muted">(${items.length})</span></h2>
    <div class="grid">${items.map(contentCard).join("") || `<p class="empty">Rien encore. Va générer du contenu ✨</p>`}</div>`;
  items.forEach(bindContentCard);
}

function statusPill(s) { return `<span class="pill status-${s}">${s}</span>`; }

function contentCard(it) {
  const imgs = it.image_paths || [];
  const isStory = it.format === "story";
  const hasImg = imgs.length > 0;
  const thumbs = imgs.length > 1
    ? `<div class="thumbs-scroll">${imgs.map((p) => `<img src="${mediaUrl(p)}">`).join("")}</div>`
    : hasImg ? `<img class="thumb ${isStory ? "story" : ""}" src="${mediaUrl(imgs[0])}">`
    : `<div class="thumb" style="display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:.8rem">Pas encore d'image — étape 2 ⬇️</div>`;
  return `<div class="card content-card" id="c${it.id}">
    ${thumbs}
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px">
      <span class="pill">${it.format}</span>
      ${it.angle ? `<span class="pill angle">${esc(it.angle)}</span>` : ""}
      ${statusPill(it.status)}
    </div>
    <div class="hook">${esc(it.hook)}</div>
    <div class="caption">${esc(it.caption)}</div>
    <div class="hashtags">${esc(it.hashtags)}</div>
    ${it.error ? `<p class="muted" style="color:var(--accent)">⚠ ${esc(it.error)}</p>` : ""}
    <label style="display:flex;align-items:center;gap:8px;margin-top:10px">
      <input type="checkbox" data-act="aiToggle" style="width:auto">
      <span style="color:var(--muted)">Image IA (sinon image de marque)</span>
    </label>
    <div class="card-actions">
      <button class="btn-ghost btn-sm" data-act="edit">✏️ Éditer</button>
      ${it.status === "draft" ? `<button class="btn-ok btn-sm" data-act="approve">✓ Valider</button>` : ""}
      <button class="${hasImg ? "btn-ghost" : "btn-primary"} btn-sm" data-act="render">🖼️ ${hasImg ? "Re-générer image" : "Générer l'image"}</button>
      <button class="btn-ghost btn-sm" data-act="schedule">📅 Planifier</button>
      <button class="btn-primary btn-sm" data-act="publish">📤 Publier</button>
      <button class="btn-danger btn-sm" data-act="del">🗑️</button>
    </div>
  </div>`;
}

function bindContentCard(it) {
  const card = $(`#c${it.id}`);
  const on = (act, fn) => { const b = card.querySelector(`[data-act="${act}"]`); if (b) b.onclick = fn; };
  on("approve", async () => { await patchJSON(`/api/content/${it.id}`, { status: "approved" }); toast("Validé", "ok"); render(); });
  on("del", async () => { if (confirm("Supprimer ?")) { await del(`/api/content/${it.id}`); toast("Supprimé", "ok"); render(); } });
  on("render", async () => {
    const useAi = card.querySelector('[data-act="aiToggle"]')?.checked || false;
    loader(true, useAi ? "Génération de l'image IA…" : "Composition du visuel…");
    try { await postJSON(`/api/content/${it.id}/render`, { use_ai_image: useAi }); toast("Image générée", "ok"); render(); }
    catch (e) { toast(e.message, "error"); } finally { loader(false); }
  });
  on("publish", async () => {
    if (!confirm("Publier maintenant sur Instagram ?")) return;
    loader(true, "Publication…");
    try { await postJSON(`/api/content/${it.id}/publish`, {}); toast("Publié 🎉", "ok"); render(); }
    catch (e) { toast(e.message, "error"); } finally { loader(false); }
  });
  on("edit", () => editContent(it));
  on("schedule", () => scheduleContent(it));
}

function editContent(it) {
  const card = $(`#c${it.id}`);
  card.innerHTML = `
    <label>Hook</label><input id="eHook${it.id}" value="${esc(it.hook)}">
    <label>Caption</label><textarea id="eCap${it.id}">${esc(it.caption)}</textarea>
    <label>Hashtags</label><input id="eTags${it.id}" value="${esc(it.hashtags)}">
    <div class="card-actions">
      <button class="btn-primary btn-sm" id="eSave${it.id}">💾 Enregistrer</button>
      <button class="btn-ghost btn-sm" id="eCancel${it.id}">Annuler</button>
    </div>`;
  $(`#eCancel${it.id}`).onclick = render;
  $(`#eSave${it.id}`).onclick = async () => {
    await patchJSON(`/api/content/${it.id}`, {
      hook: $(`#eHook${it.id}`).value, caption: $(`#eCap${it.id}`).value, hashtags: $(`#eTags${it.id}`).value,
    });
    toast("Modifié — pense à refaire le rendu si besoin", "ok"); render();
  };
}

function scheduleContent(it) {
  const card = $(`#c${it.id}`);
  const dflt = new Date(Date.now() + 3600e3).toISOString().slice(0, 16);
  card.insertAdjacentHTML("beforeend", `
    <div class="card" style="margin-top:10px;background:var(--surface-2)">
      <label>Publier le</label>
      <input type="datetime-local" id="sched${it.id}" value="${dflt}">
      <div class="card-actions">
        <button class="btn-primary btn-sm" id="schedOk${it.id}">📅 Programmer</button>
      </div>
    </div>`);
  $(`#schedOk${it.id}`).onclick = async () => {
    try {
      await postJSON("/api/schedule", { content_id: it.id, scheduled_at: $(`#sched${it.id}`).value });
      toast("Programmé", "ok"); render();
    } catch (e) { toast(e.message, "error"); }
  };
}

// =====================================================================
//  PLANNING
// =====================================================================
async function renderSchedule() {
  if (!requireBrand()) return;
  const sched = await getJSON(`/api/schedule?brand_id=${state.currentBrand.id}`);
  const today = new Date().toISOString().slice(0, 10);
  view.innerHTML = `
    <h2 class="section-title">📅 Planning auto-post</h2>
    <div class="card">
      <h3 style="margin-top:0">Auto-programmer la file</h3>
      <p class="muted">Répartit tes contenus prêts (avec visuel) à raison d'un par jour, automatiquement publiés.</p>
      <div class="row">
        <div><label>À partir du</label><input type="date" id="asDate" value="${today}"></div>
        <div><label>Heure</label><input type="time" id="asTime" value="09:00"></div>
      </div>
      <label>Nombre de jours à remplir</label>
      <input type="number" id="asDays" value="7" min="1" max="90" inputmode="numeric">
      <button class="btn-primary" id="autoSchedBtn" style="margin-top:14px">⚡ Auto-programmer</button>
    </div>
    <h3>Programmés (${sched.length})</h3>
    <div class="grid">${sched.map(scheduleCard).join("") || `<p class="empty">Aucun créneau.</p>`}</div>`;
  $("#autoSchedBtn").onclick = autoSchedule;
  sched.forEach((s) => { const b = $(`#unsched${s.id}`); if (b) b.onclick = () => unschedule(s.id); });
}

function scheduleCard(s) {
  const when = new Date(s.scheduled_at + "Z").toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
  return `<div class="card">
    <div class="hook">📌 Contenu #${s.content_id}</div>
    <p class="muted">Publication : ${when}${s.published_at ? " ✅ publié" : ""}</p>
    ${s.attempts ? `<span class="pill">tentatives: ${s.attempts}</span>` : ""}
    ${!s.published_at ? `<div class="card-actions"><button class="btn-danger btn-sm" id="unsched${s.id}">Annuler</button></div>` : ""}
  </div>`;
}

async function autoSchedule() {
  const body = {
    brand_id: state.currentBrand.id,
    start_date: $("#asDate").value + "T00:00:00",
    time_of_day: $("#asTime").value,
    days: parseInt($("#asDays").value) || 7,
  };
  loader(true, "Programmation…");
  try { const r = await postJSON("/api/schedule/auto", body); toast(`${r.length} contenus programmés`, "ok"); render(); }
  catch (e) { toast(e.message, "error"); } finally { loader(false); }
}
async function unschedule(id) { await del(`/api/schedule/${id}`); toast("Créneau annulé", "ok"); render(); }

// ---- util ----
function requireBrand() {
  if (!state.currentBrand) {
    view.innerHTML = `<div class="empty">👋 Commence par créer une marque dans l'onglet <b>Marque</b>.</div>`;
    return false;
  }
  return true;
}

init();
