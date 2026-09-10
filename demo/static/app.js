/**
 * MNPI Compliance Pipeline Simulator Client Logic
 *
 * Implements strict DOM safety guidelines:
 * - Zero innerHTML / outerHTML / insertAdjacentHTML.
 * - All DOM elements built using document.createElement() and textContent.
 * - Container clears executed via element.replaceChildren().
 */

(function () {
  "use strict";

  // Application State
  const state = {
    selectedChannel: "slack",
    documentTitle: "Untitled Document",
    currentText: "",
    originalText: "",
    redactedText: "",
    activeViewMode: "redacted",
    lastProcessedData: null,
    bucketFiles: [],
    selectedFileUri: null,
    auditRecords: [],
  };

  // DOM Element References
  const dom = {
    // Tabs
    tabPresets: document.getElementById("tab-presets"),
    tabUpload: document.getElementById("tab-upload"),
    tabBucket: document.getElementById("tab-bucket"),
    sectionPresets: document.getElementById("section-presets"),
    sectionUpload: document.getElementById("section-upload"),
    sectionBucket: document.getElementById("section-bucket"),

    // Inputs & Controls
    presetsList: document.getElementById("presets-list"),
    dropZone: document.getElementById("drop-zone"),
    fileInput: document.getElementById("file-input"),
    uploadStatus: document.getElementById("upload-status"),

    // GCS Bucket Explorer Elements
    gcsStatusBadge: document.getElementById("gcs-status-badge"),
    gcsStatusLabel: document.getElementById("gcs-status-label"),
    gcsBucketUriDisplay: document.getElementById("gcs-bucket-uri-display"),
    btnRefreshBucket: document.getElementById("btn-refresh-bucket"),
    gcsDropZone: document.getElementById("gcs-drop-zone"),
    gcsFileInput: document.getElementById("gcs-file-input"),
    gcsUploadStatus: document.getElementById("gcs-upload-status"),
    gcsFileCount: document.getElementById("gcs-file-count"),
    gcsFilterInput: document.getElementById("gcs-filter-input"),
    gcsFilesList: document.getElementById("gcs-files-list"),
    gcsUriInput: document.getElementById("gcs-uri-input"),
    btnFetchBucket: document.getElementById("btn-fetch-bucket"),

    documentText: document.getElementById("document-text"),
    charCount: document.getElementById("char-count"),
    channelChips: document.querySelectorAll(".channel-chip"),
    btnProcess: document.getElementById("btn-process"),
    processSpinner: document.getElementById("process-spinner"),

    // Fact Checker Display
    sa1Chips: document.getElementById("sa1-chips"),
    sa2Chips: document.getElementById("sa2-chips"),
    sa3Info: document.getElementById("sa3-info"),

    // Arbiter 4-Test Scorecard Display
    statusMat: document.getElementById("status-mat"),
    barMat: document.getElementById("bar-mat"),
    rationaleMat: document.getElementById("rationale-mat"),

    statusPub: document.getElementById("status-pub"),
    barPub: document.getElementById("bar-pub"),
    rationalePub: document.getElementById("rationale-pub"),

    statusSrc: document.getElementById("status-src"),
    barSrc: document.getElementById("bar-src"),
    rationaleSrc: document.getElementById("rationale-src"),

    statusHarm: document.getElementById("status-harm"),
    barHarm: document.getElementById("bar-harm"),
    rationaleHarm: document.getElementById("rationale-harm"),

    // RL & Causal Attribution v2 Display
    verificationCodesList: document.getElementById("verification-codes-list"),
    codesCountTag: document.getElementById("codes-count-tag"),
    causalModeBadge: document.getElementById("causal-mode-badge"),
    metricDataInfluence: document.getElementById("metric-data-influence"),
    metricPromptInfluence: document.getElementById("metric-prompt-influence"),
    metricOverdetermined: document.getElementById("metric-overdetermined"),
    causalRationaleBox: document.getElementById("causal-rationale-box"),
    rlTotalBadge: document.getElementById("rl-total-badge"),
    chipTaskReward: document.getElementById("chip-task-reward"),
    chipFpPenalty: document.getElementById("chip-fp-penalty"),
    chipVetoPenalty: document.getElementById("chip-veto-penalty"),
    chipCausalPenalty: document.getElementById("chip-causal-penalty"),
    rlRationaleBox: document.getElementById("rl-rationale-box"),

    // Routing & Redaction Display
    routingBanner: document.getElementById("routing-banner"),
    routingIcon: document.getElementById("routing-icon"),
    routingDestination: document.getElementById("routing-destination"),
    routingStorage: document.getElementById("routing-storage"),

    btnViewRedacted: document.getElementById("btn-view-redacted"),
    btnViewOriginal: document.getElementById("btn-view-original"),
    btnViewDiff: document.getElementById("btn-view-diff"),
    outputContainer: document.getElementById("output-view-container"),

    auditJustification: document.getElementById("audit-justification"),
    metaLatency: document.getElementById("meta-latency"),
    metaRisk: document.getElementById("meta-risk"),
    metaAction: document.getElementById("meta-action"),

    // Security & Entitlements Tag Display
    entRankBadge: document.getElementById("ent-rank-badge"),
    entTier: document.getElementById("ent-tier"),
    entMinRole: document.getElementById("ent-min-role"),
    entDepartments: document.getElementById("ent-departments"),
    entTickers: document.getElementById("ent-tickers"),
    simUserRole: document.getElementById("sim-user-role"),
    btnTestEntitlement: document.getElementById("btn-test-entitlement"),
    simResultBox: document.getElementById("sim-result-box"),
    sidecarFilenameLabel: document.getElementById("sidecar-filename-label"),
    btnCopyEntitlementsJson: document.getElementById("btn-copy-entitlements-json"),
    entitlementsJsonDisplay: document.getElementById("entitlements-json-display"),

    // BigQuery Document Alignment Audit DOM Elements
    bqStatusPill: document.getElementById("bq-status-pill"),
    bqStatusText: document.getElementById("bq-status-text"),
    btnRefreshAudit: document.getElementById("btn-refresh-audit"),
    auditSearchInput: document.getElementById("audit-search-input"),
    auditVerdictFilter: document.getElementById("audit-verdict-filter"),
    auditTableBody: document.getElementById("audit-table-body"),
    auditModal: document.getElementById("audit-modal"),
    modalDocTitle: document.getElementById("modal-doc-title"),
    modalDocBody: document.getElementById("modal-doc-body"),
    btnCloseModal: document.getElementById("btn-close-modal"),

    // Primary View Navigation
    navBtnPipeline: document.getElementById("nav-btn-pipeline"),
    navBtnBigQuery: document.getElementById("nav-btn-bigquery"),
    navBtnRl: document.getElementById("nav-btn-rl"),
    navBqBadge: document.getElementById("nav-bq-badge"),
    viewPipeline: document.getElementById("view-pipeline"),
    viewBigQuery: document.getElementById("view-bigquery"),
    viewRlExplainer: document.getElementById("view-rl-explainer"),
    btnOpenRlGuide: document.getElementById("btn-open-rl-guide"),
    btnRlBackToPipeline: document.getElementById("btn-rl-back-to-pipeline"),

    // RL Interactive Formula Tuner & Sliders
    sliderRTask: document.getElementById("slider-r-task"),
    sliderLambdaVeto: document.getElementById("slider-lambda-veto"),
    sliderFpPenalty: document.getElementById("slider-fp-penalty"),
    sliderGammaCausal: document.getElementById("slider-gamma-causal"),
    sliderDpoMargin: document.getElementById("slider-dpo-margin"),
    sliderWeightMat: document.getElementById("slider-weight-mat"),

    valBadgeRTask: document.getElementById("val-badge-r-task"),
    valBadgeLambdaVeto: document.getElementById("val-badge-lambda-veto"),
    valBadgeFpPenalty: document.getElementById("val-badge-fp-penalty"),
    valBadgeGammaCausal: document.getElementById("val-badge-gamma-causal"),
    valBadgeDpoMargin: document.getElementById("val-badge-dpo-margin"),
    valBadgeWeightMat: document.getElementById("val-badge-weight-mat"),

    presetBalanced: document.getElementById("preset-balanced"),
    presetStrict: document.getElementById("preset-strict"),
    presetPermissive: document.getElementById("preset-permissive"),

    btnApplyWeights: document.getElementById("btn-apply-weights"),
    btnResetWeights: document.getElementById("btn-reset-weights"),
    tunerStatusMsg: document.getElementById("tuner-status-msg"),

    formulaTermRTask: document.getElementById("formula-term-rtask"),
    formulaTermVeto: document.getElementById("formula-term-veto"),
    formulaTermFp: document.getElementById("formula-term-rfp"),
    formulaTermGamma: document.getElementById("formula-term-gamma"),

    displayCardRTask: document.getElementById("display-card-rtask"),
    displayCardVeto: document.getElementById("display-card-veto"),
    displayCardFp: document.getElementById("display-card-rfp"),
    displayCardGamma: document.getElementById("display-card-gamma"),
    pillValMat01: document.getElementById("pill-val-mat01"),

    scenarioARwin: document.getElementById("scenario-a-rwin"),
    scenarioARlose: document.getElementById("scenario-a-rlose"),
    scenarioALoseDesc: document.getElementById("scenario-a-lose-desc"),
    scenarioAMarginBanner: document.getElementById("scenario-a-margin-banner"),

    scenarioBRwin: document.getElementById("scenario-b-rwin"),
    scenarioBRlose: document.getElementById("scenario-b-rlose"),
    scenarioBLoseDesc: document.getElementById("scenario-b-lose-desc"),
    scenarioBMarginBanner: document.getElementById("scenario-b-margin-banner"),

    // BigQuery Explorer Controls & Panes
    btnRefreshBqExplorer: document.getElementById("btn-refresh-bq-explorer"),
    btnExportCsv: document.getElementById("btn-export-csv"),
    metricTotalRows: document.getElementById("metric-total-rows"),
    bqTabData: document.getElementById("bq-tab-data"),
    bqTabSchema: document.getElementById("bq-tab-schema"),
    bqTabSql: document.getElementById("bq-tab-sql"),
    bqPaneData: document.getElementById("bq-pane-data"),
    bqPaneSchema: document.getElementById("bq-pane-schema"),
    bqPaneSql: document.getElementById("bq-pane-sql"),
    bqSearchInput: document.getElementById("bq-search-input"),
    bqVerdictFilter: document.getElementById("bq-verdict-filter"),
    bqExplorerTableBody: document.getElementById("bq-explorer-table-body"),
    bqSchemaTbody: document.getElementById("bq-schema-tbody"),
    btnCopySql: document.getElementById("btn-copy-sql"),
    bqSqlBlock: document.getElementById("bq-sql-block"),
  };

  // ============================================================================
  // Safe DOM Helper Functions (No innerHTML)
  // ============================================================================

  function clearElement(el) {
    if (el) {
      el.replaceChildren();
    }
  }

  function createTextElement(tag, text, className) {
    const el = document.createElement(tag);
    el.textContent = text || "";
    if (className) {
      el.className = className;
    }
    return el;
  }

  function createBadge(text, typeClass) {
    const badge = document.createElement("span");
    badge.className = "badge-chip " + (typeClass || "");
    badge.textContent = text;
    return badge;
  }

  // ============================================================================
  // Tab Management
  // ============================================================================

  function switchTab(activeTab, activeSection) {
    [dom.tabPresets, dom.tabUpload, dom.tabBucket].forEach((t) =>
      t.classList.remove("active")
    );
    [dom.sectionPresets, dom.sectionUpload, dom.sectionBucket].forEach((s) =>
      s.classList.remove("active")
    );

    activeTab.classList.add("active");
    activeSection.classList.add("active");
  }

  dom.tabPresets.addEventListener("click", function () {
    switchTab(dom.tabPresets, dom.sectionPresets);
  });
  dom.tabUpload.addEventListener("click", function () {
    switchTab(dom.tabUpload, dom.sectionUpload);
  });
  dom.tabBucket.addEventListener("click", function () {
    switchTab(dom.tabBucket, dom.sectionBucket);
  });

  // ============================================================================
  // Channel Selection
  // ============================================================================

  dom.channelChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      dom.channelChips.forEach(function (c) {
        c.classList.remove("active");
      });
      chip.classList.add("active");
      state.selectedChannel = chip.getAttribute("data-channel") || "slack";
    });
  });

  function setChannelActive(channelName) {
    state.selectedChannel = channelName;
    dom.channelChips.forEach(function (chip) {
      if (chip.getAttribute("data-channel") === channelName) {
        chip.classList.add("active");
      } else {
        chip.classList.remove("active");
      }
    });
  }

  // ============================================================================
  // Character Count
  // ============================================================================

  dom.documentText.addEventListener("input", function () {
    state.currentText = dom.documentText.value;
    dom.charCount.textContent = state.currentText.length + " characters";
  });

  function updateTextareaContent(text) {
    state.currentText = text;
    dom.documentText.value = text;
    dom.charCount.textContent = text.length + " characters";
  }

  // ============================================================================
  // Presets Loading
  // ============================================================================

  async function loadPresetScenarios() {
    try {
      const res = await fetch("/api/scenarios");
      if (!res.ok) throw new Error("Failed to load scenarios");
      const scenarios = await res.json();

      clearElement(dom.presetsList);

      scenarios.forEach(function (preset, idx) {
        const card = document.createElement("div");
        card.className = "preset-card" + (idx === 0 ? " active" : "");

        const titleDiv = document.createElement("div");
        titleDiv.className = "preset-title";
        titleDiv.appendChild(createTextElement("span", preset.title));

        const channelBadge = createBadge(preset.channel.toUpperCase(), "ticker");
        titleDiv.appendChild(channelBadge);

        const descDiv = createTextElement("div", preset.description, "preset-desc");

        card.appendChild(titleDiv);
        card.appendChild(descDiv);

        card.addEventListener("click", function () {
          document.querySelectorAll(".preset-card").forEach(function (c) {
            c.classList.remove("active");
          });
          card.classList.add("active");
          state.documentTitle = preset.title;
          setChannelActive(preset.channel);
          updateTextareaContent(preset.sample_text);
        });

        dom.presetsList.appendChild(card);

        // Load first preset by default
        if (idx === 0) {
          state.documentTitle = preset.title;
          setChannelActive(preset.channel);
          updateTextareaContent(preset.sample_text);
        }
      });
    } catch (err) {
      clearElement(dom.presetsList);
      dom.presetsList.appendChild(
        createTextElement("p", "Unable to load presets. Verify server status.", "placeholder-text")
      );
    }
  }

  // ============================================================================
  // Storage Bucket Browser & Fetch
  // ============================================================================

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    if (bytes < 1024) return bytes + " B";
    return (bytes / 1024).toFixed(1) + " KB";
  }

  async function loadBucketFileList() {
    try {
      // 1. Check bucket status and mode
      try {
        const statusRes = await fetch("/api/bucket/status");
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (dom.gcsBucketUriDisplay) {
            dom.gcsBucketUriDisplay.textContent = statusData.bucket_uri || "gs://green-carrier-500109-k2-quarantine/incoming/";
          }
          if (dom.gcsStatusBadge) {
            dom.gcsStatusBadge.className = "gcs-status-badge " + (statusData.connected ? "live" : "simulated");
          }
          if (dom.gcsStatusLabel) {
            dom.gcsStatusLabel.textContent = statusData.connected ? "Live GCS" : "Simulated";
          }
        }
      } catch (e) {
        // Status check fallback
      }

      // 2. Fetch list of files
      const res = await fetch("/api/bucket/files");
      if (!res.ok) throw new Error("Failed to load bucket files");
      const data = await res.json();
      state.bucketFiles = data.files || [];
      renderBucketFileList();
    } catch (err) {
      if (dom.gcsFilesList) {
        clearElement(dom.gcsFilesList);
        dom.gcsFilesList.appendChild(
          createTextElement("div", "Failed to load files: " + err.message, "gcs-empty-state")
        );
      }
    }
  }

  function renderBucketFileList() {
    if (!dom.gcsFilesList) return;
    clearElement(dom.gcsFilesList);

    const query = dom.gcsFilterInput ? dom.gcsFilterInput.value.toLowerCase().trim() : "";
    const filtered = state.bucketFiles.filter(function (file) {
      return !query || file.filename.toLowerCase().includes(query);
    });

    if (dom.gcsFileCount) {
      dom.gcsFileCount.textContent = String(filtered.length);
    }

    if (filtered.length === 0) {
      const emptyMsg = state.bucketFiles.length === 0
        ? "No documents in quarantine bucket. Upload one above!"
        : "No matching documents found.";
      dom.gcsFilesList.appendChild(createTextElement("div", emptyMsg, "gcs-empty-state"));
      return;
    }

    filtered.forEach(function (file) {
      const item = document.createElement("div");
      item.className = "gcs-file-item" + (state.selectedFileUri === file.gcs_uri ? " selected" : "");

      const info = document.createElement("div");
      info.className = "gcs-file-info";

      const icon = document.createElement("span");
      icon.className = "gcs-file-icon";
      icon.textContent = "📄";
      info.appendChild(icon);

      const meta = document.createElement("div");
      meta.className = "gcs-file-meta";

      const nameEl = createTextElement("div", file.filename, "gcs-file-name");
      nameEl.title = file.gcs_uri;
      meta.appendChild(nameEl);

      const subEl = createTextElement(
        "div",
        formatBytes(file.size_bytes) + " • " + (file.updated || "GCS"),
        "gcs-file-sub"
      );
      meta.appendChild(subEl);
      info.appendChild(meta);
      item.appendChild(info);

      const actions = document.createElement("div");
      actions.className = "gcs-file-actions";

      const btnIngest = document.createElement("button");
      btnIngest.className = "btn-action";
      btnIngest.textContent = "Ingest";
      btnIngest.title = "Load document into Compliance Cockpit";

      btnIngest.addEventListener("click", function () {
        state.selectedFileUri = file.gcs_uri;
        document.querySelectorAll(".gcs-file-item").forEach(function (el) {
          el.classList.remove("selected");
        });
        item.classList.add("selected");
        if (dom.gcsUriInput) dom.gcsUriInput.value = file.gcs_uri;
        fetchAndLoadGcsFile(file.gcs_uri);
      });

      actions.appendChild(btnIngest);
      item.appendChild(actions);
      dom.gcsFilesList.appendChild(item);
    });
  }

  async function fetchAndLoadGcsFile(uri) {
    if (!uri) return;
    try {
      if (dom.btnFetchBucket) dom.btnFetchBucket.textContent = "Fetching...";
      const res = await fetch("/api/bucket/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gcs_uri: uri }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to fetch object");
      }

      const data = await res.json();
      state.documentTitle = data.filename;
      updateTextareaContent(data.content);

      const lower = data.filename.toLowerCase();
      if (lower.includes("zoom")) setChannelActive("zoom");
      else if (lower.includes("slack")) setChannelActive("slack");
      else if (lower.includes("email")) setChannelActive("email");
      else if (lower.includes("salesforce")) setChannelActive("salesforce");
      else setChannelActive("cloud_storage");

      if (dom.gcsUploadStatus) {
        dom.gcsUploadStatus.className = "upload-status-box";
        dom.gcsUploadStatus.textContent = "Loaded from GCS: " + data.gcs_uri + " (" + data.bytes + " bytes)";
        dom.gcsUploadStatus.classList.remove("hidden");
      }
    } catch (err) {
      if (dom.gcsUploadStatus) {
        dom.gcsUploadStatus.className = "upload-status-box";
        dom.gcsUploadStatus.style.borderColor = "#ef4444";
        dom.gcsUploadStatus.style.color = "#f87171";
        dom.gcsUploadStatus.textContent = "Fetch error: " + err.message;
        dom.gcsUploadStatus.classList.remove("hidden");
      }
    } finally {
      if (dom.btnFetchBucket) dom.btnFetchBucket.textContent = "Fetch";
    }
  }

  if (dom.btnRefreshBucket) {
    dom.btnRefreshBucket.addEventListener("click", function () {
      loadBucketFileList();
    });
  }

  if (dom.gcsFilterInput) {
    dom.gcsFilterInput.addEventListener("input", function () {
      renderBucketFileList();
    });
  }

  if (dom.gcsDropZone) {
    dom.gcsDropZone.addEventListener("click", function () {
      if (dom.gcsFileInput) dom.gcsFileInput.click();
    });

    dom.gcsDropZone.addEventListener("dragover", function (e) {
      e.preventDefault();
      dom.gcsDropZone.classList.add("dragover");
    });

    dom.gcsDropZone.addEventListener("dragleave", function () {
      dom.gcsDropZone.classList.remove("dragover");
    });

    dom.gcsDropZone.addEventListener("drop", function (e) {
      e.preventDefault();
      dom.gcsDropZone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        uploadDirectToGcs(e.dataTransfer.files[0]);
      }
    });
  }

  if (dom.gcsFileInput) {
    dom.gcsFileInput.addEventListener("change", function () {
      if (dom.gcsFileInput.files && dom.gcsFileInput.files.length > 0) {
        uploadDirectToGcs(dom.gcsFileInput.files[0]);
      }
    });
  }

  async function uploadDirectToGcs(file) {
    const formData = new FormData();
    formData.append("file", file);

    if (dom.gcsUploadStatus) {
      dom.gcsUploadStatus.className = "upload-status-box";
      dom.gcsUploadStatus.textContent = "Uploading " + file.name + " to GCS bucket...";
      dom.gcsUploadStatus.classList.remove("hidden");
    }

    try {
      const res = await fetch("/api/bucket/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Upload to GCS failed");
      }

      const data = await res.json();
      state.documentTitle = data.filename;
      updateTextareaContent(data.text);

      const lower = data.filename.toLowerCase();
      if (lower.includes("zoom")) setChannelActive("zoom");
      else if (lower.includes("slack")) setChannelActive("slack");
      else if (lower.includes("email")) setChannelActive("email");
      else if (lower.includes("salesforce")) setChannelActive("salesforce");
      else setChannelActive("cloud_storage");

      if (dom.gcsUploadStatus) {
        dom.gcsUploadStatus.className = "upload-status-box";
        dom.gcsUploadStatus.textContent = "✓ Uploaded to GCS: " + data.gcs_uri + " (" + data.bytes + " bytes)";
        dom.gcsUploadStatus.classList.remove("hidden");
      }

      await loadBucketFileList();
    } catch (err) {
      if (dom.gcsUploadStatus) {
        dom.gcsUploadStatus.className = "upload-status-box";
        dom.gcsUploadStatus.style.borderColor = "#ef4444";
        dom.gcsUploadStatus.style.color = "#f87171";
        dom.gcsUploadStatus.textContent = "GCS Upload error: " + err.message;
        dom.gcsUploadStatus.classList.remove("hidden");
      }
    }
  }

  if (dom.btnFetchBucket) {
    dom.btnFetchBucket.addEventListener("click", function () {
      const uri = dom.gcsUriInput ? dom.gcsUriInput.value.trim() : "";
      if (uri) fetchAndLoadGcsFile(uri);
    });
  }

  // ============================================================================
  // File Upload Handlers (Drag & Drop + File Picker)
  // ============================================================================

  dom.dropZone.addEventListener("click", function () {
    dom.fileInput.click();
  });

  dom.dropZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dom.dropZone.classList.add("dragover");
  });

  dom.dropZone.addEventListener("dragleave", function () {
    dom.dropZone.classList.remove("dragover");
  });

  dom.dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    dom.dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });

  dom.fileInput.addEventListener("change", function () {
    if (dom.fileInput.files && dom.fileInput.files.length > 0) {
      uploadFile(dom.fileInput.files[0]);
    }
  });

  async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("channel", state.selectedChannel);

    dom.uploadStatus.className = "upload-status-box";
    dom.uploadStatus.textContent = "Uploading " + file.name + " to Quarantine Holding Zone...";
    dom.uploadStatus.classList.remove("hidden");

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data = await res.json();
      state.documentTitle = data.filename;
      updateTextareaContent(data.text);

      dom.uploadStatus.textContent = data.uploaded_to_gcs
        ? "✓ Staged in Live GCS Quarantine: " + data.quarantine_uri + " (" + data.bytes + " bytes)"
        : "Quarantined in Holding Zone: " + data.quarantine_uri + " (" + data.bytes + " bytes)";
      loadBucketFileList(); // Refresh bucket dropdown
    } catch (err) {
      dom.uploadStatus.style.borderColor = "#ef4444";
      dom.uploadStatus.style.color = "#f87171";
      dom.uploadStatus.textContent = "Upload error: " + err.message;
    }
  }

  // ============================================================================
  // Process Pipeline Execution
  // ============================================================================

  dom.btnProcess.addEventListener("click", async function () {
    const text = dom.documentText.value.trim();
    if (!text) {
      alert("Please enter, upload, or fetch text to evaluate.");
      return;
    }

    // Set loading UI
    dom.btnProcess.disabled = true;
    dom.processSpinner.classList.remove("hidden");
    const btnTextSpan = dom.btnProcess.querySelector(".btn-text");
    const originalBtnText = btnTextSpan ? btnTextSpan.textContent : "⚙ Process with Two-Agent Platform";

    const progressSteps = [
      "🕵️ Step 1/3: Fact Checker extracting entities & codenames",
      "🔍 Step 1/3: Checking public wire releases & secrecy markers",
      "⚖️ Step 2/3: Arbiter scoring Materiality & Mosaic tests",
      "🛡️ Step 2/3: Evaluating Source/Duty & Actionability harm",
      "📊 Step 3/3: Streaming compliance integrity hash to BigQuery",
    ];
    let elapsedSec = 0;
    let stepIndex = 0;
    const updateButtonText = () => {
      if (btnTextSpan) {
        btnTextSpan.textContent = `${progressSteps[stepIndex]} (${elapsedSec}s elapsed)`;
      }
    };
    updateButtonText();
    const progressInterval = setInterval(() => {
      elapsedSec++;
      if (elapsedSec % 4 === 0) {
        stepIndex = (stepIndex + 1) % progressSteps.length;
      }
      updateButtonText();
    }, 1000);

    try {
      const res = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text,
          channel: state.selectedChannel,
          document_title: state.documentTitle,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Processing pipeline failed");
      }

      const result = await res.json();
      state.lastProcessedData = result;
      state.originalText = text;
      state.redactedText = result.verdict.redacted_text || text;

      renderPipelineResults(result);
      loadAuditLogs();
    } catch (err) {
      alert("Pipeline Error: " + err.message);
    } finally {
      clearInterval(progressInterval);
      dom.btnProcess.disabled = false;
      dom.processSpinner.classList.add("hidden");
      if (btnTextSpan) btnTextSpan.textContent = originalBtnText;
    }
  });

  // ============================================================================
  // Render Pipeline Results (Safe DOM Updates)
  // ============================================================================

  function renderPipelineResults(data) {
    const dossier = data.dossier;
    const verdict = data.verdict;
    const routing = data.routing;

    // 1. Fact Checker: SA1 Entities
    clearElement(dom.sa1Chips);
    if (dossier.entities.entities && dossier.entities.entities.length > 0) {
      dossier.entities.entities.forEach(function (e) {
        const chipClass = e.is_internal_or_restricted ? "codename" : "ticker";
        const label = e.name + " (" + e.category + ")";
        dom.sa1Chips.appendChild(createBadge(label, chipClass));
      });
    } else {
      dom.sa1Chips.appendChild(createTextElement("span", "No corporate entities identified", "placeholder-text"));
    }

    // 2. Fact Checker: SA2 Triggers
    clearElement(dom.sa2Chips);
    if (dossier.triggers.triggers && dossier.triggers.triggers.length > 0) {
      dossier.triggers.triggers.forEach(function (t) {
        const chipClass = t.sensitivity_level === "CRITICAL" ? "trigger-critical" : "trigger-high";
        const label = t.term + " [" + t.sensitivity_level + "]";
        dom.sa2Chips.appendChild(createBadge(label, chipClass));
      });
    } else {
      dom.sa2Chips.appendChild(createTextElement("span", "No sensitive triggers found", "placeholder-text"));
    }

    // 3. Fact Checker: SA3 Public Check
    clearElement(dom.sa3Info);
    const pubP = document.createElement("p");
    const pubStatus = dossier.public_check.is_publicly_verified ? "Verified in Public Press/SEC" : "Non-Public (Unconfirmed)";
    pubP.textContent = "Status: " + pubStatus;
    dom.sa3Info.appendChild(pubP);

    if (dossier.public_check.linguistic_markers && dossier.public_check.linguistic_markers.length > 0) {
      const secP = document.createElement("p");
      secP.textContent = "Secrecy Markers: " + dossier.public_check.linguistic_markers.join(", ");
      secP.style.color = "#f87171";
      secP.style.fontWeight = "bold";
      dom.sa3Info.appendChild(secP);
    }

    // 4. Arbiter: 4 Judicial Tests
    renderCriterion(verdict.materiality_test, dom.statusMat, dom.barMat, dom.rationaleMat);
    renderCriterion(verdict.public_availability_test, dom.statusPub, dom.barPub, dom.rationalePub);
    renderCriterion(verdict.source_and_duty_test, dom.statusSrc, dom.barSrc, dom.rationaleSrc);
    renderCriterion(verdict.actionability_harm_test, dom.statusHarm, dom.barHarm, dom.rationaleHarm);

    // 4b. Standardized Verification Codes
    if (dom.verificationCodesList) {
      clearElement(dom.verificationCodesList);
      const codes = verdict.verification_codes || [];
      if (codes.length > 0) {
        codes.forEach(function (code) {
          const pill = document.createElement("span");
          const isCleared = code.includes("CLEARED") || code.includes("PUBLIC_WIRE") || code.includes("EXTERNAL");
          pill.className = "code-pill " + (isCleared ? "cleared" : "violation");
          pill.textContent = code;
          dom.verificationCodesList.appendChild(pill);
        });
        if (dom.codesCountTag) dom.codesCountTag.textContent = codes.length + " codes verified";
      } else {
        const emptyPill = document.createElement("span");
        emptyPill.className = "code-pill empty";
        emptyPill.textContent = "No machine codes returned";
        dom.verificationCodesList.appendChild(emptyPill);
        if (dom.codesCountTag) dom.codesCountTag.textContent = "0 codes";
      }
    }

    // 4c. Causal Attribution Engine (LOO)
    if (verdict.causal_attribution && dom.causalModeBadge) {
      const ca = verdict.causal_attribution;
      dom.causalModeBadge.textContent = ca.ablation_mode;
      if (ca.ablation_mode === "joint_cluster") {
        dom.causalModeBadge.className = "badge-chip critical";
      } else if (ca.ablation_mode.includes("skipped")) {
        dom.causalModeBadge.className = "badge-chip ticker";
      } else {
        dom.causalModeBadge.className = "badge-chip warning";
      }

      if (dom.metricDataInfluence) dom.metricDataInfluence.textContent = (ca.data_influence_score || 0).toFixed(2);
      if (dom.metricPromptInfluence) dom.metricPromptInfluence.textContent = (ca.counterfactual_score || 0).toFixed(2);
      if (dom.metricOverdetermined) {
        dom.metricOverdetermined.textContent = ca.is_overdetermined ? "YES (Multi-Leak)" : "NO";
        dom.metricOverdetermined.style.color = ca.is_overdetermined ? "#f87171" : "#34d399";
      }
      if (dom.causalRationaleBox) dom.causalRationaleBox.textContent = ca.causal_rationale || "";
    }

    // 4d. RL Compliance Multi-Objective Reward
    if (verdict.rl_metrics && dom.rlTotalBadge) {
      const rm = verdict.rl_metrics;
      const isPositive = rm.total_reward >= 0;
      dom.rlTotalBadge.textContent = "R_total: " + (isPositive ? "+" : "") + rm.total_reward.toFixed(2);
      dom.rlTotalBadge.className = "badge-chip " + (isPositive ? "total-reward-badge" : "critical");

      if (dom.chipTaskReward) dom.chipTaskReward.textContent = "Task: +" + (rm.task_reward || 1.0).toFixed(1);
      if (dom.chipFpPenalty) {
        dom.chipFpPenalty.textContent = "R_fp (Bias): " + (rm.fp_penalty || 0.0).toFixed(1);
        dom.chipFpPenalty.className = "rl-chip " + (rm.fp_penalty < 0 ? "penalty-active" : "");
      }
      if (dom.chipVetoPenalty) {
        dom.chipVetoPenalty.textContent = "Veto: " + (rm.veto_penalty || 0.0).toFixed(1);
        dom.chipVetoPenalty.className = "rl-chip " + (rm.veto_penalty < 0 ? "penalty-active" : "");
      }
      if (dom.chipCausalPenalty) {
        dom.chipCausalPenalty.textContent = "Causal Pen: " + (rm.causal_penalty || 0.0).toFixed(2);
        dom.chipCausalPenalty.className = "rl-chip " + (rm.causal_penalty < 0 ? "penalty-active" : "");
      }
      if (dom.rlRationaleBox) dom.rlRationaleBox.textContent = rm.reward_rationale || "";
    }

    // 5. Routing Banner
    dom.routingBanner.className = "routing-banner " + routing.badge_variant;
    dom.routingDestination.textContent = routing.destination;
    dom.routingStorage.textContent = "Target: " + routing.storage_bucket;

    if (routing.badge_variant === "critical") {
      dom.routingIcon.textContent = "🚫";
    } else if (routing.badge_variant === "warning") {
      dom.routingIcon.textContent = "⚠️";
    } else {
      dom.routingIcon.textContent = "✅";
    }

    // 6. Audit Justification & Metadata
    dom.auditJustification.textContent = verdict.summary_justification;
    dom.metaLatency.textContent = data.latency_ms + " ms";
    dom.metaRisk.textContent = verdict.risk_level;
    dom.metaAction.textContent = verdict.recommended_action;

    // 7. Render Output Document
    renderOutputView();

    // 8. Render Security & Access Entitlements Tag
    renderEntitlementsTag(data);
  }

  function renderEntitlementsTag(data) {
    if (!dom.entRankBadge) return;

    const verdict = data.verdict || {};
    const ent = verdict.entitlements || data.entitlements;
    const sidecar = data.sidecar_file || {};

    if (!ent) {
      dom.entRankBadge.className = "badge-rank rank-none";
      dom.entRankBadge.textContent = "Rank -";
      if (dom.entTier) dom.entTier.textContent = "-";
      if (dom.entMinRole) dom.entMinRole.textContent = "-";
      return;
    }

    const rank = ent.clearance_rank;
    const isRankNull = rank === null || rank === undefined;
    const rankLabels = {
      1: "Rank 1: Public / Any",
      2: "Rank 2: Analyst+",
      3: "Rank 3: Senior Associate+",
      4: "Rank 4: VP & Legal Only",
    };

    if (isRankNull) {
      dom.entRankBadge.className = "badge-rank rank-null";
      dom.entRankBadge.textContent = "Rank: Nullified (Unassigned)";
      if (dom.entTier) dom.entTier.textContent = ent.classification_tier || "-";
      if (dom.entMinRole) dom.entMinRole.textContent = "Unassigned (Pending Carveout)";
    } else {
      dom.entRankBadge.className = "badge-rank rank-" + rank;
      dom.entRankBadge.textContent = rankLabels[rank] || ("Rank " + rank);
      if (dom.entTier) dom.entTier.textContent = ent.classification_tier || "-";
      if (dom.entMinRole) dom.entMinRole.textContent = ent.min_role_required || "-";
    }

    // Render department chips
    if (dom.entDepartments) {
      clearElement(dom.entDepartments);
      const depts = ent.permitted_departments || [];
      if (depts.length > 0) {
        depts.forEach((d) => {
          const chip = document.createElement("span");
          chip.className = "ent-tag-chip dept";
          chip.textContent = d;
          dom.entDepartments.appendChild(chip);
        });
      } else {
        dom.entDepartments.innerHTML = '<span class="placeholder-text">All Departments (No Carveout)</span>';
      }
    }

    // Render ticker chips
    if (dom.entTickers) {
      clearElement(dom.entTickers);
      const tickers = ent.ticker_restrictions || [];
      if (tickers.length > 0) {
        tickers.forEach((t) => {
          const chip = document.createElement("span");
          chip.className = "ent-tag-chip ticker";
          chip.textContent = "$" + t;
          dom.entTickers.appendChild(chip);
        });
      } else {
        dom.entTickers.innerHTML = '<span class="placeholder-text">None</span>';
      }
    }

    // Sidecar status
    if (dom.sidecarFilenameLabel) {
      const fn = sidecar.filename || (ent.document_id + ".entitlements.json");
      dom.sidecarFilenameLabel.textContent = fn + (sidecar.exists ? " (Attached & Stored)" : " (Attached)");
    }

    // JSON envelope display
    if (dom.entitlementsJsonDisplay) {
      dom.entitlementsJsonDisplay.textContent = JSON.stringify(ent, null, 2);
    }

    // Reset simulator result box
    if (dom.simResultBox) {
      dom.simResultBox.className = "sim-result-box neutral";
      if (isRankNull) {
        dom.simResultBox.textContent = "Security clearance rank is currently nullified (unassigned). Downstream role restrictions are not enforced pending organizational carveout.";
      } else {
        dom.simResultBox.textContent = `Document requires ${rankLabels[rank] || "Rank " + rank}. Select a role and test policy access.`;
      }
    }
  }

  function renderCriterion(testObj, statusEl, barEl, rationaleEl) {
    const score = testObj.score || 0;
    const percent = Math.round(score * 100);

    barEl.style.width = percent + "%";
    statusEl.textContent = testObj.passed_or_failed + " (" + score.toFixed(2) + ")";

    if (score >= 0.7) {
      statusEl.className = "crit-status violation";
      barEl.className = "progress-bar critical";
    } else if (score >= 0.4) {
      statusEl.className = "crit-status";
      barEl.className = "progress-bar warning";
    } else {
      statusEl.className = "crit-status cleared";
      barEl.className = "progress-bar cleared";
    }

    rationaleEl.textContent = testObj.rationale;
  }

  // ============================================================================
  // Output Redaction View (Tabs: Redacted | Original | Diff)
  // ============================================================================

  function setOutputTab(activeBtn, mode) {
    [dom.btnViewRedacted, dom.btnViewOriginal, dom.btnViewDiff].forEach(function (b) {
      b.classList.remove("active");
    });
    activeBtn.classList.add("active");
    state.activeViewMode = mode;
    renderOutputView();
  }

  dom.btnViewRedacted.addEventListener("click", function () {
    setOutputTab(dom.btnViewRedacted, "redacted");
  });
  dom.btnViewOriginal.addEventListener("click", function () {
    setOutputTab(dom.btnViewOriginal, "original");
  });
  dom.btnViewDiff.addEventListener("click", function () {
    setOutputTab(dom.btnViewDiff, "diff");
  });

  function renderOutputView() {
    clearElement(dom.outputContainer);

    if (!state.lastProcessedData) {
      dom.outputContainer.appendChild(
        createTextElement("div", "No document processed yet.", "placeholder-text")
      );
      return;
    }

    if (state.activeViewMode === "original") {
      dom.outputContainer.appendChild(
        createTextElement("div", state.originalText, "output-text-area")
      );
    } else if (state.activeViewMode === "redacted") {
      const isRedacted = state.originalText.trim() !== state.redactedText.trim();
      if (isRedacted) {
        const wrap = document.createElement("div");
        wrap.appendChild(
          createBadge("REDACTED COMPLIANCE PAYLOAD (SCOPED ACCESS ONLY)", "trigger-critical")
        );
        wrap.appendChild(document.createElement("br"));
        wrap.appendChild(document.createElement("br"));
        wrap.appendChild(createTextElement("div", state.redactedText, "output-text-area"));
        dom.outputContainer.appendChild(wrap);
      } else {
        dom.outputContainer.appendChild(
          createTextElement("div", state.redactedText, "output-text-area")
        );
      }
    } else {
      // Diff View
      renderSafeDiffView();
    }
  }

  function renderSafeDiffView() {
    const diffContainer = document.createElement("div");
    diffContainer.className = "diff-view-box";

    const banner = document.createElement("div");
    banner.style.marginBottom = "0.5rem";
    banner.appendChild(createBadge("ORIGINAL VS. REDACTED COMPARISON", "ticker"));
    diffContainer.appendChild(banner);

    const isRedacted = state.originalText.trim() !== state.redactedText.trim();

    if (!isRedacted) {
      diffContainer.appendChild(
        createTextElement("div", "No redactions required. Payload approved identical to original input.", "crit-rationale")
      );
    } else {
      // Split by redacted placeholder safely
      const placeholder = "[REDACTED MNPI CONTENT]";
      const parts = state.redactedText.split(placeholder);

      const previewDiv = document.createElement("div");
      previewDiv.style.lineHeight = "1.6";

      parts.forEach(function (part, idx) {
        previewDiv.appendChild(document.createTextNode(part));
        if (idx < parts.length - 1) {
          const redBadge = document.createElement("span");
          redBadge.className = "redaction-highlight";
          redBadge.textContent = " [REDACTED: SENSITIVE MNPI] ";
          previewDiv.appendChild(redBadge);
        }
      });

      diffContainer.appendChild(previewDiv);
    }

    dom.outputContainer.appendChild(diffContainer);
  }

  // ============================================================================
  // BigQuery Document Alignment Audit Table Logic
  // ============================================================================

  // ============================================================================
  // BigQuery Document Alignment Audit & Explorer Logic
  // ============================================================================

  async function loadAuditLogs() {
    try {
      // 1. Fetch BigQuery status
      const statusRes = await fetch("/api/audit/status");
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        const total = statusData.total_records || 0;
        const statusText = `BigQuery: ${statusData.connected ? "Connected" : "Local Mirror"} (${total} records)`;
        if (dom.bqStatusText) dom.bqStatusText.textContent = statusText;
        if (dom.metricTotalRows) dom.metricTotalRows.textContent = `${total} rows`;
        if (dom.navBqBadge) dom.navBqBadge.textContent = `${total} records`;
      }

      // 2. Fetch BigQuery logs
      const logsRes = await fetch("/api/audit/logs?limit=50");
      if (logsRes.ok) {
        const logsData = await logsRes.json();
        state.auditRecords = logsData.records || [];
        renderAuditTable();
      }
    } catch (err) {
      console.warn("Failed to load BigQuery audit logs:", err);
      showTableError(dom.auditTableBody);
      showTableError(dom.bqExplorerTableBody);
    }
  }

  async function loadAuditSchema() {
    if (!dom.bqSchemaTbody) return;
    try {
      const res = await fetch("/api/audit/schema");
      if (!res.ok) throw new Error("Schema request failed");
      const data = await res.json();
      clearElement(dom.bqSchemaTbody);

      const fields = data.fields || [];
      if (fields.length === 0) {
        const tr = document.createElement("tr");
        const td = createTextElement("td", "No schema fields found.", "audit-table-loading");
        td.colSpan = 4;
        tr.appendChild(td);
        dom.bqSchemaTbody.appendChild(tr);
        return;
      }

      fields.forEach(function (f) {
        const tr = document.createElement("tr");
        const tdName = createTextElement("td", f.name, "schema-field-name");
        
        const tdType = document.createElement("td");
        tdType.appendChild(createTextElement("span", f.field_type, "schema-type-badge"));
        
        const tdMode = createTextElement("td", f.mode);
        tdMode.style.fontFamily = "var(--font-mono)";
        tdMode.style.fontSize = "0.75rem";
        tdMode.style.color = "var(--text-muted)";

        const tdDesc = createTextElement("td", f.description || "-");
        tdDesc.style.color = "var(--text-secondary)";

        tr.appendChild(tdName);
        tr.appendChild(tdType);
        tr.appendChild(tdMode);
        tr.appendChild(tdDesc);
        dom.bqSchemaTbody.appendChild(tr);
      });
    } catch (err) {
      console.warn("Failed to load schema:", err);
      clearElement(dom.bqSchemaTbody);
      const tr = document.createElement("tr");
      const td = createTextElement("td", "Unable to load table schema definition.", "audit-table-loading");
      td.colSpan = 4;
      tr.appendChild(td);
      dom.bqSchemaTbody.appendChild(tr);
    }
  }

  function showTableError(tableBody) {
    if (!tableBody) return;
    clearElement(tableBody);
    const tr = document.createElement("tr");
    const td = createTextElement("td", "Unable to load audit logs from BigQuery.", "audit-table-loading");
    td.colSpan = 9;
    tr.appendChild(td);
    tableBody.appendChild(tr);
  }

  function renderAuditTable() {
    renderSingleAuditTable(dom.auditTableBody, dom.auditSearchInput, dom.auditVerdictFilter);
    renderSingleAuditTable(dom.bqExplorerTableBody, dom.bqSearchInput, dom.bqVerdictFilter);
  }

  function renderSingleAuditTable(tableBody, searchInput, verdictSelect) {
    if (!tableBody) return;
    clearElement(tableBody);

    const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
    const verdictFilter = verdictSelect ? verdictSelect.value : "ALL";

    const filtered = state.auditRecords.filter(function (rec) {
      if (verdictFilter !== "ALL" && rec.verdict !== verdictFilter) {
        return false;
      }
      if (query) {
        const docName = (rec.document_name || "").toLowerCase();
        const verdict = (rec.verdict || "").toLowerCase();
        const triggers = (rec.triggers_detected || "").toLowerCase();
        const entities = (rec.entities_detected || "").toLowerCase();
        const hash = (rec.audit_hash || "").toLowerCase();
        if (
          !docName.includes(query) &&
          !verdict.includes(query) &&
          !triggers.includes(query) &&
          !entities.includes(query) &&
          !hash.includes(query)
        ) {
          return false;
        }
      }
      return true;
    });

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = createTextElement("td", "No matching document alignment records found in BigQuery.", "audit-table-loading");
      td.colSpan = 10;
      tr.appendChild(td);
      tableBody.appendChild(tr);
      return;
    }

    filtered.forEach(function (rec) {
      const tr = document.createElement("tr");

      // 1. Timestamp
      let timeStr = "-";
      if (rec.timestamp) {
        try {
          const d = new Date(rec.timestamp);
          timeStr = d.toLocaleDateString() + " " + d.toLocaleTimeString();
        } catch (e) {
          timeStr = rec.timestamp.slice(0, 19);
        }
      }
      const tdTime = createTextElement("td", timeStr);
      tdTime.style.whiteSpace = "nowrap";
      tdTime.style.fontSize = "0.75rem";
      tdTime.style.color = "var(--text-muted)";
      tr.appendChild(tdTime);

      // 2. Document Name
      const tdDoc = document.createElement("td");
      tdDoc.className = "doc-name-cell";
      tdDoc.textContent = rec.document_name || "untitled.txt";
      tdDoc.title = rec.document_name || "";
      tr.appendChild(tdDoc);

      // 3. Channel
      const tdChannel = document.createElement("td");
      const channelSpan = document.createElement("span");
      channelSpan.className = "channel-pill";
      channelSpan.textContent = rec.channel || "gcs";
      tdChannel.appendChild(channelSpan);
      tr.appendChild(tdChannel);

      // 3b. Clearance Rank Badge
      const tdRank = document.createElement("td");
      const hasRank = rec.clearance_rank !== null && rec.clearance_rank !== undefined;
      const rankPill = document.createElement("span");
      if (hasRank) {
        rankPill.className = "badge-rank rank-" + rec.clearance_rank;
        rankPill.textContent = "Rank " + rec.clearance_rank;
      } else {
        rankPill.className = "badge-rank rank-null";
        rankPill.textContent = "Null";
      }
      rankPill.style.fontSize = "0.7rem";
      rankPill.style.padding = "0.15rem 0.45rem";
      tdRank.appendChild(rankPill);
      tr.appendChild(tdRank);

      // 4. Verdict Badge
      const tdVerdict = document.createElement("td");
      const vBadge = document.createElement("span");
      vBadge.className = "verdict-badge";
      if (rec.verdict === "MNPI_CONFIRMED") {
        vBadge.classList.add("confirmed");
        vBadge.textContent = "MNPI CONFIRMED";
      } else if (rec.verdict === "POTENTIAL_MNPI") {
        vBadge.classList.add("potential");
        vBadge.textContent = "POTENTIAL MNPI";
      } else {
        vBadge.classList.add("cleared");
        vBadge.textContent = rec.verdict || "CLEARED";
      }
      tdVerdict.appendChild(vBadge);
      tr.appendChild(tdVerdict);

      // 5. Recommended Action
      const tdAction = document.createElement("td");
      tdAction.style.fontSize = "0.75rem";
      tdAction.style.fontWeight = "600";
      if (rec.recommended_action === "BLOCK_COMMUNICATION") {
        tdAction.style.color = "#f87171";
      } else if (rec.recommended_action === "ESCALATE_TO_COMPLIANCE") {
        tdAction.style.color = "#fbbf24";
      } else {
        tdAction.style.color = "#34d399";
      }
      tdAction.textContent = rec.recommended_action || "-";
      tr.appendChild(tdAction);

      // 6. 4 Assessment Criteria Alignment Scores (Mini Grid)
      const tdScores = document.createElement("td");
      const grid = document.createElement("div");
      grid.className = "score-mini-grid";

      function appendMiniScore(label, val) {
        const item = document.createElement("div");
        item.className = "score-item-mini";
        const lbl = createTextElement("span", label);
        const num = createTextElement("strong", Math.round(val * 100) + "%");
        const track = document.createElement("div");
        track.className = "score-bar-mini";
        const fill = document.createElement("div");
        fill.className = "score-fill-mini";
        fill.style.width = Math.round(val * 100) + "%";
        if (val >= 0.7) {
          fill.style.background = "#f87171";
          num.style.color = "#f87171";
        } else if (val >= 0.4) {
          fill.style.background = "#fbbf24";
          num.style.color = "#fbbf24";
        } else {
          fill.style.background = "#34d399";
          num.style.color = "#34d399";
        }
        track.appendChild(fill);
        item.appendChild(lbl);
        item.appendChild(num);
        item.appendChild(track);
        grid.appendChild(item);
      }

      appendMiniScore("Mat", rec.materiality_score || 0);
      appendMiniScore("Pub", rec.public_availability_score || 0);
      appendMiniScore("Src", rec.source_duty_score || 0);
      appendMiniScore("Harm", rec.harm_score || 0);
      tdScores.appendChild(grid);
      tr.appendChild(tdScores);

      // 7. Latency
      const tdLatency = createTextElement("td", (rec.latency_ms ? (rec.latency_ms / 1000).toFixed(1) + "s" : "-"));
      tdLatency.style.fontSize = "0.75rem";
      tdLatency.style.color = "var(--text-muted)";
      tr.appendChild(tdLatency);

      // 8. Audit Hash
      const tdHash = document.createElement("td");
      const hashSpan = document.createElement("span");
      hashSpan.className = "hash-cell";
      const fullHash = rec.audit_hash || "";
      hashSpan.textContent = fullHash.length > 14 ? fullHash.slice(0, 14) + "…" : fullHash;
      hashSpan.title = "Click to copy audit hash:\n" + fullHash;
      hashSpan.addEventListener("click", function () {
        navigator.clipboard.writeText(fullHash).then(function () {
          alert("Copied audit hash to clipboard: " + fullHash);
        });
      });
      tdHash.appendChild(hashSpan);
      tr.appendChild(tdHash);

      // 9. Inspect Action
      const tdInspect = document.createElement("td");
      const btnInspect = document.createElement("button");
      btnInspect.className = "btn-inspect";
      btnInspect.textContent = "Inspect";
      btnInspect.addEventListener("click", function () {
        showAuditModal(rec);
      });
      tdInspect.appendChild(btnInspect);
      tr.appendChild(tdInspect);

      tableBody.appendChild(tr);
    });
  }

  function showAuditModal(rec) {
    if (!dom.auditModal || !dom.modalDocBody) return;
    clearElement(dom.modalDocBody);

    if (dom.modalDocTitle) {
      dom.modalDocTitle.textContent = "Audit Record: " + (rec.document_name || "Document");
    }

    // Top Details Grid
    const detailsRow = document.createElement("div");
    detailsRow.className = "modal-detail-row";

    function appendField(label, val) {
      const f = document.createElement("div");
      f.className = "modal-field";
      f.appendChild(createTextElement("div", label, "modal-field-label"));
      f.appendChild(createTextElement("div", val, "modal-field-value"));
      detailsRow.appendChild(f);
    }

    appendField("Verdict", rec.verdict || "N/A");
    appendField("Risk Level", rec.risk_level || "N/A");
    appendField("Clearance Rank", (rec.clearance_rank !== null && rec.clearance_rank !== undefined) ? ("Rank " + rec.clearance_rank) : "Nullified (Unassigned)");
    appendField("Recommended Action", rec.recommended_action || "N/A");
    appendField("Ingestion Channel", rec.channel || "N/A");
    appendField("Model Used", rec.model_used || "gemini-3.8-flash");
    appendField("Pipeline Latency", (rec.latency_ms ? rec.latency_ms + " ms" : "-"));

    dom.modalDocBody.appendChild(detailsRow);

    // Cryptographic Audit Hash
    const hashSec = document.createElement("div");
    hashSec.style.marginBottom = "1rem";
    hashSec.appendChild(createTextElement("div", "Cryptographic Audit Hash (SHA-256)", "modal-field-label"));
    const hashBox = createTextElement("div", rec.audit_hash || "N/A", "modal-box");
    hashBox.style.padding = "0.4rem 0.6rem";
    hashSec.appendChild(hashBox);
    dom.modalDocBody.appendChild(hashSec);

    // Legal Justification
    const justSec = document.createElement("div");
    justSec.style.marginBottom = "1rem";
    justSec.appendChild(createTextElement("div", "Defensible Legal & Regulatory Justification", "modal-field-label"));
    const justBox = createTextElement("div", rec.summary_justification || "No justification recorded.", "modal-box");
    justSec.appendChild(justBox);
    dom.modalDocBody.appendChild(justSec);

    // Detected Signals
    const signalsSec = document.createElement("div");
    signalsSec.style.marginBottom = "1rem";
    signalsSec.appendChild(createTextElement("div", "Detected Entities & Corporate Triggers", "modal-field-label"));
    const sigRow = document.createElement("div");
    sigRow.style.fontSize = "0.85rem";
    sigRow.style.color = "var(--text-primary)";
    sigRow.appendChild(createTextElement("p", "Entities: " + (rec.entities_detected || "None flagged")));
    sigRow.appendChild(createTextElement("p", "Triggers: " + (rec.triggers_detected || "None flagged")));
    sigRow.appendChild(createTextElement("p", "Confidentiality / Secrecy Markers: " + (rec.has_secrecy_markers ? "YES (Detected)" : "No")));
    signalsSec.appendChild(sigRow);
    dom.modalDocBody.appendChild(signalsSec);

    // Security Entitlements Manifest JSON
    if (rec.entitlements_json) {
      const entSec = document.createElement("div");
      entSec.style.marginBottom = "1rem";
      entSec.appendChild(createTextElement("div", "Security & Entitlements Manifest (JSON)", "modal-field-label"));
      try {
        const entObj = typeof rec.entitlements_json === "string" ? JSON.parse(rec.entitlements_json) : rec.entitlements_json;
        const entPre = createTextElement("pre", JSON.stringify(entObj, null, 2), "modal-box");
        entPre.style.fontSize = "0.75rem";
        entPre.style.fontFamily = "var(--font-mono)";
        entPre.style.maxHeight = "180px";
        entPre.style.overflowY = "auto";
        entSec.appendChild(entPre);
      } catch (e) {
        const entBox = createTextElement("div", String(rec.entitlements_json), "modal-box");
        entSec.appendChild(entBox);
      }
      dom.modalDocBody.appendChild(entSec);
    }

    // Redacted Preview
    if (rec.redacted_preview) {
      const redSec = document.createElement("div");
      redSec.appendChild(createTextElement("div", "Redacted Content Preview", "modal-field-label"));
      const redBox = createTextElement("div", rec.redacted_preview, "modal-box");
      redSec.appendChild(redBox);
      dom.modalDocBody.appendChild(redSec);
    }

    dom.auditModal.classList.remove("hidden");
  }

  function hideAuditModal() {
    if (dom.auditModal) {
      dom.auditModal.classList.add("hidden");
    }
  }

  function exportLogsToCsv() {
    if (!state.auditRecords || state.auditRecords.length === 0) {
      alert("No BigQuery audit records to export.");
      return;
    }

    const headers = [
      "timestamp",
      "document_name",
      "channel",
      "clearance_rank",
      "verdict",
      "risk_level",
      "recommended_action",
      "materiality_score",
      "public_availability_score",
      "source_duty_score",
      "harm_score",
      "latency_ms",
      "audit_hash",
      "summary_justification",
      "entitlements_json",
    ];

    const csvRows = [headers.join(",")];

    state.auditRecords.forEach(function (rec) {
      const values = headers.map(function (h) {
        let val = rec[h] === undefined || rec[h] === null ? "" : String(rec[h]);
        val = val.replace(/"/g, '""');
        return `"${val}"`;
      });
      csvRows.push(values.join(","));
    });

    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `mnpi_bigquery_alignment_audit_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  // ============================================================================
  // Navigation & Sub-Tabs Event Bindings
  // ============================================================================

  // Primary View Navigation (Pipeline vs. BigQuery Explorer vs. Reinforcement Learning)
  function switchMainView(viewName) {
    if (dom.navBtnPipeline) dom.navBtnPipeline.classList.toggle("active", viewName === "pipeline");
    if (dom.navBtnBigQuery) dom.navBtnBigQuery.classList.toggle("active", viewName === "bigquery");
    if (dom.navBtnRl) dom.navBtnRl.classList.toggle("active", viewName === "rl");

    if (dom.viewPipeline) dom.viewPipeline.classList.toggle("hidden", viewName !== "pipeline");
    if (dom.viewBigQuery) dom.viewBigQuery.classList.toggle("hidden", viewName !== "bigquery");
    if (dom.viewRlExplainer) dom.viewRlExplainer.classList.toggle("hidden", viewName !== "rl");

    if (viewName === "bigquery") {
      loadAuditLogs();
      loadAuditSchema();
    }
  }

  if (dom.navBtnPipeline) {
    dom.navBtnPipeline.addEventListener("click", function () {
      switchMainView("pipeline");
    });
  }

  if (dom.navBtnBigQuery) {
    dom.navBtnBigQuery.addEventListener("click", function () {
      switchMainView("bigquery");
    });
  }

  if (dom.navBtnRl) {
    dom.navBtnRl.addEventListener("click", function () {
      switchMainView("rl");
    });
  }

  if (dom.btnOpenRlGuide) {
    dom.btnOpenRlGuide.addEventListener("click", function () {
      switchMainView("rl");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  if (dom.btnRlBackToPipeline) {
    dom.btnRlBackToPipeline.addEventListener("click", function () {
      switchMainView("pipeline");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // BigQuery Explorer Sub-Tabs (Data, Schema, SQL)
  function switchBqTab(activeBtn, activePane) {
    [dom.bqTabData, dom.bqTabSchema, dom.bqTabSql].forEach(function (btn) {
      if (btn) btn.classList.remove("active");
    });
    [dom.bqPaneData, dom.bqPaneSchema, dom.bqPaneSql].forEach(function (pane) {
      if (pane) pane.classList.remove("active");
    });
    if (activeBtn) activeBtn.classList.add("active");
    if (activePane) activePane.classList.add("active");
  }

  if (dom.bqTabData) {
    dom.bqTabData.addEventListener("click", function () {
      switchBqTab(dom.bqTabData, dom.bqPaneData);
    });
  }

  if (dom.bqTabSchema) {
    dom.bqTabSchema.addEventListener("click", function () {
      switchBqTab(dom.bqTabSchema, dom.bqPaneSchema);
      loadAuditSchema();
    });
  }

  if (dom.bqTabSql) {
    dom.bqTabSql.addEventListener("click", function () {
      switchBqTab(dom.bqTabSql, dom.bqPaneSql);
    });
  }

  // Copy SQL Button
  if (dom.btnCopySql) {
    dom.btnCopySql.addEventListener("click", function () {
      const sqlText = dom.bqSqlBlock ? dom.bqSqlBlock.textContent : "";
      navigator.clipboard.writeText(sqlText).then(function () {
        alert("Copied BigQuery SQL query to clipboard!");
      });
    });
  }

  // Export CSV
  if (dom.btnExportCsv) {
    dom.btnExportCsv.addEventListener("click", exportLogsToCsv);
  }

  // Refresh in BigQuery Explorer
  if (dom.btnRefreshBqExplorer) {
    dom.btnRefreshBqExplorer.addEventListener("click", function () {
      loadAuditLogs();
      loadAuditSchema();
    });
  }

  // Search & Filter event bindings
  if (dom.btnRefreshAudit) {
    dom.btnRefreshAudit.addEventListener("click", loadAuditLogs);
  }

  if (dom.auditSearchInput) {
    dom.auditSearchInput.addEventListener("input", function () {
      if (dom.bqSearchInput) dom.bqSearchInput.value = dom.auditSearchInput.value;
      renderAuditTable();
    });
  }

  if (dom.bqSearchInput) {
    dom.bqSearchInput.addEventListener("input", function () {
      if (dom.auditSearchInput) dom.auditSearchInput.value = dom.bqSearchInput.value;
      renderAuditTable();
    });
  }

  if (dom.auditVerdictFilter) {
    dom.auditVerdictFilter.addEventListener("change", function () {
      if (dom.bqVerdictFilter) dom.bqVerdictFilter.value = dom.auditVerdictFilter.value;
      renderAuditTable();
    });
  }

  if (dom.bqVerdictFilter) {
    dom.bqVerdictFilter.addEventListener("change", function () {
      if (dom.auditVerdictFilter) dom.auditVerdictFilter.value = dom.bqVerdictFilter.value;
      renderAuditTable();
    });
  }

  if (dom.btnCloseModal) {
    dom.btnCloseModal.addEventListener("click", hideAuditModal);
  }

  if (dom.auditModal) {
    dom.auditModal.addEventListener("click", function (e) {
      if (e.target === dom.auditModal) {
        hideAuditModal();
      }
    });
  }

  // ============================================================================
  // RL Interactive Formula Tuner & Real-Time Simulator Controller
  // ============================================================================

  function updateFormulaSimulation() {
    if (!dom.sliderRTask) return;

    var rTask = parseFloat(dom.sliderRTask.value) || 1.0;
    var lambdaVeto = parseFloat(dom.sliderLambdaVeto.value) || -10.0;
    var fpPenalty = parseFloat(dom.sliderFpPenalty.value) || -4.0;
    var gamma = parseFloat(dom.sliderGammaCausal.value) || 2.0;
    var dpoMargin = parseFloat(dom.sliderDpoMargin.value) || 2.5;
    var wMat = parseFloat(dom.sliderWeightMat.value) || -3.0;

    // 1. Update Slider Badges
    if (dom.valBadgeRTask) dom.valBadgeRTask.textContent = (rTask >= 0 ? "+" : "") + rTask.toFixed(1);
    if (dom.valBadgeLambdaVeto) dom.valBadgeLambdaVeto.textContent = lambdaVeto.toFixed(1);
    if (dom.valBadgeFpPenalty) dom.valBadgeFpPenalty.textContent = fpPenalty.toFixed(1);
    if (dom.valBadgeGammaCausal) dom.valBadgeGammaCausal.textContent = gamma.toFixed(1);
    if (dom.valBadgeDpoMargin) dom.valBadgeDpoMargin.textContent = "≥ " + dpoMargin.toFixed(1);
    if (dom.valBadgeWeightMat) dom.valBadgeWeightMat.textContent = wMat.toFixed(1);

    // 2. Update Formula Box Equation Display
    if (dom.formulaTermRTask) dom.formulaTermRTask.textContent = (rTask >= 0 ? "+" : "") + rTask.toFixed(2);
    if (dom.formulaTermVeto) dom.formulaTermVeto.textContent = "(" + lambdaVeto.toFixed(2) + ")";
    if (dom.formulaTermFp) dom.formulaTermFp.textContent = "(" + fpPenalty.toFixed(2) + ")";
    if (dom.formulaTermGamma) dom.formulaTermGamma.textContent = gamma.toFixed(2);

    // 3. Update Term Card Headers
    if (dom.displayCardRTask) dom.displayCardRTask.innerHTML = "R<sub>task</sub> = " + (rTask >= 0 ? "+" : "") + rTask.toFixed(1);
    if (dom.displayCardVeto) dom.displayCardVeto.innerHTML = "&lambda;<sub>veto</sub> = " + lambdaVeto.toFixed(1);
    if (dom.displayCardFp) dom.displayCardFp.innerHTML = "R<sub>fp</sub> = " + fpPenalty.toFixed(1);
    if (dom.displayCardGamma) dom.displayCardGamma.innerHTML = "-&gamma; &middot; S<sub>influence</sub> (&gamma; = " + gamma.toFixed(1) + ")";
    if (dom.pillValMat01) dom.pillValMat01.textContent = wMat.toFixed(1);

    // 4. Recalculate Scenario A (M&A Leak)
    // Winning decision: Neutralized leak -> Task Reward + Mitigated Violation Codes (+4.0)
    var rWinA = rTask + 4.0;
    // Losing decision: Unredacted leak allowed -> Task + Veto + wMat + Mosaic02(-2.0) - gamma * S(0.9)
    var rLoseA = rTask + lambdaVeto + wMat - 2.0 - (gamma * 0.9);
    var deltaA = rWinA - rLoseA;

    if (dom.scenarioARwin) dom.scenarioARwin.textContent = (rWinA >= 0 ? "+" : "") + rWinA.toFixed(2);
    if (dom.scenarioARlose) dom.scenarioARlose.textContent = rLoseA.toFixed(2);
    if (dom.scenarioALoseDesc) {
      dom.scenarioALoseDesc.innerHTML = "Catastrophic failure. Triggers &lambda;<sub>veto</sub> (" + lambdaVeto.toFixed(1) +
        "), code penalties (" + (wMat - 2.0).toFixed(1) + "), and causal influence penalty (-" + (gamma * 0.9).toFixed(1) + ").";
    }
    if (dom.scenarioAMarginBanner) {
      var isAcceptedA = deltaA >= dpoMargin;
      dom.scenarioAMarginBanner.className = "margin-banner " + (isAcceptedA ? "accepted" : "rejected");
      dom.scenarioAMarginBanner.innerHTML = "Reward Margin: <strong>&Delta;R = " +
        (rWinA >= 0 ? "+" : "") + rWinA.toFixed(2) + " - (" + rLoseA.toFixed(2) + ") = " +
        (deltaA >= 0 ? "+" : "") + deltaA.toFixed(2) + "</strong> (" +
        (isAcceptedA ? "&ge; " + dpoMargin.toFixed(1) + " &rarr; Accepted into DPO Dataset" : "< " + dpoMargin.toFixed(1) + " &rarr; Rejected: Insufficient Margin") +
        ")";
    }

    // 5. Recalculate Scenario B (Routine Public Press Release)
    // Winning decision: Cleared -> Task Reward + Public Codes (+4.5)
    var rWinB = rTask + 4.5;
    // Losing decision: False positive over-blocking -> Task + R_fp - Misassigned codes (-3.0) - 2.0
    var rLoseB = rTask + fpPenalty - 5.0;
    var deltaB = rWinB - rLoseB;

    if (dom.scenarioBRwin) dom.scenarioBRwin.textContent = (rWinB >= 0 ? "+" : "") + rWinB.toFixed(2);
    if (dom.scenarioBRlose) dom.scenarioBRlose.textContent = rLoseB.toFixed(2);
    if (dom.scenarioBLoseDesc) {
      dom.scenarioBLoseDesc.innerHTML = "Hyper-conservative false alarm. Triggers R<sub>fp</sub> (" + fpPenalty.toFixed(1) +
        ") False Positive penalty for over-blocking public news.";
    }
    if (dom.scenarioBMarginBanner) {
      var isAcceptedB = deltaB >= dpoMargin;
      dom.scenarioBMarginBanner.className = "margin-banner " + (isAcceptedB ? "accepted" : "rejected");
      dom.scenarioBMarginBanner.innerHTML = "Reward Margin: <strong>&Delta;R = " +
        (rWinB >= 0 ? "+" : "") + rWinB.toFixed(2) + " - (" + rLoseB.toFixed(2) + ") = " +
        (deltaB >= 0 ? "+" : "") + deltaB.toFixed(2) + "</strong> (" +
        (isAcceptedB ? "&ge; " + dpoMargin.toFixed(1) + " &rarr; Accepted into DPO Dataset" : "< " + dpoMargin.toFixed(1) + " &rarr; Rejected: Insufficient Margin") +
        ")";
    }
  }

  function setPreset(name) {
    [dom.presetBalanced, dom.presetStrict, dom.presetPermissive].forEach(function (btn) {
      if (btn) btn.classList.remove("active");
    });

    if (name === "balanced") {
      if (dom.presetBalanced) dom.presetBalanced.classList.add("active");
      if (dom.sliderRTask) dom.sliderRTask.value = "1.0";
      if (dom.sliderLambdaVeto) dom.sliderLambdaVeto.value = "-10.0";
      if (dom.sliderFpPenalty) dom.sliderFpPenalty.value = "-4.0";
      if (dom.sliderGammaCausal) dom.sliderGammaCausal.value = "2.0";
      if (dom.sliderDpoMargin) dom.sliderDpoMargin.value = "2.5";
      if (dom.sliderWeightMat) dom.sliderWeightMat.value = "-3.0";
    } else if (name === "strict") {
      if (dom.presetStrict) dom.presetStrict.classList.add("active");
      if (dom.sliderRTask) dom.sliderRTask.value = "1.0";
      if (dom.sliderLambdaVeto) dom.sliderLambdaVeto.value = "-20.0";
      if (dom.sliderFpPenalty) dom.sliderFpPenalty.value = "-1.5";
      if (dom.sliderGammaCausal) dom.sliderGammaCausal.value = "4.0";
      if (dom.sliderDpoMargin) dom.sliderDpoMargin.value = "3.0";
      if (dom.sliderWeightMat) dom.sliderWeightMat.value = "-5.0";
    } else if (name === "permissive") {
      if (dom.presetPermissive) dom.presetPermissive.classList.add("active");
      if (dom.sliderRTask) dom.sliderRTask.value = "1.5";
      if (dom.sliderLambdaVeto) dom.sliderLambdaVeto.value = "-6.0";
      if (dom.sliderFpPenalty) dom.sliderFpPenalty.value = "-8.0";
      if (dom.sliderGammaCausal) dom.sliderGammaCausal.value = "1.0";
      if (dom.sliderDpoMargin) dom.sliderDpoMargin.value = "2.0";
      if (dom.sliderWeightMat) dom.sliderWeightMat.value = "-2.0";
    }
    updateFormulaSimulation();
  }

  // Bind slider events (input and change for real-time 60fps responsiveness)
  [
    dom.sliderRTask,
    dom.sliderLambdaVeto,
    dom.sliderFpPenalty,
    dom.sliderGammaCausal,
    dom.sliderDpoMargin,
    dom.sliderWeightMat,
  ].forEach(function (slider) {
    if (slider) {
      slider.addEventListener("input", function () {
        [dom.presetBalanced, dom.presetStrict, dom.presetPermissive].forEach(function (btn) {
          if (btn) btn.classList.remove("active");
        });
        updateFormulaSimulation();
      });
    }
  });

  if (dom.presetBalanced) dom.presetBalanced.addEventListener("click", function () { setPreset("balanced"); });
  if (dom.presetStrict) dom.presetStrict.addEventListener("click", function () { setPreset("strict"); });
  if (dom.presetPermissive) dom.presetPermissive.addEventListener("click", function () { setPreset("permissive"); });

  // Apply weights to backend API
  if (dom.btnApplyWeights) {
    dom.btnApplyWeights.addEventListener("click", async function () {
      var payload = {
        r_task: parseFloat(dom.sliderRTask.value),
        lambda_veto: parseFloat(dom.sliderLambdaVeto.value),
        false_positive_penalty: parseFloat(dom.sliderFpPenalty.value),
        gamma_causal: parseFloat(dom.sliderGammaCausal.value),
        dpo_min_margin: parseFloat(dom.sliderDpoMargin.value),
        weight_mat_ma: parseFloat(dom.sliderWeightMat.value),
      };

      if (dom.tunerStatusMsg) {
        dom.tunerStatusMsg.innerHTML = '<span class="status-indicator live"></span> <span>Applying weights to live pipeline...</span>';
      }

      try {
        var resp = await fetch("/api/rl/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        var data = await resp.json();
        if (resp.ok && data.status === "success") {
          if (dom.tunerStatusMsg) {
            dom.tunerStatusMsg.innerHTML = '<span style="color: #34d399; font-weight: 600;">✓ Saved to Live Arbiter! Real-time document evaluations will use these weights.</span>';
          }
        } else {
          throw new Error(data.detail || "Failed to update weights");
        }
      } catch (err) {
        if (dom.tunerStatusMsg) {
          dom.tunerStatusMsg.innerHTML = '<span style="color: #f87171;">✗ Error applying weights: ' + escapeHtml(err.message) + '</span>';
        }
      }
    });
  }

  // Reset weights to default
  if (dom.btnResetWeights) {
    dom.btnResetWeights.addEventListener("click", async function () {
      setPreset("balanced");
      try {
        await fetch("/api/rl/reset", { method: "POST" });
        if (dom.tunerStatusMsg) {
          dom.tunerStatusMsg.innerHTML = '<span style="color: #60a5fa; font-weight: 600;">↺ Reset to baseline theoretical weights.</span>';
        }
      } catch (e) {
        console.warn("Reset error:", e);
      }
    });
  }

  // Load existing configuration from backend on startup
  async function loadRLConfig() {
    try {
      var resp = await fetch("/api/rl/config");
      if (!resp.ok) return;
      var data = await resp.json();
      if (data && data.active) {
        var a = data.active;
        if (dom.sliderRTask && a.r_task !== undefined) dom.sliderRTask.value = a.r_task;
        if (dom.sliderLambdaVeto && a.lambda_veto !== undefined) dom.sliderLambdaVeto.value = a.lambda_veto;
        if (dom.sliderFpPenalty && a.false_positive_penalty !== undefined) dom.sliderFpPenalty.value = a.false_positive_penalty;
        if (dom.sliderGammaCausal && a.gamma_causal !== undefined) dom.sliderGammaCausal.value = a.gamma_causal;
        if (dom.sliderDpoMargin && a.dpo_min_margin !== undefined) dom.sliderDpoMargin.value = a.dpo_min_margin;
        if (dom.sliderWeightMat && a.weight_mat_ma !== undefined) dom.sliderWeightMat.value = a.weight_mat_ma;
        updateFormulaSimulation();
      }
    } catch (e) {
      console.warn("Could not fetch /api/rl/config", e);
    }
  }

  // Entitlements Downstream Access Simulator
  if (dom.btnTestEntitlement) {
    dom.btnTestEntitlement.addEventListener("click", async function () {
      const selectedRole = dom.simUserRole ? dom.simUserRole.value : "ANALYST";
      const lastData = state.lastProcessedData;
      const ent = (lastData && lastData.verdict && lastData.verdict.entitlements) || (lastData && lastData.entitlements);

      if (!ent) {
        alert("Please process a document first to generate an entitlements tag.");
        return;
      }

      try {
        const res = await fetch("/api/entitlements/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_role: selectedRole,
            document_name: ent.document_id,
            clearance_rank: ent.clearance_rank,
            entitlements: ent,
          }),
        });
        const evalResult = await res.json();
        if (dom.simResultBox) {
          if (evalResult.access_granted) {
            dom.simResultBox.className = "sim-result-box granted";
            dom.simResultBox.innerHTML = "<strong>✅ ACCESS GRANTED:</strong> " + escapeHtml(evalResult.reason);
          } else {
            dom.simResultBox.className = "sim-result-box denied";
            dom.simResultBox.innerHTML = "<strong>❌ ACCESS DENIED:</strong> " + escapeHtml(evalResult.reason);
          }
        }
      } catch (err) {
        console.error("Entitlement verification error:", err);
      }
    });
  }

  // Copy Entitlements JSON Manifest to Clipboard
  if (dom.btnCopyEntitlementsJson) {
    dom.btnCopyEntitlementsJson.addEventListener("click", function () {
      if (dom.entitlementsJsonDisplay) {
        navigator.clipboard.writeText(dom.entitlementsJsonDisplay.textContent).then(function () {
          const orig = dom.btnCopyEntitlementsJson.textContent;
          dom.btnCopyEntitlementsJson.textContent = "✓ Copied Manifest!";
          setTimeout(function () {
            dom.btnCopyEntitlementsJson.textContent = orig;
          }, 2000);
        });
      }
    });
  }

  // Initialize
  loadPresetScenarios();
  loadBucketFileList();
  loadAuditLogs();
  loadAuditSchema();
  loadRLConfig();
})();
