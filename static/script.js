document.addEventListener("DOMContentLoaded", () => {
  const searchForm = document.getElementById("search-form");
  const searchBtn = document.getElementById("search-btn");
  const stopButton = document.getElementById("stop-button");
  const resetFiltersBtn = document.getElementById("reset-filters-btn");

  const keywordsInput = document.getElementById("keywords");
  const roleSuggestionsDatalist = document.getElementById("it-role-suggestions");
  const countrySelect = document.getElementById("country");
  const stateSelect = document.getElementById("state");
  const cityInput = document.getElementById("city");
  const cityDatalist = document.getElementById("city-suggestions");
  const experienceMultiselect = document.getElementById("experience-multiselect");
  const workModeMultiselect = document.getElementById("work-mode-multiselect");
  const multiSelects = [experienceMultiselect, workModeMultiselect].filter(Boolean);

  const statusSection = document.getElementById("status-section");
  const statusText = document.querySelector(".status-text");
  const statusPercent = document.getElementById("status-percent");
  const progressBar = document.getElementById("progress-bar");
  const feedbackBanner = document.getElementById("feedback-banner");

  const resultsToolbar = document.getElementById("results-toolbar");
  const resultsGrid = document.getElementById("results-grid");
  const paginationBar = document.getElementById("pagination-bar");
  const emptyState = document.getElementById("empty-state");
  const resultsCountText = document.getElementById("results-count-text");
  const navbarResultsCount = document.getElementById("navbar-results-count");
  const quickFilterInput = document.getElementById("quick-filter-input");
  const excludeFilterInput = document.getElementById("exclude-filter-input");
  const easyApplyCheckbox = document.getElementById("easy_apply");
  const exportButtons = document.querySelectorAll(".export-btn");

  const jobModal = document.getElementById("job-modal");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const modalTitle = document.getElementById("modal-title");
  const modalCompany = document.getElementById("modal-company");
  const modalBadges = document.getElementById("modal-badges");
  const modalDescription = document.getElementById("modal-description");
  const modalLink = document.getElementById("modal-link");

  const LOCATION_DATA = {
    Brazil: {
      "Acre": ["Rio Branco"],
      "Alagoas": ["Maceió"],
      "Amapá": ["Macapá"],
      "Amazonas": ["Manaus"],
      "Bahia": ["Salvador", "Feira de Santana", "Vitória da Conquista"],
      "Ceará": ["Fortaleza", "Juazeiro do Norte"],
      "Distrito Federal": ["Brasília"],
      "Espírito Santo": ["Vitória", "Vila Velha", "Serra"],
      "Goiás": ["Goiânia", "Anápolis", "Aparecida de Goiânia"],
      "Maranhão": ["São Luís"],
      "Mato Grosso": ["Cuiabá"],
      "Mato Grosso do Sul": ["Campo Grande"],
      "Minas Gerais": ["Belo Horizonte", "Uberlândia", "Contagem", "Juiz de Fora", "Betim", "Montes Claros"],
      "Pará": ["Belém"],
      "Paraíba": ["João Pessoa", "Campina Grande"],
      "Paraná": ["Curitiba", "Londrina", "Maringá", "Cascavel"],
      "Pernambuco": ["Recife", "Jaboatão dos Guararapes", "Olinda"],
      "Piauí": ["Teresina"],
      "Rio de Janeiro": ["Rio de Janeiro", "Niterói", "Duque de Caxias", "Nova Iguaçu"],
      "Rio Grande do Norte": ["Natal"],
      "Rio Grande do Sul": ["Porto Alegre", "Caxias do Sul", "Canoas", "Pelotas"],
      "Rondônia": ["Porto Velho"],
      "Roraima": ["Boa Vista"],
      "Santa Catarina": ["Florianópolis", "Joinville", "Blumenau", "Itajaí"],
      "São Paulo": ["São Paulo", "Campinas", "São José dos Campos", "Ribeirão Preto", "Sorocaba", "Santos", "Barueri"],
      "Sergipe": ["Aracaju"],
      "Tocantins": ["Palmas"],
    },
    Portugal: {
      "Lisboa": ["Lisboa", "Cascais", "Oeiras", "Sintra"],
      "Porto": ["Porto", "Vila Nova de Gaia", "Matosinhos"],
      "Braga": ["Braga", "Guimarães"],
      "Coimbra": ["Coimbra"],
      "Aveiro": ["Aveiro"],
      "Setúbal": ["Setúbal", "Almada"],
      "Faro": ["Faro"],
    },
    "United States": {
      "California": ["San Francisco", "Los Angeles", "San Jose", "San Diego"],
      "New York": ["New York", "Brooklyn"],
      "Texas": ["Austin", "Dallas", "Houston"],
      "Washington": ["Seattle", "Bellevue"],
      "Florida": ["Miami", "Orlando", "Tampa"],
      "Massachusetts": ["Boston", "Cambridge"],
    },
    Canada: {
      "Ontario": ["Toronto", "Ottawa", "Waterloo"],
      "British Columbia": ["Vancouver", "Victoria"],
      "Quebec": ["Montreal", "Quebec City"],
      "Alberta": ["Calgary", "Edmonton"],
    },
    "United Kingdom": {
      "England": ["London", "Manchester", "Birmingham", "Bristol"],
      "Scotland": ["Edinburgh", "Glasgow"],
    },
    Germany: {
      "Berlin": ["Berlin"],
      "Bavaria": ["Munich", "Nuremberg"],
      "Hesse": ["Frankfurt"],
      "Hamburg": ["Hamburg"],
    },
    Spain: {
      "Madrid": ["Madrid"],
      "Catalonia": ["Barcelona"],
      "Valencia": ["Valencia"],
      "Andalusia": ["Seville", "Málaga"],
    },
    Ireland: {
      "Dublin": ["Dublin"],
      "Cork": ["Cork"],
      "Galway": ["Galway"],
    },
  };

  const langSelect = document.getElementById("lang-select");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIcon = document.getElementById("theme-icon");
  const STORAGE_KEYS = {
    seenJobs: "huntly_seen_jobs",
    lang: "huntly_lang",
    theme: "huntly_theme",
  };

  function applyTheme(theme) {
    const isDark = theme === "dark";
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    writeStorage(STORAGE_KEYS.theme, isDark ? "dark" : "light");
    if (themeIcon) {
      themeIcon.className = isDark ? "bi bi-sun" : "bi bi-moon";
    }
  }

  const I18N = window.HUNTLY_I18N || {};
  let currentLang = readStorage(STORAGE_KEYS.lang, "pt");
  if (!I18N[currentLang]) currentLang = "pt";

  function t(key, vars = {}) {
    const dict = I18N[currentLang] || I18N.pt || {};
    let str = dict[key] || (I18N.pt && I18N.pt[key]) || key;
    Object.entries(vars).forEach(([k, v]) => {
      str = str.replaceAll(`{${k}}`, String(v));
    });
    return str;
  }

  function tCountry(countryKey) {
    const dictCountries = I18N[currentLang]?.countries || {};
    const ptCountries = I18N.pt?.countries || {};
    return dictCountries[countryKey] || ptCountries[countryKey] || countryKey;
  }

  function populateRoleSuggestions() {
    if (!roleSuggestionsDatalist) return;
    const suggestions = I18N[currentLang]?.roleSuggestions || I18N.pt?.roleSuggestions || [];
    roleSuggestionsDatalist.innerHTML = "";
    suggestions.forEach((role) => {
      const opt = document.createElement("option");
      opt.value = role;
      roleSuggestionsDatalist.appendChild(opt);
    });
  }

  function applyLanguage(lang) {
    if (!I18N[lang]) return;
    currentLang = lang;
    writeStorage(STORAGE_KEYS.lang, lang);
    document.documentElement.lang = lang === "pt" ? "pt-BR" : lang;
    document.title = t("pageTitle");

    if (langSelect) langSelect.value = lang;

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
      el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel));
    });

    populateRoleSuggestions();
    updateAllMultiSelects();

    if (countrySelect && countrySelect.options.length > 0) {
      Array.from(countrySelect.options).forEach((opt, idx) => {
        opt.textContent = idx === 0 ? t("allCountries") : tCountry(opt.value);
      });
    }
    if (stateSelect && stateSelect.options.length > 0) {
      stateSelect.options[0].textContent = countrySelect.value ? t("allStates") : t("selectCountryFirst");
    }

    renderFilteredResults();

    if (jobModal.style.display !== "none" && activeModalJob) {
      openJobModal(activeModalJob);
    }
    if (lastStatusPayload && statusSection.style.display !== "none") {
      updateStatusBar(lastStatusPayload);
    }
    if (lastFeedback && feedbackBanner.style.display !== "none") {
      renderFeedback();
    }
  }

  const ITEMS_PER_PAGE = 9;
  const SESSION_TRANSLATIONS_KEY = "huntly_translations_cache";
  const MAX_SESSION_TRANSLATIONS = 200;
  let isSearching = false;
  let searchResults = [];
  let currentPage = 1;
  let pollTimeout = null;
  let lastCollectedCount = -1;
  let activeModalJob = null;
  let lastStatusPayload = null;
  let lastFeedback = null;
  const translationCache = loadSessionTranslations();
  const translationInFlight = new Set();

  function loadSessionTranslations() {
    const cache = new Map();
    try {
      const raw = sessionStorage.getItem(SESSION_TRANSLATIONS_KEY);
      if (!raw) return cache;
      const entries = JSON.parse(raw);
      if (Array.isArray(entries)) {
        entries.slice(-MAX_SESSION_TRANSLATIONS).forEach(([k, v]) => {
          if (typeof k === "string" && v && typeof v === "object") {
            cache.set(k, v);
          }
        });
      }
    } catch {
      // Ignore storage errors
    }
    return cache;
  }

  function saveSessionTranslations() {
    try {
      const entries = Array.from(translationCache.entries()).slice(-MAX_SESSION_TRANSLATIONS);
      sessionStorage.setItem(SESSION_TRANSLATIONS_KEY, JSON.stringify(entries));
    } catch {
      // Ignore storage quota errors
    }
  }

  function getDisplayJob(job) {
    if (!job || currentLang === "pt" || !job.id) return job;
    const cached = translationCache.get(`${currentLang}:${job.id}`);
    if (!cached) return job;
    return {
      ...job,
      title: cached.title || job.title,
      description: cached.description || job.description,
    };
  }

  async function ensureTranslations(jobsToTranslate) {
    if (currentLang === "pt" || !Array.isArray(jobsToTranslate) || !jobsToTranslate.length) {
      return;
    }
    const targetLang = currentLang;
    const pendingJobs = jobsToTranslate.filter((job) => {
      if (!job || !job.id || (!job.title && !job.description)) return false;
      const cacheKey = `${targetLang}:${job.id}`;
      return !translationCache.has(cacheKey) && !translationInFlight.has(cacheKey);
    });
    if (!pendingJobs.length) return;

    const batch = pendingJobs.slice(0, 20);
    const jobIds = batch.map((job) => String(job.id));
    jobIds.forEach((jid) => translationInFlight.add(`${targetLang}:${jid}`));

    try {
      const response = await fetch("/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lang: targetLang, job_ids: jobIds }),
      });
      if (!response.ok) return;

      const payload = await response.json();
      const translations = payload && typeof payload.translations === "object" ? payload.translations : null;
      if (!translations) return;

      let updated = false;
      Object.entries(translations).forEach(([jid, translated]) => {
        if (translated && typeof translated === "object") {
          const cacheKey = `${targetLang}:${jid}`;
          if (translationCache.size >= MAX_SESSION_TRANSLATIONS) {
            const oldestKey = translationCache.keys().next().value;
            if (oldestKey) translationCache.delete(oldestKey);
          }
          translationCache.set(cacheKey, {
            title: translated.title || "",
            description: translated.description || "",
          });
          updated = true;
        }
      });

      if (updated) {
        saveSessionTranslations();
        if (currentLang === targetLang) {
          renderFilteredResults();
          if (jobModal.style.display !== "none" && activeModalJob && translations[String(activeModalJob.id)]) {
            openJobModal(activeModalJob);
          }
        }
      }
    } catch {
      // Safe fallback: keep original card texts
    } finally {
      jobIds.forEach((jid) => translationInFlight.delete(`${targetLang}:${jid}`));
    }
  }

  function readStorage(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Ignore storage quota errors
    }
  }

  function getSeenJobs() {
    return new Set(readStorage(STORAGE_KEYS.seenJobs, []));
  }

  function markJobAsSeen(jobId, cardEl) {
    if (!jobId) return;
    const seen = getSeenJobs();
    if (!seen.has(jobId)) {
      seen.add(jobId);
      writeStorage(STORAGE_KEYS.seenJobs, Array.from(seen).slice(-300));
    }
    if (cardEl && !cardEl.classList.contains("is-seen")) {
      cardEl.classList.add("is-seen");
      const kickerRow = cardEl.querySelector(".card-kicker-row");
      if (kickerRow && !kickerRow.querySelector(".seen-badge")) {
        const badge = document.createElement("span");
        badge.className = "seen-badge";
        badge.textContent = t("seenBadge");
        kickerRow.appendChild(badge);
      }
    }
  }

  function initLocationCascade() {
    countrySelect.innerHTML = "";
    const worldwideOpt = document.createElement("option");
    worldwideOpt.value = "";
    worldwideOpt.textContent = t("allCountries");
    countrySelect.appendChild(worldwideOpt);

    Object.keys(LOCATION_DATA).forEach((country) => {
      const opt = document.createElement("option");
      opt.value = country;
      opt.textContent = tCountry(country);
      countrySelect.appendChild(opt);
    });

    countrySelect.value = "";
    populateStates("");
  }

  function populateStates(country) {
    stateSelect.innerHTML = "";
    const allStatesOpt = document.createElement("option");
    allStatesOpt.value = "";
    allStatesOpt.textContent = country ? t("allStates") : t("selectCountryFirst");
    stateSelect.appendChild(allStatesOpt);

    const statesMap = LOCATION_DATA[country];
    if (statesMap) {
      stateSelect.disabled = false;
      Object.keys(statesMap).forEach((stateName) => {
        const opt = document.createElement("option");
        opt.value = stateName;
        opt.textContent = stateName;
        stateSelect.appendChild(opt);
      });
    } else {
      stateSelect.disabled = true;
    }

    cityInput.value = "";
    populateCitySuggestions(country, "");
  }

  function populateCitySuggestions(country, state) {
    cityDatalist.innerHTML = "";
    const cities = LOCATION_DATA[country]?.[state] || [];
    cities.forEach((cityName) => {
      const opt = document.createElement("option");
      opt.value = cityName;
      cityDatalist.appendChild(opt);
    });
  }

  function buildLocationString() {
    return [cityInput.value.trim(), stateSelect.value.trim(), countrySelect.value.trim()]
      .filter(Boolean)
      .join(", ");
  }

  function updateMultiSelectDisplay(container) {
    if (!container) return;
    const labelEl = container.querySelector(".multi-select-label");
    const countEl = container.querySelector(".multi-select-count");
    const defaultKey = container.dataset.defaultKey || "";
    const checked = Array.from(container.querySelectorAll('input[type="checkbox"]:checked'));

    if (checked.length === 0) {
      if (labelEl) labelEl.textContent = defaultKey ? t(defaultKey) : "";
      if (countEl) {
        countEl.textContent = "";
        countEl.style.display = "none";
      }
      return;
    }

    const labels = checked.map((cb) => {
      const span = cb.closest(".multi-select-option")?.querySelector("span");
      return span ? span.textContent.trim() : cb.value;
    });
    if (labelEl) labelEl.textContent = labels.join(", ");
    if (countEl) {
      if (checked.length >= 2) {
        countEl.textContent = String(checked.length);
        countEl.style.display = "inline-flex";
      } else {
        countEl.textContent = "";
        countEl.style.display = "none";
      }
    }
  }

  function updateAllMultiSelects() {
    multiSelects.forEach(updateMultiSelectDisplay);
  }

  function closeAllMultiSelects(exceptContainer = null) {
    multiSelects.forEach((container) => {
      if (container !== exceptContainer) {
        container.classList.remove("is-open");
        const trigger = container.querySelector(".multi-select-trigger");
        if (trigger) trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  function getMultiSelectValues(container) {
    if (!container) return [];
    return Array.from(container.querySelectorAll('input[type="checkbox"]:checked'))
      .map((cb) => cb.value)
      .filter(Boolean);
  }

  function resetMultiSelects() {
    multiSelects.forEach((container) => {
      container.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        cb.checked = false;
      });
    });
    closeAllMultiSelects();
    updateAllMultiSelects();
  }

  multiSelects.forEach((container) => {
    const trigger = container.querySelector(".multi-select-trigger");
    if (trigger) {
      trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        const willOpen = !container.classList.contains("is-open");
        closeAllMultiSelects(willOpen ? container : null);
        container.classList.toggle("is-open", willOpen);
        trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
      });
    }
    container.addEventListener("change", () => updateMultiSelectDisplay(container));
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".multi-select")) {
      closeAllMultiSelects();
    }
  });

  // Event Listeners
  countrySelect.addEventListener("change", () => populateStates(countrySelect.value));
  stateSelect.addEventListener("change", () => {
    cityInput.value = "";
    populateCitySuggestions(countrySelect.value, stateSelect.value);
  });

  searchForm.addEventListener("submit", handleSearch);
  stopButton.addEventListener("click", stopSearch);
  resetFiltersBtn.addEventListener("click", resetFilters);
  quickFilterInput.addEventListener("input", () => {
    currentPage = 1;
    renderFilteredResults();
  });
  if (excludeFilterInput) {
    excludeFilterInput.addEventListener("input", () => {
      currentPage = 1;
      renderFilteredResults();
    });
  }

  exportButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!searchResults.length) return;
      window.location.href = `/export/${btn.dataset.format}?type=jobs&lang=${encodeURIComponent(currentLang)}`;
    });
  });

  closeModalBtn.addEventListener("click", closeModal);
  jobModal.addEventListener("click", (e) => {
    if (e.target === jobModal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllMultiSelects();
      if (jobModal.style.display !== "none") closeModal();
    }
  });

  if (langSelect) {
    langSelect.addEventListener("change", (e) => applyLanguage(e.target.value));
  }
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      applyTheme(current === "dark" ? "light" : "dark");
    });
  }

  applyTheme(readStorage(STORAGE_KEYS.theme, "light"));
  initLocationCascade();
  applyLanguage(currentLang);

  function renderFeedback() {
    if (!lastFeedback) {
      feedbackBanner.style.display = "none";
      feedbackBanner.textContent = "";
      return;
    }
    const prefix = lastFeedback.prefixKey ? t(lastFeedback.prefixKey) : "";
    const body = lastFeedback.key ? t(lastFeedback.key, lastFeedback.vars || {}) : lastFeedback.text || "";
    const msg = `${prefix}${body}`.trim();
    if (!msg) {
      feedbackBanner.style.display = "none";
      feedbackBanner.textContent = "";
      return;
    }
    feedbackBanner.textContent = msg;
    feedbackBanner.style.display = "block";
  }

  function showFeedback(message, key = null, vars = {}, prefixKey = null) {
    if (!message && !key) {
      lastFeedback = null;
      renderFeedback();
      return;
    }
    lastFeedback = { text: message || "", key, vars, prefixKey };
    renderFeedback();
  }

  function resetFilters() {
    searchForm.reset();
    resetMultiSelects();
    initLocationCascade();
    quickFilterInput.value = "";
    if (excludeFilterInput) excludeFilterInput.value = "";
    showFeedback("");
    if (searchResults.length > 0) {
      currentPage = 1;
      renderFilteredResults();
    }
  }

  function getFormData() {
    const formData = new FormData(searchForm);
    const workModes = getMultiSelectValues(workModeMultiselect);
    const experienceLevels = getMultiSelectValues(experienceMultiselect);
    return {
      type: "jobs",
      lang: currentLang,
      keywords: (formData.get("keywords") || "").trim(),
      location: buildLocationString(),
      max_date: formData.get("job_max_date") || "",
      sort_by: formData.get("sort_by") || "R",
      distance: "",
      job_type: [],
      work_mode: workModes,
      place: workModes,
      experience_level: experienceLevels,
      easy_apply: Boolean(easyApplyCheckbox && easyApplyCheckbox.checked),
      limit_jobs: 100,
    };
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (isSearching) return;

    const searchData = getFormData();
    if (!searchData.keywords) {
      showFeedback(t("errNoKeyword"), "errNoKeyword");
      return;
    }

    showFeedback("");

    try {
      setSearching(true);
      const response = await fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(searchData),
      });

      const payload = await response.json();
      if (!response.ok) {
        const err = new Error(payload.error || t("errGeneric"));
        err.code = payload.error_code || null;
        throw err;
      }

      pollResults();
    } catch (error) {
      if (error.code && I18N[currentLang]?.[error.code]) {
        showFeedback("", error.code, {}, "errPrefix");
      } else {
        showFeedback(`${t("errPrefix")}${error.message}`);
      }
      setIdleState();
    }
  }

  async function pollResults() {
    try {
      const response = await fetch("/status?type=jobs&include_results=0");
      const data = await response.json();
      if (!response.ok) {
        const err = new Error(data.error || t("errGeneric"));
        err.code = data.error_code || null;
        throw err;
      }

      updateStatusBar(data);
      const collectedCount = data.collected_jobs || 0;
      const isTerminal =
        data.status === "complete" ||
        data.progress === 100 ||
        data.status === "stopped" ||
        !data.is_searching;

      if (collectedCount !== lastCollectedCount || isTerminal) {
        lastCollectedCount = collectedCount;
        await fetchResults();
      }

      if (data.status === "complete" || data.progress === 100) {
        setIdleState();
      } else if (data.status === "error") {
        if (data.status_code && I18N[currentLang]?.[data.status_code]) {
          showFeedback("", data.status_code, data.status_params || {});
        } else {
          showFeedback(data.status_message || t("errGeneric"), "errGeneric");
        }
        setIdleState();
      } else if (data.status === "stopped" || !data.is_searching) {
        setIdleState();
      } else {
        pollTimeout = setTimeout(pollResults, 900);
      }
    } catch (error) {
      if (error.code && I18N[currentLang]?.[error.code]) {
        showFeedback("", error.code, {}, "errPrefix");
      } else {
        showFeedback(error.message, null, {}, "errComm");
      }
      setIdleState();
    }
  }

  async function fetchResults() {
    const response = await fetch("/results?type=jobs");
    if (!response.ok) return;
    const data = await response.json();
    searchResults = Array.isArray(data) ? data : [];
    renderFilteredResults();
  }

  function renderFilteredResults() {
    const hasResults = searchResults.length > 0;
    resultsToolbar.style.display = hasResults ? "flex" : "none";
    exportButtons.forEach((btn) => {
      btn.disabled = !hasResults;
    });

    const rawQuickTerm = quickFilterInput.value.trim();
    const quickTerm = normalizeLookup(rawQuickTerm);
    const rawExclude = excludeFilterInput ? excludeFilterInput.value.trim() : "";
    const excludeTerms = rawExclude
      ? rawExclude.split(",").map((part) => normalizeLookup(part)).filter(Boolean)
      : [];

    const filtered = !quickTerm && excludeTerms.length === 0
      ? searchResults
      : searchResults.filter((item) => {
          const display = getDisplayJob(item);
          if (quickTerm) {
            const includeHaystack = normalizeLookup(
              [
                item.title,
                item.company,
                item.location,
                item.description,
                display.title,
                display.description,
              ]
                .filter(Boolean)
                .join(" ")
            );
            if (!includeHaystack.includes(quickTerm)) {
              return false;
            }
          }
          if (excludeTerms.length > 0) {
            const excludeHaystack = normalizeLookup(
              [
                item.title,
                item.description,
                display.title,
                display.description,
              ]
                .filter(Boolean)
                .join(" ")
            );
            if (excludeTerms.some((term) => excludeHaystack.includes(term))) {
              return false;
            }
          }
          return true;
        });

    updateCounts(filtered.length, searchResults.length);
    resultsGrid.innerHTML = "";

    if (filtered.length === 0) {
      paginationBar.style.display = "none";
      emptyState.style.display = "flex";
      const h3 = emptyState.querySelector("h3");
      const p = emptyState.querySelector("p");
      if (hasResults && (quickTerm || excludeTerms.length > 0)) {
        h3.textContent = t("emptyNoMatchTitle");
        if (quickTerm && excludeTerms.length > 0) {
          p.textContent = t("emptyNoMatchCombinedDesc", {
            term: rawQuickTerm,
            excluded: rawExclude,
            total: searchResults.length,
          });
        } else if (quickTerm) {
          p.textContent = t("emptyNoMatchDesc", { term: rawQuickTerm, total: searchResults.length });
        } else {
          p.textContent = t("emptyNoMatchExcludeDesc", { excluded: rawExclude, total: searchResults.length });
        }
      } else if (isSearching) {
        h3.textContent = t("emptyCollectingTitle");
        p.textContent = t("emptyCollectingDesc");
      } else if (searchResults.length === 0 && !rawQuickTerm && !rawExclude) {
        h3.textContent = t("emptyInitialTitle");
        p.textContent = t("emptyInitialDesc");
      } else {
        h3.textContent = t("emptyNoneTitle");
        p.textContent = t("emptyNoneDesc");
      }
      return;
    }

    emptyState.style.display = "none";
    const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
    if (currentPage > totalPages) currentPage = totalPages;

    const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
    const pageItems = filtered.slice(startIdx, startIdx + ITEMS_PER_PAGE);
    const seenJobs = getSeenJobs();

    pageItems.forEach((item, idx) => {
      resultsGrid.appendChild(createJobCard(item, startIdx + idx, seenJobs.has(item.id)));
    });

    renderPagination(filtered.length, totalPages);
    ensureTranslations(pageItems);
  }

  function renderPagination(totalItems, totalPages) {
    if (totalPages <= 1) {
      paginationBar.style.display = "none";
      paginationBar.innerHTML = "";
      return;
    }

    paginationBar.style.display = "flex";
    paginationBar.innerHTML = "";

    const startItem = (currentPage - 1) * ITEMS_PER_PAGE + 1;
    const endItem = Math.min(currentPage * ITEMS_PER_PAGE, totalItems);

    const info = document.createElement("span");
    info.className = "pagination-info";
    info.textContent = t("pageInfo", {
      start: startItem,
      end: endItem,
      total: totalItems,
      page: currentPage,
      pages: totalPages,
    });

    const controls = document.createElement("div");
    controls.className = "pagination-controls";

    const goToPage = (page) => {
      currentPage = page;
      renderFilteredResults();
      const target = document.getElementById("resultados");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "pagination-btn";
    prevBtn.textContent = t("pagePrev");
    prevBtn.disabled = currentPage === 1;
    prevBtn.addEventListener("click", () => goToPage(currentPage - 1));
    controls.appendChild(prevBtn);

    for (let p = 1; p <= totalPages; p++) {
      if (totalPages > 7 && p !== 1 && p !== totalPages && Math.abs(p - currentPage) > 1) {
        if (p === 2 || p === totalPages - 1) {
          const dots = document.createElement("span");
          dots.className = "pagination-info";
          dots.textContent = "…";
          dots.style.padding = "0 0.25rem";
          controls.appendChild(dots);
        }
        continue;
      }

      const pageBtn = document.createElement("button");
      pageBtn.type = "button";
      pageBtn.className = `pagination-btn${p === currentPage ? " active" : ""}`;
      pageBtn.textContent = String(p);
      pageBtn.addEventListener("click", () => goToPage(p));
      controls.appendChild(pageBtn);
    }

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "pagination-btn";
    nextBtn.textContent = t("pageNext");
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.addEventListener("click", () => goToPage(currentPage + 1));
    controls.appendChild(nextBtn);

    paginationBar.append(info, controls);
  }

  function createMetaBadge(iconClass, text) {
    const badge = document.createElement("span");
    badge.className = "meta-badge";
    const icon = document.createElement("i");
    icon.className = iconClass;
    badge.append(icon, document.createTextNode(text));
    return badge;
  }

  function getSafeUrl(url) {
    if (typeof url !== "string") return "#";
    const trimmed = url.trim();
    return trimmed.startsWith("https://") ? trimmed : "#";
  }

  const EMPLOYMENT_CODE_KEYS = {
    full_time: "empFullTime",
    part_time: "empPartTime",
    contract: "empContract",
    temporary: "empTemporary",
    internship: "empInternship",
    volunteer: "empVolunteer",
    other: "empOther",
  };

  const EMPLOYMENT_TEXT_MAP = {
    "tempo integral": "empFullTime",
    "full-time": "empFullTime",
    "full time": "empFullTime",
    "jornada completa": "empFullTime",
    "tiempo completo": "empFullTime",
    "temps plein": "empFullTime",
    "tempo pieno": "empFullTime",
    "vollzeit": "empFullTime",
    "полная занятость": "empFullTime",
    "全职": "empFullTime",
    "meio periodo": "empPartTime",
    "part-time": "empPartTime",
    "part time": "empPartTime",
    "media jornada": "empPartTime",
    "tiempo parcial": "empPartTime",
    "temps partiel": "empPartTime",
    "teilzeit": "empPartTime",
    "частичная занятость": "empPartTime",
    "兼职": "empPartTime",
    "contrato": "empContract",
    "contract": "empContract",
    "contrat": "empContract",
    "contratto": "empContract",
    "vertrag": "empContract",
    "befristet": "empContract",
    "контракт": "empContract",
    "合同工": "empContract",
    "temporario": "empTemporary",
    "temporary": "empTemporary",
    "temporal": "empTemporary",
    "temporaire": "empTemporary",
    "temporaneo": "empTemporary",
    "zeitarbeit": "empTemporary",
    "временная": "empTemporary",
    "临时工": "empTemporary",
    "estagio": "empInternship",
    "internship": "empInternship",
    "practicas": "empInternship",
    "stage": "empInternship",
    "tirocinio": "empInternship",
    "praktikum": "empInternship",
    "стажировка": "empInternship",
    "实习": "empInternship",
    "voluntario": "empVolunteer",
    "volunteer": "empVolunteer",
    "voluntariado": "empVolunteer",
    "benevolat": "empVolunteer",
    "volontariato": "empVolunteer",
    "ehrenamt": "empVolunteer",
    "волонтерство": "empVolunteer",
    "志愿者": "empVolunteer",
    "outro": "empOther",
    "other": "empOther",
    "otro": "empOther",
    "autre": "empOther",
    "altro": "empOther",
    "sonstiges": "empOther",
    "другое": "empOther",
    "其他": "empOther",
  };

  const EXPERIENCE_CODE_KEYS = {
    internship: "lvlInternship",
    entry_level: "lvlEntryLevel",
    associate: "lvlAssociate",
    mid_senior: "lvlMidSenior",
    director: "lvlDirector",
    executive: "lvlExecutive",
    not_applicable: "lvlNotApplicable",
  };

  const EXPERIENCE_TEXT_MAP = {
    "estagio": "lvlInternship",
    "internship": "lvlInternship",
    "practicas": "lvlInternship",
    "stage": "lvlInternship",
    "tirocinio": "lvlInternship",
    "praktikum": "lvlInternship",
    "стажировка": "lvlInternship",
    "实习": "lvlInternship",
    "junior": "lvlEntryLevel",
    "entry level": "lvlEntryLevel",
    "sin experiencia": "lvlEntryLevel",
    "sin experiencia previa": "lvlEntryLevel",
    "debutant": "lvlEntryLevel",
    "livello base": "lvlEntryLevel",
    "einstiegsposition": "lvlEntryLevel",
    "начальный уровень": "lvlEntryLevel",
    "初级": "lvlEntryLevel",
    "assistente": "lvlAssociate",
    "associate": "lvlAssociate",
    "algo de responsabilidad": "lvlAssociate",
    "premier emploi": "lvlAssociate",
    "livello intermedio": "lvlAssociate",
    "mitarbeiter": "lvlAssociate",
    "специалист": "lvlAssociate",
    "助理": "lvlAssociate",
    "pleno-senior": "lvlMidSenior",
    "mid-senior level": "lvlMidSenior",
    "mid senior level": "lvlMidSenior",
    "intermedio": "lvlMidSenior",
    "confirme": "lvlMidSenior",
    "medio-alto": "lvlMidSenior",
    "mittleres management": "lvlMidSenior",
    "berufserfahren": "lvlMidSenior",
    "руководитель среднего звена": "lvlMidSenior",
    "中高级": "lvlMidSenior",
    "diretor": "lvlDirector",
    "director": "lvlDirector",
    "direttore": "lvlDirector",
    "direktor": "lvlDirector",
    "директор": "lvlDirector",
    "总监": "lvlDirector",
    "executivo": "lvlExecutive",
    "executive": "lvlExecutive",
    "ejecutivo": "lvlExecutive",
    "cadre dirigeant": "lvlExecutive",
    "dirigente": "lvlExecutive",
    "geschaftsfuhrung": "lvlExecutive",
    "руководитель": "lvlExecutive",
    "高管": "lvlExecutive",
    "nao aplicavel": "lvlNotApplicable",
    "not applicable": "lvlNotApplicable",
    "no aplicable": "lvlNotApplicable",
    "non applicable": "lvlNotApplicable",
    "non applicabile": "lvlNotApplicable",
    "nicht zutreffend": "lvlNotApplicable",
    "не применимо": "lvlNotApplicable",
    "不适用": "lvlNotApplicable",
  };

  function normalizeLookup(val) {
    return String(val || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function translateEmploymentType(job) {
    if (job.employment_type_code && EMPLOYMENT_CODE_KEYS[job.employment_type_code]) {
      return t(EMPLOYMENT_CODE_KEYS[job.employment_type_code]);
    }
    const raw =
      job["Tipo de emprego"] ||
      job["Employment type"] ||
      job["Tipo de empleo"] ||
      job["Type d'emploi"] ||
      job["Tipo di impiego"] ||
      job["Beschäftigungsart"] ||
      job["Тип занятости"] ||
      job["雇佣类型"] ||
      "";
    if (!raw) return "";
    const key = EMPLOYMENT_TEXT_MAP[normalizeLookup(raw)];
    return key ? t(key) : raw;
  }

  function translateExperienceLevel(job) {
    if (job.experience_level_code && EXPERIENCE_CODE_KEYS[job.experience_level_code]) {
      return t(EXPERIENCE_CODE_KEYS[job.experience_level_code]);
    }
    const raw =
      job["Nível de experiência"] ||
      job["Seniority level"] ||
      job["Nivel de antigüedad"] ||
      job["Niveau hiérarchique"] ||
      job["Livello di anzianità"] ||
      job["Karrierestufe"] ||
      job["Уровень"] ||
      job["Уровень опыта"] ||
      job["职级"] ||
      job["经验级别"] ||
      "";
    if (!raw) return "";
    const key = EXPERIENCE_TEXT_MAP[normalizeLookup(raw)];
    return key ? t(key) : raw;
  }

  function formatRelativeTime(rawTime) {
    if (!rawTime) return "";
    const normalized = String(rawTime).replace(/\u00a0/g, " ").trim();
    const lower = normalized.toLowerCase();

    if (/^(?:just now|agora(?: mesmo)?|ahora(?: mismo)?|à l'instant|proprio ora|gerade(?: eben)?|только что|刚刚|hoje|today|hoy|aujourd'hui|oggi|heute|сегодня|今天)$/i.test(lower)) {
      return t("timeJustNow");
    }
    if (/^(?:ontem|yesterday|ayer|hier|ieri|gestern|вчера|昨天)$/i.test(lower)) {
      return t("timeDaySingular");
    }

    const numMatch = lower.match(/\d+/);
    const n = numMatch ? parseInt(numMatch[0], 10) : 1;

    const unitRules = [
      { re: /\bmin(?:ut[eo]s?|uten?)?\b|минут|мин\.|分钟/i, singular: "timeMinuteSingular", plural: "timeMinutePlural" },
      { re: /\b(?:hora?s?|hours?|heures?|ore|stunden?)\b|час|小时/i, singular: "timeHourSingular", plural: "timeHourPlural" },
      { re: /\b(?:d[ií]as?|days?|jours?|giorn[io]|tag(?:en?)?)\b|день|дня|дней|дн\.|天/i, singular: "timeDaySingular", plural: "timeDayPlural" },
      { re: /\b(?:semanas?|weeks?|semaines?|settiman[ae]|wochen?)\b|недел|нед\.|周/i, singular: "timeWeekSingular", plural: "timeWeekPlural" },
      { re: /\b(?:m[eê]s(?:es)?|months?|mois|mes[ei]|monat(?:en?)?)\b|месяц|мес\.|个月|月/i, singular: "timeMonthSingular", plural: "timeMonthPlural" },
      { re: /\b(?:anos?|años?|years?|ans?|ann[ée]es?|ann[io]|jahr(?:en?)?)\b|год|года|лет|г\.|年/i, singular: "timeYearSingular", plural: "timeYearPlural" },
    ];

    for (const rule of unitRules) {
      if (rule.re.test(lower)) {
        return n === 1 ? t(rule.singular) : t(rule.plural, { n });
      }
    }
    return normalized;
  }

  function createJobCard(job, index = 0, isSeen = false) {
    const displayJob = getDisplayJob(job);
    const card = document.createElement("article");
    card.className = `result-card${isSeen ? " is-seen" : ""}`;
    const safeLink = getSafeUrl(job.link);

    if (safeLink !== "#") {
      card.style.cursor = "pointer";
      card.addEventListener("click", (e) => {
        if (e.target.closest("button, a")) return;
        markJobAsSeen(job.id, card);
        window.open(safeLink, "_blank", "noopener,noreferrer");
      });
    }

    const top = document.createElement("div");

    const kickerRow = document.createElement("div");
    kickerRow.className = "card-kicker-row";
    const kicker = document.createElement("span");
    kicker.className = "card-kicker";
    const employmentType = translateEmploymentType(job);
    kicker.textContent = `${String(index + 1).padStart(2, "0")} · ${employmentType || t("cardJobFallback")}`;
    kickerRow.appendChild(kicker);

    if (isSeen) {
      const seenBadge = document.createElement("span");
      seenBadge.className = "seen-badge";
      seenBadge.textContent = t("seenBadge");
      kickerRow.appendChild(seenBadge);
    }

    const header = document.createElement("div");
    header.className = "card-header";
    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = displayJob.title || t("cardTitleFallback");
    const company = document.createElement("p");
    company.className = "card-subtitle";
    company.textContent = job.company || t("cardCompanyFallback");
    header.append(title, company);

    const badges = document.createElement("div");
    badges.className = "card-badges";
    const formattedTime = formatRelativeTime(job.time);
    const experienceLevel = translateExperienceLevel(job);
    if (job.location) badges.appendChild(createMetaBadge("bi bi-geo-alt", job.location));
    if (formattedTime) badges.appendChild(createMetaBadge("bi bi-clock", formattedTime));
    if (experienceLevel) {
      badges.appendChild(createMetaBadge("bi bi-bar-chart", experienceLevel));
    }

    top.append(kickerRow, header);

    if (displayJob.description) {
      const excerpt = document.createElement("p");
      excerpt.className = "card-excerpt";
      excerpt.textContent = displayJob.description;
      top.appendChild(excerpt);
    }

    top.appendChild(badges);

    const actions = document.createElement("div");
    actions.className = "card-actions";

    const detailsBtn = document.createElement("button");
    detailsBtn.type = "button";
    detailsBtn.className = "btn btn-outline btn-sm";
    detailsBtn.textContent = t("btnDetails");
    detailsBtn.addEventListener("click", () => {
      markJobAsSeen(job.id, card);
      openJobModal(job);
    });

    const openLink = document.createElement("a");
    openLink.className = "btn btn-primary btn-sm";
    openLink.href = safeLink;
    openLink.target = "_blank";
    openLink.rel = "noopener noreferrer";
    openLink.textContent = t("btnOpenLinkedin");
    openLink.addEventListener("click", () => markJobAsSeen(job.id, card));

    actions.append(detailsBtn, openLink);
    card.append(top, actions);
    return card;
  }

  function openJobModal(job) {
    activeModalJob = job;
    const displayJob = getDisplayJob(job);
    modalTitle.textContent = displayJob.title || t("cardTitleFallback");
    modalCompany.textContent = job.company || "";
    modalBadges.innerHTML = "";
    const formattedTime = formatRelativeTime(job.time);
    const experienceLevel = translateExperienceLevel(job);
    const employmentType = translateEmploymentType(job);
    if (job.location) modalBadges.appendChild(createMetaBadge("bi bi-geo-alt", job.location));
    if (formattedTime) modalBadges.appendChild(createMetaBadge("bi bi-clock", formattedTime));
    if (experienceLevel) {
      modalBadges.appendChild(createMetaBadge("bi bi-bar-chart", experienceLevel));
    }
    if (employmentType) {
      modalBadges.appendChild(createMetaBadge("bi bi-briefcase", employmentType));
    }

    modalDescription.textContent = displayJob.description || t("modalNoDesc");
    modalLink.href = getSafeUrl(job.link);
    jobModal.style.display = "flex";
    ensureTranslations([job]);
  }

  function closeModal() {
    activeModalJob = null;
    jobModal.style.display = "none";
  }

  function updateCounts(visibleCount, totalCount = visibleCount) {
    const label = visibleCount === 1 ? t("jobSingular") : t("jobPlural");
    const text =
      visibleCount !== totalCount
        ? t("ofTotal", { visible: visibleCount, total: totalCount, label })
        : `${visibleCount} ${label}`;
    if (resultsCountText) resultsCountText.textContent = text;
    if (navbarResultsCount) navbarResultsCount.textContent = text;
  }

  function updateStatusBar(data) {
    lastStatusPayload = data;
    const pct = Math.round(data.progress || 0);
    const translatedStatus =
      data.status_code && I18N[currentLang]?.[data.status_code]
        ? t(data.status_code, data.status_params || {})
        : data.status_message || t("statusSearching");
    statusText.textContent = translatedStatus;
    statusPercent.textContent = `${pct}%`;
    progressBar.style.width = `${pct}%`;
  }

  function setSearching(searching) {
    isSearching = searching;
    searchBtn.disabled = searching;
    stopButton.style.display = searching ? "inline-flex" : "none";
    statusSection.style.display = searching ? "flex" : "none";
    if (searching) {
      lastCollectedCount = -1;
      lastStatusPayload = { status_code: "statusPreparing", status_params: {}, progress: 0 };
      statusText.textContent = t("statusPreparing");
      progressBar.style.width = "0%";
      statusPercent.textContent = "0%";
      searchResults = [];
      currentPage = 1;
      resultsGrid.innerHTML = "";
      resultsToolbar.style.display = "none";
      paginationBar.style.display = "none";
      emptyState.style.display = "flex";
    }
  }

  function setIdleState() {
    isSearching = false;
    searchBtn.disabled = false;
    stopButton.style.display = "none";
    statusSection.style.display = "none";
    if (pollTimeout) {
      clearTimeout(pollTimeout);
      pollTimeout = null;
    }
  }

  async function stopSearch() {
    if (pollTimeout) {
      clearTimeout(pollTimeout);
      pollTimeout = null;
    }
    try {
      await fetch("/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "jobs" }),
      });
    } catch (error) {
      showFeedback(error.message, null, {}, "errStop");
    } finally {
      setIdleState();
    }
  }
});
