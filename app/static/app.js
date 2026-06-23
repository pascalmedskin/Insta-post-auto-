// ===== Insta Post Auto — front (vanilla JS, mobile-first) =====
const $ = (sel, el = document) => el.querySelector(sel);
const view = $("#view");

const _loadedFonts = new Set();
function loadGFont(name) {
  if (!name || _loadedFonts.has(name)) return;
  _loadedFonts.add(name);
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name)}:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400;1,700&display=swap`;
  document.head.appendChild(link);
}
function fontPreviewHTML(fontName, label) {
  if (!fontName) return "";
  const f = esc(fontName);
  return `<div class="font-card">
    <div class="font-card-header">
      <span class="font-card-name">${f}</span>
      <span class="font-card-label">${label}</span>
    </div>
    <div class="font-card-big" style="font-family:'${f}',sans-serif">${f}</div>
    <div class="font-card-samples" style="font-family:'${f}',sans-serif">
      <div class="font-sample"><span class="font-sample-label">Light</span><span style="font-weight:300">Aa Bb Cc Dd Ee 0123456789</span></div>
      <div class="font-sample"><span class="font-sample-label">Regular</span><span style="font-weight:400">Aa Bb Cc Dd Ee 0123456789</span></div>
      <div class="font-sample"><span class="font-sample-label">Medium</span><span style="font-weight:500">Aa Bb Cc Dd Ee 0123456789</span></div>
      <div class="font-sample"><span class="font-sample-label">SemiBold</span><span style="font-weight:600">Aa Bb Cc Dd Ee 0123456789</span></div>
      <div class="font-sample"><span class="font-sample-label">Bold</span><span style="font-weight:700">Aa Bb Cc Dd Ee 0123456789</span></div>
      <div class="font-sample"><span class="font-sample-label">Black</span><span style="font-weight:900">Aa Bb Cc Dd Ee 0123456789</span></div>
      <div class="font-sample"><span class="font-sample-label">Italic</span><span style="font-weight:400;font-style:italic">Aa Bb Cc Dd Ee 0123456789</span></div>
    </div>
  </div>`;
}

const LANG_LABELS = {
  fr: "Français", de: "Deutsch", en: "English", it: "Italiano",
  es: "Español", pt: "Português", nl: "Nederlands", ja: "日本語",
  zh: "中文", ko: "한국어", ar: "العربية", ru: "Русский",
};

const state = { brands: [], products: [], currentBrand: null, tab: "home" };
let currentUser = null;

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

function confirmModal(message, confirmLabel = "Supprimer", cancelLabel = "Annuler") {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "confirm-overlay";
    const modal = document.createElement("div");
    modal.className = "confirm-modal";
    modal.innerHTML = `
      <p class="confirm-msg">${message}</p>
      <div class="confirm-actions">
        <button class="confirm-cancel">${cancelLabel}</button>
        <button class="confirm-ok">${confirmLabel}</button>
      </div>`;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("visible"));
    const close = (val) => {
      overlay.classList.remove("visible");
      setTimeout(() => overlay.remove(), 200);
      resolve(val);
    };
    modal.querySelector(".confirm-cancel").onclick = () => close(false);
    modal.querySelector(".confirm-ok").onclick = () => close(true);
    overlay.onclick = (e) => { if (e.target === overlay) close(false); };
  });
}
let _loaderInterval = null;
let _loaderProgress = 0;

function loader(on, text = "Chargement...", steps = null) {
  const el = $("#loader");
  const textEl = $("#loaderText");
  const pctEl = $("#loaderPct");
  const barFill = $("#loaderBarFill");
  const bar = $("#loaderBar");
  const stepEl = $("#loaderStep");
  const ring = el.querySelector(".loader-ring");
  const ringFill = el.querySelector(".loader-ring-fill");

  if (_loaderInterval) { clearInterval(_loaderInterval); _loaderInterval = null; }

  if (!on) {
    _loaderProgress = 0;
    el.hidden = true;
    return;
  }

  el.hidden = false;
  textEl.textContent = text;
  stepEl.textContent = "";
  _loaderProgress = 0;

  if (steps && steps.length) {
    ring.classList.remove("indeterminate");
    bar.classList.remove("indeterminate");
    ringFill.style.strokeDashoffset = "126";
    barFill.style.width = "0%";
    const totalDuration = steps.reduce((s, st) => s + st.duration, 0);
    let elapsed = 0;
    let stepIdx = 0;

    const update = () => {
      elapsed += 100;
      let cumulative = 0;
      for (let i = 0; i < steps.length; i++) {
        cumulative += steps[i].duration;
        if (elapsed <= cumulative) { stepIdx = i; break; }
        if (i === steps.length - 1) stepIdx = i;
      }
      _loaderProgress = Math.min(95, Math.round((elapsed / totalDuration) * 95));
      const dashoffset = 126 - (126 * _loaderProgress / 100);
      ringFill.style.strokeDashoffset = dashoffset;
      pctEl.textContent = _loaderProgress + "%";
      barFill.style.width = _loaderProgress + "%";
      stepEl.textContent = steps[stepIdx]?.label || "";
      if (_loaderProgress >= 95) clearInterval(_loaderInterval);
    };
    update();
    _loaderInterval = setInterval(update, 100);
  } else {
    ring.classList.add("indeterminate");
    bar.classList.add("indeterminate");
    pctEl.textContent = "";
    barFill.style.width = "";
    ringFill.style.strokeDashoffset = "";
    stepEl.textContent = "";
  }
}

function loaderDone() {
  const el = $("#loader");
  const pctEl = $("#loaderPct");
  const barFill = $("#loaderBarFill");
  const bar = $("#loaderBar");
  const stepEl = $("#loaderStep");
  const ring = el.querySelector(".loader-ring");
  const ringFill = el.querySelector(".loader-ring-fill");
  if (_loaderInterval) { clearInterval(_loaderInterval); _loaderInterval = null; }
  ring.classList.remove("indeterminate");
  bar.classList.remove("indeterminate");
  pctEl.textContent = "100%";
  barFill.style.width = "100%";
  ringFill.style.strokeDashoffset = "0";
  stepEl.textContent = "Terminé";
  setTimeout(() => loader(false), 600);
}
const mediaUrl = (p) => (p ? `/static/${p.replace(/^static\//, "")}` : "");

function styleFileInputs(root = document) {
  root.querySelectorAll('input[type="file"]:not([data-styled])').forEach((input) => {
    if (input.hidden || input.closest(".file-input-wrap") || input.closest(".product-actions")) return;
    input.setAttribute("data-styled", "1");
    const wrap = document.createElement("div");
    wrap.className = "file-input-wrap";
    const label = input.accept?.includes("pdf")
      ? "Importer un PDF" : input.multiple ? "Choisir des fichiers" : "Choisir un fichier";
    const icon = input.accept?.includes("pdf")
      ? '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
      : '<svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>';
    const btn = document.createElement("div");
    btn.className = "file-input-btn";
    btn.innerHTML = `${icon}<span>${label}</span>`;
    const nameSpan = document.createElement("span");
    nameSpan.className = "file-input-name";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(btn);
    wrap.appendChild(nameSpan);
    input.addEventListener("change", () => {
      const files = input.files;
      if (files.length === 1) nameSpan.textContent = files[0].name;
      else if (files.length > 1) nameSpan.textContent = `${files.length} fichiers`;
      else nameSpan.textContent = "";
    });
  });
}

// ---- Lightbox (vue plein écran) ----
function openLightbox(src, contentId) {
  const lb = document.createElement("div");
  lb.className = "lightbox";
  lb.innerHTML = `
    <button class="lb-close">✕</button>
    <img src="${src}">
    <div class="lb-actions">
      <button data-act="download">Télécharger</button>
      ${contentId ? `<button data-act="upscale">Upscale HD</button>` : ""}
    </div>`;
  lb.onclick = (e) => { if (e.target === lb) lb.remove(); };
  lb.querySelector(".lb-close").onclick = () => lb.remove();
  lb.querySelector('[data-act="download"]').onclick = (e) => {
    e.stopPropagation();
    const a = document.createElement("a"); a.href = src; a.download = src.split("/").pop(); a.click();
  };
  const upBtn = lb.querySelector('[data-act="upscale"]');
  if (upBtn) upBtn.onclick = async (e) => {
    e.stopPropagation();
    lb.remove();
    await upscaleContent(contentId);
  };
  document.addEventListener("keydown", function esc(e) {
    if (e.key === "Escape") { lb.remove(); document.removeEventListener("keydown", esc); }
  });
  document.body.appendChild(lb);
}

async function upscaleContent(contentId) {
  loader(true, "Upscale HD", [
    { label: "Envoi de la demande...", duration: 2000 },
    { label: "Génération haute qualité...", duration: 15000 },
    { label: "Composition finale...", duration: 5000 },
  ]);
  try {
    await postJSON(`/api/content/${contentId}/render`, { use_ai_image: true, quality: "hd" });
    loaderDone();
    toast("Image upscalée en HD", "ok");
    render();
  } catch (e) { toast(e.message, "error"); loader(false); }
}

// ---- Drawer ----
const drawer = $("#drawer");
const drawerOverlay = $("#drawerOverlay");

function openDrawer() {
  const b = state.currentBrand;
  const avatar = $("#drawerAvatar");
  const nameEl = $("#drawerBrandName");
  const urlEl = $("#drawerBrandUrl");
  if (b) {
    const initial = b.name.charAt(0).toUpperCase();
    const drawerLogo = getDarkLogo(b);
    avatar.textContent = drawerLogo ? "" : initial;
    avatar.style.backgroundImage = drawerLogo ? `url(${mediaUrl(drawerLogo)})` : "";
    avatar.classList.toggle("has-logo", !!drawerLogo);
    nameEl.textContent = b.name;
    urlEl.textContent = b.website_url || "";
  }
  const nav = $("#drawerNav");
  nav.innerHTML = `
    <button class="drawer-item" data-drawer="brands">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
      Identité de marque
    </button>
    <button class="drawer-item" data-drawer="products">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
      Produits
    </button>
    <div class="drawer-sep"></div>
    <button class="drawer-item" data-drawer="home">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
      Accueil
    </button>
    <button class="drawer-item" data-drawer="generate">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
      Créer du contenu
    </button>
    <button class="drawer-item" data-drawer="schedule">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      Planning
    </button>
    <div class="drawer-sep"></div>
    <button class="drawer-item" data-drawer="instagram">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
      Instagram
    </button>
    <div class="drawer-sep"></div>
    <button class="drawer-item drawer-logout" data-drawer="logout">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      Déconnexion
    </button>`;
  nav.querySelectorAll(".drawer-item").forEach(item => {
    item.classList.toggle("active", item.dataset.drawer === state.tab);
    item.onclick = () => {
      closeDrawer();
      if (item.dataset.drawer === "logout") { logout(); return; }
      switchTab(item.dataset.drawer);
    };
  });
  drawerOverlay.hidden = false;
  drawer.hidden = false;
  requestAnimationFrame(() => drawer.classList.add("open"));
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawerOverlay.hidden = true;
  setTimeout(() => { drawer.hidden = true; }, 250);
}

// ---- Handle / Account switcher ----
function getDarkLogo(b) {
  if (!b) return null;
  const logos = b.logos || [];
  const dark = logos.find(l => typeof l === "object" && (l.variant || "").includes("dark"));
  if (dark) return dark.path;
  return b.logo_path || null;
}

function updateHandle() {
  const b = state.currentBrand;
  const avatar = $("#handleAvatar");
  const name = $("#handleName");
  if (!b) {
    avatar.textContent = "";
    avatar.style.backgroundImage = "";
    name.textContent = "Insta Post Auto";
    return;
  }
  const darkLogo = getDarkLogo(b);
  if (darkLogo) {
    avatar.textContent = "";
    avatar.style.backgroundImage = `url(${mediaUrl(darkLogo)})`;
    avatar.classList.add("has-logo");
  } else {
    avatar.textContent = b.name.charAt(0).toUpperCase();
    avatar.style.backgroundImage = "";
    avatar.classList.remove("has-logo");
  }
  name.textContent = "@" + b.name.toLowerCase().replace(/\s+/g, "-");
}

function toggleAccountDropdown() {
  const dd = $("#accountDropdown");
  const ov = $("#accountOverlay");
  const btn = $("#handleBtn");
  const isOpen = !dd.hidden;
  if (isOpen) {
    dd.hidden = true; ov.hidden = true;
    btn.classList.remove("open");
    return;
  }
  const list = $("#accountList");
  list.innerHTML = state.brands.map(b => {
    const isCurrent = state.currentBrand && b.id === state.currentBrand.id;
    const initial = b.name.charAt(0).toUpperCase();
    const ddLogo = getDarkLogo(b);
    const avatarStyle = ddLogo ? `background-image:url(${mediaUrl(ddLogo)});background-color:#fff;background-size:contain;background-repeat:no-repeat;background-position:center;padding:3px` : "";
    return `<button class="account-item${isCurrent ? " active" : ""}" data-brand-id="${b.id}">
      <div class="account-item-avatar" style="${avatarStyle}">${ddLogo ? "" : initial}</div>
      <div class="account-item-info">
        <span class="account-item-name">${esc(b.name)}</span>
        <span class="account-item-url">${esc(b.website_url || "")}</span>
      </div>
      ${isCurrent ? `<div class="account-item-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg></div>` : ""}
    </button>`;
  }).join("");
  list.querySelectorAll(".account-item").forEach(item => {
    item.onclick = () => {
      const bid = parseInt(item.dataset.brandId);
      state.currentBrand = state.brands.find(b => b.id === bid) || null;
      updateHandle();
      toggleAccountDropdown();
      render();
    };
  });
  dd.hidden = false; ov.hidden = false;
  btn.classList.add("open");
}

function closeAccountDropdown() {
  $("#accountDropdown").hidden = true;
  $("#accountOverlay").hidden = true;
  $("#handleBtn").classList.remove("open");
}

function updateUserAvatar() {
  const el = $("#userAvatar");
  if (!el || !currentUser) return;
  if (currentUser.picture_url) {
    el.style.backgroundImage = `url(${currentUser.picture_url})`;
    el.textContent = "";
  } else {
    el.textContent = (currentUser.name || "U").charAt(0).toUpperCase();
  }
}

function renderLanding() {
  document.querySelector(".topbar").hidden = true;
  document.querySelector(".tabbar").hidden = true;
  view.innerHTML = `
    <div class="landing">
      <div class="landing-hero">
        <div class="landing-logo">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="url(#igGrad)" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
            <defs><linearGradient id="igGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#833ab4"/><stop offset="50%" stop-color="#fd1d1d"/><stop offset="100%" stop-color="#fcb045"/></linearGradient></defs>
            <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="url(#igGrad)" stroke="none"/>
          </svg>
        </div>
        <h1 class="landing-title">Insta Post Auto</h1>
        <p class="landing-sub">Crée et planifie du contenu Instagram automatiquement pour ta marque, propulsé par l'IA.</p>
      </div>

      <div class="landing-features">
        <div class="landing-feat">
          <div class="landing-feat-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          </div>
          <div>
            <div class="landing-feat-title">Hooks IA qui convertissent</div>
            <div class="landing-feat-desc">Génère des dizaines de hooks percutants avec différents angles d'attaque.</div>
          </div>
        </div>
        <div class="landing-feat">
          <div class="landing-feat-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
          </div>
          <div>
            <div class="landing-feat-title">Visuels générés par IA</div>
            <div class="landing-feat-desc">Images uniques générées automatiquement, aux couleurs de ta marque.</div>
          </div>
        </div>
        <div class="landing-feat">
          <div class="landing-feat-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <div>
            <div class="landing-feat-title">Planification automatique</div>
            <div class="landing-feat-desc">Programme tes publications à l'avance et publie automatiquement sur Instagram.</div>
          </div>
        </div>
      </div>

      <button class="btn-ig landing-cta" id="landingLogin">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
        Se connecter avec Instagram
      </button>

      <p class="landing-footer">Gratuit. Propulsé par l'intelligence artificielle.</p>
    </div>`;

  $("#landingLogin").onclick = async () => {
    try {
      const { url } = await getJSON("/api/auth/login-url");
      const popup = window.open(url, "auth_login", "width=600,height=700,scrollbars=yes");
      window.addEventListener("message", async function onMsg(e) {
        if (e.data && e.data.authSuccess !== undefined) {
          window.removeEventListener("message", onMsg);
          if (e.data.authSuccess) {
            window.location.reload();
          } else {
            toast("Connexion échouée", "error");
          }
        }
      });
      const checkPopup = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(checkPopup);
          setTimeout(() => window.location.reload(), 500);
        }
      }, 1000);
    } catch (e) { toast(e.message, "error"); }
  };
}

async function logout() {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch {}
  currentUser = null;
  window.location.reload();
}

// ---- bootstrap ----
async function init() {
  try {
    currentUser = await getJSON("/api/auth/me");
  } catch {
    currentUser = null;
  }

  if (!currentUser) {
    renderLanding();
    return;
  }

  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );
  $("#handleBtn").addEventListener("click", toggleAccountDropdown);
  $("#accountOverlay").addEventListener("click", closeAccountDropdown);
  $("#accountAdd").addEventListener("click", () => {
    closeAccountDropdown();
    switchTab("onboarding");
  });
  $("#newContentBtn").addEventListener("click", () => smartNavigate());
  $("#menuBtn").addEventListener("click", () => {
    if (!state.currentBrand) return;
    if (drawer.classList.contains("open")) closeDrawer();
    else openDrawer();
  });
  $("#drawerClose").addEventListener("click", closeDrawer);
  drawerOverlay.addEventListener("click", closeDrawer);
  await loadBrands();
  if (!state.currentBrand) {
    state.tab = "onboarding";
  }
  updateUserAvatar();
  render();
}

async function smartNavigate() {
  if (!state.currentBrand) {
    switchTab("onboarding");
  } else {
    const products = await getJSON(`/api/products?brand_id=${state.currentBrand.id}`);
    if (!products.length) {
      productView = "add";
      switchTab("products");
    } else {
      switchTab("generate");
    }
  }
}

async function loadBrands() {
  state.brands = await getJSON("/api/brands");
  if (state.brands.length) {
    const match = state.currentBrand && state.brands.find((b) => b.id === state.currentBrand.id);
    state.currentBrand = match || state.brands[0];
  } else {
    state.currentBrand = null;
  }
  updateHandle();
}

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  render();
}

async function render() {
  const map = {
    onboarding: renderOnboarding,
    home: renderHome,
    brands: renderBrands, products: renderProducts, generate: renderGenerate,
    library: renderLibrary, schedule: renderSchedule,
    instagram: renderInstagram,
  };
  await (map[state.tab] || renderHome)();
  requestAnimationFrame(() => styleFileInputs(view));
}

// ---- Onboarding (first launch) ----
function renderOnboarding() {
  document.querySelector(".tabbar").hidden = true;
  document.querySelector(".topbar-actions").hidden = true;
  view.innerHTML = `
    <div class="onboarding">
      <div class="onboarding-icon">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
      </div>
      <h1 class="onboarding-title">Insta Post Auto</h1>
      <p class="onboarding-sub">Crée et planifie du contenu Instagram automatiquement pour ta marque.</p>
      <div class="card" style="text-align:left">
        <label>Nom de la marque</label>
        <input id="obName" placeholder="Ex : MedSkin Precision" autofocus>
        <label>Site web</label>
        <input id="obWeb" type="url" placeholder="https://www.monsite.com">
        <label>Brand guidelines (PDF)</label>
        <input type="file" id="obPdf" accept="application/pdf">
        <button class="btn-primary" id="obStart" style="margin-top:16px;width:100%">Commencer</button>
      </div>
    </div>`;
  $("#obStart").onclick = async () => {
    const name = $("#obName").value.trim();
    if (!name) return toast("Donne un nom à ta marque", "error");
    const fd = new FormData();
    fd.append("name", name);
    const web = $("#obWeb").value.trim();
    if (web) fd.append("website_url", web);
    const pdf = $("#obPdf")?.files[0];
    if (pdf) fd.append("pdf", pdf);
    if (pdf) {
      loader(true, "Création de ta marque", [
        { label: "Envoi du PDF...", duration: 2000 },
        { label: "Extraction du texte...", duration: 3000 },
        { label: "Analyse IA de l'identité...", duration: 8000 },
        { label: "Finalisation...", duration: 2000 },
      ]);
    } else {
      loader(true, "Création de ta marque...");
    }
    try {
      await postForm("/api/brands/setup", fd);
      loaderDone();
      await loadBrands();
      document.querySelector(".tabbar").hidden = false;
      document.querySelector(".topbar-actions").hidden = false;
      toast("Bienvenue ! Ta marque est prête.", "ok");
      switchTab("home");
    } catch (e) { toast(e.message, "error"); loader(false); }
  };
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// =====================================================================
//  HOME (Instagram profile grid)
// =====================================================================
async function renderHome() {
  if (!state.currentBrand) return renderOnboarding();
  const b = state.currentBrand;
  let igStatus;
  try {
    igStatus = await getJSON(`/api/instagram/status?brand_id=${b.id}`);
  } catch { igStatus = { connected: false }; }

  const [items, products] = await Promise.all([
    getJSON(`/api/content?brand_id=${b.id}`),
    getJSON(`/api/products?brand_id=${b.id}`),
  ]);
  state.products = products;
  const ready = items.filter(it => ["approved", "scheduled", "published"].includes(it.status));
  const drafts = items.filter(it => it.status === "draft");
  const allWithImages = items.filter(it => (it.image_paths || []).length > 0);

  if (!items.length && !products.length) {
    view.innerHTML = `
      <div class="home-empty">
        <div class="home-empty-icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
        </div>
        <div class="home-empty-title">Commence par ajouter un produit</div>
        <div class="home-empty-sub">Ajoute tes produits puis crée du contenu Instagram automatiquement.</div>
        <button class="btn-primary" id="homeAddProduct">Ajouter un produit</button>
      </div>`;
    $("#homeAddProduct").onclick = () => { productView = "add"; switchTab("products"); };
    return;
  }

  if (!items.length && products.length) {
    view.innerHTML = `
      <div class="home-empty">
        <div class="home-empty-icon-btn" id="homeCreate">
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
        </div>
        <div class="home-empty-title">Crée ton premier contenu</div>
        <div class="home-empty-sub">${products.length} produit(s) prêt(s). Génère des hooks et visuels Instagram.</div>
      </div>`;
    $("#homeCreate").onclick = () => switchTab("generate");
    return;
  }

  const gridItems = allWithImages.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const igBannerHTML = igStatus.connected
    ? `<div class="ig-status-bar connected" id="igStatusBar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/></svg>
        <span>Publie sur <b>@${esc(igStatus.username)}</b></span>
      </div>`
    : `<div class="ig-status-bar disconnected" id="igStatusBar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--orange)" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/></svg>
        <span>Instagram non connecté</span>
        <button class="ig-status-btn" id="igConnectHome">Connecter</button>
      </div>`;

  view.innerHTML = `
    ${igBannerHTML}
    <div class="home-stats">
      <div class="home-stat"><span class="home-stat-num">${items.length}</span><span class="home-stat-label">contenus</span></div>
      <div class="home-stat"><span class="home-stat-num">${products.length}</span><span class="home-stat-label">produits</span></div>
      <div class="home-stat"><span class="home-stat-num">${ready.length}</span><span class="home-stat-label">prêts</span></div>
    </div>
    ${drafts.length ? `<div style="padding:8px 16px"><span class="pill" style="background:var(--surface-2)">${drafts.length} brouillon(s) en attente</span></div>` : ""}
    ${gridItems.length ? `
      <div class="home-grid">
        ${gridItems.map(it => {
          const img = it.image_paths[0];
          const isCarousel = it.format === "carousel" && it.image_paths.length > 1;
          return `<div class="home-cell" data-cid="${it.id}">
            <img src="${mediaUrl(img)}" loading="lazy">
            <button class="home-cell-del" data-del-cid="${it.id}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
            ${isCarousel ? `<div class="home-cell-badge">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="#fff" stroke="none"><rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/></svg>
            </div>` : ""}
          </div>`;
        }).join("")}
      </div>` : `
      <div class="home-empty" style="padding:30px 20px">
        <div class="home-empty-sub">Tes contenus n'ont pas encore de visuels. Génère les images depuis la bibliothèque.</div>
        <button class="btn-ghost" id="homeLib">Voir les brouillons</button>
      </div>`}`;

  view.querySelectorAll(".home-cell").forEach(cell => {
    cell.onclick = (e) => {
      if (e.target.closest(".home-cell-del")) return;
      const img = cell.querySelector("img");
      if (img) openLightbox(img.src, parseInt(cell.dataset.cid));
    };
  });
  view.querySelectorAll(".home-cell-del").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      if (!(await confirmModal("Supprimer ce contenu ?"))) return;
      loader(true, "Suppression…");
      try {
        await del(`/api/content/${btn.dataset.delCid}`);
        toast("Supprimé", "ok");
        render();
      } catch (err) { toast(err.message, "error"); } finally { loader(false); }
    };
  });
  const libBtn = $("#homeLib");
  if (libBtn) libBtn.onclick = () => { libSubTab = "drafts"; switchTab("library"); };
  const igConnBtn = $("#igConnectHome");
  if (igConnBtn) igConnBtn.onclick = () => switchTab("instagram");
}

// =====================================================================
//  MARQUE
// =====================================================================
function renderBrands() {
  const b = state.currentBrand;
  if (b) {
    renderBrandProfile(b);
  } else {
    renderBrandSetup();
  }
}

function renderBrandSetup() {
  view.innerHTML = `
    <h2 class="section-title">Nouvelle marque</h2>
    <div class="card">
      <label>Nom de la marque</label>
      <input id="bName" placeholder="Ex : MedSkin Precision" />
      <label>Site web</label>
      <input id="bWeb" type="url" placeholder="https://www.monsite.com" />
    </div>
    <div class="card">
      <h3 style="margin-top:0">Brand guidelines (PDF)</h3>
      <p class="muted">Importe ta charte graphique. L'IA analyse le PDF et extrait :
        <b>couleurs</b>, <b>polices</b>, <b>ton de voix</b>, <b>audience cible</b> et <b>hashtags</b>.</p>
      <input type="file" id="pdfInput" accept="application/pdf">
    </div>
    <button class="btn-primary" id="setupBrand" style="margin-top:4px">Créer la marque</button>
  `;
  $("#setupBrand").onclick = setupBrand;
}

function renderBrandProfile(b) {
  const logoEntries = (b.logos || []).map((l, i) => {
    const isObj = typeof l === "object";
    const path = isObj ? l.path : l;
    const label = isObj ? (l.label || "") : "";
    const variant = isObj ? (l.variant || "") : "";
    const isPrimary = path === b.logo_path;
    const bgClass = variant.includes("light") ? "bg-dark" : "bg-light";
    return `<div class="bi-logo-item${isPrimary ? " primary" : ""}" data-logo-path="${esc(path)}" data-logo-idx="${i}">
      <div class="bi-logo-preview ${bgClass}">
        <img src="${mediaUrl(path)}">
      </div>
      <div class="bi-logo-meta">
        <span>${esc(label || "Logo " + (i + 1))}</span>
        ${isPrimary ? `<span class="bi-logo-badge">Principal</span>` : ""}
      </div>
      <button class="bi-logo-del" data-del-logo="${i}">✕</button>
    </div>`;
  }).join("");

  const langs = b.languages || ["fr"];
  const langTags = langs.map(l => `<span class="bi-tag">${LANG_LABELS[l] || l}</span>`).join("");

  const toneWords = (b.tone_of_voice || "").split(",").map(w => w.trim()).filter(Boolean);
  const toneTags = toneWords.map(w => `<span class="bi-tag">${esc(w)}</span>`).join("");

  const hashArr = (b.default_hashtags || "").split(/\s+/).filter(Boolean);
  const hashTags = hashArr.map(h => `<span class="bi-hashtag">${esc(h)}</span>`).join("");

  view.innerHTML = `
    <div class="bi-header">
      <div class="bi-avatar-wrap">
        ${getDarkLogo(b)
          ? `<img src="${mediaUrl(getDarkLogo(b))}" class="bi-avatar-img">`
          : `<div class="bi-avatar-letter">${b.name.charAt(0).toUpperCase()}</div>`}
      </div>
      <div class="bi-header-info">
        <h1 class="bi-name">${esc(b.name)}</h1>
        ${b.website_url ? `<a class="bi-url" href="${esc(b.website_url)}" target="_blank">${esc(b.website_url.replace(/^https?:\/\//, ""))}</a>` : ""}
        <div class="bi-lang-row">${langTags}</div>
      </div>
    </div>

    <!-- Logos — affichés en premier pour visibilité -->
    <div class="bi-section">
      <div class="bi-section-label">Logos</div>
      ${logoEntries ? `<div class="bi-logo-grid" id="logoGrid">${logoEntries}</div>` : `<p class="muted" style="font-size:.8125rem">Aucun logo importé</p>`}
      <div class="bi-upload-zone" style="margin-top:12px">
        <select id="logoVariant" class="bi-input-subtle" style="margin-bottom:8px">
          <option value="primary-light">Logo clair (pour fond foncé)</option>
          <option value="primary-dark">Logo foncé (pour fond clair)</option>
          <option value="secondary-light">Secondaire clair (fond foncé)</option>
          <option value="secondary-dark">Secondaire foncé (fond clair)</option>
          <option value="icon">Icône / Favicon</option>
          <option value="monochrome">Monochrome</option>
        </select>
        <input type="file" id="logoInput" accept="image/png,image/svg+xml,image/jpeg,image/webp,image/*" multiple>
      </div>
    </div>

    <!-- Couleurs -->
    <div class="bi-section">
      <div class="bi-section-label">Palette de couleurs</div>
      <div class="bi-colors">
        <div class="bi-color-card">
          <div class="bi-color-swatch" style="background:${b.primary_color || "#111111"}"></div>
          <div class="bi-color-info">
            <span class="bi-color-name">Primaire</span>
            <span class="bi-color-hex">${(b.primary_color || "#111111").toUpperCase()}</span>
          </div>
          <input type="color" id="cPrim" value="${b.primary_color || "#111111"}" class="bi-color-input">
        </div>
        <div class="bi-color-card">
          <div class="bi-color-swatch" style="background:${b.secondary_color || "#ffffff"}"></div>
          <div class="bi-color-info">
            <span class="bi-color-name">Secondaire</span>
            <span class="bi-color-hex">${(b.secondary_color || "#ffffff").toUpperCase()}</span>
          </div>
          <input type="color" id="cSec" value="${b.secondary_color || "#ffffff"}" class="bi-color-input">
        </div>
        <div class="bi-color-card">
          <div class="bi-color-swatch" style="background:${b.accent_color || "#ff4d6d"}"></div>
          <div class="bi-color-info">
            <span class="bi-color-name">Accent</span>
            <span class="bi-color-hex">${(b.accent_color || "#ff4d6d").toUpperCase()}</span>
          </div>
          <input type="color" id="cAcc" value="${b.accent_color || "#ff4d6d"}" class="bi-color-input">
        </div>
      </div>
    </div>

    <!-- Typographie -->
    <div class="bi-section">
      <div class="bi-section-label">Typographie</div>
      <div class="bi-typo-row">
        <div class="bi-typo-edit">
          <input id="bFont" value="${esc(b.font_family || "")}" placeholder="Police titres" class="bi-input-subtle">
        </div>
      </div>
      ${fontPreviewHTML(b.font_family, "Titres")}
      ${b.font_body && b.font_body !== b.font_family ? `
        <div class="bi-typo-row" style="margin-top:8px">
          <div class="bi-typo-edit">
            <input id="bFontBody" value="${esc(b.font_body || "")}" placeholder="Police corps" class="bi-input-subtle">
          </div>
        </div>
        ${fontPreviewHTML(b.font_body, "Corps")}
      ` : `<div class="bi-typo-row" style="margin-top:8px"><div class="bi-typo-edit"><input id="bFontBody" value="${esc(b.font_body || "")}" placeholder="Police corps (si différente)" class="bi-input-subtle"></div></div>`}
    </div>

    <!-- Ton & audience -->
    <div class="bi-section">
      <div class="bi-section-label">Ton de voix</div>
      <div class="bi-tags-row">${toneTags || `<span class="muted" style="font-size:.8125rem">Non défini</span>`}</div>
      <input id="bTone" value="${esc(b.tone_of_voice || "")}" placeholder="Ex : expert, rassurant, premium" class="bi-input-subtle" style="margin-top:8px">
    </div>

    <div class="bi-section">
      <div class="bi-section-label">Audience cible</div>
      <p class="bi-audience-text">${esc(b.target_audience || "Non définie")}</p>
      <input id="bAud" value="${esc(b.target_audience || "")}" placeholder="Ex : femmes 30-50, soin de la peau" class="bi-input-subtle">
    </div>

    <div class="bi-section">
      <div class="bi-section-label">Hashtags</div>
      <div class="bi-hashtags-wrap">${hashTags || `<span class="muted" style="font-size:.8125rem">Aucun</span>`}</div>
      <input id="bTags" value="${esc(b.default_hashtags || "")}" placeholder="#skincare #beauty" class="bi-input-subtle" style="margin-top:8px">
    </div>

    <!-- Site web -->
    <div class="bi-section">
      <div class="bi-section-label">Site web</div>
      <input id="bWeb" type="url" value="${esc(b.website_url || "")}" placeholder="https://www.monsite.com" class="bi-input-subtle">
    </div>

    <button class="btn-primary" id="saveBrand" style="margin:16px 0;width:100%">Enregistrer les modifications</button>

    <!-- Brand image -->
    <div class="bi-section">
      <div class="bi-section-label">Image de marque</div>
      ${b.brand_image_path ? `<img src="${mediaUrl(b.brand_image_path)}" class="bi-brand-img">` : `<p class="muted" style="font-size:.8125rem">Aucune image</p>`}
      <input type="file" id="brandImgInput" accept="image/*" style="margin-top:8px">
    </div>

    <!-- PDF -->
    <div class="bi-section">
      <div class="bi-section-label">Brand guidelines (PDF)</div>
      <p class="muted" style="font-size:.8125rem;margin-bottom:8px">${b.guidelines_pdf_path ? "PDF importé. Ré-importe pour mettre à jour." : "Importe ta charte graphique — l'IA analyse tout automatiquement."}</p>
      <input type="file" id="pdfInput" accept="application/pdf">
    </div>

    ${b.guidelines ? `
    <div class="bi-section">
      <div class="bi-section-label">Guidelines extraites</div>
      <textarea id="bGuide" class="bi-textarea">${esc(b.guidelines)}</textarea>
      <button class="btn-ghost btn-sm" id="saveGuide" style="margin-top:8px">Sauver</button>
    </div>` : ""}

    <button class="btn-danger" id="delBrand" style="margin:10px 0 30px;width:100%">Supprimer cette marque</button>
  `;

  if (b.font_family) loadGFont(b.font_family);
  if (b.font_body) loadGFont(b.font_body);

  // Live color hex update
  ["cPrim", "cSec", "cAcc"].forEach(id => {
    const input = $(`#${id}`);
    if (input) input.oninput = () => {
      const card = input.closest(".bi-color-card");
      card.querySelector(".bi-color-swatch").style.background = input.value;
      card.querySelector(".bi-color-hex").textContent = input.value.toUpperCase();
    };
  });

  $("#saveBrand").onclick = updateBrand;
  $("#delBrand").onclick = deleteBrand;
  const saveGuideBtn = $("#saveGuide");
  if (saveGuideBtn) saveGuideBtn.onclick = async () => {
    await patchJSON(`/api/brands/${b.id}`, { guidelines: $("#bGuide").value });
    toast("Guidelines sauvées", "ok");
  };

  const pdfIn = $("#pdfInput");
  if (pdfIn) pdfIn.onchange = async (e) => {
    if (!e.target.files[0]) return;
    loader(true, "Analyse en cours", [
      { label: "Envoi du PDF...", duration: 2000 },
      { label: "Extraction du texte...", duration: 3000 },
      { label: "Analyse IA de l'identité...", duration: 8000 },
      { label: "Finalisation...", duration: 2000 },
    ]);
    try {
      const fd = new FormData();
      fd.append("name", b.name);
      fd.append("website_url", b.website_url || "");
      fd.append("pdf", e.target.files[0]);
      await postForm(`/api/brands/setup-update/${b.id}`, fd);
      loaderDone();
      await loadBrands();
      toast("Identité de marque mise à jour", "ok");
      render();
    } catch (err) { toast(err.message, "error"); loader(false); }
  };

  const logoIn = $("#logoInput");
  if (logoIn) logoIn.onchange = async (e) => {
    if (!e.target.files.length) return;
    const fd = new FormData();
    [...e.target.files].forEach((f) => fd.append("files", f));
    const variant = $("#logoVariant").value;
    const variantLabels = {
      "primary-light": "Logo clair (fond foncé)", "primary-dark": "Logo foncé (fond clair)",
      "secondary-light": "Secondaire clair", "secondary-dark": "Secondaire foncé",
      "icon": "Icône", "monochrome": "Monochrome",
    };
    fd.append("label", variantLabels[variant] || variant);
    fd.append("variant", variant);
    await uploadAsset(`/api/brands/${b.id}/logos`, fd, "Logo(s) ajouté(s)");
  };

  const imgIn = $("#brandImgInput");
  if (imgIn) imgIn.onchange = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    await uploadAsset(`/api/brands/${b.id}/brand-image`, fd, "Image enregistrée");
  };

  document.querySelectorAll("#logoGrid .bi-logo-item").forEach((card) => {
    card.onclick = async (e) => {
      if (e.target.closest(".bi-logo-del")) return;
      const path = card.dataset.logoPath;
      const fd = new FormData(); fd.append("path", path);
      await uploadAsset(`/api/brands/${b.id}/primary-logo`, fd, "Logo principal défini");
    };
  });
  document.querySelectorAll("#logoGrid .bi-logo-del").forEach((btn) => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      if (!(await confirmModal("Supprimer ce logo ?"))) return;
      loader(true, "Suppression…");
      try {
        await del(`/api/brands/${b.id}/logos/${btn.dataset.delLogo}`);
        await loadBrands(); toast("Logo supprimé", "ok"); render();
      } catch (err) { toast(err.message, "error"); } finally { loader(false); }
    };
  });
}

