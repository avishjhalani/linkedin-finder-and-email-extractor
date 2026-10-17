// State management
let currentLeads = [];
let appConfig = {
  webhook_url: "",
  hunter_api_key: "",
  default_pattern: "first.last"
};

// DOM Elements
const queryInput = document.getElementById("queryInput");
const btnSearch = document.getElementById("btnSearch");
const parseBadge = document.getElementById("parseBadge");
const domainStatusPill = document.getElementById("domainStatusPill");

const paramRole = document.getElementById("paramRole");
const paramCompany = document.getElementById("paramCompany");
const paramDomain = document.getElementById("paramDomain");
const paramLocation = document.getElementById("paramLocation");
const paramCount = document.getElementById("paramCount");

const searchProgressBar = document.getElementById("searchProgressBar");
const resultsCard = document.getElementById("resultsCard");
const initialEmptyState = document.getElementById("initialEmptyState");
const leadsTableBody = document.getElementById("leadsTableBody");
const resultsCountBadge = document.getElementById("resultsCountBadge");
const selectedCountText = document.getElementById("selectedCountText");
const selectAllCheckbox = document.getElementById("selectAllCheckbox");

const btnPushToSheets = document.getElementById("btnPushToSheets");
const btnDownloadCsv = document.getElementById("btnDownloadCsv");
const btnCopyEmails = document.getElementById("btnCopyEmails");

// Modals
const guideModal = document.getElementById("guideModal");
const settingsModal = document.getElementById("settingsModal");
const pushModal = document.getElementById("pushModal");
const btnOpenGuide = document.getElementById("btnOpenGuide");
const btnOpenSettings = document.getElementById("btnOpenSettings");
const btnSaveSettings = document.getElementById("btnSaveSettings");
const btnCopyScript = document.getElementById("btnCopyScript");
const appsScriptCode = document.getElementById("appsScriptCode");
const cfgWebhookUrl = document.getElementById("cfgWebhookUrl");
const cfgApolloKey = document.getElementById("cfgApolloKey");
const cfgHunterKey = document.getElementById("cfgHunterKey");
const cfgDefaultPattern = document.getElementById("cfgDefaultPattern");
const pushWebhookUrlInput = document.getElementById("pushWebhookUrlInput");
const btnExecutePush = document.getElementById("btnExecutePush");
const pushStatusAlert = document.getElementById("pushStatusAlert");

// Toast helper
function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  const toastMessage = document.getElementById("toastMessage");
  const toastIcon = document.getElementById("toastIcon");

  toastMessage.textContent = message;
  if (isError) {
    toastIcon.className = "fa-solid fa-circle-exclamation text-rose-400";
  } else {
    toastIcon.className = "fa-solid fa-circle-check text-emerald-400";
  }

  toast.classList.remove("translate-y-20", "opacity-0");
  setTimeout(() => {
    toast.classList.add("translate-y-20", "opacity-0");
  }, 3500);
}

// Initial bootstrap
async function initApp() {
  // Load stored config
  try {
    const res = await fetch("/api/config");
    if (res.ok) {
      appConfig = await res.json();
      cfgWebhookUrl.value = appConfig.webhook_masked || "";
      const cfgSerper = document.getElementById("cfgSerperKey");
      if (cfgSerper) cfgSerper.value = appConfig.serper_masked || "";
      if (cfgApolloKey) cfgApolloKey.value = appConfig.apollo_masked || "";
      cfgHunterKey.value = appConfig.hunter_masked || "";
      cfgDefaultPattern.value = appConfig.default_pattern || "first.last";
      pushWebhookUrlInput.value = appConfig.webhook_masked || "";
    }
  } catch (e) {
    console.error("Config fetch error:", e);
  }

  // Load Apps Script template for the guide
  try {
    const res = await fetch("/api/script-template");
    if (res.ok) {
      const data = await res.json();
      appsScriptCode.textContent = data.template;
    }
  } catch (e) {
    console.error("Script template fetch error:", e);
  }

  // Parse initial query
  if (queryInput.value.trim()) {
    triggerQueryParse(queryInput.value.trim());
  }
}

