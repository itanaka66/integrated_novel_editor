/**
 * INE Anna App — dashboard over the ine-bridge Executa.
 *
 * anna.tools.invoke({ tool_id, method, args })
 * Publish writes bundle/anna-tool-ids.js; local `anna-app dev` uses the fallback id.
 */

const DEV_FALLBACK_TOOL_ID = "tool-dev-ine-bridge";
const TOOL_ID =
  (typeof window !== "undefined" &&
    window.__ANNA_TOOL_IDS__ &&
    window.__ANNA_TOOL_IDS__["ine-bridge"]) ||
  DEV_FALLBACK_TOOL_ID;
const STORAGE_KEY = "ine:last-project-id";
const COVER_STORAGE_KEY = "ine:cover";

const $ = (sel) => document.querySelector(sel);

const els = {
  conn: $("#conn"),
  status: $("#status"),
  refresh: $("#refresh"),
  ask: $("#ask"),
  projects: $("#projects"),
  health: $("#health"),
  ep: $("#m-ep"),
  ch: $("#m-ch"),
  iss: $("#m-iss"),
  episodes: $("#episodes"),
  cover: $("#cover-img"),
};

let anna = null;
let busy = false;

function setConn(on) {
  els.conn.classList.toggle("on", on);
  els.conn.classList.toggle("off", !on);
  els.conn.title = on ? "Connected to Anna" : "Standalone / disconnected";
}

function setStatus(text) {
  els.status.textContent = text;
}

function setBusy(on) {
  busy = on;
  els.refresh.disabled = on;
  els.projects.disabled = on || els.projects.options.length <= 1;
}

async function invoke(method, args = {}) {
  if (!anna) throw new Error("not connected to Anna");
  const res = await anna.tools.invoke({
    tool_id: TOOL_ID,
    method,
    args,
  });

  console.log("[INE DEBUG] raw SDK response:", res);

  const payload = res?.result ?? res;
  if (payload && payload.success === false) {
    throw new Error(payload.error || "INE tool failed");
  }
  return payload?.data ?? payload;
}

async function init() {
  els.refresh.addEventListener("click", loadProjects);
  els.ask.addEventListener("click", askCoach);
  els.projects.addEventListener("change", onProjectChange);

  try {
    const mod = await import("/static/anna-apps/_sdk/latest/index.js");
    anna = await mod.AnnaAppRuntime.connect();
    setConn(true);
    setStatus("Connected. Load works from your INE server.");
    try {
      await anna.window.set_title({ title: "INE" });
    } catch {
      /* optional */
    }
    try {
      await anna.window.maximize();
    } catch {
      try {
        await anna.window.resize({ w: 1920, h: 1080 });
      } catch {
        /* resize not supported */
      }
    }
  } catch (e) {
    setConn(false);
    setStatus("Standalone preview — open this app with `anna-app dev` to call INE.");
    return;
  }

  await loadProjects();
}

async function loadProjects() {
  if (busy || !anna) return;
  setBusy(true);
  setStatus("Loading works…");
  try {
    const response = await invoke("list_projects");

    const projects = Array.isArray(response)
      ? response
      : Array.isArray(response?.projects)
        ? response.projects
        : [];    
    console.log("[INE DEBUG] result:", projects);
    console.log("[INE DEBUG] type:", typeof projects);
    console.log("[INE DEBUG] isArray:", Array.isArray(projects));
    const list = Array.isArray(projects) ? projects : [];
    els.projects.innerHTML = "";
    if (!list.length) {
      els.projects.append(new Option("No works yet", ""));
      setStatus("INE is up, but there are no works.");
      return;
    }
    for (const p of list) {
      els.projects.append(new Option(`${p.name} (#${p.id})`, String(p.id)));
    }
    let saved = null;
    try {
      const got = await anna.storage.get({ key: STORAGE_KEY });
      saved = got?.value != null ? String(got.value) : null;
    } catch {
      /* empty */
    }
    if (saved && list.some((p) => String(p.id) === saved)) {
      els.projects.value = saved;
    }
    els.projects.disabled = false;
    setStatus(`${list.length} work(s).`);
    await loadTwin();
  } catch (e) {
    setStatus(e?.message || String(e));
  } finally {
    setBusy(false);
  }
}

async function onProjectChange() {
  const id = els.projects.value;
  if (anna && id) {
    try {
      await anna.storage.set({ key: STORAGE_KEY, value: id });
    } catch {
      /* non-fatal */
    }
  }
  await loadTwin();
}

async function loadTwin() {
  const id = els.projects.value;
  if (!id) return;
  setBusy(true);
  try {
    const twin = await invoke("get_story_twin", { project_id: Number(id) });
    const score = twin?.health?.score ?? "–";
    const label = twin?.health?.label || "";
    els.health.textContent = `Health ${score} ${label}`.trim();
    els.health.className = `health ${label}`;
    els.ep.textContent = twin?.metrics?.episodes ?? "–";
    els.ch.textContent = twin?.metrics?.characters ?? "–";
    els.iss.textContent = twin?.metrics?.continuity_open ?? "–";
    const episodes = await invoke("list_episodes", { project_id: Number(id), limit: 8 });
    renderEpisodes(Array.isArray(episodes) ? episodes : []);
    if (anna) {
      const name = twin?.project?.name || "INE";
      anna.window.set_title({ title: `${name} — INE` }).catch(() => {});
    }
    loadCover(Number(id));
  } catch (e) {
    setStatus(e?.message || String(e));
  } finally {
    setBusy(false);
  }
}

async function loadCover(pid) {
  const storageKey = `${COVER_STORAGE_KEY}:${pid}`;
  // Show cached cover immediately while fetching.
  try {
    const cached = localStorage.getItem(storageKey);
    if (cached && els.cover) {
      els.cover.src = cached;
      els.cover.hidden = false;
    }
  } catch { /* localStorage unavailable */ }

  try {
    const covers = await invoke("list_covers", { project_id: pid });
    if (!Array.isArray(covers) || !covers.length) return;
    // Use the most recently created cover.
    const latest = covers.reduce((a, b) =>
      (a.created_at || "") >= (b.created_at || "") ? a : b
    );
    const url = latest.url || latest.thumbnail_url || "";
    if (!url) return;
    if (els.cover) {
      els.cover.src = url;
      els.cover.hidden = false;
    }
    try {
      localStorage.setItem(storageKey, url);
    } catch { /* quota exceeded or unavailable */ }
  } catch { /* covers not available */ }
}

function renderEpisodes(items) {
  els.episodes.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "No episodes yet.";
    els.episodes.append(li);
    return;
  }
  for (const e of items) {
    const li = document.createElement("li");
    const title = document.createElement("span");
    title.textContent = `${e.number}. ${e.title || "(untitled)"}`;
    const meta = document.createElement("span");
    meta.className = "muted";
    meta.textContent = e.summary || "";
    li.append(title, meta);
    els.episodes.append(li);
  }
}

async function askCoach() {
  if (!anna) return;
  const id = els.projects.value;
  const name = els.projects.selectedOptions[0]?.textContent || "this work";
  try {
    await anna.chat.write_message({
      role: "user",
      content: id
        ? `Look at INE project ${id} (${name}). Summarize story-twin health and what I should write next.`
        : "INE has no work selected. Help me list projects and pick one.",
    });
  } catch (e) {
    setStatus(e?.message || String(e));
  }
}

document.addEventListener("DOMContentLoaded", init);

