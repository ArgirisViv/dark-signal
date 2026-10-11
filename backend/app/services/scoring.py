def calculate_awareness_score(action: str, reaction_time: int):
    score = 0

    if action == "report":
        score += 10
        if reaction_time < 30:
            score += 5
    elif action == "ignore":
        score += 3
    elif action == "click":
        score -= 5

    return score
