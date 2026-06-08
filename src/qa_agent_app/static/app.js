let topics = [];
let selectedTopicId = null;
let topicSources = [];

const els = {
  topics: document.querySelector("#topics"),
  topicForm: document.querySelector("#topic-form"),
  topicSource: document.querySelector("#topic-source"),
  addTopicSource: document.querySelector("#add-topic-source"),
  topicDocuments: document.querySelector("#topic-documents"),
  topicSourceList: document.querySelector("#topic-source-list"),
  refreshTopics: document.querySelector("#refresh-topics"),
  emptyState: document.querySelector("#empty-state"),
  detail: document.querySelector("#topic-detail"),
  detailTitle: document.querySelector("#detail-title"),
  detailDescription: document.querySelector("#detail-description"),
  topicStatus: document.querySelector("#topic-status"),
  deleteTopic: document.querySelector("#delete-topic"),
  ingestForm: document.querySelector("#ingest-form"),
  uploadForm: document.querySelector("#upload-form"),
  askForm: document.querySelector("#ask-form"),
  answer: document.querySelector("#answer"),
  toast: document.querySelector("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }
  if (response.status === 204) return null;
  return response.json();
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 4500);
}

async function loadTopics() {
  topics = await api("/api/topics");
  renderTopics();
  if (selectedTopicId && topics.some((topic) => topic.id === selectedTopicId)) {
    selectTopic(selectedTopicId);
  } else if (topics.length) {
    selectTopic(topics[0].id);
  } else {
    selectedTopicId = null;
    renderDetail(null);
  }
}

function renderTopics() {
  els.topics.innerHTML = "";
  for (const topic of topics) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `topic ${topic.id === selectedTopicId ? "active" : ""}`;
    button.innerHTML = `<strong>${escapeHtml(topic.name)}</strong><small>${topic.status}</small>`;
    button.addEventListener("click", () => selectTopic(topic.id));
    els.topics.append(button);
  }
}

function selectTopic(topicId) {
  selectedTopicId = topicId;
  renderTopics();
  renderDetail(topics.find((topic) => topic.id === topicId));
}

function renderDetail(topic) {
  els.emptyState.hidden = Boolean(topic);
  els.detail.hidden = !topic;
  els.answer.hidden = true;
  if (!topic) return;
  els.detailTitle.textContent = topic.name;
  els.detailDescription.textContent = topic.description || "No description.";
  els.topicStatus.textContent = `${topic.status}${topic.graph_path ? " / graph ready" : ""}`;
}

els.topicForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.querySelector("#topic-name").value;
  addTopicSourceFromInput();
  const description = topicSources.join("\n");
  try {
    const topic = await api("/api/topics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    });
    selectedTopicId = topic.id;
    els.topicForm.reset();
    els.topicDocuments.value = "";
    topicSources = [];
    renderTopicSources();
    await loadTopics();
  } catch (error) {
    showToast(error.message);
  }
});

els.addTopicSource.addEventListener("click", addTopicSourceFromInput);

els.topicDocuments.addEventListener("change", () => {
  for (const file of els.topicDocuments.files) {
    addTopicSource(`Document: ${file.name}`);
  }
  els.topicDocuments.value = "";
});

els.topicSource.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addTopicSourceFromInput();
  }
});

els.refreshTopics.addEventListener("click", async () => {
  const originalText = els.refreshTopics.textContent;
  els.refreshTopics.disabled = true;
  els.refreshTopics.textContent = "Refreshing...";
  els.refreshTopics.classList.add("is-loading");
  try {
    await loadTopics();
    showToast("Topics refreshed.");
  } catch (error) {
    showToast(error.message);
  } finally {
    els.refreshTopics.disabled = false;
    els.refreshTopics.textContent = originalText;
    els.refreshTopics.classList.remove("is-loading");
  }
});

els.deleteTopic.addEventListener("click", async () => {
  if (!selectedTopicId) return;
  try {
    await api(`/api/topics/${selectedTopicId}`, { method: "DELETE" });
    selectedTopicId = null;
    await loadTopics();
  } catch (error) {
    showToast(error.message);
  }
});

els.ingestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedTopicId) return;
  const kind = document.querySelector("#source-kind").value;
  const value = document.querySelector("#source-value").value;
  showToast("Building graph. This may take a while.");
  try {
    await api(`/api/topics/${selectedTopicId}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, value }),
    });
    await loadTopics();
    showToast("Graph build complete.");
  } catch (error) {
    await loadTopics();
    showToast(error.message);
  }
});

els.uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedTopicId) return;
  const files = document.querySelector("#upload-files").files;
  const form = new FormData();
  for (const file of files) form.append("files", file);
  showToast("Uploading and building graph.");
  try {
    await api(`/api/topics/${selectedTopicId}/upload`, { method: "POST", body: form });
    await loadTopics();
    showToast("Upload graph build complete.");
  } catch (error) {
    await loadTopics();
    showToast(error.message);
  }
});

els.askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedTopicId) return;
  const question = document.querySelector("#question").value;
  try {
    const result = await api(`/api/topics/${selectedTopicId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    renderAnswer(result);
  } catch (error) {
    showToast(error.message);
  }
});

function renderAnswer(result) {
  const citations = result.citations
    .map((citation) => `<li>${escapeHtml(citation.label)} ${citation.path ? `(${escapeHtml(citation.path)})` : ""}</li>`)
    .join("");
  els.answer.innerHTML = `<h3>Answer</h3><div>${escapeHtml(result.answer)}</div><ul class="citations">${citations}</ul>`;
  els.answer.hidden = false;
}

function addTopicSourceFromInput() {
  const value = els.topicSource.value.trim();
  if (!value) return;
  addTopicSource(value);
  els.topicSource.value = "";
}

function addTopicSource(value) {
  if (!topicSources.includes(value)) {
    topicSources.push(value);
    renderTopicSources();
  }
}

function renderTopicSources() {
  els.topicSourceList.innerHTML = "";
  for (const [index, source] of topicSources.entries()) {
    const item = document.createElement("li");
    item.innerHTML = `<span>${escapeHtml(source)}</span><button type="button" class="remove-source" aria-label="Remove source">Remove</button>`;
    item.querySelector("button").addEventListener("click", () => {
      topicSources.splice(index, 1);
      renderTopicSources();
    });
    els.topicSourceList.append(item);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadTopics().catch((error) => showToast(error.message));
