const API_URL = "http://localhost:8000/tweak-text";

const submitBtn  = document.getElementById("submitBtn");
const btnText    = submitBtn.querySelector(".btn-text");
const btnSpinner = submitBtn.querySelector(".btn-spinner");
const status     = document.getElementById("status");
const pageTitle  = document.getElementById("pageTitle");
const pageUrl    = document.getElementById("pageUrl");

// ── Show current tab info ──
chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  pageTitle.textContent = tab.title || "Untitled page";
  pageUrl.textContent   = tab.url   || "";
});

// ── Submit ──
submitBtn.addEventListener("click", async () => {
  setLoading(true);
  hideStatus();

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    const [{ result: pageText }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.body.innerText,
    });

    if (!pageText || !pageText.trim()) {
      throw new Error("Could not read any text from this page.");
    }

    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: pageText }),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Server error ${res.status}: ${err}`);
    }

    const { redirect_url } = await res.json();
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
