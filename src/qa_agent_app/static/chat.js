let topics = [];
let threads = [];
let activeTopicId = null;
let activeThreadId = "agent";
let modalSources = [];
let modalFiles = [];
let settingsTopicId = null;
let settingsSources = [];
let settingsFiles = [];
let messages = [];
let isCreatingTopic = false;
let isUpdatingTopicSources = false;
let topicPollTimer = null;

const els = {
  sidebar: document.querySelector("#thread-history"),
  openSidebar: document.querySelector("#toggle-sidebar-open"),
  closeSidebar: document.querySelector("#toggle-sidebar-close"),
  agentThread: document.querySelector("#agent-thread"),
  manualTopic: document.querySelector("#manual-topic"),
  topicTree: document.querySelector("#topic-tree"),
  messages: document.querySelector("#messages"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  composerHint: document.querySelector("#composer-hint"),
  modal: document.querySelector("#topic-modal"),
  modalForm: document.querySelector("#modal-topic-form"),
  closeModal: document.querySelector("#close-modal"),
  modalTopicName: document.querySelector("#modal-topic-name"),
  modalTopicSource: document.querySelector("#modal-topic-source"),
  modalAddSource: document.querySelector("#modal-add-source"),
  modalTopicFiles: document.querySelector("#modal-topic-files"),
  modalSourceList: document.querySelector("#modal-source-list"),
  modalSubmit: document.querySelector("#topic-modal .modal-submit"),
  settingsModal: document.querySelector("#topic-settings-modal"),
  settingsForm: document.querySelector("#topic-settings-form"),
  closeSettingsModal: document.querySelector("#close-topic-settings"),
  settingsTitle: document.querySelector("#topic-settings-title"),
  settingsSource: document.querySelector("#topic-settings-source"),
  settingsAddSource: document.querySelector("#topic-settings-add-source"),
  settingsFiles: document.querySelector("#topic-settings-files"),
  settingsSourceList: document.querySelector("#topic-settings-source-list"),
  settingsSubmit: document.querySelector("#topic-settings-submit"),
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
  els.toast.textContent = formatUiMessage(message);
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 3600);
}

function setSidebarOpen(open) {
  els.sidebar.classList.toggle("is-collapsed", !open);
  document.querySelector(".chat-shell").classList.toggle("sidebar-hidden", !open);
}

async function loadData() {
  [topics, threads] = await Promise.all([api("/api/topics"), api("/api/threads")]);
  renderTopicTree();
  syncActiveTopicState();
  scheduleTopicPolling();
}

function renderTopicTree() {
  els.topicTree.innerHTML = "";
  for (const topic of topics) {
    const group = document.createElement("section");
    group.className = "topic-group";
    const header = document.createElement("div");
    header.className = "topic-group-header";
    const title = document.createElement("p");
    title.className = "topic-title";
    title.textContent = topic.name;
    header.append(title);

    const actions = document.createElement("div");
    actions.className = "topic-group-actions";

    const settingsButton = document.createElement("button");
    settingsButton.type = "button";
    settingsButton.className = "topic-action-button";
    settingsButton.textContent = "Settings";
    settingsButton.addEventListener("click", () => openTopicSettings(topic.id));
    actions.append(settingsButton);

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "topic-action-button topic-action-delete";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteTopic(topic.id));
    actions.append(deleteButton);

    header.append(actions);
    group.append(header);

    const topicThreads = threads.filter((thread) => thread.topic_id === topic.id);
    for (const thread of topicThreads) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `thread-button ${thread.id === activeThreadId ? "active" : ""}`;
      button.innerHTML = `<span>${escapeHtml(thread.title)}</span><small>${escapeHtml(topicStatusText(topic))}</small>`;
      button.addEventListener("click", () => selectThread(topic.id, thread.id));
      group.append(button);
    }
    els.topicTree.append(group);
  }
}

function selectThread(topicId, threadId) {
  activeTopicId = topicId;
  activeThreadId = threadId;
  els.agentThread.classList.remove("active");
  updateComposerHint(topicId);
  messages = [];
  renderMessages();
  renderTopicTree();
}

function selectAgentChat() {
  activeTopicId = null;
  activeThreadId = "agent";
  els.agentThread.classList.add("active");
  els.composerHint.textContent = "QA Agent creates a new topic from your message.";
  messages = [];
  renderMessages();
  renderTopicTree();
}

