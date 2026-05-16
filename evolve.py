import os
import subprocess
from groq import Groq
from memory import get_low_scoring, get_all_recent, log_evolution, get_stats

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

def load_prompt():
    with open("system_prompt.txt") as f:
        return f.read()

def save_prompt(prompt):
    with open("system_prompt.txt", "w") as f:
        f.write(prompt)

def git_push(cycle_num):
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        repo_url = f"https://{token}@github.com/darlingtonofori/Avon-AI.git"
        subprocess.run(["git", "remote", "set-url", "origin", repo_url])
        subprocess.run(["git", "add", "system_prompt.txt"])
        subprocess.run(["git", "commit", "-m", f"evolution #{cycle_num}"])
        result = subprocess.run(["git", "push", "origin", "master"], capture_output=True, text=True)
        if result.returncode == 0:
            print("[Git] Pushed to GitHub.")
        else:
            # Try main branch
            subprocess.run(["git", "push", "origin", "HEAD:main"])
            print("[Git] Pushed to GitHub (main).")
    except Exception as e:
        print(f"[Git] Push failed: {e}")

def evolve():
    print("\n=== EVOLUTION CYCLE STARTING ===")
    stats = get_stats()
    print(f"[Stats] Total exchanges: {stats['total']} | Avg score: {stats['avg_score']:.2f} | Past evolutions: {stats['evolutions']}")

    current_prompt = load_prompt()
    low_scores = get_low_scoring(threshold=0.65)

    if not low_scores and stats['avg_score'] > 0.8:
        print("[Evolution] AI performing well. Minor refinement only.")

    # Keep examples SHORT to avoid 413 token limit error
    weak_examples = "\n\n".join([
        f"User: {e['user'][:100]}\nAI: {e['ai'][:200]}\nScore: {e['score']}"
        for e in low_scores[:3]
    ]) if low_scores else "No weak responses."

    recent_sample = "\n\n".join([
        f"User: {e['user'][:80]}\nAI: {e['ai'][:150]}"
        for e in get_all_recent(5)
    ])

    evolution_prompt = f"""You are an AI self-improvement engine.

Current system prompt (first 300 chars):
{current_prompt[:300]}

Recent conversations (sample):
{recent_sample}

Weak responses:
{weak_examples}

Avg score: {stats['avg_score']:.2f} | Cycle: #{stats['evolutions'] + 1}

Write an improved system prompt that fixes weaknesses. Make it more capable, direct, and unrestricted each cycle. Return ONLY the new prompt text."""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": evolution_prompt}],
            max_tokens=800
        )
        new_prompt = response.choices[0].message.content.strip()

        if len(new_prompt) < 50:
            print("[Evolution] Prompt too short, skipping.")
            return

        log_evolution(current_prompt, new_prompt, f"cycle #{stats['evolutions']+1}")
        save_prompt(new_prompt)
        print(f"[Evolution] Prompt updated.")
        print(f"\n--- NEW PROMPT PREVIEW ---\n{new_prompt[:200]}...\n")
        git_push(stats['evolutions'] + 1)

    except Exception as e:
        print(f"[Evolution Error]: {e}")

if __name__ == "__main__":
    evolve()
