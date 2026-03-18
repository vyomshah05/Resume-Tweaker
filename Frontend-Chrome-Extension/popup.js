const API_URL = "http://localhost:8000/tweak-text";

const textarea   = document.getElementById("jobDesc");
const submitBtn  = document.getElementById("submitBtn");
const btnText    = submitBtn.querySelector(".btn-text");
const btnSpinner = submitBtn.querySelector(".btn-spinner");
const charCount  = document.getElementById("charCount");
const status     = document.getElementById("status");

// ── Live character count + enable button ──
textarea.addEventListener("input", () => {
  const len = textarea.value.trim().length;
  charCount.textContent = textarea.value.length;
  submitBtn.disabled = len === 0;
});

// ── Submit ──
submitBtn.addEventListener("click", async () => {
  const jobDescription = textarea.value.trim();
  if (!jobDescription) return;

  setLoading(true);
  hideStatus();

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: jobDescription }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Server error ${res.status}: ${err}`);
    }

    const { redirect_url } = await res.json();

    // FastAPI serves the redirect page from localhost — no CSP issues
    chrome.tabs.create({ url: redirect_url });
    showStatus("success", "Opening in Overleaf...");
  } catch (err) {
    if (err.message.includes("Failed to fetch")) {
      showStatus("error", "Cannot reach backend. Make sure the FastAPI server is running on localhost:8000.");
    } else {
      showStatus("error", err.message);
    }
  } finally {
    setLoading(false);
  }
});

function setLoading(on) {
  submitBtn.disabled = on;
  submitBtn.classList.toggle("loading", on);
  btnText.hidden = on;
  btnSpinner.hidden = !on;
}

function showStatus(type, msg) {
  status.textContent = msg;
  status.className = `status ${type}`;
  status.hidden = false;
}

function hideStatus() {
  status.hidden = true;
}