async function setupBrand() {
  const name = $("#bName").value.trim();
  if (!name) return toast("Donne un nom à la marque", "error");

  const fd = new FormData();
  fd.append("name", name);
  const web = $("#bWeb").value.trim();
  if (web) fd.append("website_url", web);
  const pdfFile = $("#pdfInput")?.files[0];
  if (pdfFile) fd.append("pdf", pdfFile);

  if (pdfFile) {
    loader(true, "Création de la marque", [
      { label: "Envoi du PDF...", duration: 2000 },
      { label: "Extraction du texte...", duration: 3000 },
      { label: "Analyse IA de l'identité...", duration: 8000 },
      { label: "Finalisation...", duration: 2000 },
    ]);
  } else {
    loader(true, "Création de la marque...");
  }
  try {
    await postForm("/api/brands/setup", fd);
    loaderDone();
    await loadBrands();
    toast("Marque créée", "ok");
    render();
  } catch (e) { toast(e.message, "error"); loader(false); }
}

async function updateBrand() {
  const b = state.currentBrand;
  if (!b) return;
  const payload = {
    primary_color: $("#cPrim").value, secondary_color: $("#cSec").value, accent_color: $("#cAcc").value,
    font_family: $("#bFont").value.trim(),
    font_body: $("#bFontBody").value.trim(),
    tone_of_voice: $("#bTone").value, target_audience: $("#bAud").value,
    default_hashtags: $("#bTags").value,
    website_url: $("#bWeb").value.trim() || null,
  };
  const guideEl = $("#bGuide");
  if (guideEl) payload.guidelines = guideEl.value;

  loader(true, "Enregistrement…");
  try {
    await patchJSON(`/api/brands/${b.id}`, payload);
    await loadBrands();
    toast("Modifications enregistrées", "ok");
    render();
  } catch (e) { toast(e.message, "error"); } finally { loader(false); }
}

