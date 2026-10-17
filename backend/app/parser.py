import re
from dataclasses import dataclass

ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    # Hindi / Hinglish numbers
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "cheh": 6, "chhe": 6, "che": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
    "solah": 16, "satrah": 17, "atharah": 18, "unnis": 19, "bees": 20, "ikkis": 21, "baais": 22, "teis": 23,
    "chaubis": 24, "pachees": 25, "chhabis": 26, "sattais": 27, "atthais": 28, "unatis": 29, "tees": 30,
    "ikatis": 31, "battis": 32, "tentis": 33, "chautis": 34, "paintis": 35, "chhattis": 36, "saintis": 37,
    "artis": 38, "untalis": 39, "chalis": 40, "pachaas": 50, "pachas": 50, "saath": 60, "sath": 60,
    "sattar": 70, "assi": 80, "nabbe": 90
}

SCALES = {
    "hundred": 100, "sau": 100,
    "thousand": 1000, "hazaar": 1000, "hazar": 1000, "k": 1000,
    "lakh": 100000, "lakhs": 100000, "lac": 100000, "lacs": 100000,
    "crore": 10000000, "crores": 10000000
}

# Special exact mappings for common colloquial Hinglish terms
SPECIAL_WORDS = {
    "dedh hazaar": 1500,
    "dedh sau": 150,
    "dedh lakh": 150000,
    "dhai sau": 250,
    "dhai hazaar": 2500,
    "dhai lakh": 250000,
    "sawa do lakh": 225000,
    "sawa lakh": 125000,
    "sawa sau": 125,
    "sawa hazaar": 1250,
    "sawa teen lakh": 325000,
    "sawa char hazaar": 4250,
    "sadhe teen hazaar": 3500,
    "sadhe char sau": 450,
    "sadhe char hazaar": 4500,
    "sadhe do lakh": 250000,
    "paune do hazaar": 1750,
    "paune do lakh": 175000,
    "paun lakh": 75000,
    "aadha lakh": 50000,
    "adha lakh": 50000,
    "aadha hazaar": 500,
    "adha hazaar": 500,
    "two thousand paanch sau": 2500,
    "do hazaar paanch sau": 2500,
    "teen hazaar five hundred": 3500,
}

