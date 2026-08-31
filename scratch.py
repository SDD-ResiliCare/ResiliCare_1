import re

NEGATION_TOKENS = ["not", "no", "never", "didn't", "don't", "doesn't", "nahi", "nahin", "na", "mat", "नहीं", "बिना"]

def is_negated(text_lower: str, match_start: int) -> bool:
    prefix = text_lower[:match_start]
    prefix_tokens = re.findall(r"\b\w+\b|[.,!?;]", prefix)
    
    window_words = []
    for token in reversed(prefix_tokens):
        if re.match(r"[.,!?;]", token):
            break
        window_words.append(token)
        if len(window_words) == 3:
            break
            
    return any(neg in window_words for neg in NEGATION_TOKENS)

def detect_acuity_with_negation(text: str, RED_FLAGS) -> list[str]:
    text_lower = text.lower()
    triggered = []
    for flag in RED_FLAGS:
        flag_triggered = False
        for phrase in flag["phrases"]:
            matches = list(re.finditer(re.escape(phrase), text_lower))
            for match in matches:
                if not is_negated(text_lower, match.start()):
                    flag_triggered = True
                    break
            if flag_triggered:
                break
        
        if flag_triggered:
            triggered.append(flag["id"])
    return triggered

def extract_chief_complaint(text: str, _COMPLAINT_KEYWORDS) -> str:
    text_lower = text.lower()
    for trigger_phrase, keywords in _COMPLAINT_KEYWORDS:
        for keyword in keywords:
            matches = list(re.finditer(re.escape(keyword), text_lower))
            for match in matches:
                if not is_negated(text_lower, match.start()):
                    return trigger_phrase
    return None

RED_FLAGS = [
    {"id": "chest_pain", "phrases": ["chest pain"]},
]
_COMPLAINT_KEYWORDS = [
    ("chest pain", ("chest", "heart")),
]

print(extract_chief_complaint("I do not have chest pain", _COMPLAINT_KEYWORDS))
print(extract_chief_complaint("I have chest pain", _COMPLAINT_KEYWORDS))