async function createTopic(name, sources = []) {
  const sourceValues = sources.filter((source) => typeof source === "string");
  const description = sourceValues.join("\n");
  const topic = await api("/api/topics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  await loadData();
  const defaultThread = threads.find((thread) => thread.topic_id === topic.id && thread.title === "Agent Chat");
  selectThread(topic.id, defaultThread?.id || "agent");
  if (sources.length) {
    markTopicIndexing(topic.id);
    void runTopicSetup(topic.id, topic.name, sources);
  }
  return topic;
}

async function runTopicSetup(topicId, topicName, sources) {
  try {
    await addSourcesToTopic(topicId, sources);
    await loadData();
    if (activeTopicId === topicId) {
      updateComposerHint(topicId);
    }
    showToast(`Topic "${topicName}" is ready.`);
  } catch (error) {
    await loadData().catch(() => {});
    if (activeTopicId === topicId) {
      updateComposerHint(topicId);
    }
    showToast(error.message);
  }
}

async function addSourcesToTopic(topicId, sources = []) {
  const sourceValues = sources.filter((source) => typeof source === "string");
  const uploadFiles = sources.filter((source) => source instanceof File);

  for (const source of sourceValues) {
    await api(`/api/topics/${topicId}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: inferSourceKind(source), value: source }),
    });
  }

  if (uploadFiles.length) {
    const formData = new FormData();
    for (const file of uploadFiles) {
      formData.append("files", file, file.name);
    }
    await api(`/api/topics/${topicId}/upload`, {
      method: "POST",
      body: formData,
    });
  }
}

els.agentThread.addEventListener("click", selectAgentChat);

els.openSidebar.addEventListener("click", () => setSidebarOpen(true));
els.closeSidebar.addEventListener("click", () => setSidebarOpen(false));

els.manualTopic.addEventListener("click", () => {
  modalSources = [];
  modalFiles = [];
  renderModalSources();
  els.modalForm.reset();
  els.modal.showModal();
});

els.closeModal.addEventListener("click", () => els.modal.close());
els.closeSettingsModal.addEventListener("click", () => els.settingsModal.close());

els.modalAddSource.addEventListener("click", addModalSourceFromInput);
els.settingsAddSource.addEventListener("click", addSettingsSourceFromInput);

els.modalTopicSource.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addModalSourceFromInput();
  }
});

els.settingsSource.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addSettingsSourceFromInput();
  }
});

els.modalTopicFiles.addEventListener("change", () => {
  for (const file of els.modalTopicFiles.files) {
    addModalFile(file);
  }
  els.modalTopicFiles.value = "";
});

els.settingsFiles.addEventListener("change", () => {
  for (const file of els.settingsFiles.files) {
    addSettingsFile(file);
  }
  els.settingsFiles.value = "";
});

els.modalForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isCreatingTopic) return;
  addModalSourceFromInput();
  const topicName = els.modalTopicName.value.trim();
  if (!topicName) {
    showToast("Topic name is required.");
    return;
  }
  try {
    isCreatingTopic = true;
    setModalBusy(true, "Creating...");
    const sources = [...modalSources, ...modalFiles];
    await createTopic(topicName, sources);
    els.modal.close();
    showToast(sources.length ? `Created topic "${topicName}". Building graph...` : "Topic created.");
  } catch (error) {
    showToast(error.message);
  } finally {
    isCreatingTopic = false;
    setModalBusy(false, "Create");
  }
});

els.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = els.chatInput.value.trim();
  if (!text) return;
  els.chatInput.value = "";
  messages.push({ role: "user", text });
  renderMessages();

  if (activeThreadId === "agent") {
    const topicName = text.length > 80 ? `${text.slice(0, 77)}...` : text;
    try {
      const topic = await createTopic(topicName, []);
      messages.push({ role: "agent", text: `Created topic "${topic.name}". Add sources or use Create topic to upload docs.` });
      renderMessages();
      showToast(`Created topic "${topic.name}".`);
    } catch (error) {
      messages.push({ role: "agent", text: error.message });
      renderMessages();
    }
    return;
  }

  const topic = topics.find((item) => item.id === activeTopicId);
  if (!topic || topic.status !== "ready") {
    messages.push({ role: "agent", text: topicUnavailableMessage(topic) });
    renderMessages();
    return;
  }

  try {
    const answer = await api(`/api/topics/${activeTopicId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    });
    messages.push({ role: "agent", text: answer.answer });
  } catch (error) {
    messages.push({ role: "agent", text: error.message });
  }
  renderMessages();
});

