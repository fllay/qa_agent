let topics = [];
let threads = [];
let activeTopicId = null;
let activeThreadId = "agent";
let modalSources = [];
let modalFiles = [];
let settingsTopicId = null;
let settingsSources = [];
let settingsFiles = [];
let currentTopicSources = [];
let isCreatingTopic = false;
let isUpdatingTopicSources = false;
let topicPollTimer = null;
let activeTopicMenuId = null;
const expandedTopics = new Set();
const threadSessions = new Map();

const els = {
  shell: document.querySelector(".chat-shell"),
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
  sendButton: document.querySelector("#chat-send"),
  scrollButton: document.querySelector("#scroll-to-bottom"),
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

function sessionKeyFor(threadId = activeThreadId) {
  return threadId === "agent" ? "agent" : threadId;
}

function getSession(threadId = activeThreadId) {
  const key = sessionKeyFor(threadId);
  if (!threadSessions.has(key)) {
    threadSessions.set(key, {
      messages: [],
      pending: false,
      draft: "",
      copiedId: null,
      scrollLocked: false,
      loaded: key === "agent",
    });
  }
  return threadSessions.get(key);
}

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
  els.shell.classList.toggle("sidebar-hidden", !open);
  if (!open) {
    activeTopicMenuId = null;
  }
}

function saveDraft() {
  getSession().draft = els.chatInput.value;
}

function restoreDraft() {
  els.chatInput.value = getSession().draft || "";
  autoResizeComposer();
  updateComposerState();
}

function currentThreadLabel() {
  if (activeThreadId === "agent") {
    return "QA Agent";
  }
  const thread = threads.find((item) => item.id === activeThreadId);
  return thread?.title || "New chat";
}

function currentMessages() {
  return getSession().messages;
}

function isPending() {
  return getSession().pending;
}

function setPending(pending) {
  getSession().pending = pending;
  updateComposerState();
  renderMessages();
}

function topicThreads(topicId) {
  return threads.filter((thread) => thread.topic_id === topicId);
}

function normalizeMessages(items) {
  return items.map((item) => ({
    id: item.id,
    role: item.role,
    text: item.text,
    createdAt: item.created_at,
  }));
}

async function loadThreadMessages(threadId, { force = false } = {}) {
  if (threadId === "agent") return;
  const session = getSession(threadId);
  if (session.loaded && !force) {
    return;
  }
  const items = await api(`/api/threads/${threadId}/messages`);
  session.messages = normalizeMessages(items);
  session.loaded = true;
  if (threadId === activeThreadId) {
    renderMessages();
    scrollMessagesToBottom(false);
  }
}

async function loadData() {
  [topics, threads] = await Promise.all([api("/api/topics"), api("/api/threads")]);
  for (const topic of topics) {
    if (!expandedTopics.has(topic.id)) {
      expandedTopics.add(topic.id);
    }
  }
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

    const folderButton = document.createElement("button");
    folderButton.type = "button";
    folderButton.className = "topic-folder-button";
    folderButton.innerHTML = `
      <span class="topic-folder-arrow">${expandedTopics.has(topic.id) ? "▾" : "▸"}</span>
      <span class="topic-title">${escapeHtml(topic.name)}</span>
    `;
    folderButton.addEventListener("click", () => {
      if (expandedTopics.has(topic.id)) {
        expandedTopics.delete(topic.id);
      } else {
        expandedTopics.add(topic.id);
      }
      renderTopicTree();
    });
    header.append(folderButton);

    const actions = document.createElement("div");
    actions.className = "topic-group-actions";

    const menuShell = document.createElement("div");
    menuShell.className = "topic-menu-shell";

    const menuButton = document.createElement("button");
    menuButton.type = "button";
    menuButton.className = `topic-menu-button ${activeTopicMenuId === topic.id ? "is-open" : ""}`;
    menuButton.setAttribute("aria-label", `Open menu for ${topic.name}`);
    menuButton.textContent = "...";
    menuButton.addEventListener("click", (event) => {
      event.stopPropagation();
      activeTopicMenuId = activeTopicMenuId === topic.id ? null : topic.id;
      renderTopicTree();
    });
    menuShell.append(menuButton);

    if (activeTopicMenuId === topic.id) {
      const menu = document.createElement("div");
      menu.className = "topic-menu-popover";
      menu.innerHTML = `
        <button type="button" class="topic-menu-item" data-topic-action="new-chat" data-topic-id="${topic.id}">New chat</button>
        <button type="button" class="topic-menu-item" data-topic-action="settings" data-topic-id="${topic.id}">Settings</button>
        <button type="button" class="topic-menu-item topic-menu-item-danger" data-topic-action="delete" data-topic-id="${topic.id}">Delete</button>
      `;
      menuShell.append(menu);
    }

    actions.append(menuShell);

    header.append(actions);
    group.append(header);

    if (expandedTopics.has(topic.id)) {
      const body = document.createElement("div");
      body.className = "topic-thread-list";
      for (const thread of topicThreads(topic.id)) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `thread-button ${thread.id === activeThreadId ? "active" : ""}`;
        button.innerHTML = `<span>${escapeHtml(thread.title)}</span><small>${escapeHtml(topicStatusText(topic))}</small>`;
        button.addEventListener("click", () => selectThread(topic.id, thread.id));
        body.append(button);
      }
      group.append(body);
    }

    els.topicTree.append(group);
  }

  els.topicTree.querySelectorAll("[data-topic-action]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const { topicId, topicAction } = button.dataset;
      activeTopicMenuId = null;
      renderTopicTree();
      if (!topicId) return;
      if (topicAction === "new-chat") {
        await createTopicThread(topicId);
        return;
      }
      if (topicAction === "settings") {
        openTopicSettings(topicId);
        return;
      }
      if (topicAction === "delete") {
        await deleteTopic(topicId);
      }
    });
  });
}

