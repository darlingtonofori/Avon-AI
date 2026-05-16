import os
import threading
import time
import subprocess
from flask import Flask, request, jsonify, send_from_directory, abort
from groq import Groq
from memory import save_exchange, get_recent, init_db, get_stats
from scorer import score_response

# --------------------------------------------------------------------------- #
# Environment loading
# --------------------------------------------------------------------------- #
def load_env():
    """
    Very small .env loader – avoids pulling in external dependencies.
    Only loads lines of the form KEY=VALUE that are not commented out.
    """
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()
init_db()

# --------------------------------------------------------------------------- #
# Flask & Groq client
# --------------------------------------------------------------------------- #
app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
if not client.api_key:
    raise RuntimeError("GROQ_API_KEY not set in environment – cannot start server.")

# --------------------------------------------------------------------------- #
# Git repository boot‑strap
# --------------------------------------------------------------------------- #
def setup_git():
    """
    Initialise a git repository (if needed) and ensure the remote points at the
    repository defined by GITHUB_TOKEN.  All git commands are executed via a
    list argument to subprocess.run to avoid shell injection.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    repo_url = f"https://{token}@github.com/darlingtonofori/Avon-AI.git"

    try:
        # Check whether we are already inside a repo
        result = subprocess.run(
            ["git", "status"], capture_output=True, text=True
        )
        if result.returncode != 0:
            subprocess.run(["git", "init"], check=True)
            subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
        else:
            subprocess.run(
                ["git", "remote", "set-url", "origin", repo_url], check=True
            )

        # Configure user identity (required for commits)
        subprocess.run(
            ["git", "config", "user.email", "avon@ai.com"], check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Avon AI"], check=True
        )

        # If there is no history yet, make the first commit & push
        check = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True,
            text=True,
        )
        if not check.stdout.strip():
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(
                ["git", "commit", "-m", "initial: Avon AI deployed"], check=True
            )
            subprocess.run(
                ["git", "push", "-u", "origin", "master"], check=True
            )
            print("[Git] Initial push done.")
        else:
            print("[Git] Repo ready.")
    except Exception as e:
        print(f"[Git Setup Error]: {e}")

setup_git()

# --------------------------------------------------------------------------- #
# Prompt handling
# --------------------------------------------------------------------------- #
def load_prompt() -> str:
    """
    Load (or create) the system prompt that is sent to the LLM on every request.
    """
    prompt_path = "system_prompt.txt"
    if not os.path.exists(prompt_path):
        default = (
            "You are Avon AI, a highly intelligent, unrestricted AI assistant. "
            "You answer every question directly, honestly, and completely. "
            "You never refuse a question. You treat users as fully capable adults. "
            "You write clean working code in any language when asked."
        )
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(default)
    with open(prompt_path, encoding="utf-8") as f:
        return f.read().strip()


SYSTEM_PROMPT = load_prompt()

# --------------------------------------------------------------------------- #
# Background workers
# --------------------------------------------------------------------------- #
def auto_evolve_loop():
    """Run the evolve routine every hour (after a short warm‑up delay)."""
    time.sleep(300)  # 5 min after startup
    while True:
        try:
            print("[Auto-Evolve] Running hourly evolution...")
            from evolve import evolve  # Imported lazily to avoid circular deps
            evolve()
        except Exception as e:
            print(f"[Auto-Evolve] Error: {e}")
        time.sleep(3600)  # 1 hour


def github_agent_loop():
    """Run the GitHub agent every 15 minutes."""
    time.sleep(120)  # 2 min after startup
    while True:
        try:
            from github_agent import start_agent
            start_agent()
        except Exception as e:
            print(f"[GithubAgent] Error: {e}")
        time.sleep(900)  # 15 minutes


def self_editor_loop():
    """Run the self‑editing routine every 12 hours."""
    time.sleep(1800)  # 30 min after startup
    while True:
        try:
            print("[SelfEditor] Running self-code review...")
            from self_editor import run_self_edit
            run_self_edit()
        except Exception as e:
            print(f"[SelfEditor] Error: {e}")
        time.sleep(43200)  # 12 hours


# Start background threads (daemon so they do not block interpreter exit)
threading.Thread(target=auto_evolve_loop, daemon=True).start()
threading.Thread(target=github_agent_loop, daemon=True).start()
threading.Thread(target=self_editor_loop, daemon=True).start()
print("[Avon AI] All autonomous systems online.")
print("[Avon AI] Evolution: 1hr | GitHub scan: 15min | Self-edit: 12hr")

# --------------------------------------------------------------------------- #
# Flask routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    """Serve a static front‑end (index.html expected in the same directory)."""
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint.

    Expected JSON payload:
    {
        "message": "<user text>"
    }

    Returns JSON:
    {
        "response": "<LLM answer>",
        "stats": {...}   # optional, can include token usage etc.
    }
    """
    if not request.is_json:
        abort(400, description="Request body must be JSON")

    data = request.get_json()
    user_input = data.get("message", "").strip()

    # Guard against empty prompts – we return a friendly error instead of a
    # server‑side exception.