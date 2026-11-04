const $ = (id) => document.getElementById(id);
let preview = null,
  activeJob = null,
  poll = null;
const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
async function api(url, data) {
  const response = await fetch(url, {
    method: data ? "POST" : "GET",
    headers: data
      ? { "Content-Type": "application/json", "X-CSRFToken": csrf }
      : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw Error("The app could not complete this request. Please try again.");
  }
  if (!response.ok) throw Error(result.error || "Something went wrong.");
  return result;
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function announce(message) {
  $("announcement").textContent = message;
}
function busy(value) {
  $("analyze-button").disabled = value;
  $("demo-button").disabled = value;
  $("analyze-button").querySelector("span").textContent = value
    ? "Finding your video…"
    : "Find my video";
}
function showPreview(video, demo = false) {
  preview = video;
  $("empty-state").hidden = true;
  $("video-result").hidden = false;
  $("preview-state").textContent = demo ? "DESIGN PREVIEW" : "VIDEO FOUND";
  $("video-title").textContent = video.title;
  $("video-author").textContent = video.author;
  const total = Math.round(video.duration || 0);
  $("duration").textContent =
    Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
  const image = $("thumbnail-image");
  image.hidden = !video.thumbnail;
  if (video.thumbnail) image.src = video.thumbnail;
  document.querySelector(".thumbnail-demo").hidden = Boolean(video.thumbnail);
  $("quality").replaceChildren(
    ...video.formats.map((f) => {
      const option = document.createElement("option");
      option.value = f.id;
      option.textContent =
        f.label + (f.size ? " · " + (f.size / 1048576).toFixed(1) + " MB" : "");
      return option;
    }),
  );
  $("prepare-button").hidden = false;
  $("prepare-button").disabled = demo;
  $("save-file").hidden = true;
  $("progress-wrap").hidden = true;
  $("download-note").textContent = demo
    ? "Design preview only. Paste a real link to prepare a download."
    : "Your file is prepared on the server, then saved through your browser.";
  announce(demo ? "Design preview loaded." : `Video found: ${video.title}`);
}
$("preview-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (activeJob) {
    error("Finish the current download before loading another video.");
    return;
  }
  error("");
  busy(true);
  try {
    showPreview(await api("/api/preview/", { url: $("video-url").value }));
  } catch (e) {
    error(e.message);
  } finally {
    busy(false);
  }
});
$("paste-button").addEventListener("click", async () => {
  try {
    $("video-url").value = await navigator.clipboard.readText();
    $("video-url").focus();
  } catch {
    error("Paste your copied link directly into the video link field.");
    $("video-url").focus();
  }
});
$("demo-button").addEventListener("click", () => {
  if (activeJob) return;
  error("");
  showPreview(
    {
      title: "The art of making room — a FrameDrop preview",
      author: "FrameDrop Studio · Sample interface",
      duration: 224,
      formats: [{ id: "demo", label: "720p · MP4" }],
    },
    true,
  );
});
$("prepare-button").addEventListener("click", async () => {
  error("");
  $("prepare-button").disabled = true;
  try {
    const job = await api("/api/start/", { format: $("quality").value });
    activeJob = job.id;
    $("progress-wrap").hidden = false;
    $("quality").disabled = true;
    $("preview-state").textContent = "PREPARING";
    announce("Preparing your download.");
    await history();
    poll = setInterval(update, 1200);
    await update();
  } catch (e) {
    error(e.message);
    $("prepare-button").disabled = false;
  }
});
async function update() {
  if (!activeJob) return;
  try {
    const job = await api("/api/jobs/" + activeJob + "/");
    if (job.status === "error") throw Error(job.error);
    const progress = job.progress;
    $("progress-wrap").classList.toggle("indeterminate", progress === null);
    $("progress-bar").style.width = (progress || 0) + "%";
    $("percent").textContent = progress === null ? "" : progress + "%";
    $("progress-label").textContent =
      job.status === "ready"
        ? "Ready for your device."
        : "Preparing your file…";
    if (job.status === "ready") {
      clearInterval(poll);
      $("save-file").href = "/files/" + activeJob + "/";
      $("save-file").hidden = false;
      $("prepare-button").hidden = true;
      $("preview-state").textContent = "READY TO SAVE";
      $("quality").disabled = false;
      activeJob = null;
      announce("Your file is ready. Use Save video to download it.");
      await history();
    }
  } catch (e) {
    clearInterval(poll);
    activeJob = null;
    $("prepare-button").disabled = false;
    $("quality").disabled = false;
    $("preview-state").textContent = "TRY AGAIN";
    $("progress-wrap").hidden = true;
    error(e.message);
    history();
  }
}
async function history() {
  try {
    const result = await api("/api/history/");
    $("history-count").textContent = String(result.items.length).padStart(
      2,
      "0",
    );
    $("clear-button").disabled = !result.items.length;
    if (!result.items.length) {
      $("history-list").innerHTML =
        '<div class="history-empty"><svg><use href="#clock"/></svg><p>A clean slate. Your download requests will show up here.</p></div>';
      return;
    }
    $("history-list").replaceChildren(
      ...result.items.map((item) => {
        const row = document.createElement("div");
        row.className = "history-row";
        const icon = document.createElement("span");
        icon.className = "history-icon";
        icon.innerHTML = '<svg><use href="#play"/></svg>';
        const info = document.createElement("div"),
          title = document.createElement("strong"),
          meta = document.createElement("small"),
          status = document.createElement("span");
        title.textContent = item.title;
        meta.textContent =
          item.quality + " · " + new Date(item.created * 1000).toLocaleString();
        status.textContent = item.status;
        status.className = "history-status";
        info.append(title, meta);
        row.append(icon, info, status);
        if (item.status === "ready") {
          const link = document.createElement("a");
          link.href = "/files/" + item.id + "/";
          link.textContent = "Save ↗";
          row.append(link);
        }
        return row;
      }),
    );
  } catch (e) {
    error(e.message);
  }
}
$("clear-button").addEventListener("click", async () => {
  try {
    await api("/clear/", {});
    await history();
    announce("Download history cleared.");
  } catch (e) {
    error(e.message);
  }
});
history();
