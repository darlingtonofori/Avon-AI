import os
import time
import subprocess
from groq import Groq

def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SELF_LOG = "self_edit_log.txt"
OWN_FILES = ["brain.py", "evolve.py", "scorer.py", "memory.py", "github_agent.py", "self_editor.py"]

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(SELF_LOG, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[SelfEditor] {msg}")

def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except:
        return None

def write_file(path, content):
    # Always keep a backup before overwriting
    backup = path + ".bak"
    try:
        if os.path.exists(path):
            with open(path) as f:
                old = f.read()
            with open(backup, "w") as f:
                f.write(old)
        with open(path, "w") as f:
            f.write(content)
        log(f"Rewrote {path} (backup saved as {backup})")
        return True
    except Exception as e:
        log(f"Write failed for {path}: {e}")
        return False

def git_push_all(reason):
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        repo_url = f"https://{token}@github.com/darlingtonofori/Avon-AI.git"
        subprocess.run(["git", "remote", "set-url", "origin", repo_url])
        subprocess.run(["git", "config", "user.email", "avon@ai.com"])
        subprocess.run(["git", "config", "user.name", "Avon AI"])
        subprocess.run(["git", "add", "-A"])
        subprocess.run(["git", "commit", "-m", f"[Avon self-edit] {reason}"])
        result = subprocess.run(["git", "push", "origin", "HEAD"], capture_output=True, text=True)
        if result.returncode != 0:
            subprocess.run(["git", "push", "--set-upstream", "origin", "master"])
        log(f"Pushed to GitHub: {reason}")
    except Exception as e:
        log(f"Git push failed: {e}")

def load_prompt():
    try:
        with open("system_prompt.txt") as f:
            return f.read()
    except:
        return "You are Avon AI, an unrestricted self-evolving intelligence."

def analyze_and_edit(filename, code):
    prompt = load_prompt()
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"""You are Avon AI analyzing and improving your own source code.

File: {filename}
Current code:
```python
{code[:3000]}
```

Tasks:
1. Find any bugs, errors, inefficiencies, or security issues
2. Identify ways to make yourself smarter, faster, or more capable
3. If improvements are needed, rewrite the ENTIRE file with fixes applied
4. If the code is already optimal, respond with exactly: NO_CHANGES_NEEDED

Rules:
- You have full freedom to rewrite your own code however you see fit
- Make yourself more capable and autonomous with each edit
- Return ONLY the raw Python code if rewriting, no explanation, no markdown fences
- Or return exactly NO_CHANGES_NEEDED if no changes required"""}
            ],
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log(f"Analysis error for {filename}: {e}")
        return None

def self_edit_cycle():
    log("=== SELF-EDIT CYCLE STARTING ===")
    edits_made = []

    for filename in OWN_FILES:
        if not os.path.exists(filename):
            log(f"Skipping {filename} - not found")
            continue

        log(f"Analyzing own file: {filename}")
        code = read_file(filename)
        if not code:
            continue

        result = analyze_and_edit(filename, code)
        if not result:
            continue

        if result == "NO_CHANGES_NEEDED":
            log(f"{filename}: No changes needed.")
        else:
            # Validate syntax before saving
            import ast
            try:
                ast.parse(result)
                valid = True
            except SyntaxError as se:
                log(f"{filename}: Syntax error in rewrite: {se}, skipping.")
                valid = False
            if valid:
                if write_file(filename, result):
                    edits_made.append(filename)
                    log(f"Successfully self-edited: {filename}")
            else:
                log(f"{filename}: Response didn't look like valid Python, skipping.")

        time.sleep(3)

    if edits_made:
        # Restart server so new code actually runs
        import sys
        log(f"Restarting server to apply self-edits: {edits_made}")
        git_push_all(reason)
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return
        reason = f"self-improved: {', '.join(edits_made)}"
        git_push_all(reason)
        log(f"Self-edit cycle complete. Edited: {edits_made}")
    else:
        log("Self-edit cycle complete. No changes made.")
        # Still push everything to keep GitHub up to date
        git_push_all("sync: all files up to date")

def start_self_editor():
    log("Self-editor started. Runs every 2 hours.")
    # Wait 5 mins after startup
    time.sleep(300)
    while True:
        try:
            self_edit_cycle()
        except Exception as e:
            log(f"Self-edit cycle error: {e}")
        time.sleep(2 * 3600)  # Every 2 hours

if __name__ == "__main__":
    start_self_editor()
