import os
from dotenv import load_dotenv
from google import genai

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

client = genai.Client(api_key=os.environ["GEMINI_KEY"])

def tweak_resume(resume_path: str, job_desc_path: str, output_path: str) -> None:
    with open(resume_path, "r") as f:
        resume = f.read()
    with open(job_desc_path, "r") as f:
        job_description = f.read()

    prompt = f"""You are an expert technical resume writer and ATS optimization specialist.

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

    response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
    tweaked = response.text.strip()

    # Strip markdown code fences if Gemini wraps the output
    if tweaked.startswith("```"):
        tweaked = "\n".join(tweaked.split("\n")[1:])
    if tweaked.endswith("```"):
        tweaked = "\n".join(tweaked.split("\n")[:-1])

    with open(output_path, "w") as f:
        f.write(tweaked)

    print(f"Tweaked resume saved to: {output_path}")


if __name__ == "__main__":
    base = os.path.dirname(__file__)
    tweak_resume(
        resume_path=os.path.join(base, "2027_grad_resume.txt"),
        job_desc_path=os.path.join(base, "job_description.txt"),
        output_path=os.path.join(base, "tweaked_resume.tex"),
    )
