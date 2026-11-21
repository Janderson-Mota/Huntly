document.addEventListener("DOMContentLoaded", () => {
  const searchForm = document.getElementById("search-form");
  const searchBtn = document.getElementById("search-btn");
  const stopButton = document.getElementById("stop-button");
  const resetFiltersBtn = document.getElementById("reset-filters-btn");

  const keywordsInput = document.getElementById("keywords");
  const countrySelect = document.getElementById("country");
  const stateSelect = document.getElementById("state");
  const cityInput = document.getElementById("city");
  const cityDatalist = document.getElementById("city-suggestions");

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
  const exportButtons = document.querySelectorAll(".export-btn");

  const jobModal = document.getElementById("job-modal");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const modalTitle = document.getElementById("modal-title");
  const modalCompany = document.getElementById("modal-company");
  const modalBadges = document.getElementById("modal-badges");
  const modalDescription = document.getElementById("modal-description");
  const modalLink = document.getElementById("modal-link");

  const LOCATION_DATA = {
    Brasil: {
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
    filters: "huntly_last_filters",
    recentKeywords: "huntly_recent_keywords",
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

    if (countrySelect && countrySelect.options.length > 0) {
      countrySelect.options[0].textContent = t("allCountries");
    }
    if (stateSelect && stateSelect.options.length > 0) {
      stateSelect.options[0].textContent = countrySelect.value ? t("allStates") : t("selectCountryFirst");
    }

    renderFilteredResults();
  }

  const ITEMS_PER_PAGE = 9;
  let isSearching = false;
  let searchResults = [];
  let currentPage = 1;
  let pollTimeout = null;
  let lastCollectedCount = -1;

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

  function saveCurrentFilters() {
    const formData = new FormData(searchForm);
    writeStorage(STORAGE_KEYS.filters, {
      keywords: formData.get("keywords") || "",
      country: countrySelect.value,
      state: stateSelect.value,
      city: cityInput.value,
      job_max_date: formData.get("job_max_date") || "",
      experience_level: formData.get("experience_level") || "",
      place: formData.get("place") || "",
      job_type: formData.get("job_type") || "",
    });
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
      opt.textContent = country;
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

  exportButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!searchResults.length) return;
      window.location.href = `/export/${btn.dataset.format}?type=jobs`;
    });
  });

  closeModalBtn.addEventListener("click", closeModal);
  jobModal.addEventListener("click", (e) => {
    if (e.target === jobModal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && jobModal.style.display !== "none") closeModal();
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

  function showFeedback(message) {
    if (!message) {
      feedbackBanner.style.display = "none";
      feedbackBanner.textContent = "";
      return;
    }
    feedbackBanner.textContent = message;
    feedbackBanner.style.display = "block";
  }

  function resetFilters() {
    searchForm.reset();
    initLocationCascade();
    quickFilterInput.value = "";
    localStorage.removeItem(STORAGE_KEYS.filters);
    showFeedback("");
  }

  function getFormData() {
    const formData = new FormData(searchForm);
    const jobType = formData.get("job_type");
    const place = formData.get("place");
    const expLevel = formData.get("experience_level");
    return {
      type: "jobs",
      keywords: (formData.get("keywords") || "").trim(),
      location: buildLocationString(),
      max_date: formData.get("job_max_date") || "",
      sort_by: "",
      distance: "",
      job_type: jobType ? [jobType] : [],
      place: place ? [place] : [],
      experience_level: expLevel ? expLevel.split(",") : [],
      easy_apply: false,
      limit_jobs: 100,
    };
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (isSearching) return;

    const searchData = getFormData();
    if (!searchData.keywords) {
      showFeedback(t("errNoKeyword"));
      return;
    }

    showFeedback("");
    saveCurrentFilters();

    try {
      setSearching(true);
      const response = await fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(searchData),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || t("errGeneric"));
      }

      pollResults();
    } catch (error) {
      showFeedback(`${t("errPrefix")}${error.message}`);
      setIdleState();
    }
  }

  async function pollResults() {
    try {
      const response = await fetch("/status?type=jobs&include_results=0");
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || t("errGeneric"));

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
        showFeedback(data.status_message || t("errGeneric"));
        setIdleState();
      } else if (data.status === "stopped" || !data.is_searching) {
        setIdleState();
      } else {
        pollTimeout = setTimeout(pollResults, 900);
      }
    } catch (error) {
      showFeedback(`${t("errComm")}${error.message}`);
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

    const term = quickFilterInput.value.trim().toLowerCase();
    const filtered = !term
      ? searchResults
      : searchResults.filter((item) => {
          const haystack = [item.title, item.company, item.location, item.description]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return haystack.includes(term);
        });

    updateCounts(filtered.length, searchResults.length);
    resultsGrid.innerHTML = "";

    if (filtered.length === 0) {
      paginationBar.style.display = "none";
      emptyState.style.display = "flex";
      const h3 = emptyState.querySelector("h3");
      const p = emptyState.querySelector("p");
      if (hasResults && term) {
        h3.textContent = t("emptyNoMatchTitle");
        p.textContent = t("emptyNoMatchDesc", { term: quickFilterInput.value, total: searchResults.length });
      } else if (isSearching) {
        h3.textContent = t("emptyCollectingTitle");
        p.textContent = t("emptyCollectingDesc");
      } else if (searchResults.length === 0 && !quickFilterInput.value) {
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

  function createJobCard(job, index = 0, isSeen = false) {
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
    kicker.textContent = `${String(index + 1).padStart(2, "0")} · ${job["Tipo de emprego"] || t("cardJobFallback")}`;
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
    title.textContent = job.title || t("cardTitleFallback");
    const company = document.createElement("p");
    company.className = "card-subtitle";
    company.textContent = job.company || t("cardCompanyFallback");
    header.append(title, company);

    const badges = document.createElement("div");
    badges.className = "card-badges";
    if (job.location) badges.appendChild(createMetaBadge("bi bi-geo-alt", job.location));
    if (job.time) badges.appendChild(createMetaBadge("bi bi-clock", job.time));
    if (job["Nível de experiência"]) {
      badges.appendChild(createMetaBadge("bi bi-bar-chart", job["Nível de experiência"]));
    }

    top.append(kickerRow, header);

    if (job.description) {
      const excerpt = document.createElement("p");
      excerpt.className = "card-excerpt";
      excerpt.textContent = job.description;
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
    modalTitle.textContent = job.title || t("cardTitleFallback");
    modalCompany.textContent = job.company || "";
    modalBadges.innerHTML = "";
    if (job.location) modalBadges.appendChild(createMetaBadge("bi bi-geo-alt", job.location));
    if (job.time) modalBadges.appendChild(createMetaBadge("bi bi-clock", job.time));
    if (job["Nível de experiência"]) {
      modalBadges.appendChild(createMetaBadge("bi bi-bar-chart", job["Nível de experiência"]));
    }
    if (job["Tipo de emprego"]) {
      modalBadges.appendChild(createMetaBadge("bi bi-briefcase", job["Tipo de emprego"]));
    }

    modalDescription.textContent = job.description || t("modalNoDesc");
    modalLink.href = getSafeUrl(job.link);
    jobModal.style.display = "flex";
  }

  function closeModal() {
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
    const pct = Math.round(data.progress || 0);
    statusText.textContent = data.status_message || t("statusSearching");
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
      showFeedback(`${t("errStop")}${error.message}`);
    } finally {
      setIdleState();
    }
  }
});