els.settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isUpdatingTopicSources) return;
  addSettingsSourceFromInput();
  if (!settingsTopicId) return;
  if (!settingsSources.length && !settingsFiles.length) {
    showToast("Add at least one source or document.");
    return;
  }
  try {
    isUpdatingTopicSources = true;
    setSettingsBusy(true, "Applying...");
    const topic = topics.find((item) => item.id === settingsTopicId);
    markTopicIndexing(settingsTopicId);
    void runTopicSetup(settingsTopicId, topic?.name || "Topic", [...settingsSources, ...settingsFiles]);
    els.settingsModal.close();
    showToast("Topic sources queued. Building graph...");
  } catch (error) {
    showToast(error.message);
  } finally {
    isUpdatingTopicSources = false;
    setSettingsBusy(false, "Apply sources");
  }
});

els.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.chatForm.requestSubmit();
  }
});

function addModalSourceFromInput() {
  const value = els.modalTopicSource.value.trim();
  if (!value) return;
  addModalSource(value);
  els.modalTopicSource.value = "";
}

function addModalSource(source) {
  if (!modalSources.includes(source)) {
    modalSources.push(source);
    renderModalSources();
  }
}

function addSettingsSourceFromInput() {
  const value = els.settingsSource.value.trim();
  if (!value) return;
  addSettingsSource(value);
  els.settingsSource.value = "";
}

function addSettingsSource(source) {
  if (!settingsSources.includes(source)) {
    settingsSources.push(source);
    renderSettingsSources();
  }
}