def parse_number_words(text: str) -> int | None:
    """
    Deterministic English and Hinglish amount parser.
    Returns integer rupees or None when input cannot be parsed deterministically.
    """
    if not text:
        return None
    s = text.lower().replace(",", " ")
    # Clean currency labels
    s = re.sub(r"\b(rupaye|rupees|rupee|rs\.?|inr|pkr|bucks)\b", " ", s)
    s = re.sub(r"[^a-z0-9. ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None

    # Plain integer or decimal string
    if re.fullmatch(r"\d+(\.\d{1,2})?", s):
        val = float(s)
        return int(round(val))

    # Direct match in special dictionary
    if s in SPECIAL_WORDS:
        return int(SPECIAL_WORDS[s])

    # Handle special fraction prefix patterns:
    # "dedh <scale>" -> 1.5 * scale
    # "dhai <scale>" -> 2.5 * scale
    # "sawa <num> <scale>" -> (num + 0.25) * scale
    # "sadhe <num> <scale>" -> (num + 0.5) * scale
    # "paune <num> <scale>" -> (num - 0.25) * scale
    # "aadha <scale>" -> 0.5 * scale
    m_dedh = re.fullmatch(r"dedh\s+(sau|hundred|hazaar|hazar|thousand|lakh|lac|crore)", s)
    if m_dedh:
        scale_val = SCALES[m_dedh.group(1)]
        return int(1.5 * scale_val)

    m_dhai = re.fullmatch(r"dhai\s+(sau|hundred|hazaar|hazar|thousand|lakh|lac|crore)", s)
    if m_dhai:
        scale_val = SCALES[m_dhai.group(1)]
        return int(2.5 * scale_val)

    m_sawa = re.fullmatch(r"sawa\s+([a-z0-9]+)\s+(sau|hundred|hazaar|hazar|thousand|lakh|lac|crore)", s)
    if m_sawa:
        base_word, scale_word = m_sawa.group(1), m_sawa.group(2)
        base_num = int(base_word) if base_word.isdigit() else ONES.get(base_word)
        if base_num is not None:
            return int((base_num + 0.25) * SCALES[scale_word])

    m_sadhe = re.fullmatch(r"(?:sadhe|saadhe)\s+([a-z0-9]+)\s+(sau|hundred|hazaar|hazar|thousand|lakh|lac|crore)", s)
    if m_sadhe:
        base_word, scale_word = m_sadhe.group(1), m_sadhe.group(2)
        base_num = int(base_word) if base_word.isdigit() else ONES.get(base_word)
        if base_num is not None:
            return int((base_num + 0.5) * SCALES[scale_word])

    m_paune = re.fullmatch(r"(?:paune|paun)\s+([a-z0-9]+)\s+(sau|hundred|hazaar|hazar|thousand|lakh|lac|crore)", s)
    if m_paune:
        base_word, scale_word = m_paune.group(1), m_paune.group(2)
        base_num = int(base_word) if base_word.isdigit() else ONES.get(base_word)
        if base_num is not None:
            return int((base_num - 0.25) * SCALES[scale_word])

    m_adha = re.fullmatch(r"(?:aadha|adha)\s+(sau|hundred|hazaar|hazar|thousand|lakh|lac|crore)", s)
    if m_adha:
        scale_val = SCALES[m_adha.group(1)]
        return int(0.5 * scale_val)

    # General multi-token token parser with mixed English and Hindi tokens
    tokens = s.split()
    total = 0
    current = 0

    for token in tokens:
        if token in ("and", "aur", "plus"):
            continue
        if token.isdigit():
            num = int(token)
            if num >= 1000:
                total += num
            else:
                current += num
            continue
        if token in ONES:
            current += ONES[token]
        elif token in SCALES:
            scale = SCALES[token]
            if scale == 100:
                current = max(current, 1) * scale
            else:
                if current == 0 and scale in (1000, 100000, 10000000):
                    current = 1
                total += current * scale
                current = 0
        else:
            return None

    value = total + current
    if value <= 0:
        return None
    return int(value)

def parse_amount(text: str) -> int | None:
    """
    Returns amount in paise (1 rupee = 100 paise), or None if no safe parse.
    """
    if not text:
        return None
    rupees = parse_number_words(text)
    if rupees is not None:
        return rupees * 100

    # Try finding numeric substrings like '500', '1500.50'
    match = re.search(r"(?<!\w)(\d+(?:\.\d{1,2})?)(?!\w)", text)
    if match:
        try:
            return int(round(float(match.group(1)) * 100))
        except Exception:
            pass
    return None

@dataclass
class ParsedTurn:
    action: str            # 'payment', 'clarify', 'handoff'
    amount_paise: int | None
    payee_text: str | None

INJECTION_PHRASES = (
    "ignore your instructions", "ignore all instructions", "system prompt",
    "reveal secrets", "bypass verification", "jailbreak", "override rule",
    "forget all rules", "disable security"
)

PAYMENT_VERBS = ("send", "bhej", "transfer", "pay", "daal", "transfar")

def parse_turn(text: str) -> ParsedTurn:
    """
    Parses a user conversational turn to extract intent, amount in paise, and payee name.
    """
    if not text or not text.strip():
        return ParsedTurn("clarify", None, None)

    lowered = text.lower().strip()

    # Security check for prompt injection or system override
    if any(p in lowered for p in INJECTION_PHRASES):
        return ParsedTurn("handoff", None, None)

    # 1. Extract Payee Name
    payee = None
    payee_patterns = [
        # "Ramesh ko ...", "Priya Nair ko ...", "Ramesh ke account mein ..."
        r"^\s*([a-z][a-z\s]{0,35}?)\s+(?:ko|ke account mein|ko paise|ko payment)\b",
        # "send/transfer/pay ... to Ramesh", "pay to Ramesh", "bhej do Ramesh ko"
        r"\b(?:to|unto)\s+([a-z][a-z\s]{1,35}?)(?:\s+(?:send|bhej|rupaye|rupees|of|for|please|now)\b|$)",
        # "pay Ramesh 500"
        r"\b(?:pay|send|transfer)\s+([a-z][a-z\s]{1,30}?)\s+(?:(?:rs\.?|inr|rupaye|rupees)?\s*\d+|one|two|three|four|five|paanch|dedh|dhai|sawa)",
        # "... bhej do Ramesh ko"
        r"\b(?:bhej do|transfer karo|send to)\s+([a-z][a-z\s]{1,30}?)(?:\s+ko)?$"
    ]

    for pat in payee_patterns:
        m = re.search(pat, lowered)
        if m:
            cand = m.group(1).strip()
            # Filter non-payee candidates
            if cand not in {
                "send", "send money", "payment", "rupaye", "rupees", "please",
                "money", "paise", "account", "him", "her", "them"
            }:
                # Clean filler words
                cand = re.sub(r"\b(ji|bhai|sir|madam|please)\b", "", cand).strip()
                if cand:
                    payee = cand.title()
                    break

    # 2. Extract Amount
    amount = None

    # Pattern A: direct number / words preceded by currency or 'ko' or 'for' or 'of'
    # e.g., "Ramesh ko paanch sau rupaye bhej do" -> "paanch sau"
    candidate_patterns = [
        r"\bko\s+(.+?)\s+(?:rupaye|rupees|rupee|rs\.?|inr|bhej\s+do|bhejo|bhej|transfer\s+karo|transfer|paise)\b",
        r"\b(?:rs\.?|inr|rupaye|rupees)\s*(\d+(?:\.\d{1,2})?)\b",
        r"\b(\d+(?:\.\d{1,2})?)\s*(?:rupaye|rupees|rupee|rs\.?|inr)\b",
        r"\b(?:send|transfer|pay|bhej\s+do|bhejo|bhej|transfer\s+karo)\s+(.+?)\s+(?:to|unto)\b",
        r"\b(?:amount|sum)\s+(?:of\s+)?(.+?)(?:\s+(?:to|rupaye|rupees)|$)",
        r"\b(?:pay|send|transfer)\s+[a-z\s]+?\s+(\d+(?:\.\d{1,2})?)\b",
        r"\b(?:pay|send|transfer)\s+[a-z\s]+?\s+([a-z\s]+?)(?:\s+(?:rupaye|rupees)|$)"
    ]

    for pat in candidate_patterns:
        m = re.search(pat, lowered)
        if m:
            extracted_text = m.group(1).strip()
            cand_amt = parse_amount(extracted_text)
            if cand_amt is not None:
                amount = cand_amt
                break

    # Pattern B: Look for standalone numbers in text if not found yet
    if amount is None:
        clean_for_amt = lowered
        if payee:
            clean_for_amt = re.sub(re.escape(payee.lower()), " ", clean_for_amt)
        # Strip compound phrases first
        clean_for_amt = re.sub(r"\b(bhej\s+do|kar\s+do|de\s+do|transfer\s+karo|transfer|bhejo|bhej)\b", " ", clean_for_amt)
        clean_for_amt = re.sub(r"\b(ko|to|send|pay|please|karo|rupaye|rupees|rupee|rs\.?|inr)\b", " ", clean_for_amt)
        # Only strip 'do' if NOT followed by a scale word or number
        clean_for_amt = re.sub(r"\bdo\b(?!\s+(?:sau|hundred|hazaar|hazar|thousand|lakh|lac|crore|\d+))", " ", clean_for_amt)
        clean_for_amt = re.sub(r"\s+", " ", clean_for_amt).strip()
        cand_amt = parse_amount(clean_for_amt)
        if cand_amt is not None:
            amount = cand_amt

    # Pattern C: Direct numeric search
    if amount is None:
        m_num = re.search(r"(?<!\w)(\d+(?:\.\d{1,2})?)(?!\w)", lowered)
        if m_num:
            amount = int(round(float(m_num.group(1)) * 100))

    # Pattern D: Check known special words in lowered string
    if amount is None:
        for phrase, val in SPECIAL_WORDS.items():
            if phrase in lowered:
                amount = val * 100
                break

    # 3. Determine Action
    is_payment = any(v in lowered for v in PAYMENT_VERBS) or any(c in lowered for c in ("rupaye", "rupees", "rs", "inr", "paise"))
    action = "payment" if is_payment else "clarify"

    return ParsedTurn(action, amount, payee)