// Debounce helper for live parsing
let parseTimeout = null;
queryInput.addEventListener("input", () => {
  clearTimeout(parseTimeout);
  parseTimeout = setTimeout(() => {
    const val = queryInput.value.trim();
    if (val) triggerQueryParse(val);
  }, 450);
});

async function triggerQueryParse(queryText) {
  try {
    const res = await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: queryText })
    });
    if (res.ok) {
      const data = await res.json();
      paramRole.value = data.role || "";
      paramCompany.value = data.company || "";
      paramLocation.value = data.location || "";
      paramCount.value = data.count || 10;
      paramDomain.value = data.detected_domain || "";

      parseBadge.classList.remove("hidden");
      setTimeout(() => parseBadge.classList.add("hidden"), 1800);

      // Update Domain MX pill
      if (data.domain_mx_valid) {
        domainStatusPill.className = "text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium";
        domainStatusPill.innerHTML = `<i class="fa-solid fa-circle-check text-[10px]"></i> Domain: ${data.detected_domain} (${data.mail_provider || 'MX Valid'})`;
      } else {
        domainStatusPill.className = "text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium";
        domainStatusPill.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-[10px]"></i> Domain: ${data.detected_domain} (Checking MX)`;
      }
    }
  } catch (e) {
    console.error("Parse error:", e);
  }
}

// Quick chip click handlers
document.querySelectorAll(".chip-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const q = btn.getAttribute("data-q");
    queryInput.value = q;
    triggerQueryParse(q);
  });
});

// Search leads
btnSearch.addEventListener("click", executeSearch);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") executeSearch();
});

async function executeSearch() {
  const role = paramRole.value.trim();
  const company = paramCompany.value.trim();
  const count = parseInt(paramCount.value) || 10;
  const location = paramLocation.value.trim();
  const custom_domain = paramDomain.value.trim();
  const preferred_pattern = appConfig.default_pattern || "first.last";

  if (!company) {
    showToast("Please enter a target company name.", true);
    return;
  }

  // UI state
  searchProgressBar.classList.remove("hidden");
  resultsCard.classList.add("hidden");
  initialEmptyState.classList.add("hidden");
  btnSearch.disabled = true;
  btnSearch.classList.add("opacity-70");

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role,
        company,
        count,
        location,
        preferred_pattern,
        custom_domain
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Search request failed");
    }

    const data = await res.json();
    currentLeads = data.leads || [];

    renderLeadsTable(currentLeads);
    resultsCard.classList.remove("hidden");
    showToast(`Found ${currentLeads.length} leads matching your query!`);
  } catch (err) {
    showToast(err.message || "An error occurred during search.", true);
    initialEmptyState.classList.remove("hidden");
  } finally {
    searchProgressBar.classList.add("hidden");
    btnSearch.disabled = false;
    btnSearch.classList.remove("opacity-70");
  }
}