async function deleteBrand() {
  if (!state.currentBrand) return;
  if (!(await confirmModal(`Supprimer la marque "${state.currentBrand.name}" et tout son contenu ?`))) return;
  loader(true, "Suppression…");
  try {
    await del(`/api/brands/${state.currentBrand.id}`);
    state.currentBrand = null;
    await loadBrands();
    toast("Marque supprimée", "ok");
    render();
  } catch (e) { toast(e.message, "error"); } finally { loader(false); }
}

async function uploadAsset(url, fd, okMsg) {
  loader(true, "Envoi…");
  try { await postForm(url, fd); await loadBrands(); toast(okMsg, "ok"); render(); }
  catch (e) { toast(e.message, "error"); } finally { loader(false); }
}

// =====================================================================
//  PRODUITS
// =====================================================================
let productView = "grid"; // "grid" | "detail" | "add"
let selectedProductId = null;

async function renderProducts() {
  if (!requireBrand()) return;
  const products = await getJSON(`/api/products?brand_id=${state.currentBrand.id}`);
  state.products = products;

  if (productView === "detail" && selectedProductId) {
    const p = products.find(x => x.id === selectedProductId);
    if (p) return renderProductDetail(p);
    productView = "grid";
  }
  if (productView === "add") return renderProductAdd();
  renderProductGrid(products);
}