async function selectThread(topicId, threadId) {
  saveDraft();
  activeTopicId = topicId;
  activeThreadId = threadId;
  els.agentThread.classList.remove("active");
  expandedTopics.add(topicId);
  updateComposerHint(topicId);
  renderTopicTree();
  restoreDraft();
  renderMessages();
  try {
    await loadThreadMessages(threadId);
  } catch (error) {
    showToast(error.message);
  }
}

function selectAgentChat() {
  saveDraft();
  activeTopicId = null;
  activeThreadId = "agent";
  els.agentThread.classList.add("active");
  els.composerHint.textContent = "QA Agent creates a new topic from your message.";
  renderTopicTree();
  restoreDraft();
  renderMessages();
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
  await selectThread(topic.id, defaultThread?.id || "agent");
  if (sources.length) {
    markTopicIndexing(topic.id);
    void runTopicSetup(topic.id, topic.name, sources);
  }
  return topic;
}

async function createTopicThread(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  try {
    const thread = await api(`/api/topics/${topicId}/threads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New chat" }),
    });
    threadSessions.delete(thread.id);
    await loadData();
    await selectThread(topicId, thread.id);
  } catch (error) {
    showToast(error.message);
  }
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

function buildMessage(role, text, extra = {}) {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    createdAt: Date.now(),
    ...extra,
  };
}

function pushLocalMessage(role, text, extra = {}) {
  getSession().messages.push(buildMessage(role, text, extra));
  renderMessages();
  scrollMessagesToBottom(true);
}

async function copyMessage(messageId) {
  const session = getSession();
  const message = session.messages.find((item) => item.id === messageId);
  if (!message) return;
  try {
    await navigator.clipboard.writeText(message.text);
    session.copiedId = messageId;
    renderMessages();
    window.clearTimeout(copyMessage.timer);
    copyMessage.timer = window.setTimeout(() => {
      if (session.copiedId === messageId) {
        session.copiedId = null;
        renderMessages();
      }
    }, 1500);
  } catch {
    showToast("Copy failed.");
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
  if (!text || isPending()) return;
  const session = getSession();
  els.chatInput.value = "";
  session.draft = "";
  autoResizeComposer();

  if (activeThreadId === "agent") {
    pushLocalMessage("user", text);
    setPending(true);
    const topicName = text.length > 80 ? `${text.slice(0, 77)}...` : text;
    try {
      const agentSession = getSession("agent");
      const topic = await createTopic(topicName, []);
      if (agentSession.messages.at(-1)?.role === "user" && agentSession.messages.at(-1)?.text === text) {
        agentSession.messages.pop();
      }
      const topicSession = getSession(activeThreadId);
      topicSession.messages.push(buildMessage("user", text));
      topicSession.messages.push(
        buildMessage("agent", `Created topic "${topic.name}". Add sources or use Create topic to upload docs.`),
      );
      renderMessages();
      scrollMessagesToBottom(true);
      showToast(`Created topic "${topic.name}".`);
    } catch (error) {
      pushLocalMessage("agent", error.message);
    } finally {
      setPending(false);
    }
    return;
  }

  const topic = topics.find((item) => item.id === activeTopicId);
  if (!topic || topic.status !== "ready") {
    pushLocalMessage("user", text);
    pushLocalMessage("agent", topicUnavailableMessage(topic));
    return;
  }

  pushLocalMessage("user", text);
  setPending(true);
  try {
    const response = await api(`/api/threads/${activeThreadId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const latest = getSession();
    latest.messages = normalizeMessages([
      ...latest.messages
        .filter((message) => !(message.role === "user" && message.text === text && String(message.id).startsWith("user-")))
        .map((message) => ({
          id: message.id,
          role: message.role,
          text: message.text,
          created_at: message.createdAt,
        })),
      response.user_message,
      response.assistant_message,
    ]);
    await loadData();
    renderMessages();
    scrollMessagesToBottom(true);
  } catch (error) {
    pushLocalMessage("agent", error.message);
  } finally {
    setPending(false);
  }
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

els.chatInput.addEventListener("input", () => {
  saveDraft();
  autoResizeComposer();
  updateComposerState();
});

els.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    els.chatForm.requestSubmit();
  }
});

