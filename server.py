import os
import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from engine import generate_website

app = FastAPI()

os.makedirs("output_site", exist_ok=True)
app.mount("/site", StaticFiles(directory="output_site"), name="site")

jobs = {}

class PromptRequest(BaseModel):
    prompt: str

def run_agent_job(job_id: str, prompt: str):
    try:
        job_dir = f"output_site/{job_id}"
        os.makedirs(job_dir, exist_ok=True)
        output_path = f"{job_dir}/index.html"
        
        generate_website(prompt, output_path)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["url"] = f"/site/{job_id}/index.html"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Assignment Web Builder</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white h-screen flex flex-col items-center justify-center p-6 font-sans">
    <div class="max-w-2xl w-full bg-gray-900 border border-gray-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
        <div class="relative z-10">
            <h1 class="text-4xl font-extrabold mb-3 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-500 tracking-tight">Assignment Web Builder</h1>
            <p class="text-gray-400 mb-8 text-lg">Enter your architecture prompt. The engine will queue the job and build it autonomously.</p>
            
            <textarea id="promptInput" rows="5" class="w-full bg-gray-950 border border-gray-700 rounded-xl p-5 text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none mb-6" placeholder="Build a dark mode portfolio..."></textarea>
            
            <button id="generateBtn" onclick="submitJob()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-4 px-6 rounded-xl transition-all">
                Queue Build Sequence
            </button>
            
            <div id="statusBox" class="mt-8 hidden flex flex-col items-center">
                <svg class="animate-spin h-10 w-10 text-indigo-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                <p id="statusText" class="text-indigo-400 font-mono animate-pulse text-lg">Job Queued. Orchestrating agents...</p>
            </div>
        </div>
    </div>

    <script>
        async function submitJob() {
            const prompt = document.getElementById('promptInput').value;
            if(!prompt.trim()) return alert("Please enter a prompt.");

            document.getElementById('generateBtn').classList.add('hidden');
            document.getElementById('statusBox').classList.remove('hidden');

            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt })
            });
            const data = await response.json();
            const jobId = data.job_id;

            const pollInterval = setInterval(async () => {
                const res = await fetch(`/status/${jobId}`);
                const statusData = await res.json();

                if (statusData.status === 'completed') {
                    clearInterval(pollInterval);
                    document.getElementById('statusText').innerText = "Build Complete! Redirecting...";
                    setTimeout(() => window.location.href = statusData.url, 1000);
                } else if (statusData.status === 'failed') {
                    clearInterval(pollInterval);
                    alert("Job Failed: " + statusData.error);
                    window.location.reload();
                }
            }, 3000);
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_UI

@app.post("/generate")
async def generate(req: PromptRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running"}
    background_tasks.add_task(run_agent_job, job_id, req.prompt)
    return {"job_id": job_id, "message": "Job queued successfully."}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})