function renderProductGrid(products) {
  view.innerHTML = `
    <div class="pg-header">
      <h2 class="section-title" style="margin:0">${esc(state.currentBrand.name)}</h2>
      <span class="muted">${products.length} produit(s)</span>
    </div>
    <div class="pg-grid">
      <div class="pg-tile pg-tile-add" id="pgAdd">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>Ajouter</span>
      </div>
      ${products.map(p => {
        const thumb = p.image_path ? mediaUrl(p.image_path)
          : ((p.images && p.images.length) ? mediaUrl(typeof p.images[0] === "string" ? p.images[0] : p.images[0].path) : "");
        const imgCount = (p.images || []).length;
        return `<div class="pg-tile" data-pid="${p.id}">
          ${thumb
            ? `<img src="${thumb}" alt="${esc(p.name)}">`
            : `<div class="pg-tile-empty"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg></div>`}
          <div class="pg-tile-info">
            <span class="pg-tile-name">${esc(p.name)}</span>
            ${imgCount > 1 ? `<span class="pg-tile-badge">${imgCount}</span>` : ""}
          </div>
        </div>`;
      }).join("")}
    </div>`;
  $("#pgAdd").onclick = () => { productView = "add"; render(); };
  view.querySelectorAll(".pg-tile[data-pid]").forEach(tile => {
    tile.onclick = () => { selectedProductId = parseInt(tile.dataset.pid); productView = "detail"; render(); };
  });
}