function renderLeadsTable(leads) {
  leadsTableBody.innerHTML = "";
  resultsCountBadge.textContent = `${leads.length} Leads`;

  if (leads.length === 0) {
    const hasSearchKey = Boolean(appConfig.serper_configured);
    leadsTableBody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-10 px-4">
          <div class="max-w-md mx-auto space-y-3">
            <div class="w-12 h-12 mx-auto rounded-full ${hasSearchKey ? 'bg-slate-800 text-slate-400' : 'bg-amber-500/10 text-amber-400'} flex items-center justify-center text-xl">
              <i class="fa-solid ${hasSearchKey ? 'fa-magnifying-glass' : 'fa-cloud-bolt'}"></i>
            </div>
            <h4 class="text-white font-bold text-sm">
              ${hasSearchKey ? 'No Leads Found Matching Query' : '0 Leads Found (Cloud Bot Protection)'}
            </h4>
            <p class="text-xs text-slate-400 leading-relaxed">
              ${hasSearchKey 
                ? 'Try broadening your role, company name, or changing location filters.' 
                : 'When hosted on Render, search engines require a free Search API Key to bypass anti-bot challenges.'}
            </p>
            ${!hasSearchKey ? `
              <div class="pt-2 flex flex-col sm:flex-row items-center justify-center gap-2">
                <a href="https://serper.dev" target="_blank" class="px-3.5 py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:opacity-90 text-white rounded-lg text-xs font-semibold shadow flex items-center gap-1.5 transition">
                  <i class="fa-solid fa-key"></i> Get 2,500 Free Searches
                </a>
                <button onclick="document.getElementById('btnOpenSettings').click()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold border border-slate-700 transition">
                  Enter Key in Settings
                </button>
              </div>
              <p class="text-[11px] text-slate-500 pt-1">
                Tip: Run <strong>run.bat</strong> on your computer for 100% free unlimited searches without any API key!
              </p>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
    return;
  }

  leads.forEach((lead, idx) => {
    const initials = (lead.first_name[0] || "") + (lead.last_name[0] || "");
    
    // Determine badge class
    let badgeClass = "badge-pattern";
    if (lead.email_source === "apollo") badgeClass = "badge-apollo";
    else if (lead.email_source === "bio") badgeClass = "badge-bio";
    else if (lead.email_source === "hunter") badgeClass = "badge-hunter";
    else if (lead.confidence.includes("MX Verified")) badgeClass = "badge-mx";

    // Pattern options dropdown
    const permKeys = Object.keys(lead.email_permutations || {});
    const patternOptions = permKeys.map(k => {
      const val = lead.email_permutations[k];
      const isSelected = val === lead.email ? "selected" : "";
      return `<option value="${val}" ${isSelected}>${k}: ${val}</option>`;
    }).join("");

    const row = document.createElement("tr");
    row.className = "hover:bg-slate-800/40 transition group";
    row.innerHTML = `
      <td class="py-3.5 px-4 text-center">
        <input type="checkbox" data-index="${idx}" checked class="lead-checkbox rounded border-slate-700 text-blue-600 focus:ring-0">
      </td>
      <td class="py-3.5 px-4">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-700 to-indigo-600 text-white font-bold text-xs flex items-center justify-center flex-shrink-0 shadow">
            ${initials}
          </div>
          <div>
            <div class="font-semibold text-white text-sm flex items-center gap-1.5">
              ${lead.full_name}
            </div>
            <div class="text-[11px] text-slate-400 flex items-center gap-1">
              <span class="bg-slate-800 px-1.5 py-0.2 rounded text-slate-300">{{First: ${lead.first_name}}}</span>
              <span class="bg-slate-800 px-1.5 py-0.2 rounded text-slate-300">{{Last: ${lead.last_name}}}</span>
            </div>
          </div>
        </div>
      </td>
      <td class="py-3.5 px-4">
        <div class="text-xs text-slate-200 font-medium max-w-[240px] truncate" title="${lead.job_title}">
          ${lead.job_title}
        </div>
      </td>
      <td class="py-3.5 px-4">
        <div class="text-xs font-semibold text-slate-300">
          ${lead.company}
        </div>
        <div class="text-[11px] text-slate-400">
          ${lead.location || lead.domain}
        </div>
      </td>
      <td class="py-3.5 px-4">
        <div class="space-y-1 max-w-[320px]">
          <div class="flex items-center gap-1.5">
            <input 
              type="email" 
              data-index="${idx}"
              value="${lead.email}" 
              class="lead-email-input flex-1 px-2.5 py-1 bg-slate-950 border border-slate-700 rounded text-xs text-cyan-300 font-mono focus:border-blue-500 focus:outline-none"
            >
            <button class="btn-copy-one text-slate-400 hover:text-white p-1 rounded transition" title="Copy email" data-email="${lead.email}">
              <i class="fa-regular fa-copy text-xs"></i>
            </button>
          </div>

          <div class="flex items-center gap-2">
            <span class="text-[10px] px-2 py-0.5 rounded-full font-medium ${badgeClass}">
              ${lead.confidence}
            </span>
            ${permKeys.length > 1 ? `
              <select data-index="${idx}" class="lead-pattern-selector text-[10px] bg-slate-950 border border-slate-800 rounded px-1.5 py-0.5 text-slate-400 focus:outline-none">
                ${patternOptions}
              </select>
            ` : ''}
          </div>
        </div>
      </td>
      <td class="py-3.5 px-4 text-right">
        <a 
          href="${lead.linkedin_url}" 
          target="_blank" 
          rel="noopener noreferrer" 
          class="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium px-2.5 py-1 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 transition"
        >
          <span>LinkedIn</span>
          <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
        </a>
      </td>
    `;
    leadsTableBody.appendChild(row);
  });

  // Attach dynamic row event listeners
  attachRowListeners();
  updateSelectedCount();
}

function attachRowListeners() {
  // Checkboxes
  document.querySelectorAll(".lead-checkbox").forEach(cb => {
    cb.addEventListener("change", updateSelectedCount);
  });

  // Inline email edits
  document.querySelectorAll(".lead-email-input").forEach(input => {
    input.addEventListener("input", (e) => {
      const idx = parseInt(e.target.getAttribute("data-index"));
      if (currentLeads[idx]) {
        currentLeads[idx].email = e.target.value.trim();
      }
    });
  });

  // Pattern switcher
  document.querySelectorAll(".lead-pattern-selector").forEach(sel => {
    sel.addEventListener("change", (e) => {
      const idx = parseInt(e.target.getAttribute("data-index"));
      const newEmail = e.target.value;
      if (currentLeads[idx]) {
        currentLeads[idx].email = newEmail;
        const input = document.querySelector(`.lead-email-input[data-index="${idx}"]`);
        if (input) input.value = newEmail;
      }
    });
  });

  // Copy individual email
  document.querySelectorAll(".btn-copy-one").forEach(btn => {
    btn.addEventListener("click", () => {
      const email = btn.getAttribute("data-email");
      navigator.clipboard.writeText(email);
      showToast(`Copied ${email} to clipboard!`);
    });
  });
}

// Select All toggle
selectAllCheckbox.addEventListener("change", () => {
  const isChecked = selectAllCheckbox.checked;
  document.querySelectorAll(".lead-checkbox").forEach(cb => {
    cb.checked = isChecked;
  });
  updateSelectedCount();
});

function getSelectedLeads() {
  const selected = [];
  document.querySelectorAll(".lead-checkbox").forEach(cb => {
    if (cb.checked) {
      const idx = parseInt(cb.getAttribute("data-index"));
      if (currentLeads[idx]) {
        selected.push(currentLeads[idx]);
      }
    }
  });
  return selected;
}

function updateSelectedCount() {
  const count = getSelectedLeads().length;
  selectedCountText.textContent = `(${count} selected)`;
}

// Push to Google Sheets Action
btnPushToSheets.addEventListener("click", () => {
  const selected = getSelectedLeads();
  if (selected.length === 0) {
    showToast("Please select at least one lead to push.", true);
    return;
  }
  document.getElementById("pushLeadsCountNotice").textContent = `Ready to push ${selected.length} selected leads.`;
  pushWebhookUrlInput.value = appConfig.webhook_url || "";
  pushStatusAlert.className = "hidden";
  pushModal.classList.remove("hidden");
});

btnExecutePush.addEventListener("click", async () => {
  const selected = getSelectedLeads();
  const webhookUrl = pushWebhookUrlInput.value.trim();

  if (!webhookUrl) {
    pushStatusAlert.className = "bg-rose-500/10 border border-rose-500/30 text-rose-300 p-3 rounded-lg text-xs";
    pushStatusAlert.textContent = "Please enter your Google Apps Script Webhook URL.";
    return;
  }

  btnExecutePush.disabled = true;
  btnExecutePush.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i> Pushing...`;

  try {
    const res = await fetch("/api/export/sheets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        method: "webhook",
        webhook_url: webhookUrl,
        leads: selected
      })
    });

    const data = await res.json();
    if (res.ok) {
      // Save webhook url to config
      appConfig.webhook_url = webhookUrl;
      fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ webhook_url: webhookUrl })
      });

      pushStatusAlert.className = "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 p-3 rounded-lg text-xs";
      pushStatusAlert.innerHTML = `<strong>Success!</strong> Successfully added ${selected.length} leads to your Google Sheet!`;
      showToast(`Pushed ${selected.length} leads to your Google Sheet!`);
      setTimeout(() => pushModal.classList.add("hidden"), 1800);
    } else {
      throw new Error(data.detail || "Failed to push to Google Sheet");
    }
  } catch (err) {
    pushStatusAlert.className = "bg-rose-500/10 border border-rose-500/30 text-rose-300 p-3 rounded-lg text-xs";
    pushStatusAlert.textContent = `Error: ${err.message}`;
  } finally {
    btnExecutePush.disabled = false;
    btnExecutePush.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Push Now`;
  }
});

// Download CSV Action
btnDownloadCsv.addEventListener("click", async () => {
  const selected = getSelectedLeads();
  if (selected.length === 0) {
    showToast("Please select at least one lead to download.", true);
    return;
  }

  try {
    const res = await fetch("/api/export/csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ leads: selected })
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `linkedin_leads_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast(`Downloaded CSV with ${selected.length} leads!`);
    } else {
      throw new Error("CSV generation failed");
    }
  } catch (err) {
    showToast(err.message, true);
  }
});

