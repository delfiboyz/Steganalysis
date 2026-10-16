const dropzone = document.getElementById("dropzone");
const dropzoneText = document.getElementById("dropzoneText");
const fileInput = document.getElementById("fileInput");
const preview = document.getElementById("preview");
const analyzeBtn = document.getElementById("analyzeBtn");
const uploadForm = document.getElementById("uploadForm");
const errorBox = document.getElementById("errorBox");
const loading = document.getElementById("loading");
const resultsSection = document.getElementById("resultsSection");
const channelTabs = document.getElementById("channelTabs");

let selectedFile = null;
let lastData = null;
let activeChannel = null;
let chiChart = null;
let rsChart = null;

dropzone.addEventListener("click", () => fileInput.click());

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);

["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

function handleFile(file) {
  selectedFile = file;
  dropzoneText.textContent = file.name;
  analyzeBtn.disabled = false;
  errorBox.hidden = true;

  const reader = new FileReader();
  reader.onload = (e) => {
    preview.src = e.target.result;
    preview.hidden = false;
  };
  reader.readAsDataURL(file);
}

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedFile) return;

  errorBox.hidden = true;
  resultsSection.hidden = true;
  loading.hidden = false;
  analyzeBtn.disabled = true;

  const formData = new FormData();
  formData.append("image", selectedFile);

  try {
    const res = await fetch("/analyze", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Terjadi kesalahan saat menganalisis.");
    }

    lastData = data;
    renderResults(data);
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.hidden = false;
  } finally {
    loading.hidden = true;
    analyzeBtn.disabled = false;
  }
});

function renderResults(data) {
  const summary = data.summary;

  document.getElementById("verdictText").textContent = summary.verdict;
  document.getElementById("fileMeta").textContent =
    `${data.filename} — ${data.width}x${data.height}px`;

  const badge = document.getElementById("confidenceBadge");
  badge.textContent = `Keyakinan: ${summary.confidence}`;
  badge.className = "badge " +
    (summary.confidence === "Tinggi" ? "high" : summary.confidence === "Sedang" ? "medium" : "low");

  const noteEl = document.getElementById("verdictNote");
  if (summary.note) {
    noteEl.textContent = summary.note;
    noteEl.hidden = false;
  } else {
    noteEl.hidden = true;
  }

  const channelNames = Object.keys(data.channels);
  activeChannel = "Grayscale" in data.channels ? "Grayscale" : channelNames[0];

  const roleByChannel = {};
  summary.details.forEach((d) => { roleByChannel[d.channel] = d.role; });

  channelTabs.innerHTML = "";
  channelNames.forEach((name) => {
    const tab = document.createElement("div");
    tab.className = "channel-tab" + (name === activeChannel ? " active" : "");
    tab.textContent = roleByChannel[name] === "primary" ? `${name} (utama)` : name;
    tab.addEventListener("click", () => {
      activeChannel = name;
      document.querySelectorAll(".channel-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      drawCharts(data, activeChannel);
    });
    channelTabs.appendChild(tab);
  });

  renderTable(summary.details);
  drawCharts(data, activeChannel);

  resultsSection.hidden = false;
}

function renderTable(details) {
  const tbody = document.querySelector("#compareTable tbody");
  tbody.innerHTML = "";

  details.forEach((d) => {
    const tr = document.createElement("tr");
    const roleLabel = d.role === "primary"
      ? '<span class="role-tag primary">Utama</span>'
      : '<span class="role-tag supporting">Pendukung</span>';

    tr.innerHTML = `
      <td>${d.channel}</td>
      <td>${roleLabel}</td>
      <td>${pill(d.chi_square_suspect)}</td>
      <td>${d.chi_square_estimated_percent.toFixed(1)}%</td>
      <td>${pill(d.rs_suspect)}</td>
      <td>${d.rs_estimated_percent.toFixed(2)}%</td>
      <td>${pill(d.agreement, "Ya", "Tidak")}</td>
    `;
    tbody.appendChild(tr);
  });
}

function pill(bool, yesLabel = "Terdeteksi", noLabel = "Normal") {
  return `<span class="pill ${bool ? "yes" : "no"}">${bool ? yesLabel : noLabel}</span>`;
}

function drawCharts(data, channelName) {
  const channel = data.channels[channelName];

  // Chi-square p-value curve
  const chiCtx = document.getElementById("chiChart").getContext("2d");
  const labels = channel.chi_square_curve.map((r) => r.sample_percentage + "%");
  const pValues = channel.chi_square_curve.map((r) => r.p_value);

  if (chiChart) chiChart.destroy();
  chiChart = new Chart(chiCtx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: `P-Value (${channelName})`,
        data: pValues,
        borderColor: "#4fa3ff",
        backgroundColor: "rgba(79,163,255,0.15)",
        tension: 0.25,
        fill: true,
        pointRadius: 2,
      }],
    },
    options: {
      scales: {
        y: { min: 0, max: 1, ticks: { color: "#8b96a3" }, grid: { color: "#2b3645" } },
        x: { ticks: { color: "#8b96a3" }, grid: { color: "#2b3645" } },
      },
      plugins: { legend: { labels: { color: "#e6edf3" } } },
    },
  });

  // RS analysis bar chart
  const rs = channel.rs_analysis;
  const rsCtx = document.getElementById("rsChart").getContext("2d");

  if (rsChart) rsChart.destroy();
  rsChart = new Chart(rsCtx, {
    type: "bar",
    data: {
      labels: ["RM", "SM", "R-M", "S-M"],
      datasets: [{
        label: `% Grup (${channelName})`,
        data: [rs.RM, rs.SM, rs.R_minus_M, rs.S_minus_M],
        backgroundColor: ["#4fa3ff", "#ff5c5c", "#4ad9a0", "#ffb648"],
      }],
    },
    options: {
      scales: {
        y: { beginAtZero: true, ticks: { color: "#8b96a3" }, grid: { color: "#2b3645" } },
        x: { ticks: { color: "#8b96a3" }, grid: { color: "#2b3645" } },
      },
      plugins: { legend: { display: false } },
    },
  });
}