function renderProductDetail(p) {
  const images = (p.images || []).map(img => typeof img === "string" ? { path: img, label: "" } : img);
  const mainImg = p.image_path || (images.length ? images[0].path : "");
  const dims = [];
  if (p.width_mm) dims.push(`L ${p.width_mm}`);
  if (p.height_mm) dims.push(`H ${p.height_mm}`);
  if (p.depth_mm) dims.push(`P ${p.depth_mm}`);
  const dimStr = dims.length ? dims.join(" × ") + " mm" : "";

  view.innerHTML = `
    <div class="pd-back" id="pdBack">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      Produits
    </div>
    <div class="pd-hero">
      ${mainImg
        ? `<img src="${mediaUrl(mainImg)}" class="pd-hero-img" id="pdMainImg">`
        : `<div class="pd-hero-empty">Pas de photo</div>`}
    </div>
    ${images.length > 1 ? `
      <div class="pd-thumbs">
        ${images.map((img, i) => `
          <div class="pd-thumb${img.path === mainImg ? " active" : ""}" data-idx="${i}" data-path="${esc(img.path)}">
            <img src="${mediaUrl(img.path)}">
            <button class="pd-thumb-del" data-idx="${i}" title="Supprimer">✕</button>
          </div>`).join("")}
      </div>` : ""}
    <div class="pd-info">
      <h2 class="pd-name">${esc(p.name)}</h2>
      ${dimStr ? `<span class="pill" style="margin-bottom:8px">${dimStr}</span>` : ""}
      ${p.descriptions && Object.keys(p.descriptions).length > 1 ? `
        <div class="pd-lang-tabs" id="pdLangTabs">
          ${Object.keys(p.descriptions).map((lang, i) =>
            `<button class="pd-lang-tab${i === 0 ? " active" : ""}" data-lang="${lang}">${LANG_LABELS[lang] || lang}</button>`
          ).join("")}
        </div>
        <p class="pd-desc" id="pdDesc">${esc(Object.values(p.descriptions)[0] || p.description || "Aucune description")}</p>
      ` : `<p class="pd-desc">${esc(p.description || "Aucune description")}</p>`}
    </div>
    <div class="pd-actions">
      <label class="pd-action-btn" style="cursor:pointer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/><line x1="16" y1="3" x2="16" y2="10"/><line x1="12.5" y1="6.5" x2="19.5" y2="6.5"/></svg>
        <span>+ Photos</span>
        <input type="file" accept="image/*" multiple id="pdUpload" hidden>
      </label>
      <button class="pd-action-btn" id="pdEdit">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        <span>Modifier</span>
      </button>
      <button class="pd-action-btn pd-action-del" id="pdDel">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        <span>Supprimer</span>
      </button>
    </div>
    <div id="pdEditForm" hidden></div>`;

  $("#pdBack").onclick = () => { productView = "grid"; selectedProductId = null; render(); };

  if (p.descriptions && Object.keys(p.descriptions).length > 1) {
    view.querySelectorAll(".pd-lang-tab").forEach(tab => {
      tab.onclick = () => {
        view.querySelectorAll(".pd-lang-tab").forEach(t => t.classList.toggle("active", t === tab));
        const descEl = $("#pdDesc");
        if (descEl) descEl.textContent = p.descriptions[tab.dataset.lang] || p.description || "";
      };
    });
  }

  if ($("#pdMainImg")) {
    $("#pdMainImg").onclick = () => openLightbox(mediaUrl(mainImg));
  }

  view.querySelectorAll(".pd-thumb").forEach(thumb => {
    thumb.onclick = (e) => {
      if (e.target.closest(".pd-thumb-del")) return;
      const path = thumb.dataset.path;
      const mainEl = $("#pdMainImg");
      if (mainEl) mainEl.src = mediaUrl(path);
      view.querySelectorAll(".pd-thumb").forEach(t => t.classList.toggle("active", t === thumb));
    };
  });

  view.querySelectorAll(".pd-thumb-del").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      if (!(await confirmModal("Supprimer cette photo ?"))) return;
      loader(true, "Suppression...");
      try { await del(`/api/products/${p.id}/images/${btn.dataset.idx}`); toast("Photo supprimée", "ok"); render(); }
      catch (err) { toast(err.message, "error"); } finally { loader(false); }
    };
  });

  $("#pdUpload").onchange = async (e) => {
    if (!e.target.files.length) return;
    const fd = new FormData();
    [...e.target.files].forEach(f => fd.append("files", f));
    fd.append("label", "");
    loader(true, "Upload des photos...");
    try { await postForm(`/api/products/${p.id}/images`, fd); toast("Photos ajoutées", "ok"); render(); }
    catch (err) { toast(err.message, "error"); } finally { loader(false); }
  };

  $("#pdEdit").onclick = () => {
    const form = $("#pdEditForm");
    form.hidden = !form.hidden;
    if (!form.hidden && !form.innerHTML) {
      form.innerHTML = `
        <div class="card" style="margin-top:12px">
          <label>Nom</label><input id="ePName" value="${esc(p.name)}">
          <label>Description</label><textarea id="ePDesc" style="min-height:80px">${esc(p.description || "")}</textarea>
          <div class="row">
            <div><label>Largeur (mm)</label><input id="ePW" type="number" value="${p.width_mm || ""}"></div>
            <div><label>Hauteur (mm)</label><input id="ePH" type="number" value="${p.height_mm || ""}"></div>
            <div><label>Prof. (mm)</label><input id="ePD" type="number" value="${p.depth_mm || ""}"></div>
          </div>
          <button class="btn-primary" id="ePSave" style="margin-top:10px">Enregistrer</button>
        </div>`;
      $("#ePSave").onclick = async () => {
        const fd = new FormData();
        fd.append("name", $("#ePName").value.trim());
        fd.append("description", $("#ePDesc").value);
        const w = $("#ePW").value, h = $("#ePH").value, d = $("#ePD").value;
        if (w) fd.append("width_mm", w);
        if (h) fd.append("height_mm", h);
        if (d) fd.append("depth_mm", d);
        loader(true, "Enregistrement...");
        try { await api(`/api/products/${p.id}`, { method: "PATCH", body: fd }); toast("Produit modifié", "ok"); render(); }
        catch (err) { toast(err.message, "error"); } finally { loader(false); }
      };
    }
  };

  $("#pdDel").onclick = async () => {
    if (!(await confirmModal(`Supprimer "${p.name}" ?`))) return;
    await del(`/api/products/${p.id}`);
    toast("Supprimé", "ok");
    productView = "grid"; selectedProductId = null; render();
  };
}

function renderProductAdd() {
  view.innerHTML = `
    <div class="pd-back" id="pdBackAdd">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      Produits
    </div>
    <h2 class="section-title">Ajouter un produit</h2>
    <div class="card">
      <div class="pa-url-section">
        <label>Lien de la page produit</label>
        <p class="muted" style="margin:4px 0 10px;font-size:.75rem">Colle le lien du produit sur le site de la marque. L'IA analyse la page et extrait tout automatiquement.</p>
        <input id="pUrl" type="url" placeholder="https://medskin-precision.ch/produit/..." style="margin-bottom:10px">
        <button class="btn-primary" id="pAnalyze" style="width:100%">Analyser avec l'IA</button>
      </div>
      <div class="pa-separator">
        <span>ou ajouter manuellement</span>
      </div>
      <label>Nom du produit</label><input id="pName" placeholder="Ex : HydraCare Pro, Sérum 30ml...">
      <label>Description</label><textarea id="pDesc" placeholder="Description du produit..." style="min-height:60px"></textarea>
      <div class="row">
        <div><label>Largeur (mm)</label><input id="pW" type="number" inputmode="decimal" placeholder="ex: 400"></div>
        <div><label>Hauteur (mm)</label><input id="pH" type="number" inputmode="decimal" placeholder="ex: 1200"></div>
        <div><label>Prof. (mm)</label><input id="pD" type="number" inputmode="decimal" placeholder="ex: 350"></div>
      </div>
      <label>Photo principale</label>
      <input type="file" id="pImg" accept="image/*">
      <button class="btn-ghost" id="addProduct" style="margin-top:14px;width:100%">Ajouter manuellement</button>
    </div>`;
  $("#pdBackAdd").onclick = () => { productView = "grid"; render(); };

  $("#pAnalyze").onclick = async () => {
    const url = $("#pUrl").value.trim();
    if (!url) return toast("Colle le lien de la page produit", "error");
    loader(true, "Analyse du produit", [
      { label: "Chargement de la page...", duration: 3000 },
      { label: "Extraction des informations...", duration: 6000 },
      { label: "Téléchargement des photos...", duration: 8000 },
      { label: "Création du produit...", duration: 2000 },
    ]);
    try {
      const fd = new FormData();
      fd.append("brand_id", state.currentBrand.id);
      fd.append("url", url);
      const product = await postForm("/api/products/from-url", fd);
      loaderDone();
      const imgCount = (product.images || []).length;
      toast(`${product.name} ajouté avec ${imgCount} photo(s)`, "ok");
      selectedProductId = product.id;
      productView = "detail";
      render();
    } catch (e) { toast(e.message, "error"); loader(false); }
  };

  $("#addProduct").onclick = async () => {
    if (!$("#pName").value.trim()) return toast("Nom requis", "error");
    const fd = new FormData();
    fd.append("brand_id", state.currentBrand.id);
    fd.append("name", $("#pName").value.trim());
    fd.append("description", $("#pDesc").value);
    if ($("#pW").value) fd.append("width_mm", $("#pW").value);
    if ($("#pH").value) fd.append("height_mm", $("#pH").value);
    if ($("#pD").value) fd.append("depth_mm", $("#pD").value);
    if ($("#pImg").files[0]) fd.append("file", $("#pImg").files[0]);
    loader(true, "Ajout du produit...");
    try { await postForm("/api/products", fd); toast("Produit ajouté", "ok"); productView = "grid"; render(); }
    catch (e) { toast(e.message, "error"); } finally { loader(false); }
  };
}

