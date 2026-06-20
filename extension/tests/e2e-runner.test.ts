import assert from "node:assert/strict";
import test from "node:test";

import { handleE2ERuntimeEvent } from "../src/background/e2e-runner.ts";
import { installChromeMock } from "./helpers/chrome-mock.ts";

test("e2e background runner opens a platform tab, dispatches content execution, and posts backend result", async () => {
  const state = installChromeMock();
  state.sendMessageImpl = async () => ({
    status: "ok",
    actions: [{ action: "click", status: "ok", detail: "clicked" }],
  });

  try {
    const handled = await handleE2ERuntimeEvent({
      type: "extension_e2e_run",
      run_id: "e2e-test",
      token: "secret",
      platforms: ["twitter"],
      actions: { twitter: ["click"] },
      allow_state_changing: false,
      timeout_seconds: 5,
    });

    assert.equal(handled, true);
    assert.deepEqual(state.createdTabs, [{ active: true, url: "https://x.com/home" }]);
    assert.deepEqual(state.sentMessages, [
      {
        tabId: 42,
        message: {
          action: "OBC_E2E_EXECUTE",
          runId: "e2e-test",
          platform: "twitter",
          actions: ["click"],
          allowStateChanging: false,
        },
      },
    ]);
    assert.equal(state.fetchCalls.length, 1);
    assert.equal(state.fetchCalls[0].method, "POST");
    assert.match(state.fetchCalls[0].url, /\/api\/extension\/e2e\/result$/);
    assert.deepEqual(state.fetchCalls[0].body, {
      run_id: "e2e-test",
      token: "secret",
      platforms: [
        {
          platform: "twitter",
          status: "ok",
          url: "https://x.com/home",
          actions: [{ action: "click", status: "ok", detail: "clicked" }],
        },
      ],
    });
  } finally {
    state.restore();
  }
});

test("e2e background runner reuses an existing platform tab by host", async () => {
  const state = installChromeMock();
  state.queryResult = [{ id: 7, status: "complete", url: "https://www.douyin.com/user/self" }];
  state.tabById.set(7, { id: 7, status: "complete", url: "https://www.douyin.com/user/self" });

  try {
    await handleE2ERuntimeEvent({
      type: "extension_e2e_run",
      run_id: "e2e-reuse",
      token: "secret",
      platforms: ["douyin"],
      actions: { douyin: ["snapshot"] },
      allow_state_changing: false,
      timeout_seconds: 5,
    });

    assert.deepEqual(state.createdTabs, []);
    assert.deepEqual(state.updatedTabs, [
      { tabId: 7, active: true, url: "https://www.douyin.com/user/self" },
    ]);
    assert.equal(state.sentMessages[0].tabId, 7);
  } finally {
    state.restore();
  }
});

test("e2e background runner posts a failed platform result when content messaging throws", async () => {
  const state = installChromeMock();
  state.sendMessageImpl = async () => {
    throw new Error("content script unavailable");
  };

  try {
    const handled = await handleE2ERuntimeEvent({
      type: "extension_e2e_run",
      run_id: "e2e-fail",
      token: "secret",
      platforms: ["xiaohongshu"],
      actions: { xiaohongshu: ["snapshot"] },
      allow_state_changing: false,
      timeout_seconds: 5,
    });

    assert.equal(handled, true);
    assert.equal(state.fetchCalls.length, 1);
    assert.deepEqual(state.fetchCalls[0].body, {
      run_id: "e2e-fail",
      token: "secret",
      platforms: [
        {
          platform: "xiaohongshu",
          status: "failed",
          actions: [],
          error: "content script unavailable",
        },
      ],
    });
  } finally {
    state.restore();
  }
});

test("e2e background runner ignores non e2e runtime events", async () => {
  const state = installChromeMock();

  try {
    const handled = await handleE2ERuntimeEvent({ type: "dy_task_available" });

    assert.equal(handled, false);
    assert.deepEqual(state.createdTabs, []);
    assert.deepEqual(state.sentMessages, []);
    assert.deepEqual(state.fetchCalls, []);
  } finally {
    state.restore();
  }
});

test("e2e background runner rejects concurrent runs with a failed backend result", async () => {
  const state = installChromeMock();
  let releaseFirstRun!: () => void;
  state.sendMessageImpl = async () => {
    await new Promise<void>((resolve) => {
      releaseFirstRun = resolve;
    });
    return { status: "ok", actions: [{ action: "snapshot", status: "ok" }] };
  };

  try {
    const firstRun = handleE2ERuntimeEvent({
      type: "extension_e2e_run",
      run_id: "e2e-first",
      token: "first-token",
      platforms: ["twitter"],
      actions: { twitter: ["snapshot"] },
      allow_state_changing: false,
      timeout_seconds: 5,
    });

    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    const secondHandled = await handleE2ERuntimeEvent({
      type: "extension_e2e_run",
      run_id: "e2e-second",
      token: "second-token",
      platforms: ["douyin"],
      actions: { douyin: ["snapshot"] },
      allow_state_changing: false,
      timeout_seconds: 5,
    });

    assert.equal(secondHandled, true);
    assert.equal(state.fetchCalls.length, 1);
    assert.deepEqual(state.fetchCalls[0].body, {
      run_id: "e2e-second",
      token: "second-token",
      platforms: [
        {
          platform: "douyin",
          status: "failed",
          actions: [],
          error: "e2e run already in progress: e2e-first",
        },
      ],
    });

    releaseFirstRun();
    await firstRun;
    assert.equal(state.fetchCalls.length, 2);
  } finally {
    state.restore();
  }
});
