const statsEls = {
  total: document.querySelector("#stat-total"),
  queued: document.querySelector("#stat-queued"),
  processing: document.querySelector("#stat-processing"),
  done: document.querySelector("#stat-done"),
  failed: document.querySelector("#stat-failed"),
};

const jobsTableBody = document.querySelector("#jobs-table-body");
const form = document.querySelector("#create-job-form");
const payloadInput = document.querySelector("#payload-input");
const maxRetriesInput = document.querySelector("#max-retries-input");
const formMessage = document.querySelector("#form-message");
const refreshButton = document.querySelector("#refresh-button");
const lastUpdated = document.querySelector("#last-updated");

async function loadStats() {
  const response = await fetch("/api/jobs/stats");
  const stats = await response.json();

  statsEls.total.textContent = stats.total ?? 0;
  statsEls.queued.textContent = stats.queued ?? 0;
  statsEls.processing.textContent = stats.processing ?? 0;
  statsEls.done.textContent = stats.done ?? 0;
  statsEls.failed.textContent = stats.failed ?? 0;
}

async function loadJobs() {
  const response = await fetch("/api/jobs?limit=20");
  const jobs = await response.json();

  if (jobs.length === 0) {
    jobsTableBody.innerHTML = `<tr><td colspan="6">No jobs yet.</td></tr>`;
    return;
  }

  jobsTableBody.innerHTML = jobs.map((job) => {
    const canRequeue = job.status === "failed";

    return `
      <tr>
        <td class="job-id">${job.id.slice(0, 8)}...</td>
        <td>${escapeHtml(job.payload)}</td>
        <td><span class="status ${job.status}">${job.status}</span></td>
        <td>${job.attempts}/${job.max_retries}</td>
        <td>${formatDate(job.updated_at)}</td>
        <td>
          ${
            canRequeue
              ? `<button class="secondary" data-requeue-id="${job.id}">Requeue</button>`
              : ""
          }
        </td>
      </tr>
    `;
  }).join("");
}

async function refreshDashboard() {
  await Promise.all([loadStats(), loadJobs()]);
  lastUpdated.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = payloadInput.value.trim();
  const maxRetries = Number(maxRetriesInput.value);

  if (!payload) {
    formMessage.textContent = "Payload is required.";
    return;
  }

  await fetch("/api/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      payload,
      max_retries: maxRetries,
    }),
  });

  payloadInput.value = "";
  formMessage.textContent = "Job created.";
  await refreshDashboard();
});

refreshButton.addEventListener("click", refreshDashboard);

jobsTableBody.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-requeue-id]");
  if (!button) return;

  const jobId = button.dataset.requeueId;

  await fetch(`/api/jobs/${jobId}/requeue`, {
    method: "POST",
  });

  await refreshDashboard();
});

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

refreshDashboard();
setInterval(refreshDashboard, 2000);