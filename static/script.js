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
  const locationPreviewText = document.getElementById("location-preview-text");

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

  const statusSection = document.getElementById("status-section");
  const statusText = document.querySelector(".status-text");
  const statusPercent = document.getElementById("status-percent");
  const progressBar = document.getElementById("progress-bar");

  const logsContainer = document.getElementById("logs-container");
  const clearLogsButton = document.getElementById("clear-logs");

  const resultsGrid = document.getElementById("results-grid");
  let paginationBar = document.getElementById("pagination-bar");
  if (!paginationBar && resultsGrid && resultsGrid.parentNode) {
    paginationBar = document.createElement("nav");
    paginationBar.id = "pagination-bar";
    paginationBar.className = "pagination-bar";
    paginationBar.style.display = "none";
    resultsGrid.parentNode.insertBefore(paginationBar, resultsGrid.nextSibling);
  }
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

  const ITEMS_PER_PAGE = 9;
  const currentSearchType = "jobs";
  let isSearching = false;
  let searchResults = [];
  let currentPage = 1;
  let pollTimeout = null;

  // Event Listeners
  searchForm.addEventListener("submit", handleSearch);
  stopButton.addEventListener("click", stopSearch);
  resetFiltersBtn.addEventListener("click", resetFilters);
  clearLogsButton.addEventListener("click", (e) => {
    e.preventDefault();
    logsContainer.innerHTML = "";
    log("Logs limpos", "info");
  });

  quickFilterInput.addEventListener("input", () => {
    currentPage = 1;
    renderFilteredResults();
  });

  exportButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const format = btn.dataset.format;
      if (!searchResults.length) {
        log("Nenhum resultado disponível para exportar.", "warn");
        return;
      }
      window.location.href = `/export/${format}?type=${encodeURIComponent(currentSearchType)}`;
    });
  });

  document.querySelectorAll(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const target = document.getElementById(chip.dataset.target);
      if (target) {
        target.value = chip.dataset.value;
        target.focus();
      }
    });
  });

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
    updateLocationPreview();
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
    const country = countrySelect.value.trim();
    const state = stateSelect.value.trim();
    const city = cityInput.value.trim();
    return [city, state, country].filter(Boolean).join(", ");
  }

  function updateLocationPreview() {
    const country = countrySelect.value.trim();
    const state = stateSelect.value.trim();
    const city = cityInput.value.trim();
    const parts = [country, state, city].filter(Boolean);
    locationPreviewText.textContent = parts.length ? parts.join(" → ") : "Mundial (sem filtro de local)";
  }

  countrySelect.addEventListener("change", () => populateStates(countrySelect.value));
  stateSelect.addEventListener("change", () => {
    cityInput.value = "";
    populateCitySuggestions(countrySelect.value, stateSelect.value);
    updateLocationPreview();
  });
  cityInput.addEventListener("input", updateLocationPreview);

  initLocationCascade();

  closeModalBtn.addEventListener("click", closeModal);
  jobModal.addEventListener("click", (e) => {
    if (e.target === jobModal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && jobModal.style.display !== "none") closeModal();
  });

  function setSearchType(type) {
    currentSearchType = type;

    searchTypeButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.type === type);
    });

    jobFilters.style.display = type === "jobs" ? "flex" : "none";
    publicationFilters.style.display = type === "publications" ? "flex" : "none";
    peopleFilters.style.display = type === "people" ? "flex" : "none";
    locationGroup.style.display = type === "publications" ? "none" : "flex";

    if (type === "jobs") {
      keywordsLabel.textContent = "Cargo ou Palavra-chave";
      keywordsInput.placeholder = "Ex: Desenvolvedor Python, Estágio React, Dados...";
      searchBtnText.textContent = "Buscar Vagas";
    } else if (type === "publications") {
      keywordsLabel.textContent = "Tema da Publicação";
      keywordsInput.placeholder = "Ex: vaga python, contratando dev, tecnologia...";
      searchBtnText.textContent = "Buscar Publicações";
    } else {
      keywordsLabel.textContent = "Cargo ou Perfil";
      keywordsInput.placeholder = "Ex: Tech Recruiter, CTO, Head de Engenharia...";
      searchBtnText.textContent = "Buscar Pessoas";
    }

    updateCounts(0);
    searchResults = [];
    resultsGrid.innerHTML = "";
    emptyState.style.display = "flex";
  }

  function resetFilters() {
    searchForm.reset();
    initLocationCascade();
    quickFilterInput.value = "";
    log("Filtros restaurados para o padrão.", "info");
  }

  function log(message, type = "info") {
    const timestamp = new Date().toLocaleTimeString("pt-BR");
    const entry = document.createElement("div");
    entry.className = `log-entry ${type}`;

    const tsSpan = document.createElement("span");
    tsSpan.className = "log-timestamp";
    tsSpan.textContent = timestamp;

    const typeSpan = document.createElement("span");
    typeSpan.className = `log-type ${type}`;
    typeSpan.textContent = type;

    const msgSpan = document.createElement("span");
    msgSpan.className = "log-message";
    msgSpan.textContent = message;

    entry.append(tsSpan, typeSpan, msgSpan);
    logsContainer.insertBefore(entry, logsContainer.firstChild);
  }

  function getFormData() {
    const formData = new FormData(searchForm);
    const keywords = (formData.get("keywords") || "").trim();
    const location = buildLocationString();

    if (currentSearchType === "jobs") {
      const jobType = formData.get("job_type");
      const place = formData.get("place");
      const expLevel = formData.get("experience_level");
      const easyApply = formData.get("easy_apply") === "true";
      return {
        type: "jobs",
        keywords,
        location,
        max_date: formData.get("job_max_date") || "r7d",
        sort_by: formData.get("sort_by") || "DD",
        distance: formData.get("distance") || "",
        job_type: jobType ? [jobType] : [],
        place: place ? [place] : [],
        experience_level: expLevel ? [expLevel] : [],
        easy_apply: easyApply,
        limit_jobs: 100,
      };
    }

    if (currentSearchType === "publications") {
      return {
        type: "publications",
        keywords,
        max_date: formData.get("pub_max_date") || "past-week",
        limit_publications: Number(formData.get("limit_publications") || 50),
      };
    }

    return {
      type: "people",
      keywords,
      location,
      hiring_only: hiringOnlyCheckbox.checked,
      hiring_keywords: (hiringKeywordsInput.value || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      limit_people: Number(formData.get("limit_people") || 50),
    };
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (isSearching) {
      log("Já existe uma busca em andamento.", "warn");
      return;
    }

    const searchData = getFormData();
    if (!searchData.keywords) {
      log("Informe uma palavra-chave para iniciar a busca.", "error");
      return;
    }

    try {
      setSearching(true);
      log(`Iniciando busca (${currentSearchType}): ${searchData.keywords}`);

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
      log(`Erro: ${error.message}`, "error");
      setIdleState();
    }
  }

  async function pollResults() {
    try {
      const response = await fetch(`/status?type=${encodeURIComponent(currentSearchType)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Falha ao consultar status");

      updateStatusBar(data);
      await fetchResults();

      if (data.status === "complete" || data.progress === 100) {
        log(data.status_message || "Busca concluída!", "success");
        setIdleState();
      } else if (data.status === "error") {
        log(data.status_message || "Erro durante a busca.", "error");
        setIdleState();
      } else if (data.status === "stopped" || !data.is_searching) {
        log(data.status_message || "Busca interrompida.", "warn");
        setIdleState();
      } else {
        pollTimeout = setTimeout(pollResults, 900);
      }
    } catch (error) {
      log(`Erro de comunicação: ${error.message}`, "error");
      setIdleState();
    }
  }

  async function fetchResults() {
    const response = await fetch(`/results?type=${encodeURIComponent(currentSearchType)}`);
    if (!response.ok) return;
    const data = await response.json();
    searchResults = Array.isArray(data) ? data : [];
    renderFilteredResults();
  }

  function renderFilteredResults() {
    const term = quickFilterInput.value.trim().toLowerCase();
    const filtered = !term
      ? searchResults
      : searchResults.filter((item) => {
          const haystack = [
            item.title,
            item.company,
            item.location,
            item.author,
            item.name,
            item.headline,
            item.description,
          ]
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
      if (searchResults.length > 0 && term) {
        h3.textContent = "Nenhum card corresponde ao filtro rápido";
        p.textContent = `Tente limpar o filtro "${quickFilterInput.value}" para ver todos os ${searchResults.length} resultados.`;
      } else if (isSearching) {
        h3.textContent = "Coletando resultados...";
        p.textContent = "Os cards aparecerão aqui conforme forem encontrados.";
      } else {
        h3.textContent = "Nenhum resultado para exibir";
        p.textContent = "Configure os filtros acima e clique em Buscar Vagas.";
      }
      return;
    }

    emptyState.style.display = "none";
    const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
    if (currentPage > totalPages) currentPage = totalPages;

    const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
    const pageItems = filtered.slice(startIdx, startIdx + ITEMS_PER_PAGE);

    pageItems.forEach((item, idx) => {
      resultsGrid.appendChild(createJobCard(item, startIdx + idx));
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

  function attachCardNavigation(card, url) {
    if (!url || url === "#") return;
    card.style.cursor = "pointer";
    card.addEventListener("click", (e) => {
      if (e.target.closest("button, a")) return;
      window.open(url, "_blank", "noopener,noreferrer");
    });
  }

  function createJobCard(job, index = 0) {
    const card = document.createElement("article");
    card.className = "result-card";
    attachCardNavigation(card, job.link);

    const top = document.createElement("div");

    const kicker = document.createElement("div");
    kicker.className = "card-kicker";
    const num = String(index + 1).padStart(2, "0");
    kicker.textContent = `${num} · ${job["Tipo de emprego"] || "VAGA"}`;

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

    top.append(kicker, header);

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
    detailsBtn.addEventListener("click", () => openJobModal(job));

    const openLink = document.createElement("a");
    openLink.className = "card-action-link";
    openLink.href = job.link || "#";
    openLink.target = "_blank";
    openLink.rel = "noopener noreferrer";
    openLink.textContent = "ver no linkedin ↗";

    actions.append(detailsBtn, openLink);
    card.append(top, actions);
    return card;
  }

  function createPublicationCard(pub, index = 0) {
    const card = document.createElement("article");
    card.className = "result-card";
    attachCardNavigation(card, pub.link);

    const top = document.createElement("div");
    const kicker = document.createElement("div");
    kicker.className = "card-kicker";
    kicker.textContent = `${String(index + 1).padStart(2, "0")} · PUBLICAÇÃO`;

    const header = document.createElement("div");
    header.className = "card-header";
    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = pub.title || "Publicação LinkedIn";
    const author = document.createElement("p");
    author.className = "card-subtitle";
    author.textContent = pub.author || "Autor LinkedIn";
    header.append(title, author);

    const excerpt = document.createElement("p");
    excerpt.className = "card-excerpt";
    excerpt.textContent = pub.content || "";
    top.append(kicker, header, excerpt);

    const actions = document.createElement("div");
    actions.className = "card-actions";
    const openLink = document.createElement("a");
    openLink.className = "card-action-link";
    openLink.href = pub.link || "#";
    openLink.target = "_blank";
    openLink.rel = "noopener noreferrer";
    openLink.textContent = "abrir no linkedin ↗";

    actions.append(openLink);
    card.append(top, actions);
    return card;
  }

  function createPersonCard(person, index = 0) {
    const card = document.createElement("article");
    card.className = "result-card";
    attachCardNavigation(card, person.link);

    const top = document.createElement("div");
    const kicker = document.createElement("div");
    kicker.className = "card-kicker";
    kicker.textContent = `${String(index + 1).padStart(2, "0")} · PERFIL`;

    const header = document.createElement("div");
    header.className = "card-header";
    const name = document.createElement("h3");
    name.className = "card-title";
    name.textContent = person.name || "Perfil LinkedIn";
    const headline = document.createElement("p");
    headline.className = "card-excerpt";
    headline.textContent = person.headline || "";
    header.append(name, headline);

    const badges = document.createElement("div");
    badges.className = "card-badges";
    badges.appendChild(createMetaBadge("bi bi-geo-alt", person.location || "Brasil"));
    top.append(kicker, header, badges);

    const actions = document.createElement("div");
    actions.className = "card-actions";
    const openLink = document.createElement("a");
    openLink.className = "card-action-link";
    openLink.href = person.link || "#";
    openLink.target = "_blank";
    openLink.rel = "noopener noreferrer";
    openLink.textContent = "ver perfil ↗";

    actions.append(openLink);
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
    const labelMap = {
      jobs: visibleCount === 1 ? "vaga" : "vagas",
      publications: visibleCount === 1 ? "publicação" : "publicações",
      people: visibleCount === 1 ? "perfil" : "perfis",
    };
    const suffix = labelMap[currentSearchType] || "resultados";
    const text =
      visibleCount !== totalCount
        ? `${visibleCount} de ${totalCount} ${suffix}`
        : `${visibleCount} ${suffix}`;
    resultsCountText.textContent = text;
    navbarResultsCount.textContent = text;
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
        body: JSON.stringify({ type: currentSearchType }),
      });
      log("Solicitação de parada enviada.", "warn");
    } catch (error) {
      log(`Erro ao parar busca: ${error.message}`, "error");
    } finally {
      setIdleState();
    }
  }
});
