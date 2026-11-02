// State management
let currentLeads = [];
let appConfig = {
  webhook_configured: false,
  webhook_masked: "",
  hunter_configured: false,
  hunter_masked: "",
  default_pattern: "first.last"
};

// DOM Elements
const companyInput = document.getElementById("companyInput");
const btnSearch = document.getElementById("btnSearch");
const countSelect = document.getElementById("countSelect");
const patternSelect = document.getElementById("patternSelect");
const searchProgressBar = document.getElementById("searchProgressBar");

const companyStatusBar = document.getElementById("companyStatusBar");
const detectedDomainBadge = document.getElementById("detectedDomainBadge");
const detectedProviderBadge = document.getElementById("detectedProviderBadge");

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
const btnOpenGuide = document.getElementById("btnOpenGuide");
const btnOpenSettings = document.getElementById("btnOpenSettings");
const btnSaveSettings = document.getElementById("btnSaveSettings");
const btnCopyScript = document.getElementById("btnCopyScript");
const appsScriptCode = document.getElementById("appsScriptCode");
const cfgWebhookUrl = document.getElementById("cfgWebhookUrl");
const cfgHunterKey = document.getElementById("cfgHunterKey");
const cfgDefaultPattern = document.getElementById("cfgDefaultPattern");

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

// Bootstrap
async function initApp() {
  // Load configuration
  try {
    const res = await fetch("/api/config");
    if (res.ok) {
      appConfig = await res.json();
      cfgWebhookUrl.value = appConfig.webhook_masked || "";
      cfgHunterKey.value = appConfig.hunter_masked || "";
      cfgDefaultPattern.value = appConfig.default_pattern || "first.last";
      patternSelect.value = appConfig.default_pattern || "first.last";
    }
  } catch (e) {
    console.error("Failed to load config:", e);
  }

  // Load Apps Script template
  try {
    const res = await fetch("/api/script-template");
    if (res.ok) {
      const data = await res.json();
      appsScriptCode.textContent = data.template;
    }
  } catch (e) {
    console.error("Failed to load script template:", e);
  }

  // Company quick-select pills
  document.querySelectorAll(".company-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      companyInput.value = pill.dataset.company;
      performSearch();
    });
  });
}

// Extract search
async function performSearch() {
  const company = companyInput.value.trim();
  if (!company) {
    showToast("Please enter a company name.", true);
    companyInput.focus();
    return;
  }

  // Collect checked roles
  const checkedRoles = [];
  document.querySelectorAll(".role-checkbox:checked").forEach(cb => {
    checkedRoles.push(cb.value);
  });

  const count = parseInt(countSelect.value, 10) || 10;
  const preferred_pattern = patternSelect.value || "first.last";

  // UI loading state
  searchProgressBar.classList.remove("hidden");
  btnSearch.disabled = true;
  btnSearch.classList.add("opacity-70");

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company,
        target_roles: checkedRoles,
        count,
        preferred_pattern
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Search request failed");
    }

    const data = await res.json();
    currentLeads = data.leads || [];

    // Render Domain status bar
    detectedDomainBadge.textContent = data.domain || `${company.toLowerCase()}.com`;
    detectedProviderBadge.textContent = `${data.mail_provider || 'Mail Server'} (${data.mx_valid ? 'Active MX' : 'No MX'})`;
    companyStatusBar.classList.remove("hidden");

    // Render table
    renderLeadsTable(currentLeads);
    initialEmptyState.classList.add("hidden");
    resultsCard.classList.remove("hidden");

    showToast(`Found ${currentLeads.length} HR & talent leads at ${company}!`);
  } catch (err) {
    showToast(err.message || "An error occurred during search.", true);
  } finally {
    searchProgressBar.classList.add("hidden");
    btnSearch.disabled = false;
    btnSearch.classList.remove("opacity-70");
  }
}