function addModalFile(file) {
  const exists = modalFiles.some(
    (item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified,
  );
  if (!exists) {
    modalFiles.push(file);
    renderModalSources();
  }
}

function addSettingsFile(file) {
  const exists = settingsFiles.some(
    (item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified,
  );
  if (!exists) {
    settingsFiles.push(file);
    renderSettingsSources();
  }
}

function renderModalSources() {
  els.modalSourceList.innerHTML = "";
  for (const source of modalSources) {
    const item = document.createElement("li");
    item.textContent = source;
    els.modalSourceList.append(item);
  }
  for (const file of modalFiles) {
    const item = document.createElement("li");
    item.textContent = `Upload: ${file.name}`;
    els.modalSourceList.append(item);
  }
}

function renderSettingsSources() {
  els.settingsSourceList.innerHTML = "";
  for (const source of settingsSources) {
    const item = document.createElement("li");
    item.textContent = source;
    els.settingsSourceList.append(item);
  }
  for (const file of settingsFiles) {
    const item = document.createElement("li");
    item.textContent = `Upload: ${file.name}`;
    els.settingsSourceList.append(item);
  }
}

function openTopicSettings(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  settingsTopicId = topicId;
  settingsSources = [];
  settingsFiles = [];
  renderSettingsSources();
  els.settingsForm.reset();
  els.settingsTitle.textContent = `Topic settings: ${topic.name}`;
  els.settingsModal.showModal();
}

async function deleteTopic(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  if (!window.confirm(`Delete topic "${topic.name}"?`)) {
    return;
  }
  try {
    await api(`/api/topics/${topicId}`, { method: "DELETE" });
    await loadData();
    if (activeTopicId === topicId) {
      selectAgentChat();
    } else {
      renderTopicTree();
    }
    showToast(`Deleted topic "${topic.name}".`);
  } catch (error) {
    showToast(error.message);
  }
}

function markTopicIndexing(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  topic.status = "indexing";
  topic.progress_percent = Math.max(topic.progress_percent || 0, 5);
  topic.progress_label = topic.progress_label || "Queued";
  topic.last_error = null;
  renderTopicTree();
  if (activeTopicId === topicId) {
    updateComposerHint(topicId);
  }
  scheduleTopicPolling();
}

function updateComposerHint(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  els.composerHint.textContent =
    topic?.status === "ready"
      ? "Ask this topic using its graph context."
      : topic?.status === "error"
        ? formatUiMessage(topic.last_error || "Topic setup failed. Update the sources or server configuration.")
        : topic?.progress_label
          ? `${topic.progress_label} (${topic.progress_percent || 0}%)`
          : "Add sources and build the graph before grounded Q&A.";
}

function setModalBusy(busy, label) {
  els.modalSubmit.disabled = busy;
  els.modalSubmit.textContent = label;
}

function setSettingsBusy(busy, label) {
  els.settingsSubmit.disabled = busy;
  els.settingsSubmit.textContent = label;
}

function renderMessages() {
  els.messages.classList.toggle("is-empty", !messages.length);
  els.messages.classList.toggle("has-messages", messages.length > 0);
  if (!messages.length) {
    els.messages.innerHTML = `
      <div class="empty-chat">
        <h2>${activeThreadId === "agent" ? "QA Agent" : escapeHtml(currentThreadTitle())}</h2>
        <p>${activeThreadId === "agent" ? "Tell the agent what topic you want to create, or use the Create topic button." : "Ask questions in this thread."}</p>
      </div>
    `;
    return;
  }
  els.messages.innerHTML = `<div class="message-list">${messages
    .map((message) => `<div class="message ${message.role}">${escapeHtml(message.text)}</div>`)
    .join("")}</div>`;
  els.messages.scrollTop = els.messages.scrollHeight;
}

function inferSourceKind(source) {
  if (/github\.com[:/]/i.test(source)) {
    return "github";
  }
  throw new Error("Manual topic creation currently supports GitHub repository URLs and uploaded documents.");
}

function topicUnavailableMessage(topic) {
  if (!topic) {
    return "This topic is not ready yet. Add sources and build the graph first.";
  }
  if (topic.status === "error") {
    return `Topic setup failed: ${formatUiMessage(topic.last_error || "Unknown error.")}`;
  }
  if (topic.status === "indexing") {
    return topic.progress_label
      ? `Topic indexing in progress: ${topic.progress_label} (${topic.progress_percent || 0}%).`
      : "This topic is not ready yet. Add sources and build the graph first.";
  }
  return "This topic is not ready yet. Add sources and build the graph first.";
}

function syncActiveTopicState() {
  if (activeThreadId === "agent") {
    return;
  }
  const topic = topics.find((item) => item.id === activeTopicId);
  if (!topic) {
    selectAgentChat();
    return;
  }
  updateComposerHint(activeTopicId);
}

function scheduleTopicPolling() {
  if (topicPollTimer) {
    window.clearTimeout(topicPollTimer);
    topicPollTimer = null;
  }
  if (!topics.some((item) => item.status === "indexing")) {
    return;
  }
  topicPollTimer = window.setTimeout(async () => {
    try {
      await loadData();
    } catch (error) {
      showToast(error.message);
      scheduleTopicPolling();
    }
  }, 3000);
}

function topicStatusText(topic) {
  if (topic.status === "indexing") {
    return `indexing ${effectiveProgressPercent(topic)}%`;
  }
  if (topic.status === "error") {
    return "error";
  }
  if (topic.status === "ready") {
    return "ready";
  }
  return topic.status;
}

function effectiveProgressPercent(topic) {
  if (topic.status !== "indexing") {
    return topic.progress_percent || 0;
  }
  return Math.max(topic.progress_percent || 0, 5);
}

function currentThreadTitle() {
  const thread = threads.find((item) => item.id === activeThreadId);
  const topic = topics.find((item) => item.id === activeTopicId);
  return `${topic?.name || "Topic"} / ${thread?.title || "Thread"}`;
}

function formatUiMessage(message) {
  const text = String(message || "").trim();
  if (!text) {
    return "Unknown error.";
  }
  if (text.includes("Graphify completed but produced an empty graph")) {
    return "This repository does not expose analyzable code in the current source snapshot.";
  }
  if (text.includes("Graphify command") && text.includes("was not found")) {
    return "Graphify is not installed or not configured on this server.";
  }
  if (text.length > 140) {
    return `${text.slice(0, 137)}...`;
  }
  return text;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadData()
  .then(() => {
    renderMessages();
    const params = new URLSearchParams(window.location.search);
    if (params.get("createTopic") === "true") {
      els.modal.showModal();
    }
  })
  .catch((error) => showToast(error.message));
