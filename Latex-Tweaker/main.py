import os
import html
from dotenv import load_dotenv
from google import genai
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import uvicorn

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

client = genai.Client(api_key=os.environ["GEMINI_KEY"])

BASE_DIR = os.path.dirname(__file__)
RESUME_PATH = os.path.join(BASE_DIR, "2027_grad_resume.txt")

with open(RESUME_PATH, "r") as f:
    BASE_RESUME = f.read()

app = FastAPI(title="Resume Tweaker")


def build_prompt(resume: str, job_description: str) -> str:
    return f"""You are an expert technical resume writer and ATS optimization specialist.

Your task is to tailor the following LaTeX resume to better match the job description below.

Rules:
- Preserve ALL LaTeX formatting, commands, and structure exactly — do not change any LaTeX syntax
- Only modify the text content (bullet points, skill keywords, project descriptions, section text)
- Reframe existing experience using keywords and terminology from the job description
- Do NOT fabricate new experiences, companies, dates, or skills the candidate doesn't have
- Prioritize keywords that ATS systems will scan for from the job description
- Keep bullet points concise, action-verb-led, and impact-focused
- Return ONLY the complete modified LaTeX source — no explanation, no markdown fences
- Ensure the length of the resume remains the same number of lines of text

Job Description:
{job_description}

Original LaTeX Resume:
{resume}"""


def call_gemini(job_description: str) -> str:
    prompt = build_prompt(BASE_RESUME, job_description)
    response = client.models.generate_content(
        model="gemini-3-flash-preview", contents=prompt
    )
    tweaked = response.text.strip()
    if tweaked.startswith("```"):
        tweaked = "\n".join(tweaked.split("\n")[1:])
    if tweaked.endswith("```"):
        tweaked = "\n".join(tweaked.split("\n")[:-1])
    return tweaked


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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