// =====================================================================
//  GÉNÉRER
// =====================================================================
async function renderGenerate() {
  if (!requireBrand()) return;
  state.products = await getJSON(`/api/products?brand_id=${state.currentBrand.id}`);
  const langs = state.currentBrand.languages || ["fr"];
  const langOptions = langs.map(l =>
    `<option value="${l}"${l === langs[0] ? " selected" : ""}>${LANG_LABELS[l] || l}</option>`
  ).join("");
  view.innerHTML = `
    <h2 class="section-title">Générer du contenu</h2>
    <div class="card">
      <p class="muted" style="margin-top:0">
        <b style="color:var(--text)">Étape 1</b> — génère d'abord les hooks qui convertissent
        (ex : « Tu perds chaque jour 1000 CHF… »). <b style="color:var(--text)">Étape 2</b> —
        depuis la bibliothèque, tu génères l'image à partir du hook choisi.
      </p>
      <div class="seg" id="fmtSeg">
        <button data-fmt="post" class="active">Post</button>
        <button data-fmt="carousel">Carousel</button>
        <button data-fmt="story">Story</button>
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
      ${langs.length > 1 ? `
      <label>Langue du contenu</label>
      <select id="gLang" class="lang-select">${langOptions}</select>
      ` : ""}
      <button class="btn-primary" id="genBtn" style="margin-top:16px">Générer les hooks qui convertissent</button>
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
  const langEl = $("#gLang");
  const body = {
    brand_id: state.currentBrand.id, prompt, format: fmt,
    variations: parseInt($("#gVar").value) || 10,
    language: langEl ? langEl.value : (state.currentBrand.languages?.[0] || "fr"),
    auto_compose: false,
    generate_images: false,
    product_id: $("#gProduct").value ? parseInt($("#gProduct").value) : null,
  };
  loader(true, "Génération en cours", [
    { label: "Analyse du brief...", duration: 2000 },
    { label: "Génération des hooks...", duration: 8000 },
    { label: "Rédaction des captions...", duration: 10000 },
    { label: "Finalisation...", duration: 3000 },
  ]);
  try {
    const items = await postJSON("/api/content/generate", body);
    loaderDone();
    toast(`${items.length} hooks générés — images en cours…`, "ok");
    switchTab("library");
    generateImagesBackground(items);
  } catch (e) { toast(e.message, "error"); loader(false); }
}

let _bgImageQueue = [];
let _bgImageRunning = false;

async function generateImagesBackground(items) {
  const toRender = items.filter(it => !it.image_paths || !it.image_paths.length);
  if (!toRender.length) return;
  _bgImageQueue.push(...toRender);
  if (_bgImageRunning) return;
  _bgImageRunning = true;
  let done = 0;
  const total = _bgImageQueue.length;
  toast(`Génération de ${total} images en arrière-plan…`, "ok");

  while (_bgImageQueue.length) {
    const it = _bgImageQueue.shift();
    try {
      const updated = await postJSON(`/api/content/${it.id}/render`, { use_ai_image: true });
      done++;
      toast(`Images : ${done}/${total}`, "ok");
      const card = $(`#c${it.id}`);
      if (card && updated.image_paths && updated.image_paths.length) {
        const thumbArea = card.querySelector(".thumb.placeholder, .thumb-wrap");
        if (thumbArea) {
          const parent = thumbArea.parentElement || card;
          const isStory = it.format === "story";
          const img = updated.image_paths[0];
          const newThumb = document.createElement("div");
          newThumb.className = "thumb-wrap";
          newThumb.dataset.src = mediaUrl(img);
          newThumb.dataset.cid = it.id;
          newThumb.innerHTML = `<img class="thumb ${isStory ? "story" : ""}" src="${mediaUrl(img)}">`;
          if (thumbArea.classList.contains("placeholder")) {
            thumbArea.replaceWith(newThumb);
          }
        }
      }
    } catch (e) {
      done++;
      console.warn(`Image gen failed for content ${it.id}:`, e.message);
    }
  }
  _bgImageRunning = false;
  toast(`${done} images générées`, "ok");
  if (state.tab === "library") render();
}

// =====================================================================
//  BIBLIOTHÈQUE (Brouillons + Prêts à poster)
// =====================================================================
let libSubTab = "drafts";

async function renderLibrary() {
  if (!requireBrand()) return;
  const items = await getJSON(`/api/content?brand_id=${state.currentBrand.id}`);

  const drafts = items.filter((it) => it.status === "draft");
  const ready = items.filter((it) => ["approved", "scheduled", "published"].includes(it.status));

  const draftCount = drafts.length;
  const readyCount = ready.length;

  view.innerHTML = `
    <h2 class="section-title">Bibliothèque</h2>
    <div class="seg lib-tabs" id="libTabs">
      <button data-sub="drafts" class="${libSubTab === "drafts" ? "active" : ""}">Brouillons <span class="muted">(${draftCount})</span></button>
      <button data-sub="ready" class="${libSubTab === "ready" ? "active" : ""}">Prêts <span class="muted">(${readyCount})</span></button>
    </div>
    <div id="libContent"></div>`;

  document.querySelectorAll("#libTabs button").forEach((btn) => {
    btn.onclick = () => {
      libSubTab = btn.dataset.sub;
      document.querySelectorAll("#libTabs button").forEach((b) => b.classList.toggle("active", b === btn));
      renderLibSubContent(libSubTab === "drafts" ? drafts : ready, libSubTab);
    };
  });

  renderLibSubContent(libSubTab === "drafts" ? drafts : ready, libSubTab);
}

let libSelected = new Set();

function renderLibSubContent(items, mode) {
  const container = $("#libContent");
  libSelected.clear();
  if (!items.length) {
    container.innerHTML = mode === "drafts"
      ? `<p class="empty">Aucun brouillon. Crée du contenu depuis l'onglet Créer.</p>`
      : `<p class="empty">Aucun contenu validé. Valide des brouillons pour les retrouver ici.</p>`;
    return;
  }
  container.innerHTML = `
    <div class="lib-toolbar" id="libToolbar">
      <button class="btn-ghost btn-sm" id="libSelectAll">Tout sélectionner</button>
      <button class="btn-danger btn-sm" id="libDelSelected" hidden>Supprimer la sélection</button>
    </div>
    <div class="grid">${items.map((it) => contentCard(it, mode)).join("")}</div>`;

  items.forEach((it) => bindContentCard(it));

  const selAllBtn = $("#libSelectAll");
  const delSelBtn = $("#libDelSelected");

  selAllBtn.onclick = () => {
    const allSelected = libSelected.size === items.length;
    libSelected.clear();
    if (!allSelected) items.forEach(it => libSelected.add(it.id));
    items.forEach(it => {
      const card = $(`#c${it.id}`);
      if (card) card.classList.toggle("selected", libSelected.has(it.id));
    });
    selAllBtn.textContent = libSelected.size === items.length ? "Tout désélectionner" : "Tout sélectionner";
    delSelBtn.hidden = libSelected.size === 0;
  };

  delSelBtn.onclick = async () => {
    if (!(await confirmModal(`Supprimer ${libSelected.size} contenu(s) ?`))) return;
    loader(true, "Suppression…");
    try {
      await Promise.all([...libSelected].map(id => del(`/api/content/${id}`)));
      toast(`${libSelected.size} contenus supprimés`, "ok");
      libSelected.clear();
      render();
    } catch (e) { toast(e.message, "error"); } finally { loader(false); }
  };
}

function toggleLibSelect(it) {
  if (libSelected.has(it.id)) libSelected.delete(it.id);
  else libSelected.add(it.id);
  const card = $(`#c${it.id}`);
  if (card) card.classList.toggle("selected", libSelected.has(it.id));
  const delSelBtn = $("#libDelSelected");
  const selAllBtn = $("#libSelectAll");
  if (delSelBtn) delSelBtn.hidden = libSelected.size === 0;
  if (selAllBtn) selAllBtn.textContent = libSelected.size > 0 ? `${libSelected.size} sélectionné(s)` : "Tout sélectionner";
}

function statusPill(s) {
  const labels = { draft: "Brouillon", approved: "Validé", scheduled: "Planifié", published: "Publié", failed: "Échec" };
  return `<span class="pill status-${s}">${labels[s] || s}</span>`;
}

function contentCard(it, mode) {
  const imgs = it.image_paths || [];
  const isStory = it.format === "story";
  const hasImg = imgs.length > 0;
  const thumbs = imgs.length > 1
    ? `<div class="thumbs-scroll">${imgs.map((p) => `<div class="thumb-wrap" data-src="${mediaUrl(p)}" data-cid="${it.id}"><img src="${mediaUrl(p)}"></div>`).join("")}</div>`
    : hasImg ? `<div class="thumb-wrap" data-src="${mediaUrl(imgs[0])}" data-cid="${it.id}"><img class="thumb ${isStory ? "story" : ""}" src="${mediaUrl(imgs[0])}"></div>`
    : `<div class="thumb placeholder"><span>Pas d'image</span></div>`;

  const isDraft = mode === "drafts";

  const actions = isDraft ? `
    <div class="toggle-row" style="margin-top:8px">
      <input type="checkbox" data-act="aiToggle" checked>
      <span>Image IA</span>
    </div>
    <div class="card-actions">
      <button class="btn-ghost btn-sm" data-act="edit">Éditer</button>
      <button class="${hasImg ? "btn-ghost" : "btn-primary"} btn-sm" data-act="render">${hasImg ? "Re-générer" : "Générer image"}</button>
      ${hasImg ? `<button class="btn-ok btn-sm" data-act="approve">Valider</button>` : ""}
      <button class="btn-danger btn-sm" data-act="del">Suppr.</button>
    </div>` : `
    <div class="card-actions">
      ${hasImg ? `<button class="btn-ok btn-sm" data-act="upscale">Upscale HD</button>` : ""}
      <button class="btn-ghost btn-sm" data-act="edit">Éditer</button>
      <button class="btn-ghost btn-sm" data-act="schedule">Planifier</button>
      <button class="btn-primary btn-sm" data-act="publish">Publier</button>
      <button class="btn-danger btn-sm" data-act="del">Suppr.</button>
    </div>`;

  return `<div class="card content-card" id="c${it.id}">
    <div class="card-select" data-act="select">
      <div class="card-checkbox"></div>
    </div>
    ${thumbs}
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">
      <span class="pill">${it.format}</span>
      ${it.angle ? `<span class="pill angle">${esc(it.angle)}</span>` : ""}
      ${statusPill(it.status)}
    </div>
    <div class="hook">${esc(it.hook)}</div>
    <div class="caption">${esc(it.caption)}</div>
    <div class="hashtags">${esc(it.hashtags)}</div>
    ${it.error ? `<p class="muted" style="color:var(--red)">${esc(it.error)}</p>` : ""}
    ${actions}
  </div>`;
}

