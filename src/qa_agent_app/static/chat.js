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
let llmDefaultSettings = null;
let llmSettings = null;
let isCreatingTopic = false;
let isUpdatingTopicSources = false;
let isSavingLlmSettings = false;
let topicPollTimer = null;
let activeTopicMenuId = null;
let activeGraphTopicId = null;
let activeGraphView = { scale: 1, offsetX: 0, offsetY: 0 };
let activeGraphScene = null;
let activeGraphFrame = 0;
let activeGraphCanvas = null;
let activeCosmograph = null;
let cosmographLibPromise = null;
let activeGraphSettleTimer = null;
let graphWindowListenersBound = false;
const graphDragState = { dragging: false, startX: 0, startY: 0 };
const GRAPH_VIEWBOX = { width: 1320, height: 720 };
const GRAPH_NODE_LIST_LIMIT = 120;
const LARGE_GRAPH_LAYOUT_THRESHOLD = 9000;
const LARGE_GRAPH_NODE_PICK_THRESHOLD = 12000;
const LARGE_GRAPH_EDGE_VISIBILITY_SCALE = 0.28;
const LARGE_GRAPH_LABEL_VISIBILITY_SCALE = 0.48;
const LARGE_GRAPH_OVERVIEW_LOD_SCALE = 0.5;
const LARGE_GRAPH_MID_LOD_SCALE = 0.9;
const LARGE_GRAPH_OVERVIEW_CELL_SIZE = 11;
const LARGE_GRAPH_MID_LOD_SCREEN_CELL = 7;
const LARGE_GRAPH_SPATIAL_CELL_SIZE = 92;
const LARGE_GRAPH_MAX_EDGE_DRAWS = 6000;
const LARGE_GRAPH_MAX_EDGE_VISIBLE_NODES = 3500;
const LARGE_GRAPH_MAX_DIRECT_NODE_DRAWS = 5200;
const LARGE_GRAPH_DENSE_DIRECT_NODE_THRESHOLD = 2400;
const GRAPH_NODE_OUTLINE_COLOR = "rgba(132, 149, 178, 0.44)";
const GRAPH_NODE_OUTLINE_HOVER_COLOR = "rgba(226, 232, 240, 0.94)";
const GRAPH_MAIN_NODE_OUTLINE_COLOR = "rgba(183, 198, 255, 0.78)";
const COSMOGRAPH_MODULE_URL = "/static/vendor/cosmograph-bundle.js?v=20260616-graph-ratio1";
const expandedTopics = new Set();
const threadSessions = new Map();

const els = {
  shell: document.querySelector(".chat-shell"),
  sidebar: document.querySelector("#thread-history"),
  openSidebar: document.querySelector("#toggle-sidebar-open"),
  closeSidebar: document.querySelector("#toggle-sidebar-close"),
  openLlmSettings: document.querySelector("#open-llm-settings"),
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
  llmSettingsModal: document.querySelector("#llm-settings-modal"),
  llmSettingsForm: document.querySelector("#llm-settings-form"),
  closeLlmSettingsModal: document.querySelector("#close-llm-settings"),
  llmSettingsSubmit: document.querySelector("#llm-settings-submit"),
  llmProvider: document.querySelector("#llm-provider"),
  llmDefaultProviderLabel: document.querySelector("#llm-default-provider-label"),
  localSettingsFields: document.querySelector("#local-settings-fields"),
  llmLocalBaseUrl: document.querySelector("#llm-local-base-url"),
  llmLocalApiKey: document.querySelector("#llm-local-api-key"),
  llmLocalModel: document.querySelector("#llm-local-model"),
  openrouterSettingsFields: document.querySelector("#openrouter-settings-fields"),
  llmOpenrouterApiKey: document.querySelector("#llm-openrouter-api-key"),
  llmOpenrouterBaseUrl: document.querySelector("#llm-openrouter-base-url"),
  llmOpenrouterMainModel: document.querySelector("#llm-openrouter-main-model"),
  llmOpenrouterReserveModel1: document.querySelector("#llm-openrouter-reserve-model-1"),
  llmOpenrouterReserveModel2: document.querySelector("#llm-openrouter-reserve-model-2"),
  graphModal: document.querySelector("#topic-graph-modal"),
  closeGraphModal: document.querySelector("#close-topic-graph"),
  graphTitle: document.querySelector("#topic-graph-title"),
  graphSubtitle: document.querySelector("#topic-graph-subtitle"),
  graphStage: document.querySelector("#topic-graph-stage"),
  graphNodeCount: document.querySelector("#topic-graph-node-count"),
  graphEdgeCount: document.querySelector("#topic-graph-edge-count"),
  graphKind: document.querySelector("#topic-graph-kind"),
  graphClusterList: document.querySelector("#topic-graph-cluster-list"),
  graphNodeList: document.querySelector("#topic-graph-node-list"),
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
      turnBranches: {},
      editingTurnId: null,
      editingDraft: "",
      loadingTurnId: null,
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

async function loadCosmographLibrary() {
  if (!cosmographLibPromise) {
    cosmographLibPromise = import(COSMOGRAPH_MODULE_URL);
  }
  return cosmographLibPromise;
}

async function destroyActiveGraphRenderer() {
  if (activeGraphSettleTimer) {
    window.clearTimeout(activeGraphSettleTimer);
    activeGraphSettleTimer = null;
  }
  const current = activeCosmograph;
  activeCosmograph = null;
  if (current?.destroy) {
    try {
      await current.destroy();
    } catch (error) {
      console.warn("Failed to destroy Cosmograph instance.", error);
    }
  }
  activeGraphScene = null;
  activeGraphCanvas = null;
  graphDragState.dragging = false;
}

function showToast(message) {
  els.toast.textContent = formatUiMessage(message);
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 3600);
}

function normalizeLlmSettings(payload = {}) {
  return {
    provider: payload.provider === "openrouter" ? "openrouter" : "local",
    local_base_url: payload.local_base_url || "http://127.0.0.1:11434/v1",
    local_api_key: payload.local_api_key || "local",
    local_model: payload.local_model || "llama3.1:8b",
    openrouter_api_key: payload.openrouter_api_key || "",
    openrouter_base_url: payload.openrouter_base_url || "https://openrouter.ai/api/v1",
    openrouter_main_model: payload.openrouter_main_model || "openrouter/auto",
    openrouter_reserve_model_1: payload.openrouter_reserve_model_1 || "openai/gpt-4o-mini",
    openrouter_reserve_model_2: payload.openrouter_reserve_model_2 || "google/gemini-flash-1.5",
  };
}

function sameLlmSettings(left, right) {
  if (!left || !right) return false;
  const leftValue = normalizeLlmSettings(left);
  const rightValue = normalizeLlmSettings(right);
  return JSON.stringify(leftValue) === JSON.stringify(rightValue);
}

function labelProvider(provider) {
  return provider === "openrouter" ? "OpenRouter" : "Local";
}

function setLlmDefaultLabel(settings) {
  const providerLabel = labelProvider(normalizeLlmSettings(settings).provider);
  els.llmDefaultProviderLabel.textContent = `Default (.env): ${providerLabel}`;
  const defaultOption = els.llmProvider.querySelector('option[value="default"]');
  if (defaultOption) {
    defaultOption.textContent = `Default (.env: ${providerLabel})`;
  }
}

function setLlmInputsDisabled(disabled) {
  [
    els.llmLocalBaseUrl,
    els.llmLocalApiKey,
    els.llmLocalModel,
    els.llmOpenrouterApiKey,
    els.llmOpenrouterBaseUrl,
    els.llmOpenrouterMainModel,
    els.llmOpenrouterReserveModel1,
    els.llmOpenrouterReserveModel2,
  ].forEach((input) => {
    input.disabled = disabled;
  });
}

function applyLlmProviderVisibility(provider) {
  const useDefault = provider === "default";
  if (useDefault && llmDefaultSettings) {
    provider = llmDefaultSettings.provider;
  }
  const local = provider !== "openrouter";
  els.localSettingsFields.hidden = !local;
  els.openrouterSettingsFields.hidden = local;
  setLlmInputsDisabled(useDefault);
}

function populateLlmSettingsForm(settings, providerMode = null) {
  const next = normalizeLlmSettings(settings);
  const mode = providerMode || (sameLlmSettings(next, llmDefaultSettings) ? "default" : next.provider);
  els.llmProvider.value = mode;
  els.llmLocalBaseUrl.value = next.local_base_url;
  els.llmLocalApiKey.value = next.local_api_key;
  els.llmLocalModel.value = next.local_model;
  els.llmOpenrouterApiKey.value = next.openrouter_api_key;
  els.llmOpenrouterBaseUrl.value = next.openrouter_base_url;
  els.llmOpenrouterMainModel.value = next.openrouter_main_model;
  els.llmOpenrouterReserveModel1.value = next.openrouter_reserve_model_1;
  els.llmOpenrouterReserveModel2.value = next.openrouter_reserve_model_2;
  applyLlmProviderVisibility(mode);
}

function setLlmSettingsBusy(busy, label = "Save settings") {
  isSavingLlmSettings = busy;
  els.llmSettingsSubmit.disabled = busy;
  els.openLlmSettings.disabled = busy;
  els.llmSettingsSubmit.textContent = label;
}