// Render Leads Table
function renderLeadsTable(leads) {
  leadsTableBody.innerHTML = "";
  resultsCountBadge.textContent = `${leads.length} Leads`;

  if (leads.length === 0) {
    leadsTableBody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-10 text-slate-400">
          No LinkedIn profiles found matching these parameters. Try broadening your company name.
        </td>
      </tr>
    `;
    updateSelectedCount();
    return;
  }

  leads.forEach((lead, idx) => {
    const initials = (lead.first_name[0] || "") + (lead.last_name[0] || "");
    
    // Determine badge class
    let badgeClass = "badge-mx";
    if (lead.deliverability.includes("Verified")) {
      badgeClass = "badge-verified";
    } else if (lead.deliverability.includes("Inactive") || lead.deliverability.includes("Undeliverable")) {
      badgeClass = "badge-inactive";
    }

    // Pattern options dropdown
    const permKeys = Object.keys(lead.permutations || {});
    const patternOptions = permKeys.map(k => {
      const val = lead.permutations[k];
      const isSelected = val === lead.email ? "selected" : "";
      return `<option value="${val}" ${isSelected}>${k}: ${val}</option>`;
    }).join("");

    const row = document.createElement("tr");
    row.className = "hover:bg-slate-900/60 transition group";
    row.innerHTML = `
      <td class="py-3 px-4 text-center">
        <input type="checkbox" data-index="${idx}" checked class="lead-checkbox rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0 cursor-pointer">
      </td>
      <td class="py-3 px-4">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-700 to-cyan-600 text-white font-bold text-xs flex items-center justify-center flex-shrink-0 shadow">
            ${initials}
          </div>
          <div>
            <div class="font-bold text-white text-xs flex items-center gap-1.5">
              <span>${lead.name}</span>
              <a href="${lead.linkedin_url}" target="_blank" rel="noopener" class="text-blue-400 hover:text-blue-300 text-[11px]" title="Open LinkedIn Profile">
                <i class="fa-brands fa-linkedin"></i>
              </a>
            </div>
            <div class="text-[11px] text-slate-400">India</div>
          </div>
        </div>
      </td>
      <td class="py-3 px-4 text-slate-300 max-w-xs truncate" title="${lead.role}">
        ${lead.role}
      </td>
      <td class="py-3 px-4 font-semibold text-slate-300">
        ${lead.company}
      </td>
      <td class="py-3 px-4">
        <div class="flex items-center gap-1.5">
          <select data-index="${idx}" class="lead-email-select bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-cyan-300 font-mono text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none">
            ${patternOptions}
          </select>
          <button class="btn-copy-one text-slate-500 hover:text-white p-1 rounded" title="Copy Email">
            <i class="fa-regular fa-copy"></i>
          </button>
        </div>
      </td>
      <td class="py-3 px-4 text-right">
        <span class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold ${badgeClass}">
          ${lead.deliverability}
        </span>
      </td>
    `;

    leadsTableBody.appendChild(row);
  });

  // Attach dropdown change listener
  document.querySelectorAll(".lead-email-select").forEach(select => {
    select.addEventListener("change", (e) => {
      const idx = e.target.dataset.index;
      currentLeads[idx].email = e.target.value;
    });
  });

  // Attach individual copy button
  document.querySelectorAll(".btn-copy-one").forEach((btn, idx) => {
    btn.addEventListener("click", () => {
      const email = currentLeads[idx].email;
      navigator.clipboard.writeText(email);
      showToast(`Copied ${email}!`);
    });
  });

  updateSelectedCount();
}

function updateSelectedCount() {
  const selected = document.querySelectorAll(".lead-checkbox:checked").length;
  selectedCountText.textContent = `${selected} selected`;
  selectAllCheckbox.checked = selected === currentLeads.length && currentLeads.length > 0;
}

// Select all toggle
selectAllCheckbox.addEventListener("change", (e) => {
  const isChecked = e.target.checked;
  document.querySelectorAll(".lead-checkbox").forEach(cb => {
    cb.checked = isChecked;
  });
  updateSelectedCount();
});

leadsTableBody.addEventListener("change", (e) => {
  if (e.target.classList.contains("lead-checkbox")) {
    updateSelectedCount();
  }
});

function getSelectedLeads() {
  const selected = [];
  document.querySelectorAll(".lead-checkbox:checked").forEach(cb => {
    const idx = parseInt(cb.dataset.index, 10);
    if (currentLeads[idx]) {
      selected.push(currentLeads[idx]);
    }
  });
  return selected;
}

// 1-Click Push to Google Sheets
btnPushToSheets.addEventListener("click", async () => {
  const selected = getSelectedLeads();
  if (selected.length === 0) {
    showToast("Please select at least 1 lead to upload.", true);
    return;
  }

  btnPushToSheets.disabled = true;
  btnPushToSheets.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Uploading ${selected.length} Leads...`;

  try {
    const res = await fetch("/api/export/sheets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        leads: selected
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`Successfully uploaded ${selected.length} leads to your Google Sheet!`);
    } else {
      throw new Error(data.error || "Failed to push to Google Sheet");
    }
  } catch (err) {
    showToast(err.message || "Failed to upload to Google Sheet.", true);
  } finally {
    btnPushToSheets.disabled = false;
    btnPushToSheets.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Upload to Google Sheet`;
  }
});

// Download CSV for YAMM
btnDownloadCsv.addEventListener("click", async () => {
  const selected = getSelectedLeads();
  if (selected.length === 0) {
    showToast("Please select at least 1 lead to download.", true);
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
      a.download = "verified_hr_leads.csv";
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

// Settings & Guide Modals
btnOpenSettings.addEventListener("click", () => settingsModal.classList.remove("hidden"));
btnOpenGuide.addEventListener("click", () => guideModal.classList.remove("hidden"));

document.querySelectorAll(".modal-close").forEach(btn => {
  btn.addEventListener("click", () => {
    guideModal.classList.add("hidden");
    settingsModal.classList.add("hidden");
  });
});

// Copy Apps Script
btnCopyScript.addEventListener("click", () => {
  navigator.clipboard.writeText(appsScriptCode.textContent);
  showToast("Google Apps Script code copied to clipboard!");
});

// Save Settings
btnSaveSettings.addEventListener("click", async () => {
  const payload = {
    default_pattern: cfgDefaultPattern.value
  };
  const webVal = cfgWebhookUrl.value.trim();
  if (webVal && !webVal.includes("••••")) payload.webhook_url = webVal;

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
      showToast("Settings updated successfully!");
      setTimeout(() => {
        document.getElementById("settingsSaveStatus").textContent = "";
        settingsModal.classList.add("hidden");
      }, 1000);
    }
  } catch (e) {
    showToast("Failed to save settings.", true);
  }
});

// Event Listeners
btnSearch.addEventListener("click", performSearch);
companyInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") performSearch();
});

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", initApp);
