# File: backend/main.py
import os
import io
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import openai
import PyPDF2

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. /ask will fail without one.")
openai.api_key = OPENAI_API_KEY

app = FastAPI(title="StudyBuddy Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for hackathon; restrict before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    text: str
    mode: str = "explain"

@app.post("/ask")
async def ask(req: AskRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Server not configured with OPENAI_API_KEY")

    # system prompt to steer behavior
    system_prompt = "You are Study Buddy, a friendly and patient tutor. Provide clear explanations, examples, and generate flashcards when requested."
    mode = req.mode or "explain"
    mode_instruction = ""
    if mode == "tutor":
        mode_instruction = "Act as a tutor: ask the user probing conceptual questions and suggest small practice tasks."
    elif mode == "quiz":
        mode_instruction = "Generate a short quiz (3-5 Qs) and provide answers. Also return flashcards if relevant."
    else:
        mode_instruction = "Explain the content clearly and concisely with examples and next steps to practice."

    prompt = f"{mode_instruction}\n\nUser content:\n{req.text}"

    try:
        resp = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=900,
        )
        assistant_text = resp.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {e}")

    # basic flashcard extraction heuristic:
    flashcards = []
    if mode == "quiz":
        # attempt a simple parse: split assistant_text into lines and extract Q/A pairs
        lines = assistant_text.splitlines()
        q, a = None, None
        for ln in lines:
            ln = ln.strip()
            if ln.startswith("Q") or ln.startswith("1)") or ln.endswith("?"):
                q = ln
            elif ln.startswith("A:") or ln.startswith("Answer") or ln.startswith("Ans"):
                a = ln
            if q and a:
                flashcards.append({"q": q, "a": a})
                q, a = None, None

    return {"output": assistant_text, "flashcards": flashcards}

@app.post("/extract_pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs are supported.")
    try:
        data = await file.read()
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        text = []
        for p in reader.pages[:10]:  # limit pages for speed
            try:
                text.append(p.extract_text() or "")
            except:
                continue
        full = "\n".join(text).strip()
        excerpt = full[:4000]  # limit size
        return {"excerpt": excerpt, "excerpt_length": len(excerpt)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {e}")
