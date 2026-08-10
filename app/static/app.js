let assets = [];
let currentAsset;
let currentAnalysis;
let currentChange;

const $ = (id) => document.getElementById(id);
const show = (id) => $(id).classList.remove("hidden");
const hide = (id) => $(id).classList.add("hidden");
const escapeHtml = (value) => String(value).replace(
  /[&<>"']/g,
  (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character],
);

function initializeHero() {
  const hero = $("hero");
  const stage = hero?.querySelector(".hero-sticky");
  if (!hero || !stage) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let active = false;
  let frame;

  const clamp = (value, minimum = 0, maximum = 1) => Math.min(maximum, Math.max(minimum, value));

  function paintHero() {
    if (reducedMotion.matches) return;

    const rect = hero.getBoundingClientRect();
    const scrollDistance = Math.max(1, hero.offsetHeight - window.innerHeight);
    const progress = clamp(-rect.top / scrollDistance);
    const compact = window.innerWidth <= 680;
    // Keep each hand visible as an edge anchor after the title is revealed.
    const travel = progress * (compact ? 8 : 18);
    const scale = 1 + progress * .045;
    const reveal = compact
      ? clamp((progress - .55) / .35)
      : clamp((progress - .42) / .38);
    stage.style.setProperty("--left-shift", `${-travel}vw`);
    stage.style.setProperty("--right-shift", `${travel}vw`);
    stage.style.setProperty("--hand-scale", scale.toFixed(3));
    stage.style.setProperty("--title-opacity", reveal.toFixed(3));
    stage.style.setProperty("--title-y", `${((1 - reveal) * 28).toFixed(1)}px`);
  }

  function animateVisibleHero() {
    if (!active || reducedMotion.matches) return;
    paintHero();
    frame = window.requestAnimationFrame(animateVisibleHero);
  }

  const observer = new IntersectionObserver(([entry]) => {
    active = entry.isIntersecting;
    window.cancelAnimationFrame(frame);
    if (active) animateVisibleHero();
  });

  observer.observe(hero);
  window.addEventListener("resize", paintHero);
  reducedMotion.addEventListener?.("change", paintHero);
  paintHero();
}

async function json(url, options) {
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function setGlobalError(message = "") {
  $("global-error").textContent = message;
  $("global-error").classList.toggle("hidden", !message);
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (busy) {
    button.dataset.previousLabel = button.querySelector("span").textContent;
    button.querySelector("span").textContent = label;
  } else if (button.dataset.previousLabel) {
    button.querySelector("span").textContent = button.dataset.previousLabel;
    delete button.dataset.previousLabel;
  }
}

function selectedAsset() {
  return assets.find((asset) => asset.id === $("asset-select").value);
}

function renderAssetDetails() {
  const asset = selectedAsset();
  if (!asset) return;
  $("asset-details").innerHTML = [asset.platform, asset.type, asset.owner, asset.domain]
    .map((value) => `<span>${escapeHtml(value.replaceAll("_", " "))}</span>`)
    .join("");
}

async function loadAssets() {
  try {
    const [catalogAssets, health] = await Promise.all([json("/api/assets"), json("/api/health")]);
    assets = catalogAssets.filter((asset) => asset.columns.length);
    $("asset-select").innerHTML = assets
      .map((asset) => `<option value="${escapeHtml(asset.id)}">${escapeHtml(asset.name)}</option>`)
      .join("");
    const runtime = $("runtime-status");
    runtime.classList.add("ready");
    runtime.querySelector("span:last-child").textContent = health.catalog_mode === "mcp"
      ? "DataHub MCP connected"
      : "Deterministic demo ready";
    renderAssetDetails();
    await discover();
  } catch (error) {
    $("runtime-status").classList.add("error");
    $("runtime-status").querySelector("span:last-child").textContent = "Catalog unavailable";
    setGlobalError(error.message);
  }
}

function renderMetrics(summary) {
  const preferred = ["direct_consumers", "all_consumers", "teams", "domains", "dashboards", "models", "critical_consumers"];
  $("metrics").innerHTML = preferred
    .filter((key) => Object.hasOwn(summary, key))
    .map((key) => `<div class="metric"><b>${escapeHtml(summary[key])}</b><span>${escapeHtml(key.replaceAll("_", " "))}</span></div>`)
    .join("");
}

function renderConsumers(convergence) {
  $("consumer-count").textContent = `${convergence.consumers.length} known consumers`;
  $("source-node").innerHTML = `<strong>${escapeHtml(convergence.asset.name)}</strong><span>${escapeHtml(convergence.asset.owner)} · ${escapeHtml(convergence.asset.domain)}</span>`;
  $("consumers").innerHTML = convergence.consumers.map((item) => `
    <article class="consumer-card">
      <div class="consumer-top"><span class="type-label">${escapeHtml(item.type.replaceAll("_", " "))}</span><span class="hop-label">${escapeHtml(item.hops)} hop${item.hops === 1 ? "" : "s"}</span></div>
      <strong>${escapeHtml(item.name)}</strong>
      <p>${escapeHtml(item.owner)}<br>${escapeHtml(item.domain)}</p>
    </article>`).join("");
}

function renderContract(contract) {
  $("contract").innerHTML = contract.dependencies.map((item) => `
    <div class="contract-row">
      <code>${escapeHtml(item.column)}</code>
      <span>${escapeHtml(item.roles.join(", ") || "No observed role")}</span>
      <span>${escapeHtml(item.consumer_count)} known</span>
      <span class="confidence">${escapeHtml(item.confidence)}</span>
    </div>`).join("");
  $("column-select").innerHTML = contract.dependencies
    .map((item) => `<option value="${escapeHtml(item.column)}">${escapeHtml(item.column)} · ${escapeHtml(item.type)}</option>`)
    .join("");
}

async function discover() {
  const button = $("discover-button");
  currentAsset = $("asset-select").value;
  if (!currentAsset) return;
  setGlobalError();
  setBusy(button, true, "Tracing graph");
  $("overview").setAttribute("aria-busy", "true");
  try {
    const [convergence, contract] = await Promise.all([
      json(`/api/assets/${encodeURIComponent(currentAsset)}/convergence`),
      json(`/api/assets/${encodeURIComponent(currentAsset)}/contract`),
    ]);
    $("score").textContent = convergence.score;
    $("risk").textContent = `${convergence.risk} convergence`;
    $("risk").dataset.level = convergence.risk;
    renderMetrics(convergence.summary);
    renderConsumers(convergence);
    renderContract(contract);
    ["overview", "consumer-section", "contract-section", "change-section"].forEach(show);
    hide("analysis");
    document.querySelectorAll(".flow li").forEach((item, index) => item.classList.toggle("active", index <= 1));
  } catch (error) {
    setGlobalError(error.message);
  } finally {
    $("overview").setAttribute("aria-busy", "false");
    setBusy(button, false);
  }
}

function syncChangeFields() {
  const kind = $("change-kind").value;
  const input = $("new-value");
  const label = $("new-value-label").querySelector("span");
  label.textContent = kind === "rename" ? "New name" : kind === "type_change" ? "New type" : "No replacement required";
  input.disabled = kind === "remove";
  input.required = kind !== "remove";
  input.placeholder = kind === "rename" ? "buyer_id" : kind === "type_change" ? "BIGINT" : "Removal will be evaluated";
  input.value = kind === "rename" ? "buyer_id" : kind === "type_change" ? "BIGINT" : "";
}

function codePanel(id, label, content, active) {
  return `<div id="${id}" class="code-panel${active ? "" : " hidden"}" role="tabpanel">
    <button class="copy-button" type="button" data-copy="${id}-code">Copy</button>
    <pre id="${id}-code"><code>${escapeHtml(content)}</code></pre>
  </div>`;
}

function renderAnalysis(analysis) {
  const affected = analysis.known_affected_consumers;
  const verdict = analysis.verdict.replaceAll("_", " ");
  $("analysis").innerHTML = `
    <div class="analysis-layout">
      <article class="result-card">
        <div class="result-heading"><p class="result-label">Impact verdict</p><span class="severity-badge" data-level="${escapeHtml(analysis.severity)}">${escapeHtml(analysis.severity)} risk</span></div>
        <h3 class="verdict-name">${escapeHtml(verdict)}</h3>
        <p class="verdict-summary">${affected.length} known consumer${affected.length === 1 ? "" : "s"} depend on this column across the captured organizational graph.</p>
        <ul class="affected-list">${affected.map((item) => `<li><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.owner)}<br>${escapeHtml(item.domain)}</span></li>`).join("") || "<li><strong>No known affected consumers</strong><span>Coverage may still be incomplete</span></li>"}</ul>
        <p class="coverage-warning"><span><strong>Unknown coverage remains.</strong><br>${escapeHtml(analysis.unknown_coverage)}</span></p>
      </article>
      <article class="result-card">
        <div class="result-heading"><div><p class="result-label">Generated repair</p><h3>Reviewable migration package</h3></div></div>
        <div class="code-tabs" role="tablist" aria-label="Generated code">
          <button class="code-tab active" type="button" role="tab" aria-selected="true" data-panel="migration-panel">Compatibility SQL</button>
          <button class="code-tab" type="button" role="tab" aria-selected="false" data-panel="test-panel">Regression test</button>
        </div>
        ${codePanel("migration-panel", "Compatibility SQL", analysis.generated.compatibility_sql, true)}
        ${codePanel("test-panel", "Regression test", analysis.generated.regression_tests, false)}
        <div class="action-bar">
          <button id="package-button" class="button button-primary" type="button"><span>Generate review package</span></button>
          <button id="writeback-button" class="button button-secondary" type="button"><span>Approve & record</span></button>
        </div>
        <p class="review-note">Generates four review files. ChangeSafe never merges autonomously.</p>
        <div id="package-result" class="hidden" aria-live="polite"></div>
        <div id="writeback-result" class="hidden" aria-live="polite"></div>
      </article>
    </div>`;
  show("analysis");
  document.querySelectorAll(".flow li").forEach((item, index) => item.classList.toggle("active", index <= 2));
  document.querySelectorAll(".code-tab").forEach((button) => button.addEventListener("click", switchCodePanel));
  document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", copyCode));
  $("package-button").addEventListener("click", generatePackage);
  $("writeback-button").addEventListener("click", writeback);
  $("analysis").scrollIntoView({ behavior: "smooth", block: "start" });
}