function bindContentCard(it) {
  const card = $(`#c${it.id}`);
  if (!card) return;
  const on = (act, fn) => { const b = card.querySelector(`[data-act="${act}"]`); if (b) b.onclick = fn; };

  on("select", () => toggleLibSelect(it));

  on("approve", async () => {
    await patchJSON(`/api/content/${it.id}`, { status: "approved" });
    toast("Contenu validé — disponible dans Prêts", "ok");
    libSubTab = "ready";
    render();
  });
  on("del", async () => { if (await confirmModal("Supprimer ce contenu ?")) { await del(`/api/content/${it.id}`); toast("Supprimé", "ok"); render(); } });
  on("render", async () => {
    const useAi = card.querySelector('[data-act="aiToggle"]')?.checked ?? true;
    loader(true, useAi ? "Génération IA" : "Composition", [
      { label: useAi ? "Génération de l'image IA..." : "Composition du visuel...", duration: 12000 },
      { label: "Assemblage final...", duration: 3000 },
    ]);
    try { await postJSON(`/api/content/${it.id}/render`, { use_ai_image: useAi }); loaderDone(); toast("Image générée", "ok"); render(); }
    catch (e) { toast(e.message, "error"); loader(false); }
  });
  on("upscale", async () => {
    loader(true, "Upscale HD en cours…");
    try { await postJSON(`/api/content/${it.id}/render`, { use_ai_image: true, quality: "hd" }); toast("Upscalé en HD", "ok"); render(); }
    catch (e) { toast(e.message, "error"); } finally { loader(false); }
  });
  on("publish", async () => {
    if (!(await confirmModal("Publier sur Instagram maintenant ?", "Publier", "Annuler"))) return;
    loader(true, "Publication…");
    try { await postJSON(`/api/content/${it.id}/publish`, {}); toast("Publié sur Instagram", "ok"); render(); }
    catch (e) { toast(e.message, "error"); } finally { loader(false); }
  });
  on("edit", () => editContent(it));
  on("schedule", () => scheduleContent(it));
  card.querySelectorAll(".thumb-wrap").forEach((w) => {
    w.onclick = () => openLightbox(w.dataset.src, parseInt(w.dataset.cid));
  });
}

function editContent(it) {
  const card = $(`#c${it.id}`);
  card.innerHTML = `
    <label>Hook</label><input id="eHook${it.id}" value="${esc(it.hook)}">
    <label>Caption</label><textarea id="eCap${it.id}">${esc(it.caption)}</textarea>
    <label>Hashtags</label><input id="eTags${it.id}" value="${esc(it.hashtags)}">
    <div class="card-actions">
      <button class="btn-primary btn-sm" id="eSave${it.id}">Enregistrer</button>
      <button class="btn-ghost btn-sm" id="eCancel${it.id}">Annuler</button>
    </div>`;
  $(`#eCancel${it.id}`).onclick = render;
  $(`#eSave${it.id}`).onclick = async () => {
    await patchJSON(`/api/content/${it.id}`, {
      hook: $(`#eHook${it.id}`).value, caption: $(`#eCap${it.id}`).value, hashtags: $(`#eTags${it.id}`).value,
    });
    toast("Contenu modifié", "ok"); render();
  };
}

function scheduleContent(it) {
  const card = $(`#c${it.id}`);
  const dflt = new Date(Date.now() + 3600e3).toISOString().slice(0, 16);
  card.insertAdjacentHTML("beforeend", `
    <div class="card" style="margin-top:10px;background:var(--surface-2)">
      <label>Date et heure de publication</label>
      <input type="datetime-local" id="sched${it.id}" value="${dflt}">
      <div class="card-actions">
        <button class="btn-primary btn-sm" id="schedOk${it.id}">Programmer</button>
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
//  PLANNING (vue des publications)
// =====================================================================
async function renderSchedule() {
  if (!requireBrand()) return;
  const b = state.currentBrand;
  const [sched, items, igStatus] = await Promise.all([
    getJSON(`/api/schedule?brand_id=${b.id}`),
    getJSON(`/api/content?brand_id=${b.id}`),
    getJSON(`/api/instagram/status?brand_id=${b.id}`).catch(() => ({ connected: false, username: "" })),
  ]);

  const contentMap = {};
  items.forEach((it) => { contentMap[it.id] = it; });

  const upcoming = sched.filter((s) => !s.published_at).sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at));
  const published = sched.filter((s) => s.published_at).sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
  const readyToSchedule = items.filter((it) => (it.status === "approved" || it.status === "draft") && !sched.find((s) => s.content_id === it.id) && (it.image_paths || []).length > 0);

  // Build calendar
  const now = new Date();
  const calYear = now.getFullYear();
  const calMonth = now.getMonth();
  const monthName = now.toLocaleString("fr-FR", { month: "long", year: "numeric" });
  const firstDay = new Date(calYear, calMonth, 1);
  const lastDay = new Date(calYear, calMonth + 1, 0);
  const startWeekday = (firstDay.getDay() + 6) % 7; // Monday=0

  // Map scheduled dates
  const schedDates = {};
  upcoming.forEach(s => {
    const d = new Date(s.scheduled_at + "Z");
    const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
    if (!schedDates[key]) schedDates[key] = [];
    schedDates[key].push(s);
  });

  let calCells = "";
  // Empty cells before first day
  for (let i = 0; i < startWeekday; i++) calCells += `<div class="cal-cell empty"></div>`;
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const key = `${calYear}-${String(calMonth+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const isToday = d === now.getDate() && calMonth === now.getMonth();
    const hasPost = schedDates[key];
    const count = hasPost ? hasPost.length : 0;
    calCells += `<div class="cal-cell${isToday ? " today" : ""}${count ? " has-post" : ""}">
      <span class="cal-day">${d}</span>
      ${count ? `<div class="cal-dots">${count > 3 ? '<span class="cal-dot"></span><span class="cal-dot"></span><span class="cal-dot"></span>' : Array(count).fill('<span class="cal-dot"></span>').join("")}</div>` : ""}
    </div>`;
  }

  view.innerHTML = `
    <h2 class="section-title">Planning</h2>

    <div class="sched-ig-bar ${igStatus.connected ? "connected" : "warn"}">
      ${igStatus.connected
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
           <span>Publications sur <b>@${esc(igStatus.username)}</b></span>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--orange)" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
           <span>Instagram non connecté</span>
           <button class="btn-ghost btn-sm" id="schedIgConnect">Connecter</button>`}
    </div>

    <div class="cal-card">
      <div class="cal-title">${monthName.charAt(0).toUpperCase() + monthName.slice(1)}</div>
      <div class="cal-grid">
        <div class="cal-head">Lu</div><div class="cal-head">Ma</div><div class="cal-head">Me</div>
        <div class="cal-head">Je</div><div class="cal-head">Ve</div><div class="cal-head">Sa</div><div class="cal-head">Di</div>
        ${calCells}
      </div>
    </div>

    ${readyToSchedule.length ? `
    <div class="smart-sched-card">
      <div class="smart-sched-header">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        <span>Planification IA</span>
        <span class="smart-sched-badge">${readyToSchedule.length} contenu(s)</span>
      </div>
      <textarea id="smartInstruction" class="smart-sched-input" rows="3" placeholder="Ex : 1 story à 12h, 1 post à 8h et 1 carousel à 20h du lundi au vendredi"></textarea>
      <button class="btn-primary" id="smartSchedBtn" style="width:100%">Planifier avec l'IA</button>
    </div>

    <div class="sched-auto-card">
      <div class="sched-auto-info">
        <span class="sched-auto-count">${readyToSchedule.length}</span>
        <span>contenu(s) prêt(s) à planifier</span>
      </div>
      <div class="sched-auto-row">
        <div style="flex:1"><label style="margin:0 0 4px">Heure</label><input type="time" id="asTime" value="09:00"></div>
        <button class="btn-primary" id="autoSchedBtn" style="flex:2;margin-top:18px">Programmer 1/jour</button>
      </div>
    </div>` : ""}

    ${upcoming.length ? `
    <h3 style="margin-top:20px">A venir</h3>
    <div class="schedule-timeline">
      ${upcoming.map((s) => scheduleCard(s, contentMap[s.content_id])).join("")}
    </div>` : ""}

    ${published.length ? `
    <h3 style="margin-top:20px">Publié</h3>
    <div class="schedule-timeline">
      ${published.map((s) => scheduleCard(s, contentMap[s.content_id], true)).join("")}
    </div>` : ""}
  `;

  const igBtn = $("#schedIgConnect");
  if (igBtn) igBtn.onclick = () => switchTab("instagram");
  const smartBtn = $("#smartSchedBtn");
  if (smartBtn) smartBtn.onclick = async () => {
    const instruction = $("#smartInstruction").value.trim();
    if (!instruction) return toast("Décris comment tu veux planifier", "error");
    loader(true, "Planification IA", [
      { label: "Analyse de l'instruction…", duration: 3000 },
      { label: "Distribution du contenu…", duration: 4000 },
      { label: "Création des créneaux…", duration: 2000 },
    ]);
    try {
      const result = await postJSON("/api/schedule/smart", { brand_id: b.id, instruction });
      loaderDone();
      toast(result.summary, "ok");
      render();
    } catch (e) { toast(e.message, "error"); loader(false); }
  };
  const autoBtn = $("#autoSchedBtn");
  if (autoBtn) autoBtn.onclick = async () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const body = {
      brand_id: b.id,
      start_date: tomorrow.toISOString().slice(0, 10) + "T00:00:00",
      time_of_day: $("#asTime").value || "09:00",
      days: readyToSchedule.length,
    };
    loader(true, "Programmation…");
    try { const r = await postJSON("/api/schedule/auto", body); toast(`${r.length} publications programmées`, "ok"); render(); }
    catch (e) { toast(e.message, "error"); } finally { loader(false); }
  };
  sched.forEach((s) => {
    const b = $(`#unsched${s.id}`);
    if (b) b.onclick = () => unschedule(s.id);
  });
}

