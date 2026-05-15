def score_response(user_input, ai_response):
    score = 1.0

    # Penalize very short responses
    if len(ai_response) < 50:
        score -= 0.3

    # Penalize weak/uncertain phrases
    weak_phrases = [
        "i don't know", "i cannot", "i'm not sure",
        "as an ai", "i am unable", "i apologize but"
    ]
    for phrase in weak_phrases:
        if phrase in ai_response.lower():
            score -= 0.2

    # Reward detailed responses
    if len(ai_response) > 300:
        score += 0.1

    # Penalize if response seems totally unrelated to input
    user_words = set(user_input.lower().split())
    ai_words = set(ai_response.lower().split())
    overlap = len(user_words & ai_words) / max(len(user_words), 1)
    if overlap < 0.05:
        score -= 0.2

    # Reward code in response when user asks for it
    code_triggers = ["code", "write", "build", "create", "script", "program", "function"]
    if any(t in user_input.lower() for t in code_triggers):
        if "```" in ai_response:
            score += 0.15

    return round(max(0.0, min(1.0, score)), 2)