els.messages.addEventListener("scroll", () => {
  const gap = els.messages.scrollHeight - els.messages.scrollTop - els.messages.clientHeight;
  const locked = gap > 96;
  getSession().scrollLocked = locked;
  els.scrollButton.hidden = !locked;
});

els.scrollButton.addEventListener("click", () => scrollMessagesToBottom(true));

document.addEventListener("click", (event) => {
  if (!activeTopicMenuId) {
    return;
  }
  const target = event.target;
  if (!(target instanceof Element)) {
    activeTopicMenuId = null;
    renderTopicTree();
    return;
  }
  if (!target.closest(".topic-menu-shell")) {
    activeTopicMenuId = null;
    renderTopicTree();
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
  for (const [index, source] of modalSources.entries()) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span>${escapeHtml(source)}</span>
      <button type="button" class="source-remove-button" data-modal-source-index="${index}" aria-label="Remove source">×</button>
    `;
    els.modalSourceList.append(item);
  }
  for (const [index, file] of modalFiles.entries()) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span>Upload: ${escapeHtml(file.name)}</span>
      <button type="button" class="source-remove-button" data-modal-file-index="${index}" aria-label="Remove upload">×</button>
    `;
    els.modalSourceList.append(item);
  }
  els.modalSourceList.querySelectorAll("[data-modal-source-index]").forEach((button) => {
    button.addEventListener("click", () => {
      modalSources.splice(Number(button.dataset.modalSourceIndex), 1);
      renderModalSources();
    });
  });
  els.modalSourceList.querySelectorAll("[data-modal-file-index]").forEach((button) => {
    button.addEventListener("click", () => {
      modalFiles.splice(Number(button.dataset.modalFileIndex), 1);
      renderModalSources();
    });
  });
}

function renderSettingsSources() {
  els.settingsSourceList.innerHTML = "";
  for (const source of currentTopicSources) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span>${escapeHtml(source.kind === "upload" ? `Upload: ${source.label}` : source.value)}</span>
      <button type="button" class="source-remove-button" data-current-source-id="${source.id}" aria-label="Delete source">×</button>
    `;
    els.settingsSourceList.append(item);
  }
  for (const [index, source] of settingsSources.entries()) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span>${escapeHtml(source)}</span>
      <button type="button" class="source-remove-button" data-settings-source-index="${index}" aria-label="Remove source">×</button>
    `;
    els.settingsSourceList.append(item);
  }
  for (const [index, file] of settingsFiles.entries()) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span>Upload: ${escapeHtml(file.name)}</span>
      <button type="button" class="source-remove-button" data-settings-file-index="${index}" aria-label="Remove upload">×</button>
    `;
    els.settingsSourceList.append(item);
  }
  els.settingsSourceList.querySelectorAll("[data-settings-source-index]").forEach((button) => {
    button.addEventListener("click", () => {
      settingsSources.splice(Number(button.dataset.settingsSourceIndex), 1);
      renderSettingsSources();
    });
  });
  els.settingsSourceList.querySelectorAll("[data-settings-file-index]").forEach((button) => {
    button.addEventListener("click", () => {
      settingsFiles.splice(Number(button.dataset.settingsFileIndex), 1);
      renderSettingsSources();
    });
  });
  els.settingsSourceList.querySelectorAll("[data-current-source-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!settingsTopicId) return;
      try {
        await api(`/api/topics/${settingsTopicId}/sources/${button.dataset.currentSourceId}`, { method: "DELETE" });
        currentTopicSources = currentTopicSources.filter((item) => item.id !== button.dataset.currentSourceId);
        await loadData();
        renderSettingsSources();
        if (activeTopicId === settingsTopicId) {
          updateComposerHint(settingsTopicId);
        }
        showToast("Source removed.");
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function openTopicSettings(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  settingsTopicId = topicId;
  settingsSources = [];
  settingsFiles = [];
  currentTopicSources = [];
  renderSettingsSources();
  els.settingsForm.reset();
  els.settingsTitle.textContent = `Topic settings: ${topic.name}`;
  els.settingsModal.showModal();
  void api(`/api/topics/${topicId}/sources`)
    .then((sources) => {
      currentTopicSources = sources;
      renderSettingsSources();
    })
    .catch((error) => showToast(error.message));
}

async function deleteTopic(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  if (!window.confirm(`Delete topic "${topic.name}"?`)) {
    return;
  }
  try {
    await api(`/api/topics/${topicId}`, { method: "DELETE" });
    for (const thread of topicThreads(topicId)) {
      threadSessions.delete(thread.id);
    }
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
      ? `Ask in ${currentThreadLabel()}.`
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
  const session = getSession();
  const messages = currentMessages();
  els.messages.classList.toggle("is-empty", !messages.length);
  els.messages.classList.toggle("has-messages", messages.length > 0);
  if (!messages.length) {
    els.messages.innerHTML = `
      <div class="empty-chat">
        <h2>${escapeHtml(currentThreadLabel())}</h2>
        <p>${activeThreadId === "agent" ? "Tell the agent what topic you want to create, or use the Create topic button." : "Ask questions in this thread."}</p>
      </div>
    `;
    els.scrollButton.hidden = true;
    return;
  }

  els.messages.innerHTML = `
    <div class="message-list">
      ${messages
        .map(
          (message) => `
            <article class="message-row ${message.role}">
              <div class="message ${message.role}">
                <div class="message-body">${escapeHtml(message.text)}</div>
                ${
                  message.role === "agent"
                    ? `
                      <div class="message-actions">
                        <button class="message-action" type="button" data-copy-id="${message.id}">
                          ${session.copiedId === message.id ? "Copied" : "Copy"}
                        </button>
                      </div>
                    `
                    : ""
                }
              </div>
            </article>
          `,
        )
        .join("")}
      ${
        session.pending
          ? `
            <article class="message-row agent">
              <div class="message agent message-loading">
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
              </div>
            </article>
          `
          : ""
      }
    </div>
  `;

  els.messages.querySelectorAll("[data-copy-id]").forEach((button) => {
    button.addEventListener("click", () => copyMessage(button.dataset.copyId));
  });
  if (!session.scrollLocked || session.pending) {
    scrollMessagesToBottom(false);
  }
}

function autoResizeComposer() {
  els.chatInput.style.height = "0px";
  const nextHeight = Math.min(els.chatInput.scrollHeight, 288);
  els.chatInput.style.height = `${Math.max(nextHeight, 96)}px`;
  els.chatInput.style.overflowY = els.chatInput.scrollHeight > 288 ? "auto" : "hidden";
}

function updateComposerState() {
  const session = getSession();
  const hasInput = els.chatInput.value.trim().length > 0;
  els.sendButton.disabled = session.pending || !hasInput;
  els.sendButton.textContent = session.pending ? "Sending..." : "Send";
}

function scrollMessagesToBottom(smooth) {
  els.messages.scrollTo({
    top: els.messages.scrollHeight,
    behavior: smooth ? "smooth" : "auto",
  });
  getSession().scrollLocked = false;
  els.scrollButton.hidden = true;
}

function inferSourceKind(source) {
  if (/github\.com[:/]/i.test(source) || /gitlab\.com[:/]/i.test(source)) {
    return "github";
  }
  throw new Error("Manual topic creation currently supports repository URLs and uploaded documents.");
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
  const thread = threads.find((item) => item.id === activeThreadId);
  if (!topic || !thread) {
    selectAgentChat();
    return;
  }
  expandedTopics.add(topic.id);
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
  if (text.length > 180) {
    return `${text.slice(0, 177)}...`;
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
    autoResizeComposer();
    updateComposerState();
    renderMessages();
    const params = new URLSearchParams(window.location.search);
    if (params.get("createTopic") === "true") {
      els.modal.showModal();
    }
  })
  .catch((error) => showToast(error.message));