function scheduleCard(s, content, isPublished = false) {
  const when = new Date(s.scheduled_at + "Z").toLocaleString("fr-FR", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const imgs = content?.image_paths || [];
  const thumb = imgs.length ? `<img src="${mediaUrl(imgs[0])}" class="sched-thumb">` : `<div class="sched-thumb placeholder"></div>`;

  return `<div class="sched-card${isPublished ? " published" : ""}">
    ${thumb}
    <div class="sched-info">
      <div class="sched-date">${when}</div>
      <div class="sched-hook">${esc(content?.hook || "Contenu #" + s.content_id)}</div>
      <div style="display:flex;gap:4px;margin-top:4px">
        <span class="pill">${content?.format || "post"}</span>
        ${isPublished ? `<span class="pill status-published">Publié</span>` : `<span class="pill status-scheduled">Programmé</span>`}
      </div>
    </div>
    ${!isPublished ? `<button class="btn-danger btn-sm sched-cancel" id="unsched${s.id}">Annuler</button>` : ""}
  </div>`;
}

async function unschedule(id) { await del(`/api/schedule/${id}`); toast("Créneau annulé", "ok"); render(); }

// =====================================================================
//  INSTAGRAM (connexion & publication)
// =====================================================================
async function renderInstagram() {
  if (!requireBrand()) return;
  const b = state.currentBrand;
  let igStatus;
  try {
    igStatus = await getJSON(`/api/instagram/status?brand_id=${b.id}`);
  } catch {
    igStatus = { connected: false, meta_oauth_available: false, username: "" };
  }

  if (igStatus.connected) {
    view.innerHTML = `
      <div class="ig-page">
        <div class="ig-page-icon connected">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="#22c55e" stroke="none"/></svg>
        </div>
        <h2 class="ig-page-title">Instagram connecté</h2>
        <div class="ig-page-username">@${esc(igStatus.username)}</div>
        <p class="ig-page-desc">Ton compte est prêt. Tu peux publier et planifier du contenu directement depuis l'app.</p>

        <div class="ig-page-features">
          <div class="ig-feature">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Publication immédiate</span>
          </div>
          <div class="ig-feature">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Planification automatique</span>
          </div>
          <div class="ig-feature">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Posts, carousels & stories</span>
          </div>
        </div>

        <button class="btn-danger" id="igDisconnect" style="margin-top:24px;width:100%">Déconnecter Instagram</button>
      </div>`;
    $("#igDisconnect").onclick = async () => {
      if (!(await confirmModal("Déconnecter Instagram ?", "Déconnecter"))) return;
      try {
        await postJSON(`/api/instagram/disconnect?brand_id=${b.id}`, {});
        await loadBrands();
        toast("Instagram déconnecté", "ok");
        render();
      } catch (e) { toast(e.message, "error"); }
    };
    return;
  }

  // Not connected
  if (igStatus.meta_oauth_available) {
    // ── OAuth configuré → un seul bouton ──
    view.innerHTML = `
      <div class="ig-page">
        <div class="ig-page-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
        </div>
        <h2 class="ig-page-title">Connecter Instagram</h2>
        <p class="ig-page-desc">Connecte ton compte Instagram Business en un clic. Tu pourras ensuite publier et planifier du contenu.</p>
        <p class="ig-page-desc" style="font-size:.75rem">Ton compte Instagram doit être <b>Business</b> ou <b>Créateur</b>, et lié à une Page Facebook.</p>

        <button class="btn-ig" id="igOAuth" style="margin-top:8px">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
          Connecter Instagram
        </button>

        <button class="btn-ghost btn-sm" id="igShowManual" style="margin-top:20px;opacity:.5">Mode avancé (token manuel)</button>
        <div id="igManualSection" hidden></div>

        <button class="btn-ghost btn-sm" id="igDebugBtn" style="margin-top:8px;opacity:.4;font-size:.75rem">Diagnostic connexion</button>
        <pre id="igDebugOutput" style="display:none;text-align:left;font-size:.7rem;color:var(--muted);background:var(--surface-2);padding:12px;border-radius:8px;margin-top:8px;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow:auto"></pre>
      </div>`;

    $("#igDebugBtn").onclick = async () => {
      const out = $("#igDebugOutput");
      out.style.display = "block";
      out.textContent = "Chargement...";
      try {
        const data = await getJSON(`/api/instagram/debug?brand_id=${b.id}`);
        out.textContent = JSON.stringify(data, null, 2);
      } catch (e) { out.textContent = "Erreur: " + e.message; }
    };

    $("#igOAuth").onclick = async () => {
      try {
        const { url } = await getJSON(`/api/instagram/auth-url?brand_id=${b.id}`);
        const popup = window.open(url, "ig_connect", "width=600,height=700,scrollbars=yes");
        window.addEventListener("message", async function onMsg(e) {
          if (e.data && e.data.igConnected !== undefined) {
            window.removeEventListener("message", onMsg);
            await loadBrands();
            toast(e.data.igConnected ? "Instagram connecté !" : "Connexion échouée", e.data.igConnected ? "ok" : "error");
            render();
          }
        });
      } catch (e) { toast(e.message, "error"); }
    };
    $("#igShowManual").onclick = () => {
      const sec = $("#igManualSection");
      sec.hidden = !sec.hidden;
      if (!sec.innerHTML) {
        sec.innerHTML = _igManualForm();
        _bindIgManualForm(b);
      }
    };

  } else {
    // ── OAuth pas configuré → setup admin + fallback token ──
    view.innerHTML = `
      <div class="ig-page">
        <div class="ig-page-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>
        </div>
        <h2 class="ig-page-title">Connecter Instagram</h2>
        <p class="ig-page-desc">Configure la connexion Instagram pour publier et planifier du contenu.</p>

        <div class="ig-page-steps">
          <div class="ig-step">
            <div class="ig-step-num">1</div>
            <div class="ig-step-content">
              <div class="ig-step-title">Créer une App Meta (une seule fois)</div>
              <div class="ig-step-desc">
                Va sur <a href="https://developers.facebook.com/apps/" target="_blank" style="color:var(--accent)">developers.facebook.com</a> → Créer une app → Type "Business" → Ajoute le produit "Facebook Login".
              </div>
            </div>
          </div>
          <div class="ig-step">
            <div class="ig-step-num">2</div>
            <div class="ig-step-content">
              <div class="ig-step-title">Entrer les identifiants ci-dessous</div>
              <div class="ig-step-desc">Copie l'App ID et l'App Secret depuis les paramètres de ton app Meta.</div>
            </div>
          </div>
          <div class="ig-step">
            <div class="ig-step-num">3</div>
            <div class="ig-step-content">
              <div class="ig-step-title">Connexion en un clic</div>
              <div class="ig-step-desc">Une fois configuré, chaque marque pourra se connecter à Instagram d'un simple clic.</div>
            </div>
          </div>
        </div>

        <div class="card" style="text-align:left;margin-top:16px">
          <label>Meta App ID</label>
          <input id="igAppId" placeholder="Ex : 1234567890" autocomplete="off">
          <label style="margin-top:10px">Meta App Secret</label>
          <input id="igAppSecret" type="password" placeholder="Ex : abc123def456..." autocomplete="off">
          <button class="btn-primary" id="igSaveConfig" style="margin-top:14px;width:100%">Sauvegarder et activer</button>
        </div>

        <div class="ig-page-divider">
          <span>ou connecte-toi directement avec un token</span>
        </div>

        ${_igManualForm()}
      </div>`;

    $("#igSaveConfig").onclick = async () => {
      const appId = $("#igAppId").value.trim();
      const appSecret = $("#igAppSecret").value.trim();
      if (!appId || !appSecret) return toast("App ID et App Secret requis", "error");
      loader(true, "Sauvegarde…");
      try {
        await postJSON("/api/instagram/save-app-config", { app_id: appId, app_secret: appSecret });
        loaderDone();
        toast("Configuration sauvée — le bouton Connecter est maintenant actif", "ok");
        render();
      } catch (e) { toast(e.message, "error"); loader(false); }
    };
    _bindIgManualForm(b);
  }
}

function _igManualForm() {
  return `
    <div class="card ig-manual-card" style="text-align:left;margin-top:16px">
      <label>Access Token (Page Facebook)</label>
      <input id="igToken" type="password" placeholder="Colle ton token ici…" autocomplete="off" style="font-size:.8125rem">
      <p class="muted" style="font-size:.6875rem;margin:6px 0 0">
        Obtiens-le sur le <a href="https://developers.facebook.com/tools/explorer/" target="_blank" style="color:var(--accent)">Graph API Explorer</a>
        avec les permissions <code>pages_show_list</code>, <code>instagram_basic</code>, <code>instagram_content_publish</code>.
      </p>
      <button class="btn-ig" id="igTokenConnect" style="margin-top:12px">Connecter avec le token</button>
    </div>`;
}

function _bindIgManualForm(b) {
  const btn = $("#igTokenConnect");
  if (!btn) return;
  btn.onclick = async () => {
    const token = $("#igToken").value.trim();
    if (!token) return toast("Colle ton access token", "error");
    loader(true, "Connexion…", [
      { label: "Vérification du token…", duration: 2000 },
      { label: "Recherche de ta page Facebook…", duration: 3000 },
      { label: "Liaison avec Instagram…", duration: 2000 },
    ]);
    try {
      await postJSON(`/api/instagram/connect-token?brand_id=${b.id}`, { token });
      loaderDone();
      await loadBrands();
      toast("Instagram connecté !", "ok");
      render();
    } catch (e) { toast(e.message, "error"); loader(false); }
  };
}

// ---- util ----
function requireBrand() {
  if (!state.currentBrand) {
    view.innerHTML = `<div class="empty">Commence par créer une marque dans l'onglet <b>Marque</b>.</div>`;
    return false;
  }
  return true;
}

init();
