def generate_feedback(indicators: list, missed: list):
    return {
        "recognized_indicators": indicators,
        "missed_indicators": missed,
        "message": "Review suspicious signals carefully next time."
    }
