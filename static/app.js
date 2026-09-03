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
    bucketSelect: document.getElementById("bucket-select"),
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

  async function loadBucketFileList() {
    try {
      const res = await fetch("/api/bucket/files");
      if (!res.ok) throw new Error("Failed to load bucket files");
      const data = await res.json();

      clearElement(dom.bucketSelect);

      const defaultOpt = document.createElement("option");
      defaultOpt.value = "";
      defaultOpt.textContent = "-- Select file in " + (data.bucket || "gs://quarantine-holding-zone/incoming/") + " --";
      dom.bucketSelect.appendChild(defaultOpt);

      data.files.forEach(function (file) {
        const opt = document.createElement("option");
        opt.value = file.gcs_uri;
        opt.textContent = file.filename + " (" + file.size_bytes + " bytes)";
        dom.bucketSelect.appendChild(opt);
      });
    } catch (err) {
      // Bucket list optional failure
    }
  }

  dom.bucketSelect.addEventListener("change", function () {
    if (dom.bucketSelect.value) {
      dom.gcsUriInput.value = dom.bucketSelect.value;
    }
  });

  dom.btnFetchBucket.addEventListener("click", async function () {
    const uri = dom.gcsUriInput.value.trim();
    if (!uri) return;

    dom.btnFetchBucket.textContent = "Fetching...";
    try {
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

      // Auto-detect channel from filename
      if (data.filename.includes("zoom")) setChannelActive("zoom");
      else if (data.filename.includes("slack")) setChannelActive("slack");
      else if (data.filename.includes("email")) setChannelActive("email");
      else if (data.filename.includes("salesforce")) setChannelActive("salesforce");
      else setChannelActive("cloud_storage");

      dom.uploadStatus.className = "upload-status-box";
      dom.uploadStatus.textContent = "Fetched: " + data.gcs_uri + " (" + data.bytes + " bytes)";
      dom.uploadStatus.classList.remove("hidden");
    } catch (err) {
      dom.uploadStatus.className = "upload-status-box";
      dom.uploadStatus.style.borderColor = "#ef4444";
      dom.uploadStatus.style.color = "#f87171";
      dom.uploadStatus.textContent = "Fetch error: " + err.message;
      dom.uploadStatus.classList.remove("hidden");
    } finally {
      dom.btnFetchBucket.textContent = "Fetch";
    }
  });

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

      dom.uploadStatus.textContent = "Quarantined in Cloud Storage: " + data.quarantine_uri;
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
    } catch (err) {
      alert("Pipeline Error: " + err.message);
    } finally {
      dom.btnProcess.disabled = false;
      dom.processSpinner.classList.add("hidden");
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

  // Initialize
  loadPresetScenarios();
  loadBucketFileList();
})();