async function openLlmSettingsModal() {
  try {
    setLlmSettingsBusy(true, "Loading...");
    const [effectiveSettings, defaultSettings] = await Promise.all([
      api("/api/llm-settings"),
      api("/api/llm-settings/defaults"),
    ]);
    llmDefaultSettings = normalizeLlmSettings(defaultSettings);
    llmSettings = normalizeLlmSettings(effectiveSettings);
    setLlmDefaultLabel(llmDefaultSettings);
    populateLlmSettingsForm(llmSettings);
    els.llmSettingsModal.showModal();
  } catch (error) {
    showToast(error.message);
  } finally {
    setLlmSettingsBusy(false);
  }
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

function setPending(pending, threadId = activeThreadId) {
  getSession(threadId).pending = pending;
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
      <span class="topic-folder-text">
        <span class="topic-title">${escapeHtml(topic.name)}</span>
        <span class="topic-status">${escapeHtml(topicStatusText(topic))}</span>
      </span>
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
        <button type="button" class="topic-menu-item" data-topic-action="show-graph" data-topic-id="${topic.id}">Show graph</button>
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
        button.innerHTML = `<span>${escapeHtml(thread.title)}</span>`;
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
      if (topicAction === "show-graph") {
        openTopicGraph(topicId);
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

async function createTopic(name, sources = [], options = {}) {
  const sourceValues = sources.filter((source) => typeof source === "string");
  const description = sourceValues.join("\n");
  const initialThreadTitle = options.initialThreadTitle || "New chat";
  const deleteInitialThreadOnReady = Boolean(options.deleteInitialThreadOnReady);
  const topic = await api("/api/topics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, initial_thread_title: initialThreadTitle }),
  });
  await loadData();
  const defaultThread = threads.find(
    (thread) => thread.topic_id === topic.id && thread.title === initialThreadTitle,
  );
  await selectThread(topic.id, defaultThread?.id || "agent");
  if (sources.length) {
    markTopicIndexing(topic.id);
    void runTopicSetup(topic.id, topic.name, sources, {
      cleanupThreadId: deleteInitialThreadOnReady ? defaultThread?.id || null : null,
    });
  }
  return topic;
}

async function draftAgentTopic(message) {
  return api("/api/agent/topic-draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
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

async function deleteThread(threadId, { silent = false } = {}) {
  if (!threadId) return;
  await api(`/api/threads/${threadId}`, { method: "DELETE" });
  threadSessions.delete(threadId);
  await loadData();
  if (!silent) {
    showToast("Thread deleted.");
  }
}

async function runTopicSetup(topicId, topicName, sources, options = {}) {
  try {
    await addSourcesToTopic(topicId, sources);
    await loadData();
    if (options.cleanupThreadId) {
      await deleteThread(options.cleanupThreadId, { silent: true });
    }
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

async function copyTurnText(turnId, role) {
  const session = getSession();
  const branch = session.turnBranches?.[turnId];
  const version = branch?.versions?.[branch.activeIndex ?? 0];
  const text = role === "agent" ? version?.agentText : version?.userText;
  if (!text) return;
  const copyId = `${turnId}:${role}`;
  try {
    await navigator.clipboard.writeText(text);
    session.copiedId = copyId;
    renderMessages();
    window.clearTimeout(copyTurnText.timer);
    copyTurnText.timer = window.setTimeout(() => {
      if (session.copiedId === copyId) {
        session.copiedId = null;
        renderMessages();
      }
    }, 1500);
  } catch {
    showToast("Copy failed.");
  }
}

function editMessage(turnId) {
  if (isPending()) return;
  const session = getSession();
  const branch = session.turnBranches?.[turnId];
  const version = branch?.versions?.[branch.activeIndex ?? 0];
  if (!version) return;
  session.editingTurnId = turnId;
  session.editingDraft = String(version.userText || "");
  renderMessages();
}

function cancelEditMessage() {
  const session = getSession();
  session.editingTurnId = null;
  session.editingDraft = "";
  renderMessages();
}

async function commitEditMessage() {
  if (!activeTopicId || isPending()) return;
  const session = getSession();
  if (!session.editingTurnId) return;
  const nextText = session.editingDraft.trim();
  if (!nextText) {
    showToast("Message cannot be empty.");
    return;
  }
  const turnId = session.editingTurnId;
  const branch = session.turnBranches?.[turnId];
  if (!branch) return;
  session.loadingTurnId = turnId;
  branch.loading = true;
  renderMessages();
  try {
    const response = await api(`/api/topics/${activeTopicId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: nextText }),
    });
    branch.versions.push({
      id: `${turnId}:v${branch.versions.length + 1}`,
      userText: nextText,
      agentText: response.answer,
      source: "edit",
    });
    branch.activeIndex = branch.versions.length - 1;
    session.editingTurnId = null;
    session.editingDraft = "";
  } catch (error) {
    showToast(error.message);
  } finally {
    branch.loading = false;
    session.loadingTurnId = null;
    renderMessages();
  }
}

async function refreshMessage(turnId) {
  if (!activeTopicId || activeThreadId === "agent" || isPending()) return;
  const session = getSession();
  const branch = session.turnBranches?.[turnId];
  const version = branch?.versions?.[branch.activeIndex ?? 0];
  if (!branch || !version) return;
  session.loadingTurnId = turnId;
  branch.loading = true;
  renderMessages();
  try {
    const response = await api(`/api/topics/${activeTopicId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: version.userText }),
    });
    branch.versions.push({
      id: `${turnId}:v${branch.versions.length + 1}`,
      userText: version.userText,
      agentText: response.answer,
      source: "refresh",
    });
    branch.activeIndex = branch.versions.length - 1;
  } catch (error) {
    showToast(error.message);
  } finally {
    branch.loading = false;
    session.loadingTurnId = null;
    renderMessages();
  }
}

function stepTurnVersion(turnId, delta) {
  const session = getSession();
  const branch = session.turnBranches?.[turnId];
  if (!branch || branch.versions.length < 2) return;
  const nextIndex = branch.activeIndex + delta;
  if (nextIndex < 0 || nextIndex >= branch.versions.length) {
    return;
  }
  branch.activeIndex = nextIndex;
  if (session.editingTurnId === turnId) {
    session.editingDraft = branch.versions[nextIndex].userText;
  }
  renderMessages();
}

els.agentThread.addEventListener("click", selectAgentChat);
els.openSidebar.addEventListener("click", () => setSidebarOpen(true));
els.closeSidebar.addEventListener("click", () => setSidebarOpen(false));
els.openLlmSettings.addEventListener("click", () => {
  if (!isSavingLlmSettings) {
    void openLlmSettingsModal();
  }
});

els.manualTopic.addEventListener("click", () => {
  modalSources = [];
  modalFiles = [];
  renderModalSources();
  els.modalForm.reset();
  els.modal.showModal();
});

els.closeModal.addEventListener("click", () => els.modal.close());
els.closeSettingsModal.addEventListener("click", () => els.settingsModal.close());
els.closeLlmSettingsModal.addEventListener("click", () => els.llmSettingsModal.close());
els.closeGraphModal.addEventListener("click", () => {
  activeGraphTopicId = null;
  els.graphModal.close();
  void destroyActiveGraphRenderer();
});
els.graphModal.addEventListener("close", () => {
  activeGraphTopicId = null;
  void destroyActiveGraphRenderer();
});
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
    setPending(true, "agent");
    try {
      const agentSession = getSession("agent");
      const draft = await draftAgentTopic(text);
      const topic = await createTopic(draft.name, draft.sources, {
        initialThreadTitle: "Topic chat",
        deleteInitialThreadOnReady: true,
      });
      if (agentSession.messages.at(-1)?.role === "user" && agentSession.messages.at(-1)?.text === text) {
        agentSession.messages.pop();
      }
      const topicSession = getSession(activeThreadId);
      topicSession.messages.push(buildMessage("user", text));
      topicSession.messages.push(
        buildMessage(
          "agent",
          draft.sources.length
            ? `Created topic "${topic.name}" and started indexing ${draft.sources.join(", ")}.`
            : `Created topic "${topic.name}". Add sources or use Create topic to upload docs.`,
        ),
      );
      renderMessages();
      scrollMessagesToBottom(true);
      showToast(
        draft.sources.length
          ? `Created topic "${topic.name}". Building graph...`
          : `Created topic "${topic.name}".`,
      );
    } catch (error) {
      pushLocalMessage("agent", error.message);
    } finally {
      setPending(false, "agent");
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

els.llmProvider.addEventListener("change", () => {
  if (els.llmProvider.value === "default" && llmDefaultSettings) {
    populateLlmSettingsForm(llmDefaultSettings, "default");
    return;
  }
  applyLlmProviderVisibility(els.llmProvider.value);
});

els.llmSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSavingLlmSettings) return;
  const providerValue = els.llmProvider.value;
  const payload = normalizeLlmSettings({
    provider: providerValue,
    local_base_url: els.llmLocalBaseUrl.value.trim(),
    local_api_key: els.llmLocalApiKey.value.trim(),
    local_model: els.llmLocalModel.value.trim(),
    openrouter_api_key: els.llmOpenrouterApiKey.value.trim(),
    openrouter_base_url: els.llmOpenrouterBaseUrl.value.trim(),
    openrouter_main_model: els.llmOpenrouterMainModel.value.trim(),
    openrouter_reserve_model_1: els.llmOpenrouterReserveModel1.value.trim(),
    openrouter_reserve_model_2: els.llmOpenrouterReserveModel2.value.trim(),
  });

  try {
    setLlmSettingsBusy(true, "Saving...");
    llmSettings = normalizeLlmSettings(
      providerValue === "default"
        ? await api("/api/llm-settings", { method: "DELETE" })
        : await api("/api/llm-settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }),
    );
    populateLlmSettingsForm(llmSettings, providerValue === "default" ? "default" : null);
    els.llmSettingsModal.close();
    showToast(
      providerValue === "default"
        ? `User override cleared. Using the .env default (${labelProvider(llmSettings.provider)}).`
        : `Model settings saved for ${labelProvider(llmSettings.provider)}.`,
    );
  } catch (error) {
    showToast(error.message);
  } finally {
    setLlmSettingsBusy(false);
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

async function openTopicGraph(topicId) {
  const topic = topics.find((item) => item.id === topicId);
  if (!topic) return;
  await destroyActiveGraphRenderer();
  activeGraphTopicId = topicId;
  els.graphTitle.textContent = `Topic graph: ${topic.name}`;
  els.graphSubtitle.textContent = "Loading saved graph preview...";
  els.graphNodeCount.textContent = "0";
  els.graphEdgeCount.textContent = "0";
  els.graphKind.textContent = "-";
  els.graphNodeList.innerHTML = "";
  els.graphStage.innerHTML = `<div class="graph-stage-empty">Loading graph preview...</div>`;
  els.graphModal.showModal();
  try {
    const payload = await api(`/api/topics/${topicId}/graph`);
    if (activeGraphTopicId !== topicId) {
      return;
    }
    await renderTopicGraph(payload);
  } catch (error) {
    if (activeGraphTopicId !== topicId) {
      return;
    }
    els.graphSubtitle.textContent = topicStatusText(topic);
    els.graphStage.innerHTML = `<div class="graph-stage-empty">${escapeHtml(formatUiMessage(error.message))}</div>`;
    showToast(error.message);
  }
}

async function renderTopicGraph(payload) {
  const graphModel = buildGraphModel(payload);
  els.graphTitle.textContent = `Topic graph: ${payload.topic_name}`;
  els.graphSubtitle.textContent = payload.sampled
    ? "Showing a sampled preview of the saved graph for faster rendering."
    : "Showing the full topic graph with clustered communities.";
  els.graphNodeCount.textContent = String(payload.total_nodes);
  els.graphEdgeCount.textContent = String(payload.total_edges);
  els.graphKind.textContent = payload.graph_kind === "fallback" ? "Fallback graph" : "Graphify graph";
  await renderGraphStage(payload, graphModel);
  renderGraphClusterList(payload, graphModel.groups);
  renderGraphNodeList(graphModel.nodes);
}

function renderGraphNodeList(nodes) {
  els.graphNodeList.innerHTML = "";
  for (const node of nodes.slice(0, GRAPH_NODE_LIST_LIMIT)) {
    const item = document.createElement("li");
    item.className = "graph-node-item";
    item.innerHTML = `
      <div>
        <strong>${escapeHtml(node.label)}</strong>
        <span><i class="graph-node-swatch" style="background:${escapeHtml(node.color)}"></i>${escapeHtml(node.familyLabel)}</span>
      </div>
      <small>${node.degree} links</small>
    `;
    els.graphNodeList.append(item);
  }
}

function renderGraphClusterList(payload, groups) {
  els.graphClusterList.innerHTML = "";
  for (const group of groups) {
    const groupCount = payload.kind_counts?.[group.family] ?? group.nodes.length;
    const item = document.createElement("li");
    item.className = "graph-cluster-item";
    item.innerHTML = `
      <span class="graph-cluster-name">
        <i class="graph-node-swatch graph-node-swatch-large" style="background:${escapeHtml(group.color)}"></i>
        ${escapeHtml(group.label)}
      </span>
      <strong>${groupCount}</strong>
    `;
    els.graphClusterList.append(item);
  }
}

async function renderGraphStage(payload, graphModel) {
  const nodes = graphModel.nodes;
  if (!nodes.length) {
    activeGraphScene = null;
    els.graphStage.innerHTML = `<div class="graph-stage-empty">This graph does not contain previewable nodes.</div>`;
    return;
  }

  const { Cosmograph, prepareCosmographData } = await loadCosmographLibrary();
  if (!els.graphModal.open || activeGraphTopicId === null) {
    return;
  }

  const nodeIds = new Set(nodes.map((node) => node.id));
  const smallGraphMode = graphModel.totalNodes <= 600;
  const mediumGraphMode = !smallGraphMode && graphModel.totalNodes < LARGE_GRAPH_LAYOUT_THRESHOLD;
  const largeGraphMode = graphModel.totalNodes >= LARGE_GRAPH_LAYOUT_THRESHOLD;
  const hugeGraphMode = graphModel.totalNodes >= 24000;
  const mainNodes = nodes.filter((node) => node.family === "repository");
  if (!mainNodes.length) {
    const fallbackMainNode = nodes.reduce((best, node) => (!best || node.degree > best.degree ? node : best), null);
    if (fallbackMainNode) {
      mainNodes.push(fallbackMainNode);
    }
  }
  const mainNodeIds = mainNodes.map((node) => node.id);
  const pointRows = nodes.map((node) => ({
    id: node.id,
    label: shortGraphLabel(node.label),
    color: node.color,
    size: Number(
      (
        node.radius *
        (node.family === "repository"
          ? smallGraphMode
            ? 2.1
            : mediumGraphMode
              ? 2.78
              : hugeGraphMode
                ? 3.15
                : 3.38
          : smallGraphMode
            ? 2.34
            : mediumGraphMode
              ? 3.0
              : hugeGraphMode
                ? 3.5
                : 3.74)
      ).toFixed(3),
    ),
    family: node.familyLabel,
    degree: node.degree,
  }));
  const linkRows = (payload.edges || [])
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => {
      const sourceNode = graphModel.nodeMap.get(edge.source);
      const targetNode = graphModel.nodeMap.get(edge.target);
      const sameFamily = sourceNode && targetNode ? sourceNode.family === targetNode.family : false;
      const touchesRepository =
        sourceNode && targetNode ? sourceNode.family === "repository" || targetNode.family === "repository" : false;
      const widthScale = smallGraphMode ? 1 : mediumGraphMode ? 0.88 : hugeGraphMode ? 0.52 : 0.66;
      return {
        source: edge.source,
        target: edge.target,
        color: sameFamily ? "rgba(126, 156, 196, 0.28)" : "rgba(91, 103, 125, 0.2)",
        width: Number(((touchesRepository ? 0.082 : sameFamily ? 0.064 : 0.046) * widthScale).toFixed(4)),
      };
    });

  const prepared = await prepareCosmographData(
    {
      points: {
        pointIdBy: "id",
        pointLabelBy: "label",
        pointColorBy: "color",
        pointColorStrategy: "direct",
        pointSizeBy: "size",
        pointSizeStrategy: "direct",
      },
      links: {
        linkSourceBy: "source",
        linkTargetsBy: ["target"],
        linkColorBy: "color",
        linkColorStrategy: "direct",
        linkWidthBy: "width",
        linkWidthStrategy: "direct",
      },
    },
    pointRows,
    linkRows,
  );
  if (!prepared || !els.graphModal.open || activeGraphTopicId === null) {
    return;
  }

  els.graphStage.innerHTML = `
    <div class="graph-toolbar">
      <button type="button" class="graph-tool-button" data-graph-zoom="out" aria-label="Zoom out">-</button>
      <button type="button" class="graph-tool-button" data-graph-zoom="in" aria-label="Zoom in">+</button>
      <button type="button" class="graph-tool-button" data-graph-zoom="reset" aria-label="Reset zoom">Reset</button>
    </div>
    <div class="graph-cosmograph-host" aria-label="Graph preview for ${escapeHtml(payload.topic_name)}"></div>
  `;
  const host = els.graphStage.querySelector(".graph-cosmograph-host");
  if (!host) {
    return;
  }

  const { points, links, cosmographConfig } = prepared;
  const pointIndexById = new Map(pointRows.map((point, index) => [point.id, index]));
  activeGraphScene = {
    totalNodes: graphModel.totalNodes,
    totalEdges: linkRows.length,
    mainNodeIds: new Set(mainNodeIds),
  };
  activeCosmograph = new Cosmograph(host, {
    points,
    links,
    ...cosmographConfig,
    backgroundColor: "#f8fafc",
    pointOpacity: 0.94,
    pointSizeScale: smallGraphMode ? 0.92 : mediumGraphMode ? 1.08 : hugeGraphMode ? 1.22 : 1.3,
    pointSamplingDistance: 2,
    pixelRatio: Math.min(window.devicePixelRatio || 1, 1.5),
    scalePointsOnZoom: false,
    renderLinks: true,
    linkOpacity: largeGraphMode ? 0.8 : 0.86,
    renderHoveredPointRing: true,
    hoveredPointRingColor: GRAPH_NODE_OUTLINE_HOVER_COLOR,
    focusedPointRingColor: GRAPH_MAIN_NODE_OUTLINE_COLOR,
    fitViewOnInit: true,
    fitViewPadding: 0.08,
    fitViewDuration: 250,
    enableSimulationDuringZoom: false,
    enableDrag: false,
    spaceSize: 8192,
    randomSeed: payload.topic_name,
    showTopLabels: true,
    showTopLabelsLimit: graphModel.totalNodes >= LARGE_GRAPH_LAYOUT_THRESHOLD ? 18 : 28,
    showDynamicLabels: true,
    showDynamicLabelsLimit: graphModel.totalNodes >= LARGE_GRAPH_LAYOUT_THRESHOLD ? 14 : 22,
    showLabelsFor: mainNodeIds,
    showHoveredPointLabel: true,
    onGraphRebuilt: () => {
      if (activeGraphSettleTimer) {
        window.clearTimeout(activeGraphSettleTimer);
      }
      activeGraphSettleTimer = window.setTimeout(() => {
        activeGraphSettleTimer = null;
        activeCosmograph?.stop?.();
      }, 900);
    },
    onPointClick: (index) => {
      activeCosmograph?.zoomToPoint(index, 220, Math.max(activeCosmograph?.getZoomLevel?.() || 1, 1.6), true);
    },
  });

  els.graphStage.querySelectorAll("[data-graph-zoom]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!activeCosmograph) {
        return;
      }
      const action = button.dataset.graphZoom;
      if (action === "reset") {
        activeCosmograph.fitView(220, 0.08);
        return;
      }
      const currentZoom = activeCosmograph.getZoomLevel?.() || 1;
      const nextZoom = action === "in" ? currentZoom * 1.2 : currentZoom / 1.2;
      activeCosmograph.setZoomLevel(nextZoom, 180);
    });
  });
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

function ensureTurnBranches(session, messages) {
  const branches = session.turnBranches || {};
  for (let index = 0; index < messages.length; index += 1) {
    const userMessage = messages[index];
    if (userMessage.role !== "user") {
      continue;
    }
    const agentMessage = messages[index + 1]?.role === "agent" ? messages[index + 1] : null;
    if (!branches[userMessage.id]) {
      branches[userMessage.id] = {
        activeIndex: 0,
        loading: false,
        versions: [
          {
            id: `${userMessage.id}:v1`,
            userText: String(userMessage.text || ""),
            agentText: String(agentMessage?.text || ""),
            source: "initial",
          },
        ],
      };
    } else if (!branches[userMessage.id].versions.length) {
      branches[userMessage.id].versions.push({
        id: `${userMessage.id}:v1`,
        userText: String(userMessage.text || ""),
        agentText: String(agentMessage?.text || ""),
        source: "initial",
      });
    } else if (!branches[userMessage.id].versions[0].agentText && agentMessage?.text) {
      branches[userMessage.id].versions[0].agentText = String(agentMessage.text || "");
    }
    if (agentMessage) {
      index += 1;
    }
  }
  session.turnBranches = branches;
}

function buildMessageTurns(messages, session) {
  ensureTurnBranches(session, messages);
  const turns = [];
  for (let index = 0; index < messages.length; index += 1) {
    const userMessage = messages[index];
    if (userMessage.role !== "user") {
      continue;
    }
    const agentMessage = messages[index + 1]?.role === "agent" ? messages[index + 1] : null;
    const branch = session.turnBranches[userMessage.id];
    if (!branch) {
      continue;
    }
    const activeIndex = Math.max(0, Math.min(branch.activeIndex || 0, branch.versions.length - 1));
    branch.activeIndex = activeIndex;
    turns.push({
      id: userMessage.id,
      baseUserId: userMessage.id,
      baseAgentId: agentMessage?.id || null,
      branch,
      version: branch.versions[activeIndex],
      activeIndex,
    });
    if (agentMessage) {
      index += 1;
    }
  }
  return turns;
}

function renderTurnVersionControls(turn, role, session) {
  const copied = session.copiedId === `${turn.id}:${role}`;
  const canStepBack = turn.activeIndex > 0;
  const canStepForward = turn.activeIndex < turn.branch.versions.length - 1;
  const isUser = role === "user";
  const canEdit = isUser && !turn.branch.loading;
  const canRefresh = !isUser && !turn.branch.loading;
  const countMarkup =
    turn.branch.versions.length > 1
      ? `
        <div class="message-version-switcher" aria-label="Version selector">
          <button class="message-action-icon" type="button" data-version-step="${turn.id}:-1" aria-label="Previous version" ${canStepBack ? "" : "disabled"}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M15 18l-6-6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <span class="message-version-count">${turn.activeIndex + 1}/${turn.branch.versions.length}</span>
          <button class="message-action-icon" type="button" data-version-step="${turn.id}:1" aria-label="Next version" ${canStepForward ? "" : "disabled"}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 18l6-6-6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      `
      : "";

  return `
    <div class="message-actions">
      ${countMarkup}
      ${
        canRefresh
          ? `
            <button class="message-action-icon" type="button" data-refresh-id="${turn.id}" aria-label="Refresh" ${turn.branch.loading ? "disabled" : ""}>
              <svg viewBox="0 0 24 24" aria-hidden="true" class="${turn.branch.loading ? "is-spinning" : ""}">
                <path d="M21 12a9 9 0 1 1-2.64-6.36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <path d="M21 3v6h-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          `
          : ""
      }
      <button class="message-action-icon" type="button" data-copy-id="${turn.id}:${role}" aria-label="${copied ? "Copied" : "Copy"}">
        ${
          copied
            ? `
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            `
            : `
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="9" y="9" width="10" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="2"/>
                <path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            `
        }
      </button>
      ${
        canEdit
          ? `
            <button class="message-action-icon" type="button" data-edit-id="${turn.id}" aria-label="Edit">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 20h9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <path d="M16.5 3.5a2.12 2.12 0 1 1 3 3L7 19l-4 1 1-4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
              </svg>
            </button>
          `
          : ""
      }
    </div>
  `;
}

function renderAssistantContent(text) {
  return renderMarkdown(String(text || "").trimEnd());
}

function renderMessages() {
  const session = getSession();
  const messages = currentMessages();
  const turns = buildMessageTurns(messages, session);
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
      ${turns
        .map(
          (turn) => `
            <article class="message-row user">
              <div class="message-shell user">
                ${
                  session.editingTurnId === turn.id
                    ? `
                      <div class="message message-editing user">
                        <textarea class="message-edit-textarea" data-edit-textarea="true" data-edit-id="${turn.id}" aria-label="Edit message">${escapeHtml(session.editingDraft)}</textarea>
                        <div class="message-edit-actions">
                          <button class="message-edit-button message-edit-button-secondary" type="button" data-edit-cancel="true">Cancel</button>
                          <button class="message-edit-button" type="button" data-edit-commit="true" ${turn.branch.loading ? "disabled" : ""}>${turn.branch.loading ? "Working..." : "Use text"}</button>
                        </div>
                      </div>
                    `
                    : `
                      <div class="message user">
                        <div class="message-body">${escapeHtml(String(turn.version.userText || "").trimEnd())}</div>
                      </div>
                    `
                }
                ${session.editingTurnId !== turn.id ? renderTurnVersionControls(turn, "user", session) : ""}
              </div>
            </article>
            ${
              turn.version.agentText
                ? `
                  <article class="message-row agent">
                    <div class="message-shell agent">
                      <div class="message agent">
                        <div class="message-body message-body-rich">${renderAssistantContent(turn.version.agentText)}</div>
                      </div>
                      ${renderTurnVersionControls(turn, "agent", session)}
                    </div>
                  </article>
                `
                : ""
            }
          `,
        )
        .join("")}
      ${
        session.pending
          ? `
            <article class="message-row agent">
              <div class="message-shell agent">
                <div class="message agent message-loading" aria-label="Loading response">
                  <span class="loading-dot"></span>
                  <span class="loading-dot"></span>
                  <span class="loading-dot"></span>
                </div>
              </div>
            </article>
          `
          : ""
      }
    </div>
  `;

  els.messages.querySelectorAll("[data-copy-id]").forEach((button) => {
    const [turnId, role] = String(button.dataset.copyId || "").split(":");
    button.addEventListener("click", () => copyTurnText(turnId, role));
  });
  els.messages.querySelectorAll("[data-refresh-id]").forEach((button) => {
    button.addEventListener("click", () => refreshMessage(button.dataset.refreshId));
  });
  els.messages.querySelectorAll("[data-edit-id]").forEach((button) => {
    button.addEventListener("click", () => editMessage(button.dataset.editId));
  });
  els.messages.querySelectorAll("[data-version-step]").forEach((button) => {
    const [turnId, step] = String(button.dataset.versionStep || "").split(":");
    button.addEventListener("click", () => stepTurnVersion(turnId, Number(step)));
  });
  els.messages.querySelectorAll("[data-edit-textarea]").forEach((field) => {
    field.style.height = "0px";
    field.style.height = `${Math.max(field.scrollHeight, 72)}px`;
    field.addEventListener("input", () => {
      const sessionState = getSession();
      sessionState.editingDraft = field.value;
      field.style.height = "0px";
      field.style.height = `${Math.max(field.scrollHeight, 72)}px`;
    });
    field.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        commitEditMessage();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        cancelEditMessage();
      }
    });
    field.focus();
    const caret = field.value.length;
    field.setSelectionRange(caret, caret);
  });
  els.messages.querySelectorAll("[data-edit-cancel]").forEach((button) => {
    button.addEventListener("click", () => cancelEditMessage());
  });
  els.messages.querySelectorAll("[data-edit-commit]").forEach((button) => {
    button.addEventListener("click", () => commitEditMessage());
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

function shortGraphLabel(value) {
  const text = String(value || "").trim();
  if (text.length <= 22) {
    return text;
  }
  return `${text.slice(0, 19)}...`;
}

function shouldShowGraphNodeLabel(node, totalNodes = 0) {
  if (node.family === "repository") {
    return true;
  }
  if (totalNodes >= LARGE_GRAPH_LAYOUT_THRESHOLD) {
    return node.degree >= 200 && node.rankInGroup < 3;
  }
  if (totalNodes > 3200) {
    return node.degree >= 24 && node.rankInGroup < 2;
  }
  if (totalNodes > 1600) {
    return node.degree >= 12 && node.rankInGroup < 2;
  }
  if (totalNodes > 700) {
    return node.degree >= 8 && node.rankInGroup < 2;
  }
  if (node.degree >= 8) {
    return true;
  }
  return node.rankInGroup < 3 && node.degree >= 2;
}

function buildGraphModel(payload) {
  const totalNodes = Math.max((payload.nodes || []).length, 1);
  const largeGraphMode = totalNodes >= LARGE_GRAPH_LAYOUT_THRESHOLD;
  const layoutScale = largeGraphMode ? Math.max(0.18, Math.min(0.42, 78 / Math.sqrt(totalNodes))) : Math.max(0.72, Math.min(1.08, 15 / Math.sqrt(totalNodes)));
  const nodes = (payload.nodes || []).map((node) => {
    const family = graphFamily(node.kind || node.label || "");
    const color = graphFamilyColor(family);
    const degree = Number(node.degree || 0);
    const radius = largeGraphMode
      ? Math.max(
          family === "repository" ? 5.4 : 0.92,
          Math.min(
            family === "repository" ? 10.8 : degree >= 12 ? 3.35 : 2.28,
            (family === "repository" ? 6.2 + Math.sqrt(degree + 1) * 0.52 : 1.04 + Math.sqrt(degree + 1) * 0.2) *
              layoutScale,
          ),
        )
      : Math.max(
          family === "document" || family === "config" ? 4.2 : 5.2,
          Math.min(
            family === "repository" ? 17 : family === "document" || family === "config" ? 10.8 : 13.2,
            (family === "repository" ? 10.8 + Math.sqrt(degree + 1) * 1.85 : 5.2 + Math.sqrt(degree + 1) * 1.55) *
              layoutScale,
          ),
        );
    return {
      ...node,
      degree,
      family,
      familyLabel: graphFamilyLabel(family),
      color,
      strokeColor: GRAPH_NODE_OUTLINE_COLOR,
      strokeWidth: largeGraphMode ? 0.35 : degree >= 10 ? 1.6 : 1.05,
      opacity: largeGraphMode ? (family === "repository" ? 0.88 : degree >= 10 ? 0.62 : 0.46) : 1,
      radius,
    };
  });

  const groupsByFamily = new Map();
  for (const node of nodes) {
    if (!groupsByFamily.has(node.family)) {
      groupsByFamily.set(node.family, {
        family: node.family,
        label: node.familyLabel,
        color: node.color,
        nodes: [],
      });
    }
    groupsByFamily.get(node.family).nodes.push(node);
  }

  const groups = [...groupsByFamily.values()]
    .map((group) => {
      group.nodes.sort((a, b) => b.degree - a.degree || a.label.localeCompare(b.label));
      group.nodes.forEach((node, index) => {
        node.rankInGroup = index;
      });
      const isLargeGroup = group.nodes.length > LARGE_GRAPH_LAYOUT_THRESHOLD / 2;
      group.spreadScale = Math.max(
        1,
        Math.min(
          isLargeGroup
            ? group.family === "document" || group.family === "config"
              ? 17.5
              : 13.5
            : group.family === "document" || group.family === "config"
              ? 7.4
              : 5.6,
          1 +
            Math.sqrt(group.nodes.length) /
              (isLargeGroup
                ? group.family === "document" || group.family === "config"
                  ? 1.85
                  : 2.45
                : group.family === "document" || group.family === "config"
                  ? 3.35
                  : 4.8),
        ),
      );
      return group;
    })
    .sort((a, b) => b.nodes.length - a.nodes.length || b.nodes[0].degree - a.nodes[0].degree);

  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  nodes.sort((a, b) => b.degree - a.degree || a.label.localeCompare(b.label));
  nodes.forEach((node, index) => {
    node.layoutIndex = index;
  });
  return { nodes, groups, nodeMap, totalNodes, layoutScale };
}

function assignGraphGroupCenters(groups, width, height) {
  const centerX = width / 2;
  const centerY = height / 2;
  const repositoryGroup = groups.find((group) => group.family === "repository");
  const others = groups.filter((group) => group.family !== "repository");

  if (repositoryGroup) {
    repositoryGroup.cx = centerX - 30;
    repositoryGroup.cy = centerY + 10;
  }

  if (!others.length) {
    return;
  }

  const totalWeight = others.reduce((sum, group) => sum + Math.max(group.nodes.length, 1), 0);
  const orbitX = Math.max(230, Math.min(width * 0.3, 310 + others.length * 24));
  const orbitY = Math.max(150, Math.min(height * 0.27, 190 + others.length * 18));
  let cursor = -Math.PI / 2;

  others.forEach((group) => {
    const slice = (Math.max(group.nodes.length, 1) / totalWeight) * Math.PI * 2;
    const angle = cursor + slice / 2 + (hashStringUnit(group.family) - 0.5) * 0.22;
    const familyBiasY = group.family === "document" ? -34 : group.family === "repository" ? 16 : 0;
    group.cx = centerX + Math.cos(angle) * orbitX;
    group.cy = centerY + Math.sin(angle) * orbitY + familyBiasY;
    cursor += slice;
  });
}

function normalizeGraphPositions(groups, positions, width, height) {
  const paddingX = 96;
  const paddingY = 72;
  const points = [...positions.values()];
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const usableWidth = width - paddingX * 2;
  const usableHeight = height - paddingY * 2;
  const scale = Math.min(usableWidth / spanX, usableHeight / spanY, 1);
  const offsetX = (width - spanX * scale) / 2 - minX * scale;
  const offsetY = (height - spanY * scale) / 2 - minY * scale;

  positions.forEach((point, key) => {
    positions.set(key, {
      x: point.x * scale + offsetX,
      y: point.y * scale + offsetY,
    });
  });

  groups.forEach((group) => {
    group.cx = group.cx * scale + offsetX;
    group.cy = group.cy * scale + offsetY;
  });
}

function spreadLargeGraphPositions(nodes, positions, groups) {
  const groupMap = new Map(groups.map((group) => [group.family, group]));
  for (const node of nodes) {
    const point = positions.get(node.id);
    const group = groupMap.get(node.family);
    if (!point || !group || node.family === "repository") {
      continue;
    }
    const rank = node.rankInGroup || 0;
    const jitter = hashStringUnit(node.id);
    const angle = rank * 2.399963229728653 + jitter * 0.9;
    const familySpread =
      node.family === "document" || node.family === "config" ? 11.2 : node.family === "code" ? 9.8 : 8.1;
    const shell = Math.pow(rank + 1, 0.42) * familySpread;
    const lobe = 0.74 + hashStringUnit(`${node.id}:lobe`) * 0.62;
    const skew = node.family === "code" ? 0.8 : 0.9;
    point.x = group.cx + Math.cos(angle) * shell * lobe;
    point.y = group.cy + Math.sin(angle) * shell * skew + (hashStringUnit(`${node.id}:ly`) - 0.5) * 10;
    positions.set(node.id, point);
  }
}

function graphViewportBounds(nodes) {
  const points = nodes.filter((node) => Number.isFinite(node.x) && Number.isFinite(node.y));
  if (!points.length) {
    return null;
  }
  return {
    minX: Math.min(...points.map((node) => node.x - node.radius)),
    maxX: Math.max(...points.map((node) => node.x + node.radius)),
    minY: Math.min(...points.map((node) => node.y - node.radius)),
    maxY: Math.max(...points.map((node) => node.y + node.radius)),
  };
}

function buildGraphSpatialIndex(nodes) {
  const buckets = new Map();
  for (const node of nodes) {
    const cellX = Math.floor(node.x / LARGE_GRAPH_SPATIAL_CELL_SIZE);
    const cellY = Math.floor(node.y / LARGE_GRAPH_SPATIAL_CELL_SIZE);
    const key = `${cellX}:${cellY}`;
    if (!buckets.has(key)) {
      buckets.set(key, []);
    }
    buckets.get(key).push(node);
  }
  return { buckets, cellSize: LARGE_GRAPH_SPATIAL_CELL_SIZE };
}

function buildGraphOverviewNodes(nodes) {
  const bounds = graphViewportBounds(nodes);
  if (!bounds) {
    return [];
  }
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const radiusX = Math.max(1, (bounds.maxX - bounds.minX) / 2);
  const radiusY = Math.max(1, (bounds.maxY - bounds.minY) / 2);
  const buckets = new Map();
  for (const node of nodes) {
    const cellX = Math.floor(node.x / LARGE_GRAPH_OVERVIEW_CELL_SIZE);
    const cellY = Math.floor(node.y / LARGE_GRAPH_OVERVIEW_CELL_SIZE);
    const key = `${cellX}:${cellY}:${node.family}`;
    const bucket = buckets.get(key) || {
      x: 0,
      y: 0,
      count: 0,
      color: node.color,
      family: node.family,
      maxRadius: 0,
      opacityTotal: 0,
      rank: Number.POSITIVE_INFINITY,
    };
    bucket.x += node.x;
    bucket.y += node.y;
    bucket.count += 1;
    bucket.maxRadius = Math.max(bucket.maxRadius, node.radius || 1);
    bucket.opacityTotal += node.opacity || 1;
    bucket.rank = Math.min(bucket.rank, node.rankInGroup ?? Number.POSITIVE_INFINITY);
    buckets.set(key, bucket);
  }
  const overviewNodes = [];
  for (const bucket of buckets.values()) {
    const x = bucket.x / bucket.count;
    const y = bucket.y / bucket.count;
    const normalizedX = (x - centerX) / radiusX;
    const normalizedY = (y - centerY) / radiusY;
    const radialDistance = Math.sqrt(normalizedX * normalizedX + normalizedY * normalizedY);
    const edgeFade = Math.max(0.12, Math.min(1, (1.1 - radialDistance) / 0.32));
    const meanOpacity = bucket.opacityTotal / bucket.count;
    overviewNodes.push({
      x,
      y,
      count: bucket.count,
      color: bucket.color,
      family: bucket.family,
      radius: Math.max(1, Math.min(4.8, Math.sqrt(bucket.count) * 0.95 + bucket.maxRadius * 0.24)),
      alpha: Math.max(0.16, Math.min(0.88, meanOpacity * (0.78 + edgeFade * 0.22))),
      rank: bucket.rank,
    });
  }
  overviewNodes.sort((left, right) => {
    const familyPriority = { repository: 0, code: 1, config: 2, document: 3, entity: 4 };
    return (
      (familyPriority[left.family] ?? 5) - (familyPriority[right.family] ?? 5) ||
      left.rank - right.rank ||
      right.count - left.count
    );
  });
  return overviewNodes;
}

function buildVisibleGraphLodPoints(nodes, scale) {
  if (!nodes.length) {
    return [];
  }
  const worldCellSize = Math.max(4, LARGE_GRAPH_MID_LOD_SCREEN_CELL / Math.max(scale, 0.001));
  const buckets = new Map();
  for (const node of nodes) {
    const cellX = Math.floor(node.x / worldCellSize);
    const cellY = Math.floor(node.y / worldCellSize);
    const key = `${cellX}:${cellY}:${node.family}`;
    const bucket = buckets.get(key) || {
      x: 0,
      y: 0,
      count: 0,
      color: node.color,
      family: node.family,
      maxRadius: 0,
      opacityTotal: 0,
      rank: Number.POSITIVE_INFINITY,
    };
    bucket.x += node.x;
    bucket.y += node.y;
    bucket.count += 1;
    bucket.maxRadius = Math.max(bucket.maxRadius, node.radius || 1);
    bucket.opacityTotal += node.opacity || 1;
    bucket.rank = Math.min(bucket.rank, node.rankInGroup ?? Number.POSITIVE_INFINITY);
    buckets.set(key, bucket);
  }
  const points = [];
  for (const bucket of buckets.values()) {
    const meanOpacity = bucket.opacityTotal / bucket.count;
    points.push({
      x: bucket.x / bucket.count,
      y: bucket.y / bucket.count,
      color: bucket.color,
      family: bucket.family,
      count: bucket.count,
      radius: Math.max(1, Math.min(3.8, Math.sqrt(bucket.count) * 0.72 + bucket.maxRadius * 0.28)),
      alpha: Math.max(0.16, Math.min(0.88, meanOpacity * (0.82 + Math.min(bucket.count, 8) * 0.02))),
      rank: bucket.rank,
    });
  }
  points.sort((left, right) => {
    const familyPriority = { repository: 0, code: 1, config: 2, document: 3, entity: 4 };
    return (
      (familyPriority[left.family] ?? 5) - (familyPriority[right.family] ?? 5) ||
      left.rank - right.rank ||
      right.count - left.count
    );
  });
  return points;
}

function drawGraphNodeLabel(context, node, text, scale, radiusScale, fontScale) {
  const x = node.x * scale + activeGraphView.offsetX;
  const y = node.y * scale + activeGraphView.offsetY + (node.radius * radiusScale + 11);
  context.font = `${Math.max(8, Math.round(10 * fontScale))}px Inter, system-ui, sans-serif`;
  context.lineWidth = 4;
  context.strokeStyle = "rgba(255, 255, 255, 0.92)";
  context.strokeText(text, x, y);
  context.fillStyle = node.strokeColor;
  context.fillText(text, x, y);
}

function drawMainGraphNodes(context, mainNodes, scale, radiusScale, fontScale) {
  if (!mainNodes?.length) {
    return;
  }
  context.textAlign = "center";
  context.lineJoin = "round";
  for (const mainNode of mainNodes) {
    const screenX = mainNode.x * scale + activeGraphView.offsetX;
    const screenY = mainNode.y * scale + activeGraphView.offsetY;
    const radius = Math.max(4.5, mainNode.radius * radiusScale * 1.18);
    context.beginPath();
    context.arc(screenX, screenY, radius, 0, Math.PI * 2);
    context.fillStyle = mainNode.color;
    context.globalAlpha = 1;
    context.fill();
    context.strokeStyle = GRAPH_MAIN_NODE_OUTLINE_COLOR;
    context.lineWidth = Math.max(1.15, mainNode.strokeWidth + 0.32);
    context.stroke();
    drawGraphNodeLabel(context, mainNode, shortGraphLabel(mainNode.label), scale, radiusScale, fontScale);
  }
}

function graphWorldViewport(padding = 64) {
  const scale = activeGraphView.scale || 1;
  return {
    minX: (-padding - activeGraphView.offsetX) / scale,
    maxX: (GRAPH_VIEWBOX.width + padding - activeGraphView.offsetX) / scale,
    minY: (-padding - activeGraphView.offsetY) / scale,
    maxY: (GRAPH_VIEWBOX.height + padding - activeGraphView.offsetY) / scale,
  };
}

function graphVisibleNodes(scene, worldViewport) {
  if (!scene.largeGraphMode || !scene.spatialIndex) {
    return scene.nodes;
  }
  if (activeGraphView.scale <= scene.minScale * 1.35) {
    return scene.nodes;
  }
  const { buckets, cellSize } = scene.spatialIndex;
  const minCellX = Math.floor(worldViewport.minX / cellSize);
  const maxCellX = Math.floor(worldViewport.maxX / cellSize);
  const minCellY = Math.floor(worldViewport.minY / cellSize);
  const maxCellY = Math.floor(worldViewport.maxY / cellSize);
  const visible = [];
  for (let cellX = minCellX; cellX <= maxCellX; cellX += 1) {
    for (let cellY = minCellY; cellY <= maxCellY; cellY += 1) {
      const bucket = buckets.get(`${cellX}:${cellY}`);
      if (!bucket) {
        continue;
      }
      for (const node of bucket) {
        if (
          node.x + node.radius >= worldViewport.minX &&
          node.x - node.radius <= worldViewport.maxX &&
          node.y + node.radius >= worldViewport.minY &&
          node.y - node.radius <= worldViewport.maxY
        ) {
          visible.push(node);
        }
      }
    }
  }
  return visible;
}

function relaxGraphPositions(nodes, edges, positions, nodeMap, groups, width, height) {
  const groupMap = new Map(groups.map((group) => [group.family, group]));
  const nodeList = nodes.filter((node) => positions.has(node.id));
  const iterations =
    nodeList.length > 4500 ? 10 : nodeList.length > 2500 ? 14 : nodeList.length > 1200 ? 22 : nodeList.length > 600 ? 38 : 62;
  const baseCellSize = nodeList.length > 2500 ? 84 : 72;

  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const displacements = new Map(nodeList.map((node) => [node.id, { x: 0, y: 0 }]));
    const buckets = new Map();
    const cellSize = baseCellSize + iteration * 2;

    for (const node of nodeList) {
      const point = positions.get(node.id);
      const cellX = Math.floor(point.x / cellSize);
      const cellY = Math.floor(point.y / cellSize);
      const key = `${cellX}:${cellY}`;
      if (!buckets.has(key)) {
        buckets.set(key, []);
      }
      buckets.get(key).push(node);
    }

    for (const node of nodeList) {
      const posA = positions.get(node.id);
      const cellX = Math.floor(posA.x / cellSize);
      const cellY = Math.floor(posA.y / cellSize);
      for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
        for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
          const nearby = buckets.get(`${cellX + offsetX}:${cellY + offsetY}`) || [];
          for (const other of nearby) {
            if (other.layoutIndex <= node.layoutIndex) {
              continue;
            }
            const posB = positions.get(other.id);
            const dx = posA.x - posB.x;
            const dy = posA.y - posB.y;
            const distanceSq = dx * dx + dy * dy + 0.01;
            const distance = Math.sqrt(distanceSq);
            const sameFamily = node.family === other.family;
            const repulsionBase = sameFamily
              ? node.family === "document" || node.family === "config"
                ? 13200
                : 6800
              : 3600;
            const repulsion = Math.min(repulsionBase / distanceSq, sameFamily ? 18 : 10);
            const forceX = (dx / distance) * repulsion;
            const forceY = (dy / distance) * repulsion;
            displacements.get(node.id).x += forceX;
            displacements.get(node.id).y += forceY;
            displacements.get(other.id).x -= forceX;
            displacements.get(other.id).y -= forceY;
          }
        }
      }
    }

    for (const edge of edges) {
      const sourceNode = nodeMap.get(edge.source);
      const targetNode = nodeMap.get(edge.target);
      if (!sourceNode || !targetNode || !positions.has(sourceNode.id) || !positions.has(targetNode.id)) {
        continue;
      }
      const source = positions.get(sourceNode.id);
      const target = positions.get(targetNode.id);
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const sameFamily = sourceNode.family === targetNode.family;
      const touchesRepository = sourceNode.family === "repository" || targetNode.family === "repository";
      const preferred = touchesRepository ? 245 : sameFamily ? (sourceNode.family === "document" || sourceNode.family === "config" ? 126 : 88) : 168;
      const pull = (distance - preferred) * (touchesRepository ? 0.0015 : sameFamily ? 0.0052 : 0.0024);
      const forceX = (dx / distance) * pull;
      const forceY = (dy / distance) * pull;
      displacements.get(sourceNode.id).x += forceX;
      displacements.get(sourceNode.id).y += forceY;
      displacements.get(targetNode.id).x -= forceX;
      displacements.get(targetNode.id).y -= forceY;
    }

    for (const node of nodeList) {
      const group = groupMap.get(node.family);
      if (!group) continue;
      const displacement = displacements.get(node.id);
      const point = positions.get(node.id);
      const gravity =
        node.family === "repository"
          ? 0.038
          : node.family === "document" || node.family === "config"
            ? 0.0045
            : 0.012;
      displacement.x += (group.cx - point.x) * gravity;
      displacement.y += (group.cy - point.y) * gravity;
    }

    const temperature = 12 * (1 - iteration / iterations);
    for (const node of nodeList) {
      const point = positions.get(node.id);
      const displacement = displacements.get(node.id);
      point.x += Math.max(-temperature, Math.min(temperature, displacement.x));
      point.y += Math.max(-temperature, Math.min(temperature, displacement.y));
      positions.set(node.id, point);
    }
  }
}

function separateOverlappingGraphNodes(nodes, positions) {
  const nodeList = nodes.filter((node) => positions.has(node.id));
  const passes = nodeList.length > 3000 ? 5 : nodeList.length > 1200 ? 8 : 12;
  for (let pass = 0; pass < passes; pass += 1) {
    let moved = false;
    const buckets = new Map();
    const cellSize = 46;
    for (const node of nodeList) {
      const point = positions.get(node.id);
      const cellX = Math.floor(point.x / cellSize);
      const cellY = Math.floor(point.y / cellSize);
      const key = `${cellX}:${cellY}`;
      if (!buckets.has(key)) {
        buckets.set(key, []);
      }
      buckets.get(key).push(node);
    }
    for (const node of nodeList) {
      const posA = positions.get(node.id);
      const cellX = Math.floor(posA.x / cellSize);
      const cellY = Math.floor(posA.y / cellSize);
      for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
        for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
          const nearby = buckets.get(`${cellX + offsetX}:${cellY + offsetY}`) || [];
          for (const other of nearby) {
            if (other.layoutIndex <= node.layoutIndex) {
              continue;
            }
            const posB = positions.get(other.id);
            const dx = posB.x - posA.x;
            const dy = posB.y - posA.y;
            const distance = Math.sqrt(dx * dx + dy * dy) || 0.001;
            const sameFamily = node.family === other.family;
            const minGap =
              node.radius +
              other.radius +
              (sameFamily ? (node.family === "document" || node.family === "config" ? 16 : 14) : 20);
            if (distance >= minGap) {
              continue;
            }
            const push = (minGap - distance) / 2;
            const pushX = (dx / distance) * push;
            const pushY = (dy / distance) * push;
            posA.x -= pushX;
            posA.y -= pushY;
            posB.x += pushX;
            posB.y += pushY;
            moved = true;
          }
        }
      }
    }
    if (!moved) {
      break;
    }
  }
}

function computeGraphGroupBounds(groups, positions) {
  const boundsByFamily = new Map();
  for (const group of groups) {
    const points = group.nodes
      .filter((node) => positions.has(node.id))
      .map((node) => {
        const point = positions.get(node.id);
        return {
          x: point.x,
          y: point.y,
          radius: node.radius,
        };
      });
    if (!points.length) {
      continue;
    }
    const padX = group.family === "repository" ? 26 : 34;
    const padY = group.family === "repository" ? 22 : 30;
    const minX = Math.min(...points.map((point) => point.x - point.radius)) - padX;
    const maxX = Math.max(...points.map((point) => point.x + point.radius)) + padX;
    const minY = Math.min(...points.map((point) => point.y - point.radius)) - padY;
    const maxY = Math.max(...points.map((point) => point.y + point.radius)) + padY;
    boundsByFamily.set(group.family, {
      cx: (minX + maxX) / 2,
      cy: (minY + maxY) / 2,
      rx: Math.max((maxX - minX) / 2, group.family === "repository" ? 42 : 58),
      ry: Math.max((maxY - minY) / 2, group.family === "repository" ? 32 : 46),
    });
  }
  return boundsByFamily;
}

function wireGraphTooltip() {
  const canvas = els.graphStage.querySelector(".graph-canvas");
  const tooltip = els.graphStage.querySelector(".graph-tooltip");
  if (!tooltip || !canvas) {
    return;
  }
  canvas.addEventListener("mousemove", (event) => {
    if (!activeGraphScene) {
      return;
    }
    if (graphDragState.dragging) {
      tooltip.hidden = true;
      return;
    }
    const stageRect = els.graphStage.getBoundingClientRect();
    const canvasRect = canvas.getBoundingClientRect();
    const x = ((event.clientX - canvasRect.left) / canvasRect.width) * activeGraphScene.width;
    const y = ((event.clientY - canvasRect.top) / canvasRect.height) * activeGraphScene.height;
    const hitNode = findGraphHoverNode(x, y);

    if (hitNode?.id !== activeGraphScene.hoverNodeId) {
      activeGraphScene.hoverNodeId = hitNode?.id || null;
      scheduleGraphRedraw();
    }

    if (!hitNode) {
      tooltip.hidden = true;
      return;
    }

    tooltip.innerHTML = `
      <strong>${escapeHtml(hitNode.label)}</strong>
      <span>${escapeHtml(hitNode.familyLabel || "Node")} • ${hitNode.degree || 0} links</span>
    `;
    tooltip.hidden = false;
    const tooltipWidth = Math.min(stageRect.width - 20, Math.max(180, tooltip.offsetWidth || 220));
    const offsetX = event.clientX - stageRect.left + 14;
    const offsetY = event.clientY - stageRect.top - 14;
    tooltip.style.left = `${Math.max(10, Math.min(offsetX, stageRect.width - tooltipWidth - 10))}px`;
    tooltip.style.top = `${Math.max(offsetY, 14)}px`;
  });

  canvas.addEventListener("mouseleave", () => {
    tooltip.hidden = true;
    if (activeGraphScene?.hoverNodeId) {
      activeGraphScene.hoverNodeId = null;
      scheduleGraphRedraw();
    }
  });
}

function resetGraphViewport(width = GRAPH_VIEWBOX.width, height = GRAPH_VIEWBOX.height, bounds = activeGraphScene?.bounds || null) {
  if (bounds) {
    const padding = 44;
    const spanX = Math.max(bounds.maxX - bounds.minX, 1);
    const spanY = Math.max(bounds.maxY - bounds.minY, 1);
    const fittedScale = Math.min((width - padding * 2) / spanX, (height - padding * 2) / spanY, 1);
    const scale = Math.max(fittedScale, activeGraphScene?.largeGraphMode ? 0.07 : 0.025);
    if (activeGraphScene) {
      activeGraphScene.minScale = Math.max(scale * 0.82, activeGraphScene.largeGraphMode ? 0.055 : 0.018);
    }
    activeGraphView = {
      scale,
      offsetX: width / 2 - ((bounds.minX + bounds.maxX) / 2) * scale,
      offsetY: height / 2 - ((bounds.minY + bounds.maxY) / 2) * scale,
    };
    return;
  }
  activeGraphView = {
    scale: 1,
    offsetX: width * 0.02,
    offsetY: height * 0.02,
  };
}

function updateGraphViewport() {
  scheduleGraphRedraw();
}

function adjustGraphZoom(factor, centerX, centerY) {
  const minScale = activeGraphScene?.minScale || 0.55;
  const maxScale = activeGraphScene?.largeGraphMode ? 6.5 : 2.8;
  const nextScale = Math.max(minScale, Math.min(maxScale, activeGraphView.scale * factor));
  const appliedFactor = nextScale / activeGraphView.scale;
  activeGraphView.offsetX = centerX - (centerX - activeGraphView.offsetX) * appliedFactor;
  activeGraphView.offsetY = centerY - (centerY - activeGraphView.offsetY) * appliedFactor;
  activeGraphView.scale = nextScale;
  updateGraphViewport();
}

const GRAPH_BUTTON_ZOOM_FACTOR = 1.1;
const GRAPH_WHEEL_ZOOM_FACTOR = 1.045;

function wireGraphZoom() {
  const canvas = els.graphStage.querySelector(".graph-canvas");
  const controls = els.graphStage.querySelectorAll("[data-graph-zoom]");
  if (!canvas) {
    return;
  }
  activeGraphCanvas = canvas;

  controls.forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.graphZoom;
      if (action === "reset") {
        resetGraphViewport();
        updateGraphViewport();
        return;
      }
      adjustGraphZoom(
        action === "in" ? GRAPH_BUTTON_ZOOM_FACTOR : 1 / GRAPH_BUTTON_ZOOM_FACTOR,
        GRAPH_VIEWBOX.width / 2,
        GRAPH_VIEWBOX.height / 2,
      );
    });
  });

  canvas.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * GRAPH_VIEWBOX.width;
      const y = ((event.clientY - rect.top) / rect.height) * GRAPH_VIEWBOX.height;
      adjustGraphZoom(event.deltaY < 0 ? GRAPH_WHEEL_ZOOM_FACTOR : 1 / GRAPH_WHEEL_ZOOM_FACTOR, x, y);
    },
    { passive: false },
  );

  canvas.addEventListener("mousedown", (event) => {
    graphDragState.dragging = true;
    graphDragState.startX = event.clientX;
    graphDragState.startY = event.clientY;
    if (activeGraphScene?.hoverNodeId) {
      activeGraphScene.hoverNodeId = null;
    }
    canvas.classList.add("is-dragging");
  });

  if (graphWindowListenersBound) {
    return;
  }
  graphWindowListenersBound = true;
  window.addEventListener("mousemove", (event) => {
    if (!graphDragState.dragging || !activeGraphCanvas) {
      return;
    }
    activeGraphView.offsetX +=
      ((event.clientX - graphDragState.startX) / activeGraphCanvas.clientWidth) * GRAPH_VIEWBOX.width;
    activeGraphView.offsetY +=
      ((event.clientY - graphDragState.startY) / activeGraphCanvas.clientHeight) * GRAPH_VIEWBOX.height;
    graphDragState.startX = event.clientX;
    graphDragState.startY = event.clientY;
    updateGraphViewport();
  });

  window.addEventListener("mouseup", () => {
    const wasDragging = graphDragState.dragging;
    graphDragState.dragging = false;
    activeGraphCanvas?.classList.remove("is-dragging");
    if (wasDragging) {
      scheduleGraphRedraw();
    }
  });
}

function scheduleGraphRedraw() {
  if (activeGraphFrame) {
    return;
  }
  activeGraphFrame = window.requestAnimationFrame(() => {
    activeGraphFrame = 0;
    drawGraphScene();
  });
}

function drawGraphScene() {
  if (!activeGraphScene) {
    return;
  }
  const canvas = els.graphStage.querySelector(".graph-canvas");
  if (!canvas) {
    return;
  }
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const { width, height } = activeGraphScene;
  context.clearRect(0, 0, width, height);

  const scale = activeGraphView.scale;
  const radiusScale = graphNodeZoomScale(scale);
  const fontScale = Math.max(0.58, Math.min(1, 0.78 + (radiusScale - 0.55) * 0.9));
  const edgeStride = 1;
  const useOverviewLod =
    activeGraphScene.largeGraphMode && activeGraphScene.overviewNodes.length && scale < LARGE_GRAPH_OVERVIEW_LOD_SCALE;
  const suppressEdgesForScale = activeGraphScene.largeGraphMode && scale < LARGE_GRAPH_MID_LOD_SCALE;
  const drawLargeGraphEdges =
    !useOverviewLod &&
    !suppressEdgesForScale &&
    (!activeGraphScene.largeGraphMode || scale >= LARGE_GRAPH_EDGE_VISIBILITY_SCALE);
  const viewportPadding = 64;
  const viewportMinX = -viewportPadding;
  const viewportMaxX = width + viewportPadding;
  const viewportMinY = -viewportPadding;
  const viewportMaxY = height + viewportPadding;
  const worldViewport = graphWorldViewport(viewportPadding);
  const visibleNodes = useOverviewLod ? [] : graphVisibleNodes(activeGraphScene, worldViewport);
  const useMidLod =
    activeGraphScene.largeGraphMode &&
    !useOverviewLod &&
    scale < LARGE_GRAPH_MID_LOD_SCALE &&
    visibleNodes.length > LARGE_GRAPH_MAX_DIRECT_NODE_DRAWS;
  const lodNodes = useMidLod ? buildVisibleGraphLodPoints(visibleNodes, scale) : [];
  const useDenseDirectMode =
    activeGraphScene.largeGraphMode &&
    !useOverviewLod &&
    !useMidLod &&
    visibleNodes.length > LARGE_GRAPH_DENSE_DIRECT_NODE_THRESHOLD;
  const visibleNodeIds =
    activeGraphScene.largeGraphMode && !useMidLod && visibleNodes.length <= LARGE_GRAPH_MAX_EDGE_VISIBLE_NODES
      ? new Set(visibleNodes.map((node) => node.id))
      : null;

  if (useOverviewLod) {
    context.save();
    for (const point of activeGraphScene.overviewNodes) {
      const screenX = point.x * scale + activeGraphView.offsetX;
      const screenY = point.y * scale + activeGraphView.offsetY;
      if (screenX < viewportMinX || screenX > viewportMaxX || screenY < viewportMinY || screenY > viewportMaxY) {
        continue;
      }
      const radius = Math.max(0.9, Math.min(4.5, point.radius * (0.82 + scale * 0.8)));
      context.beginPath();
      context.arc(screenX, screenY, radius, 0, Math.PI * 2);
      context.fillStyle = point.color;
      context.globalAlpha = point.alpha;
      context.fill();
    }
    context.globalAlpha = 1;
    context.restore();
    drawMainGraphNodes(context, activeGraphScene.mainNodes, scale, radiusScale, fontScale);
  }

  if (useMidLod) {
    context.save();
    for (const point of lodNodes) {
      const screenX = point.x * scale + activeGraphView.offsetX;
      const screenY = point.y * scale + activeGraphView.offsetY;
      if (screenX < viewportMinX || screenX > viewportMaxX || screenY < viewportMinY || screenY > viewportMaxY) {
        continue;
      }
      const radius = Math.max(1, Math.min(4.2, point.radius * (0.9 + scale * 0.4)));
      context.beginPath();
      context.arc(screenX, screenY, radius, 0, Math.PI * 2);
      context.fillStyle = point.color;
      context.globalAlpha = point.alpha;
      context.fill();
    }
    context.globalAlpha = 1;
    context.restore();
    drawMainGraphNodes(context, activeGraphScene.mainNodes, scale, radiusScale, fontScale);
  }

  context.save();
  context.lineCap = "round";
  if (
    drawLargeGraphEdges &&
    !graphDragState.dragging &&
    (!activeGraphScene.largeGraphMode || visibleNodeIds)
  ) {
    const edgeSource = activeGraphScene.largeGraphMode ? activeGraphScene.rawEdges : activeGraphScene.edges;
    let drawnEdges = 0;
    for (let index = 0; index < edgeSource.length; index += edgeStride) {
      const edge = edgeSource[index];
      const sourceNode = activeGraphScene.largeGraphMode ? activeGraphScene.nodeById.get(edge.source) : edge.source;
      const targetNode = activeGraphScene.largeGraphMode ? activeGraphScene.nodeById.get(edge.target) : edge.target;
      if (!sourceNode || !targetNode) {
        continue;
      }
      if (visibleNodeIds && (!visibleNodeIds.has(sourceNode.id) || !visibleNodeIds.has(targetNode.id))) {
        continue;
      }
      const sourceX = sourceNode.x * scale + activeGraphView.offsetX;
      const sourceY = sourceNode.y * scale + activeGraphView.offsetY;
      const targetX = targetNode.x * scale + activeGraphView.offsetX;
      const targetY = targetNode.y * scale + activeGraphView.offsetY;
      if (
        (sourceX < viewportMinX && targetX < viewportMinX) ||
        (sourceX > viewportMaxX && targetX > viewportMaxX) ||
        (sourceY < viewportMinY && targetY < viewportMinY) ||
        (sourceY > viewportMaxY && targetY > viewportMaxY)
      ) {
        continue;
      }
      let strokeStyle = edge.color;
      let opacity = edge.opacity;
      let width = edge.width;
      if (activeGraphScene.largeGraphMode) {
        const sameFamily = sourceNode.family === targetNode.family;
        const touchesRepository = sourceNode.family === "repository" || targetNode.family === "repository";
        strokeStyle = sameFamily ? "rgba(67, 76, 91, 0.08)" : "rgba(67, 76, 91, 0.055)";
        opacity = touchesRepository ? 0.22 : 0.12;
        width = touchesRepository ? 0.24 : 0.14;
      }
      context.beginPath();
      context.moveTo(sourceX, sourceY);
      context.lineTo(targetX, targetY);
      context.strokeStyle = strokeStyle;
      context.globalAlpha = opacity;
      context.lineWidth = activeGraphScene.largeGraphMode
        ? Math.max(0.08, width * Math.max(0.45, Math.min(scale, 1.4)))
        : Math.max(0.4, width * Math.max(0.5, Math.min(scale, 1.1)));
      context.stroke();
      drawnEdges += 1;
      if (activeGraphScene.largeGraphMode && drawnEdges >= LARGE_GRAPH_MAX_EDGE_DRAWS) {
        break;
      }
    }
  }
  context.restore();

  if (!useOverviewLod && !useMidLod) {
    for (const node of visibleNodes) {
      const screenX = node.x * scale + activeGraphView.offsetX;
      const screenY = node.y * scale + activeGraphView.offsetY;
      const radius = node.radius * radiusScale;
      if (
        screenX + radius < viewportMinX ||
        screenX - radius > viewportMaxX ||
        screenY + radius < viewportMinY ||
        screenY - radius > viewportMaxY
      ) {
        continue;
      }
      const hovered = node.id === activeGraphScene.hoverNodeId;
      const isMainNode = activeGraphScene.mainNodeIds?.has(node.id);
      if (activeGraphScene.largeGraphMode && !hovered && scale < 0.38) {
        const pointSize = Math.max(1.35, Math.min(2.8, radius * 1.7));
        context.fillStyle = node.color;
        context.globalAlpha = node.opacity || 0.58;
        context.fillRect(screenX - pointSize / 2, screenY - pointSize / 2, pointSize, pointSize);
        continue;
      }
      context.beginPath();
      context.arc(screenX, screenY, hovered ? radius + 1 : radius, 0, Math.PI * 2);
      context.fillStyle = node.color;
      context.globalAlpha = hovered ? 1 : node.opacity || 1;
      context.fill();
      context.globalAlpha = 1;
      if (isMainNode && !hovered) {
        continue;
      }
      if (!useDenseDirectMode || hovered || node.family === "repository" || node.degree >= 20) {
        context.strokeStyle = hovered ? GRAPH_NODE_OUTLINE_HOVER_COLOR : node.strokeColor;
        context.lineWidth = hovered ? Math.max(1.4, node.strokeWidth + 0.4) : node.strokeWidth;
        context.stroke();
      }
    }
    drawMainGraphNodes(context, activeGraphScene.mainNodes, scale, radiusScale, fontScale);
  }
  context.globalAlpha = 1;

  context.textAlign = "center";
  context.lineJoin = "round";
  if (useOverviewLod || useMidLod || (activeGraphScene.largeGraphMode && scale < LARGE_GRAPH_LABEL_VISIBILITY_SCALE)) {
    return;
  }
  for (const label of activeGraphScene.labels) {
    const node = activeGraphScene.nodeById.get(label.id);
    if (!node || activeGraphScene.mainNodeIds?.has(node.id)) {
      continue;
    }
    const x = label.x * scale + activeGraphView.offsetX;
    const y = label.y * scale + activeGraphView.offsetY + (node.radius * radiusScale + 11);
    if (x < viewportMinX || x > viewportMaxX || y < viewportMinY || y > viewportMaxY) {
      continue;
    }
    drawGraphNodeLabel(context, node, label.text, scale, radiusScale, fontScale);
  }
}

function findGraphHoverNode(screenX, screenY) {
  if (!activeGraphScene) {
    return null;
  }
  if (activeGraphScene.largeGraphMode && activeGraphView.scale < LARGE_GRAPH_MID_LOD_SCALE) {
    return null;
  }
  if (activeGraphScene.totalNodes > LARGE_GRAPH_NODE_PICK_THRESHOLD && activeGraphView.scale < 0.22) {
    return null;
  }
  const radiusScale = graphNodeZoomScale(activeGraphView.scale);
  let bestNode = null;
  let bestDistanceRatio = Number.POSITIVE_INFINITY;
  const worldX = (screenX - activeGraphView.offsetX) / activeGraphView.scale;
  const worldY = (screenY - activeGraphView.offsetY) / activeGraphView.scale;
  const hitRadius = activeGraphScene.largeGraphMode ? 36 / activeGraphView.scale : 24 / activeGraphView.scale;
  const candidates = activeGraphScene.largeGraphMode
    ? graphVisibleNodes(activeGraphScene, {
        minX: worldX - hitRadius,
        maxX: worldX + hitRadius,
        minY: worldY - hitRadius,
        maxY: worldY + hitRadius,
      })
    : activeGraphScene.nodes;
  for (let index = candidates.length - 1; index >= 0; index -= 1) {
    const node = candidates[index];
    const x = node.x * activeGraphView.scale + activeGraphView.offsetX;
    const y = node.y * activeGraphView.scale + activeGraphView.offsetY;
    const radius = Math.max(node.radius * radiusScale + 2, activeGraphScene.largeGraphMode ? 5 : 0);
    const dx = screenX - x;
    const dy = screenY - y;
    const distanceSq = dx * dx + dy * dy;
    if (distanceSq > radius * radius) {
      continue;
    }
    const distanceRatio = distanceSq / (radius * radius);
    if (distanceRatio < bestDistanceRatio) {
      bestDistanceRatio = distanceRatio;
      bestNode = node;
    }
  }
  return bestNode;
}

function graphNodeZoomScale(scale) {
  return Math.max(0.8, Math.min(1.26, 1 / Math.pow(scale, 0.14)));
}

function placeClusterNodes(group, positions) {
  if (!group.nodes.length) {
    return;
  }
  const firstNode = group.nodes[0];
  const firstJitter = hashStringUnit(firstNode.id);
  positions.set(firstNode.id, {
    x: group.cx + (firstJitter - 0.5) * 42,
    y: group.cy + (hashStringUnit(`${firstNode.id}:y`) - 0.5) * 42,
  });
  for (let index = 1; index < group.nodes.length; index += 1) {
    const node = group.nodes[index];
    const isRepository = group.family === "repository";
    let angle;
    let radiusX;
    let radiusY;
    if (isRepository) {
      const jitter = hashStringUnit(node.id);
      angle = index * 2.17 + jitter * 1.8;
      radiusX = 42 + index * 28;
      radiusY = 36 + index * 22;
    } else {
      const rank = index;
      const jitter = hashStringUnit(node.id);
      angle = rank * 2.099963229728653 + jitter * Math.PI;
      const familyBase = group.family === "document" || group.family === "config" ? 24 : group.family === "code" ? 22 : 19;
      const shell = Math.sqrt(rank) * familyBase * group.spreadScale;
      const lobe = 0.72 + hashStringUnit(`${node.id}:lobe`) * 0.72;
      radiusX = shell * lobe * (group.family === "document" || group.family === "config" ? 1.18 : 1.0);
      radiusY = shell * (0.64 + hashStringUnit(`${node.id}:y`) * 0.54);
    }
    positions.set(node.id, {
      x: group.cx + Math.cos(angle) * radiusX,
      y: group.cy + Math.sin(angle) * radiusY,
    });
  }
}

function hashStringUnit(value) {
  let hash = 0;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0;
  }
  return (hash % 1000) / 1000;
}

function graphFamily(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("repository") || text.includes("repo")) return "repository";
  if (text.includes("config") || text.includes("cmake") || text.includes("yaml") || text.includes("yml") || text.includes("toml") || text.includes("json")) return "config";
  if (text.includes("document") || text.includes("readme") || text.includes("markdown") || text.includes("md")) return "document";
  if (text.includes("class") || text.includes("entity") || text.includes("struct")) return "entity";
  if (text.includes("function") || text.includes("method") || text.includes("call")) return "logic";
  if (text.includes("code") || text.includes("file") || text.includes("source")) return "code";
  return "other";
}

function graphFamilyLabel(family) {
  const labels = {
    repository: "Repository",
    config: "Config",
    document: "Documents",
    entity: "Entities",
    logic: "Logic",
    code: "Code",
    other: "Other",
  };
  return labels[family] || "Other";
}

function graphFamilyColor(family) {
  const colors = {
    repository: "#c8d0f4",
    config: "#95a4c0",
    document: "#e0af68",
    entity: "#bb9af7",
    logic: "#f0c38a",
    code: "#7dcfff",
    other: "#79aac8",
  };
  return colors[family] || "#79aac8";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMarkdown(input) {
  const lines = String(input || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];

  for (let index = 0; index < lines.length; ) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const fence = trimmed.slice(3).trim();
      index += 1;
      const codeLines = [];
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push(
        `<pre class="md-pre"><code class="md-code-block"${fence ? ` data-lang="${escapeHtml(fence)}"` : ""}>${escapeHtml(codeLines.join("\n"))}</code></pre>`,
      );
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      blocks.push(`<h${level} class="md-heading md-h${level}">${renderMarkdownInline(headingMatch[2])}</h${level}>`);
      index += 1;
      continue;
    }

    if (isMarkdownTable(lines, index)) {
      const tableLines = [lines[index], lines[index + 1]];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push(renderMarkdownTable(tableLines));
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, ""));
        index += 1;
      }
      blocks.push(`<ul class="md-list">${items.map((item) => `<li>${renderMarkdownInline(item)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(`<ol class="md-list md-list-ordered">${items.map((item) => `<li>${renderMarkdownInline(item)}</li>`).join("")}</ol>`);
      continue;
    }

    const paragraphLines = [];
    while (index < lines.length) {
      const next = lines[index];
      const nextTrimmed = next.trim();
      if (
        !nextTrimmed ||
        nextTrimmed.startsWith("```") ||
        /^(#{1,6})\s+/.test(nextTrimmed) ||
        /^\s*[-*+]\s+/.test(next) ||
        /^\s*\d+\.\s+/.test(next) ||
        isMarkdownTable(lines, index)
      ) {
        break;
      }
      paragraphLines.push(nextTrimmed);
      index += 1;
    }
    blocks.push(`<p>${renderMarkdownInline(paragraphLines.join(" "))}</p>`);
  }

  return blocks.join("");
}

function renderMarkdownInline(text) {
  const placeholders = [];
  let safe = escapeHtml(text);

  safe = safe.replace(/&lt;br\s*\/?&gt;/gi, "<br>");

  safe = safe.replace(/`([^`]+)`/g, (_, code) => {
    const token = `__MD_TOKEN_${placeholders.length}__`;
    placeholders.push(`<code class="md-inline-code">${escapeHtml(code)}</code>`);
    return token;
  });

  safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_, label, url) => {
    const token = `__MD_TOKEN_${placeholders.length}__`;
    placeholders.push(
      `<a class="md-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">${renderMarkdownInline(label)}</a>`,
    );
    return token;
  });

  safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  safe = safe.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  safe = safe.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");

  placeholders.forEach((value, index) => {
    safe = safe.replaceAll(`__MD_TOKEN_${index}__`, value);
  });
  return safe;
}

function isMarkdownTable(lines, index) {
  if (index + 1 >= lines.length) {
    return false;
  }
  const header = lines[index].trim();
  const separator = lines[index + 1].trim();
  return header.includes("|") && /^[\s|:-]+$/.test(separator) && separator.includes("|");
}

function renderMarkdownTable(lines) {
  const parseRow = (line) =>
    line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());

  const headers = parseRow(lines[0]);
  const rows = lines.slice(2).map(parseRow);
  return `
    <div class="md-table-wrap">
      <table class="md-table">
        <thead><tr>${headers.map((cell) => `<th>${renderMarkdownInline(cell)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows
            .map((row) => `<tr>${row.map((cell) => `<td>${renderMarkdownInline(cell)}</td>`).join("")}</tr>`)
            .join("")}
        </tbody>
      </table>
    </div>
  `;
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
