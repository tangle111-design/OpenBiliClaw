import { apiUrl } from "../shared/backend-endpoint.ts";
import {
  actionsForE2EPlatform,
  E2E_PLATFORM_URLS,
  type E2EActionExecutionResult,
  type E2EContentExecuteMessage,
  type E2EPlatform,
  type E2EPlatformExecutionResult,
  type ExtensionE2ERuntimeEvent,
  isExtensionE2ERuntimeEvent,
} from "../shared/e2e.ts";

interface E2EContentExecuteResponse {
  status: "ok" | "failed";
  actions: E2EActionExecutionResult[];
  error?: string;
}

let activeRunId: string | null = null;

export async function handleE2ERuntimeEvent(event: unknown): Promise<boolean> {
  if (!isExtensionE2ERuntimeEvent(event)) {
    return false;
  }

  if (activeRunId !== null) {
    await postE2EResult(event, buildConcurrentFailureResults(event, activeRunId));
    return true;
  }

  activeRunId = event.run_id;
  const platformResults: E2EPlatformExecutionResult[] = [];
  try {
    for (const platform of event.platforms) {
      platformResults.push(await executePlatformE2ERun(event, platform));
    }
    await postE2EResult(event, platformResults);
  } finally {
    activeRunId = null;
  }

  return true;
}

function buildConcurrentFailureResults(
  event: ExtensionE2ERuntimeEvent,
  currentRunId: string,
): E2EPlatformExecutionResult[] {
  return event.platforms.map((platform) => ({
    platform,
    status: "failed",
    actions: [],
    error: `e2e run already in progress: ${currentRunId}`,
  }));
}

async function executePlatformE2ERun(
  event: ExtensionE2ERuntimeEvent,
  platform: E2EPlatform,
): Promise<E2EPlatformExecutionResult> {
  try {
    const tab = await openOrReusePlatformTab(platform);
    if (typeof tab.id !== "number") {
      throw new Error(`Missing tab id for ${platform}`);
    }

    await waitForTabComplete(tab.id, timeoutMsForEvent(event));
    const actions = actionsForE2EPlatform(event, platform);
    const message: E2EContentExecuteMessage = {
      action: "OBC_E2E_EXECUTE",
      runId: event.run_id,
      platform,
      actions,
      allowStateChanging: event.allow_state_changing === true,
    };
    const response = normalizeContentResponse(await chrome.tabs.sendMessage(tab.id, message));

    return {
      platform,
      status: response.status,
      url: tab.url,
      actions: response.actions,
      ...(response.error ? { error: response.error } : {}),
    };
  } catch (error) {
    return {
      platform,
      status: "failed",
      actions: [],
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function openOrReusePlatformTab(platform: E2EPlatform): Promise<chrome.tabs.Tab> {
  const targetUrl = E2E_PLATFORM_URLS[platform];
  const targetHost = new URL(targetUrl).host;
  const tabs = await chrome.tabs.query({});
  const existing = tabs.find((tab) => sameHost(tab.url, targetHost));

  if (existing?.id !== undefined) {
    const updated = await chrome.tabs.update(existing.id, {
      active: true,
      url: existing.url ?? targetUrl,
    });
    if (!updated) {
      throw new Error(`Missing updated tab for ${platform}`);
    }
    return updated;
  }

  return chrome.tabs.create({ active: true, url: targetUrl });
}

async function waitForTabComplete(tabId: number, timeoutMs: number): Promise<void> {
  const tab = await chrome.tabs.get(tabId);
  if (tab.status === "complete") return;

  await new Promise<void>((resolve, reject) => {
    const listener = (updatedTabId: number, changeInfo: { status?: string }): void => {
      if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    };
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error(`Timed out waiting for tab ${tabId} to finish loading`));
    }, timeoutMs);

    chrome.tabs.onUpdated.addListener(listener);
  });
}

function sameHost(url: string | undefined, targetHost: string): boolean {
  if (!url) return false;
  try {
    return new URL(url).host === targetHost;
  } catch {
    return false;
  }
}

function normalizeContentResponse(value: unknown): E2EContentExecuteResponse {
  if (typeof value !== "object" || value === null) {
    return {
      status: "failed",
      actions: [],
      error: "Invalid OBC_E2E_EXECUTE response",
    };
  }

  const response = value as Partial<E2EContentExecuteResponse>;
  return {
    status: response.status === "ok" ? "ok" : "failed",
    actions: Array.isArray(response.actions) ? response.actions : [],
    ...(typeof response.error === "string" && response.error
      ? { error: response.error }
      : {}),
  };
}

function timeoutMsForEvent(event: ExtensionE2ERuntimeEvent): number {
  return Math.max(1, event.timeout_seconds ?? 45) * 1000;
}

async function postE2EResult(
  event: ExtensionE2ERuntimeEvent,
  platforms: E2EPlatformExecutionResult[],
): Promise<void> {
  await fetch(await apiUrl("/extension/e2e/result"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run_id: event.run_id,
      token: event.token,
      platforms,
    }),
  });
}