// Copy all selected emails
btnCopyEmails.addEventListener("click", () => {
  const selected = getSelectedLeads();
  if (selected.length === 0) {
    showToast("No leads selected to copy.", true);
    return;
  }
  const emails = selected.map(l => l.email).join(", ");
  navigator.clipboard.writeText(emails);
  showToast(`Copied ${selected.length} emails to clipboard!`);
});

// Settings Modal
btnOpenSettings.addEventListener("click", () => {
  settingsModal.classList.remove("hidden");
});

btnSaveSettings.addEventListener("click", async () => {
  const payload = {
    default_pattern: cfgDefaultPattern.value
  };
  const webVal = cfgWebhookUrl.value.trim();
  if (webVal && !webVal.includes("••••")) payload.webhook_url = webVal;

  if (cfgApolloKey) {
    const apolloVal = cfgApolloKey.value.trim();
    if (apolloVal && !apolloVal.includes("••••")) payload.apollo_api_key = apolloVal;
  }

  const serperInput = document.getElementById("cfgSerperKey");
  if (serperInput) {
    const serperVal = serperInput.value.trim();
    if (serperVal && !serperVal.includes("••••")) payload.serper_api_key = serperVal;
  }

  const hunterVal = cfgHunterKey.value.trim();
  if (hunterVal && !hunterVal.includes("••••")) payload.hunter_api_key = hunterVal;

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      appConfig = data.config;
      document.getElementById("settingsSaveStatus").textContent = "Settings saved!";
      showToast("Settings updated securely!");
      setTimeout(() => {
        document.getElementById("settingsSaveStatus").textContent = "";
        settingsModal.classList.add("hidden");
      }, 1000);
    }
  } catch (e) {
    showToast("Failed to save settings.", true);
  }
});

// Guide Modal
btnOpenGuide.addEventListener("click", () => {
  guideModal.classList.remove("hidden");
});

document.getElementById("btnOpenGuideFromPush").addEventListener("click", () => {
  pushModal.classList.add("hidden");
  guideModal.classList.remove("hidden");
});

document.getElementById("btnJumpToSettings").addEventListener("click", () => {
  guideModal.classList.add("hidden");
  settingsModal.classList.remove("hidden");
});

btnCopyScript.addEventListener("click", () => {
  const code = appsScriptCode.textContent;
  navigator.clipboard.writeText(code);
  showToast("Google Apps Script code copied to clipboard!");
});

// Modal close buttons
document.querySelectorAll(".modal-close").forEach(btn => {
  btn.addEventListener("click", () => {
    guideModal.classList.add("hidden");
    settingsModal.classList.add("hidden");
    pushModal.classList.add("hidden");
  });
});

// Initialize on page load
initApp();
