import os
import html
import uuid
import logging
from dotenv import load_dotenv
from google import genai
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

client = genai.Client(api_key=os.environ["GEMINI_KEY"])

BASE_DIR = os.path.dirname(__file__)
RESUME_PATH = os.path.join(BASE_DIR, "2027_grad_resume.txt")

with open(RESUME_PATH, "r") as f:
    BASE_RESUME = f.read()

app = FastAPI(title="Resume Tweaker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    job_description: str

# In-memory store: token -> latex (single-use)
latex_cache: dict[str, str] = {}

# Unicode invisible/control characters that break LaTeX argument scanning
_STRIP_CHARS = str.maketrans('', '', ''.join(chr(c) for c in [
    0x200B, 0x200C, 0x200D, 0x200E, 0x200F,  # Zero-width chars
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # Bidi embedding marks
    0x2060, 0x2061, 0x2062, 0x2063, 0x2064,  # Word joiners
    0xFEFF, 0x00AD,                            # BOM, soft hyphen
]))


def clean_latex(text: str) -> str:
    """Strip invisible Unicode characters that cause TeX argument-scanning errors."""
    return text.translate(_STRIP_CHARS)


def braces_balanced(text: str) -> bool:
    """Return True if every unescaped { has a matching }, ignoring % comments."""
    depth = 0
    for line in text.split('\n'):
        # Strip everything after an unescaped %
        j = 0
        while j < len(line):
            if line[j] == '%':
                bs = 0
                k = j - 1
                while k >= 0 and line[k] == '\\':
                    bs += 1
                    k -= 1
                if bs % 2 == 0:
                    line = line[:j]
                    break
            j += 1
        # Count unescaped braces
        for j, ch in enumerate(line):
            if ch in '{}':
                bs = 0
                k = j - 1
                while k >= 0 and line[k] == '\\':
                    bs += 1
                    k -= 1
                if bs % 2 == 0:
                    depth += 1 if ch == '{' else -1
    return depth == 0


def build_prompt(resume: str, job_description: str) -> str:
    return f"""You are an expert technical Hiring Manager and ATS optimization specialist.

Your task is to tailor the following LaTeX resume to better match the job description below.

Rules:
- Preserve ALL LaTeX formatting, commands, and structure exactly — do not change any LaTeX syntax
- Only modify the text content (bullet points, skill keywords, project descriptions, section text)
- Reframe existing experience using keywords and terminology from the job description
- Do NOT fabricate new experiences, projects, companies, dates, or skills the candidate doesn't have
- Prioritize keywords that ATS systems will scan for from the job description
- Keep bullet points concise, action-verb-led, impact-focused, include numbers
- Return ONLY the complete modified LaTeX source — no explanation, no markdown fences
- Every \\resumeProjectHeading call MUST have exactly two brace-enclosed arguments: the title and an empty second argument {{}}, e.g. \\resumeProjectHeading{{Title $|$ \\emph{{Stack}}}}{{}}
- Always escape bare ampersands in text as \\& (e.g. "Data \\& Analytics", never "Data & Analytics")
- CRITICAL: Every opening brace {{ must have a matching closing brace }}. Never leave a brace unmatched.
- Do NOT insert any non-ASCII or Unicode characters — use only standard ASCII and LaTeX commands
- Do NOT add LaTeX comments (lines starting with %)
- Ensure the length of the resume remains the same number of lines of text

Job Description:
{job_description}

Original LaTeX Resume:
{resume}"""


def call_gemini(job_description: str) -> str:
    prompt = build_prompt(BASE_RESUME, job_description)
    last_result = ""
    for attempt in range(3):
        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=prompt
        )
        tweaked = response.text.strip()
        if tweaked.startswith("```"):
            tweaked = "\n".join(tweaked.split("\n")[1:])
        if tweaked.endswith("```"):
            tweaked = "\n".join(tweaked.split("\n")[:-1])
        tweaked = clean_latex(tweaked)
        if braces_balanced(tweaked):
            return tweaked
        logging.warning("Attempt %d: unbalanced braces in Gemini output, retrying.", attempt + 1)
        last_result = tweaked
    logging.error("All attempts produced unbalanced LaTeX. Returning last result.")
    return last_result


def overleaf_autosubmit_page(latex: str) -> str:
    """Return an HTML page that auto-POSTs the LaTeX to Overleaf and opens it."""
    escaped = html.escape(latex, quote=True)
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Opening in Overleaf...</title>
</head>
<body>
  <p>Sending tweaked resume to Overleaf...</p>
  <form id="ol" action="https://www.overleaf.com/docs" method="POST" target="_blank">
    <input type="hidden" name="snip"      value="{escaped}" />
    <input type="hidden" name="snip_name" value="tweaked_resume.tex" />
  </form>
  <script>document.getElementById("ol").submit();</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!DOCTYPE html>
<html>
<head><title>Resume Tweaker</title></head>
<body>
  <h2>Resume Tweaker</h2>
  <form action="/tweak" method="post" enctype="multipart/form-data">
    <label>Upload job description (.txt):</label><br><br>
    <input type="file" name="job_description" accept=".txt" required /><br><br>
    <button type="submit">Tweak & Open in Overleaf</button>
  </form>
</body>
</html>"""


@app.post("/tweak", response_class=HTMLResponse)
async def tweak(job_description: UploadFile = File(...)):
    contents = await job_description.read()
    job_text = contents.decode("utf-8")

    tweaked_latex = call_gemini(job_text)

    return HTMLResponse(content=overleaf_autosubmit_page(tweaked_latex))


@app.post("/tweak-text")
async def tweak_text(body: TextRequest):
    tweaked_latex = call_gemini(body.job_description)
    token = str(uuid.uuid4())
    latex_cache[token] = tweaked_latex
    return JSONResponse({"redirect_url": f"http://localhost:8000/redirect/{token}"})


@app.get("/redirect/{token}", response_class=HTMLResponse)
async def redirect_to_overleaf(token: str):
    latex = latex_cache.pop(token, None)
    if not latex:
        return HTMLResponse("Token expired or not found.", status_code=404)
    return HTMLResponse(content=overleaf_autosubmit_page(latex))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
