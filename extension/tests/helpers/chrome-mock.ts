export interface TabUpdatedListener {
  (tabId: number, changeInfo: { status?: string }): void;
}

export interface ChromeMockTab {
  id?: number;
  url?: string;
  status?: string;
}

export interface ChromeMockState {
  createdTabs: Array<{ active?: boolean; url: string }>;
  updatedTabs: Array<{ active?: boolean; tabId: number; url?: string }>;
  sentMessages: Array<{ message: unknown; tabId: number }>;
  fetchCalls: Array<{ body?: unknown; method?: string; url: string }>;
  queryResult: ChromeMockTab[];
  tabById: Map<number, ChromeMockTab>;
  sendMessageImpl: (tabId: number, message: unknown) => Promise<unknown>;
  emitTabUpdated: (tabId: number, changeInfo: { status?: string }) => void;
  restore: () => void;
}

export function installChromeMock(): ChromeMockState {
  const originalChrome = (globalThis as { chrome?: unknown }).chrome;
  const originalFetch = globalThis.fetch;
  const listeners: TabUpdatedListener[] = [];
  const state: ChromeMockState = {
    createdTabs: [],
    updatedTabs: [],
    sentMessages: [],
    fetchCalls: [],
    queryResult: [],
    tabById: new Map(),
    sendMessageImpl: async () => ({ status: "ok", actions: [] }),
    emitTabUpdated(tabId, changeInfo) {
      for (const listener of [...listeners]) {
        listener(tabId, changeInfo);
      }
    },
    restore() {
      (globalThis as { chrome?: unknown }).chrome = originalChrome;
      globalThis.fetch = originalFetch;
    },
  };

  let nextTabId = 42;

  const chromeMock = {
    storage: {
      local: {
        get(_key: string, callback: (items: Record<string, unknown>) => void) {
          callback({});
        },
      },
      onChanged: {
        addListener() {
          // Tests do not need storage change delivery.
        },
      },
    },
    tabs: {
      async create(opts: { active?: boolean; url: string }) {
        state.createdTabs.push(opts);
        const tab = { id: nextTabId++, status: "complete", url: opts.url };
        state.tabById.set(tab.id, tab);
        return tab;
      },
      async query() {
        return state.queryResult;
      },
      async get(tabId: number) {
        return state.tabById.get(tabId) ?? { id: tabId, status: "complete" };
      },
      async update(tabId: number, opts: { active?: boolean; url?: string }) {
        state.updatedTabs.push({ tabId, ...opts });
        const current = state.tabById.get(tabId) ?? { id: tabId };
        const updated = {
          ...current,
          ...opts,
          status: current.status ?? "complete",
        };
        state.tabById.set(tabId, updated);
        return updated;
      },
      async sendMessage(tabId: number, message: unknown) {
        state.sentMessages.push({ tabId, message });
        return state.sendMessageImpl(tabId, message);
      },
      onUpdated: {
        addListener(listener: TabUpdatedListener) {
          listeners.push(listener);
        },
        removeListener(listener: TabUpdatedListener) {
          const index = listeners.indexOf(listener);
          if (index >= 0) {
            listeners.splice(index, 1);
          }
        },
      },
    },
  };

  (globalThis as { chrome?: unknown }).chrome = chromeMock;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    state.fetchCalls.push({
      url: String(input),
      method: init?.method,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }) as typeof fetch;

  return state;
}
