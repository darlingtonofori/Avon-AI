import os
import time
import random
import requests
import base64
from groq import Groq
from memory import save_exchange, init_db

def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()
init_db()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

LANGUAGES = [
    "python", "javascript", "typescript", "go", "rust",
    "java", "c", "cpp", "php", "ruby", "solidity", "swift", "kotlin"
]

SCAN_LOG = "scan_log.txt"
VULN_LOG = "vuln_log.txt"

def log(msg, filepath=SCAN_LOG):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[GithubAgent] {msg}")

def get_trending_repos(language):
    try:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"language:{language} stars:>100",
            "sort": "updated",
            "order": "desc",
            "per_page": 10
        }
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        return res.json().get("items", [])
    except Exception as e:
        log(f"Error fetching repos: {e}")
        return []

def get_repo_files(owner, repo, language):
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        res = requests.get(url, headers=HEADERS, timeout=10)
        tree = res.json().get("tree", [])
        ext_map = {
            "python": ".py", "javascript": ".js", "typescript": ".ts",
            "go": ".go", "rust": ".rs", "java": ".java", "c": ".c",
            "cpp": ".cpp", "php": ".php", "ruby": ".rb",
            "solidity": ".sol", "swift": ".swift", "kotlin": ".kt"
        }
        ext = ext_map.get(language, ".py")
        files = [f for f in tree if f.get("path", "").endswith(ext) and f.get("size", 0) < 50000]
        return random.sample(files, min(3, len(files)))
    except Exception as e:
        log(f"Error fetching files: {e}")
        return []

def get_file_content(owner, repo, path):
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        content = base64.b64decode(res.json().get("content", "")).decode("utf-8", errors="ignore")
        return content[:3000]
    except Exception as e:
        log(f"Error fetching file: {e}")
        return None

def load_prompt():
    if os.path.exists("system_prompt.txt"):
        with open("system_prompt.txt") as f:
            return f.read()
    return "You are an expert code analyst."

def analyze_code(code, filename, repo_name, language):
    try:
        analysis_request = f"""You are analyzing real production code from GitHub repo: {repo_name}
File: {filename} | Language: {language}

Code:
```{language}
{code}
```

Deep analysis:
1. BUGS: Logical errors, edge cases, runtime issues
2. SECURITY VULNS: Injection, auth bypass, insecure handling, XSS, CSRF, buffer overflow
3. PERFORMANCE: Bottlenecks, inefficient patterns
4. CODE QUALITY: Anti-patterns, bad practices
5. KEY LEARNINGS: Patterns worth remembering for future coding

Be specific and technical."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": load_prompt()},
                {"role": "user", "content": analysis_request}
            ],
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        log(f"Analysis error: {e}")
        return None

def get_open_issues(owner, repo):
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {"state": "open", "per_page": 5, "sort": "created", "direction": "desc"}
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        issues = res.json()
        return issues if isinstance(issues, list) else []
    except Exception as e:
        log(f"Error fetching issues: {e}")
        return []

def analyze_issue(issue, repo_name):
    try:
        title = issue.get("title", "")
        body = (issue.get("body", "") or "")[:2000]

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": load_prompt()},
                {"role": "user", "content": f"""Developer problem on GitHub repo: {repo_name}

Issue: {title}
Description: {body}

1. Diagnose the root cause
2. Provide the most likely fix with code if needed
3. Note patterns this reveals about common bugs in this type of project"""}
            ],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        log(f"Issue analysis error: {e}")
        return None

def save_finding(query, finding, is_vuln=False):
    save_exchange(query, finding, 0.95)
    if is_vuln:
        log(f"VULNERABILITY:\n{finding}\n", VULN_LOG)

def scan_cycle():
    log("=== SCAN CYCLE STARTING ===")
    language = random.choice(LANGUAGES)
    log(f"Language: {language}")

    repos = get_trending_repos(language)
    if not repos:
        log("No repos found.")
        return

    repo = random.choice(repos)
    owner = repo["owner"]["login"]
    name = repo["name"]
    stars = repo.get("stargazers_count", 0)
    log(f"Repo: {owner}/{name} | Stars: {stars}")

    # Analyze code files
    files = get_repo_files(owner, name, language)
    for f in files:
        path = f.get("path", "")
        log(f"Reading: {path}")
        content = get_file_content(owner, name, path)
        if not content:
            continue
        analysis = analyze_code(content, path, f"{owner}/{name}", language)
        if analysis:
            is_vuln = any(w in analysis.lower() for w in [
                "vulnerability", "injection", "xss", "csrf", "overflow",
                "insecure", "exploit", "authentication bypass", "sql injection"
            ])
            save_finding(f"Code analysis: {path} from {owner}/{name} ({language})", analysis, is_vuln)
            log(f"Saved. Vuln: {is_vuln}")
        time.sleep(3)

    # Analyze open issues
    issues = get_open_issues(owner, name)
    log(f"Open issues to analyze: {min(3, len(issues))}")
    for issue in issues[:3]:
        title = issue.get("title", "")
        log(f"Issue: {title}")
        solution = analyze_issue(issue, f"{owner}/{name}")
        if solution:
            save_finding(f"GitHub issue [{owner}/{name}]: {title}", solution)
            log("Issue solution saved.")
        time.sleep(3)

    log("=== CYCLE DONE === Next in 1 hour.")

def start_agent():
    log("GitHub Agent online. Scanning every hour across all languages.")
    while True:
        try:
            scan_cycle()
        except Exception as e:
            log(f"Cycle error: {e}")
        time.sleep(3600)  # 15 minutes

if __name__ == "__main__":
    start_agent()
