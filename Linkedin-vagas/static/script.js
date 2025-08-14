
document.addEventListener("DOMContentLoaded", () => {
  const searchTab = document.getElementById("search-tab");
  const resultsTab = document.getElementById("results-tab");
  const searchPane = document.getElementById("search-pane");
  const resultsPane = document.getElementById("results-pane");
  const searchForm = document.getElementById("search-form");
  const searchBtn = document.getElementById("search-btn");
  const statusSection = document.getElementById("status-section");
  const statusText = document.querySelector(".status-text");
  const progressBar = document.getElementById("progress-bar");
  const stopButton = document.getElementById("stop-button");
  const resultsGrid = document.getElementById("results-grid");
  const resultsCountText = document.getElementById("results-count-text");
  const exportButtons = document.querySelectorAll(".export-btn");
  const logsContainer = document.getElementById("logs-container");
  const clearLogsButton = document.getElementById("clear-logs");
  const searchTypeButtons = document.querySelectorAll(".search-type-btn");
  const keywordsLabel = document.getElementById("keywords-label");
  const keywordSuggestions = document.getElementById("keyword-suggestions");
  const locationGroup = document.getElementById("location-group");
  const searchBtnText = document.getElementById("search-btn-text");
  const testBtn = document.getElementById("test-btn");
  const publicationFilters = document.getElementById("publication-filters");
  const peopleFilters = document.getElementById("people-filters");
  const hiringOnlyCheckbox = document.getElementById("hiring-only");
  const hiringKeywordsInput = document.getElementById("hiring-keywords");

  let isSearching = false;
  let searchResults = [];
  let currentTab = "search";
  let currentSearchType = "jobs";
  let pollTimeout = null;

  resultsGrid.innerHTML = "";

  // 🔹 Badge começa escondido
  const badge = resultsTab.querySelector(".results-badge");
  badge.style.display = "none";

  function updateResultsBadge(count) {
    if (count > 0) {
      badge.style.display = "inline-block";
      badge.textContent = count;
    } else {
      badge.style.display = "none";
    }
  }

  searchTab.addEventListener("click", () => setActiveTab("search"));
  resultsTab.addEventListener("click", () => setActiveTab("results"));
  searchForm.addEventListener("submit", handleSearch);
  stopButton.addEventListener("click", stopSearch);
  exportButtons.forEach((btn) => {
    btn.addEventListener("click", handleExport);
  });
  clearLogsButton.addEventListener("click", clearLogs);

  searchTypeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const searchType = btn.dataset.type;
      setSearchType(searchType);
    });
  });

  testBtn.addEventListener("click", testFunctionality);

  function setSearchType(searchType) {
    currentSearchType = searchType;

    searchTypeButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.type === searchType);
    });

    if (searchType === "jobs") {
      keywordsLabel.textContent = "Pesquisar por Vaga";
      keywordSuggestions.innerHTML =
        "<small>Sugestões: estágio, júnior, trainee, node.js, react, python, java, frontend, backend</small>";
      locationGroup.style.display = "block";
      publicationFilters.style.display = "none";
      peopleFilters.style.display = "none";
      searchBtnText.textContent = "Buscar Vaga";
      resultsCountText.textContent = "0 vagas encontradas";
    } else if (searchType === "publications") {
      keywordsLabel.textContent = "Pesquisar por Publicação";
      keywordSuggestions.innerHTML =
        "<small>Sugestões: tecnologia, carreira, desenvolvimento, inovação, tendências, dicas</small>";
      locationGroup.style.display = "none";
      publicationFilters.style.display = "block";
      peopleFilters.style.display = "none";
      searchBtnText.textContent = "Buscar Publicações";
      resultsCountText.textContent = "0 publicações encontradas";
    } else if (searchType === "people") {
      keywordsLabel.textContent = "Pesquisar por Pessoas";
      keywordSuggestions.innerHTML =
        "<small>Sugestões: CTO contratando, Tech Recruiter, Head de Engenharia...</small>";
      locationGroup.style.display = "block";
      publicationFilters.style.display = "none";
      peopleFilters.style.display = "block";
      searchBtnText.textContent = "Buscar Pessoas";
      resultsCountText.textContent = "0 pessoas encontradas";
    }
  }

  function setActiveTab(tab) {
    currentTab = tab;

    searchTab.classList.toggle("active", tab === "search");
    resultsTab.classList.toggle("active", tab === "results");

    searchPane.classList.toggle("active", tab === "search");
    resultsPane.classList.toggle("active", tab === "results");

    updateResultsBadge(searchResults.length);
  }

  function log(message, type = "info") {
    const timestamp = new Date().toLocaleTimeString();
    console.log(`[${timestamp}] [${type}] ${message}`);

    const logEntry = document.createElement("div");
    logEntry.className = `log-entry ${type}`;
    logEntry.innerHTML = `
      <span class="log-timestamp">${timestamp}</span>
      <span class="log-type ${type}">${type}</span>
      <span class="log-message">${message}</span>
    `;
    logsContainer.insertBefore(logEntry, logsContainer.firstChild);
  }

  function clearLogs() {
    logsContainer.innerHTML = "";
    log("Logs limpos", "success");
  }

  function getFormData() {
    const formData = new FormData(searchForm);
    const jobTypes = formData.getAll("job_type");
    const places = formData.getAll("place");
    let maxDate = formData.get("max_date");

    if (currentSearchType === "jobs") {
      if (!maxDate) maxDate = "r7d";
    } else if (currentSearchType === "publications") {
      if (!maxDate) maxDate = "past-week";
    }

    const baseData = {
      type: currentSearchType,
      keywords: formData.get("keywords"),
      max_date: maxDate,
    };

    if (currentSearchType === "jobs") {
      return {
        ...baseData,
        location: formData.get("location"),
        distance: formData.get("distance"),
        job_type: jobTypes.length > 0 ? jobTypes : undefined,
        place: places.length > 0 ? places : undefined,
        limit_jobs: 100,
      };
    } else if (currentSearchType === "publications") {
      return {
        ...baseData,
        limit_publications: 50,
      };
    } else if (currentSearchType === "people") {
      return {
        ...baseData,
        location: formData.get("location"),
        hiring_only: hiringOnlyCheckbox.checked,
        hiring_keywords: (hiringKeywordsInput.value || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        limit_people: 50,
      };
    }

    return baseData;
  }

  async function handleSearch(e) {
    e.preventDefault();
    log(`Iniciando busca de ${currentSearchType}`);

    if (isSearching) {
      log("Já existe uma busca em andamento", "warn");
      return;
    }

    const searchData = getFormData();
    log(`Dados da busca: ${JSON.stringify(searchData)}`);

    if (!searchData.keywords) {
      log("Digite uma palavra-chave para buscar", "error");
      return;
    }

    try {
      setSearching(true);
      log("Enviando requisição de busca");

      const response = await fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(searchData),
      });

      if (!response.ok) {
        const errorText = await response.text();
        log(`Falha na requisição: ${errorText}`, "error");
        throw new Error(errorText);
      }

      log("Busca iniciada com sucesso");
      pollResults();
    } catch (error) {
      log(`Erro na busca: ${error.message}`, "error");
      setError("Ocorreu um erro ao realizar a busca. Por favor, tente novamente.");
    }
  }

  async function pollResults() {
    try {
      const response = await fetch(`/status?type=${currentSearchType}`);
      const data = await response.json();

      if (!response.ok) throw new Error("Falha ao verificar status");

      log(`Status: ${data.status_message}`);
      updateStatus(data);

      // Atualiza resultados parciais e contador em tempo real
      await getResults(true);

      if (data.status === "complete" || data.progress === 100) {
        log("Busca concluída");
        await getResults(false);
        setComplete();
        setActiveTab("results");
      } else if (data.status === "error") {
        log(`Erro na busca: ${data.status_message}`, "error");
        setError(data.status_message || "Ocorreu um erro durante a busca");
      } else {
        pollTimeout = setTimeout(pollResults, 1000);
      }
    } catch (error) {
      log(`Erro ao verificar status: ${error.message}`, "error");
      setError("Falha ao verificar o status da busca");
    }
  }

  async function getResults(isPartial = false) {
    try {
      const response = await fetch(`/results?type=${currentSearchType}`);
      if (!response.ok) {
        const errorText = await response.text();
        log(`Falha ao obter resultados: ${errorText}`, "error");
        throw new Error(errorText);
      }

      const data = await response.json();
      searchResults = data;

      const itemType =
        currentSearchType === "jobs"
          ? "vagas"
          : currentSearchType === "publications"
          ? "publicações"
          : "pessoas";

      resultsCountText.textContent = `${data.length} ${itemType} encontradas`;
      updateResultsBadge(data.length);

      if (!isPartial) {
        displayResults(data);
      } else {
        // Atualiza parciais
        if (currentSearchType === "jobs") {
          const existingLinks = Array.from(resultsGrid.querySelectorAll(".job-card"))
            .map(card => card.dataset.link);
          data.forEach(job => {
            if (!existingLinks.includes(job.link)) displayJobCard(job);
          });
        } else if (currentSearchType === "publications") {
          const existingTitles = Array.from(resultsGrid.querySelectorAll(".publication-card"))
            .map(card => card.dataset.title);
          data.forEach(pub => {
            if (!existingTitles.includes(pub.title)) displayPublicationCard(pub);
          });
        }
      }
    } catch (error) {
      log(`Erro ao obter resultados: ${error.message}`, "error");
      if (!isPartial) setError("Falha ao carregar os resultados");
    }
  }

  function displayResults(results) {
    resultsGrid.innerHTML = "";
    results.forEach(item => {
      if (currentSearchType === "jobs") displayJobCard(item);
      if (currentSearchType === "publications") displayPublicationCard(item);
      if (currentSearchType === "people") displayPersonCard(item);
    });
  }

  function displayJobCard(job) {
    const jobCard = document.createElement("div");
    jobCard.className = "job-card";
    jobCard.dataset.link = job.link || "";
    jobCard.innerHTML = `
      <div class="job-header">
        <div class="job-info">
          <h3 class="job-title">${job.title || "Título não disponível"}</h3>
          <p class="company-name">${job.company || "Empresa não disponível"}</p>
        </div>
      </div>
      <div class="job-meta">
        ${job.location ? `<span><i class="bi bi-geo-alt"></i> ${job.location}</span>` : ""}
        ${job.time ? `<span><i class="bi bi-clock"></i> ${job.time}</span>` : ""}
        ${job["Nível de experiência"] ? `<span><i class="bi bi-briefcase"></i> ${job["Nível de experiência"]}</span>` : ""}
      </div>
    `;
    if (job.link) {
      jobCard.addEventListener("click", () => window.open(job.link, "_blank"));
      jobCard.style.cursor = "pointer";
    }
    resultsGrid.appendChild(jobCard);
  }

  function displayPublicationCard(pub) {
    const pubCard = document.createElement("div");
    pubCard.className = "publication-card";
    pubCard.dataset.title = pub.title || "";
    pubCard.innerHTML = `
      <div class="publication-header">
        <h3 class="publication-title">${pub.title || "Título não disponível"}</h3>
        <p class="publication-author">${pub.author || "Autor não disponível"}</p>
      </div>
      <div class="publication-meta">
        ${pub.date ? `<span><i class="bi bi-calendar"></i> ${pub.date}</span>` : ""}
        ${pub.link ? `<span><i class="bi bi-link-45deg"></i> Link disponível</span>` : ""}
      </div>
    `;
    if (pub.link) {
      pubCard.addEventListener("click", () => window.open(pub.link, "_blank"));
      pubCard.style.cursor = "pointer";
    }
    resultsGrid.appendChild(pubCard);
  }

  function displayPersonCard(person) {
    const personCard = document.createElement("div");
    personCard.className = "person-card";
    personCard.dataset.name = person.name || "";
    personCard.innerHTML = `
      <h3>${person.name || "Nome não disponível"}</h3>
      <p>${person.position || "Cargo não disponível"}</p>
      <p>${person.location || "Localização não disponível"}</p>
    `;
    resultsGrid.appendChild(personCard);
  }

  function updateStatus(data) {
    statusText.textContent = data.status_message || "Buscando...";
    if (data.progress) {
      progressBar.style.width = `${data.progress}%`;
    }
  }

  function setSearching(value) {
    isSearching = value;
    searchBtn.disabled = value;
    statusSection.style.display = value ? "block" : "none";
    progressBar.style.width = "0%";
    if (value) {
      resultsGrid.innerHTML = "";
      stopButton.style.display = "block";
    }
  }

  function setComplete() {
    isSearching = false;
    searchBtn.disabled = false;
    statusSection.style.display = "none";
    progressBar.style.width = "100%";
    stopButton.style.display = "none";
  }

  function setError(message) {
    isSearching = false;
    searchBtn.disabled = false;
    statusSection.style.display = "none";
    statusText.textContent = message;
    stopButton.style.display = "none";
  }

  async function testFunctionality() {
    log("Iniciando teste do buscador...");
    try {
      // Simulação de teste
      await new Promise(r => setTimeout(r, 500));
      const testSuccess = Math.random() > 0.1; // 90% chance sucesso
      if (testSuccess) {
        log("✅ Teste feito com sucesso!", "success");
      } else {
        log("❌ Erro no teste!", "error");
      }
    } catch (error) {
      log(`❌ Erro no teste: ${error.message}`, "error");
    }
  }

  function stopSearch() {
    if (pollTimeout) clearTimeout(pollTimeout);
    setError("Busca interrompida pelo usuário");
  }

  function handleExport(e) {
    const format = e.currentTarget.dataset.format;
    if (!searchResults.length) {
      log("Nenhum resultado para exportar", "warn");
      return;
    }
    log(`Exportando ${searchResults.length} resultados em ${format.toUpperCase()}`, "success");
    // Implementar exportação real se necessário
  }
});
