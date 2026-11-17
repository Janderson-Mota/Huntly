document.addEventListener("DOMContentLoaded", () => {
  const searchForm = document.getElementById("search-form");
  const searchBtn = document.getElementById("search-btn");
  const stopButton = document.getElementById("stop-button");
  const resetFiltersBtn = document.getElementById("reset-filters-btn");

  const keywordsInput = document.getElementById("keywords");
  const recentSearchesEl = document.getElementById("recent-searches");
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

  const STORAGE_KEYS = {
    filters: "huntly_last_filters",
    recentKeywords: "huntly_recent_keywords",
    seenJobs: "huntly_seen_jobs",
  };

  const ITEMS_PER_PAGE = 9;
  let isSearching = false;
  let searchResults = [];
  let currentPage = 1;
  let pollTimeout = null;

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
        badge.textContent = "vista ✓";
        kickerRow.appendChild(badge);
      }
    }
  }

  function saveRecentKeyword(keyword) {
    const clean = keyword.trim();
    if (!clean) return;
    const current = readStorage(STORAGE_KEYS.recentKeywords, []).filter(
      (item) => item.toLowerCase() !== clean.toLowerCase()
    );
    const updated = [clean, ...current].slice(0, 5);
    writeStorage(STORAGE_KEYS.recentKeywords, updated);
    renderRecentKeywords();
  }

  function renderRecentKeywords() {
    const recent = readStorage(STORAGE_KEYS.recentKeywords, []);
    recentSearchesEl.innerHTML = "";
    if (!recent.length) {
      recentSearchesEl.style.display = "none";
      return;
    }
    recentSearchesEl.style.display = "flex";
    const label = document.createElement("span");
    label.className = "chip-label";
    label.textContent = "Recentes:";
    recentSearchesEl.appendChild(label);

    recent.forEach((kw) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "suggestion-chip";
      btn.textContent = kw;
      btn.addEventListener("click", () => {
        keywordsInput.value = kw;
        keywordsInput.focus();
      });
      recentSearchesEl.appendChild(btn);
    });
  }

  function saveCurrentFilters() {
    const formData = new FormData(searchForm);
    writeStorage(STORAGE_KEYS.filters, {
      keywords: formData.get("keywords") || "",
      country: countrySelect.value,
      state: stateSelect.value,
      city: cityInput.value,
      job_max_date: formData.get("job_max_date") || "r7d",
      experience_level: formData.get("experience_level") || "",
      place: formData.get("place") || "",
      job_type: formData.get("job_type") || "",
      distance: formData.get("distance") || "",
      sort_by: formData.get("sort_by") || "DD",
      easy_apply: formData.get("easy_apply") || "",
    });
  }

  function restoreSavedFilters() {
    const saved = readStorage(STORAGE_KEYS.filters, null);
    if (!saved) return;

    if (saved.keywords) keywordsInput.value = saved.keywords;
    if (saved.country !== undefined) {
      countrySelect.value = saved.country;
      populateStates(saved.country);
    }
    if (saved.state) {
      stateSelect.value = saved.state;
      populateCitySuggestions(countrySelect.value, saved.state);
    }
    if (saved.city) cityInput.value = saved.city;

    ["job_max_date", "experience_level", "place", "job_type", "distance", "sort_by", "easy_apply"].forEach(
      (field) => {
        const el = document.getElementById(field);
        if (el && saved[field] !== undefined) el.value = saved[field];
      }
    );
  }

  function initLocationCascade() {
    countrySelect.innerHTML = "";
    Object.keys(LOCATION_DATA).forEach((country) => {
      const opt = document.createElement("option");
      opt.value = country;
      opt.textContent = country;
      countrySelect.appendChild(opt);
    });
    const worldwideOpt = document.createElement("option");
    worldwideOpt.value = "";
    worldwideOpt.textContent = "Qualquer país (Mundial)";
    countrySelect.appendChild(worldwideOpt);

    countrySelect.value = "Brasil";
    populateStates("Brasil");
  }

  function populateStates(country) {
    stateSelect.innerHTML = "";
    const allStatesOpt = document.createElement("option");
    allStatesOpt.value = "";
    allStatesOpt.textContent = country ? "Todos os estados" : "Selecione um país";
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

  initLocationCascade();
  restoreSavedFilters();
  renderRecentKeywords();

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
      max_date: formData.get("job_max_date") || "r7d",
      sort_by: formData.get("sort_by") || "DD",
      distance: formData.get("distance") || "",
      job_type: jobType ? [jobType] : [],
      place: place ? [place] : [],
      experience_level: expLevel ? [expLevel] : [],
      easy_apply: formData.get("easy_apply") === "true",
      limit_jobs: 100,
    };
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (isSearching) return;

    const searchData = getFormData();
    if (!searchData.keywords) {
      showFeedback("Informe um cargo ou palavra-chave para iniciar a busca.");
      return;
    }

    showFeedback("");
    saveCurrentFilters();
    saveRecentKeyword(searchData.keywords);

    try {
      setSearching(true);
      const response = await fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(searchData),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Falha ao iniciar busca");
      }

      pollResults();
    } catch (error) {
      showFeedback(`Erro: ${error.message}`);
      setIdleState();
    }
  }

  async function pollResults() {
    try {
      const response = await fetch("/status?type=jobs");
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Falha ao consultar status");

      updateStatusBar(data);
      await fetchResults();

      if (data.status === "complete" || data.progress === 100) {
        setIdleState();
      } else if (data.status === "error") {
        showFeedback(data.status_message || "Ocorreu um erro durante a busca.");
        setIdleState();
      } else if (data.status === "stopped" || !data.is_searching) {
        setIdleState();
      } else {
        pollTimeout = setTimeout(pollResults, 900);
      }
    } catch (error) {
      showFeedback(`Erro de comunicação: ${error.message}`);
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
        h3.textContent = "Nenhum card corresponde ao filtro rápido";
        p.textContent = `Tente limpar o filtro "${quickFilterInput.value}" para ver todas as ${searchResults.length} vagas.`;
      } else if (isSearching) {
        h3.textContent = "Coletando vagas...";
        p.textContent = "Os cards aparecerão aqui conforme forem encontrados.";
      } else {
        h3.textContent = "Nenhuma vaga para exibir";
        p.textContent = "Configure os filtros acima e clique em Buscar Vagas.";
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
    info.textContent = `Mostrando ${startItem}–${endItem} de ${totalItems} vagas (página ${currentPage} de ${totalPages})`;

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
    prevBtn.textContent = "← anterior";
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
    nextBtn.textContent = "próxima →";
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

  function createJobCard(job, index = 0, isSeen = false) {
    const card = document.createElement("article");
    card.className = `result-card${isSeen ? " is-seen" : ""}`;

    if (job.link && job.link !== "#") {
      card.style.cursor = "pointer";
      card.addEventListener("click", (e) => {
        if (e.target.closest("button, a")) return;
        markJobAsSeen(job.id, card);
        window.open(job.link, "_blank", "noopener,noreferrer");
      });
    }

    const top = document.createElement("div");

    const kickerRow = document.createElement("div");
    kickerRow.className = "card-kicker-row";
    const kicker = document.createElement("span");
    kicker.className = "card-kicker";
    kicker.textContent = `${String(index + 1).padStart(2, "0")} · ${job["Tipo de emprego"] || "VAGA"}`;
    kickerRow.appendChild(kicker);

    if (isSeen) {
      const seenBadge = document.createElement("span");
      seenBadge.className = "seen-badge";
      seenBadge.textContent = "vista ✓";
      kickerRow.appendChild(seenBadge);
    }

    const header = document.createElement("div");
    header.className = "card-header";
    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = job.title || "Título não disponível";
    const company = document.createElement("p");
    company.className = "card-subtitle";
    company.textContent = job.company || "Empresa não informada";
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
    detailsBtn.className = "card-action-link";
    detailsBtn.textContent = "ver detalhes ↗";
    detailsBtn.addEventListener("click", () => {
      markJobAsSeen(job.id, card);
      openJobModal(job);
    });

    const openLink = document.createElement("a");
    openLink.className = "card-action-link";
    openLink.href = job.link || "#";
    openLink.target = "_blank";
    openLink.rel = "noopener noreferrer";
    openLink.textContent = "ver no linkedin ↗";
    openLink.addEventListener("click", () => markJobAsSeen(job.id, card));

    actions.append(detailsBtn, openLink);
    card.append(top, actions);
    return card;
  }

  function openJobModal(job) {
    modalTitle.textContent = job.title || "Vaga LinkedIn";
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

    modalDescription.textContent = job.description || "Descrição não disponível.";
    modalLink.href = job.link || "#";
    jobModal.style.display = "flex";
  }

  function closeModal() {
    jobModal.style.display = "none";
  }

  function updateCounts(visibleCount, totalCount = visibleCount) {
    const suffix = visibleCount === 1 ? "vaga" : "vagas";
    const text =
      visibleCount !== totalCount
        ? `${visibleCount} de ${totalCount} ${suffix}`
        : `${visibleCount} ${suffix}`;
    if (resultsCountText) resultsCountText.textContent = text;
    if (navbarResultsCount) navbarResultsCount.textContent = text;
  }

  function updateStatusBar(data) {
    const pct = Math.round(data.progress || 0);
    statusText.textContent = data.status_message || "Buscando...";
    statusPercent.textContent = `${pct}%`;
    progressBar.style.width = `${pct}%`;
  }

  function setSearching(searching) {
    isSearching = searching;
    searchBtn.disabled = searching;
    stopButton.style.display = searching ? "inline-flex" : "none";
    statusSection.style.display = searching ? "flex" : "none";
    if (searching) {
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
      showFeedback(`Erro ao parar busca: ${error.message}`);
    } finally {
      setIdleState();
    }
  }
});