function switchCodePanel(event) {
  document.querySelectorAll(".code-tab").forEach((button) => {
    const active = button === event.currentTarget;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    $(button.dataset.panel).classList.toggle("hidden", !active);
  });
}

async function copyCode(event) {
  const button = event.currentTarget;
  try {
    await navigator.clipboard.writeText($(button.dataset.copy).textContent);
    button.textContent = "Copied";
    window.setTimeout(() => { button.textContent = "Copy"; }, 1400);
  } catch {
    button.textContent = "Select text";
  }
}

async function analyzeChange(event) {
  event.preventDefault();
  const kind = $("change-kind").value;
  const payload = { asset_id: currentAsset, kind, column: $("column-select").value };
  if (kind === "rename") payload.new_name = $("new-value").value.trim();
  if (kind === "type_change") payload.new_type = $("new-value").value.trim();
  const button = $("analyze-button");
  setGlobalError();
  setBusy(button, true, "Analyzing impact");
  try {
    currentChange = payload;
    currentAnalysis = await json("/api/change/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderAnalysis(currentAnalysis);
  } catch (error) {
    setGlobalError(error.message);
  } finally {
    setBusy(button, false);
  }
}

function renderReceipt(id, title, message, files = [], error = false) {
  const element = $(id);
  element.className = `receipt${error ? " error" : ""}`;
  element.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p>${files.length ? `<div class="file-list">${files.map((file) => `<code>${escapeHtml(file)}</code>`).join("")}</div>` : ""}`;
}

async function generatePackage() {
  const button = $("package-button");
  setBusy(button, true, "Generating files");
  try {
    const result = await json("/api/change/package", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentChange),
    });
    renderReceipt("package-result", "Review package ready", `${result.package_id} · Human review required`, result.files);
    document.querySelectorAll(".flow li").forEach((item, index) => item.classList.toggle("active", index <= 3));
  } catch (error) {
    renderReceipt("package-result", "Package generation failed", error.message, [], true);
  } finally {
    setBusy(button, false);
  }
}

async function writeback() {
  const button = $("writeback-button");
  setBusy(button, true, "Recording decision");
  try {
    const result = await json("/api/change/writeback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis: currentAnalysis }),
    });
    const destination = result.mode === "datahub" ? `DataHub · ${result.urn}` : result.mode === "mcp" ? `DataHub MCP · ${result.document_id}` : `Demo receipt · ${result.document_id}`;
    const owners = new Set(currentAnalysis.known_affected_consumers.map((item) => item.owner)).size;
    renderReceipt("writeback-result", "Reviewed decision recorded", `${destination}. ${owners} known owner${owners === 1 ? "" : "s"} identified for coordination; no notifications sent.`);
    document.querySelectorAll(".flow li").forEach((item) => item.classList.add("active"));
  } catch (error) {
    renderReceipt("writeback-result", "Decision write-back failed", error.message, [], true);
  } finally {
    setBusy(button, false);
  }
}

$("asset-select").addEventListener("change", renderAssetDetails);
$("discover-button").addEventListener("click", discover);
$("change-kind").addEventListener("change", syncChangeFields);
$("change-form").addEventListener("submit", analyzeChange);
syncChangeFields();
initializeHero();
loadAssets();
