import re

# Title keywords for jobs a data scientist would want to see.
# Edit freely -- each entry is matched case-insensitively as a regex against the job title.
DEFAULT_KEYWORDS = [
    r"data scien",                 # data science / data scientist
    r"applied scien",              # applied science / applied scientist
    r"machine learning",
    r"\bmle\b",                    # machine learning engineer (abbrev.)
    r"ml engineer",
    r"research scientist",
    r"applied ai",
    r"\bai\b scientist",
    r"\bai\b engineer",
    r"artificial intelligence",
    r"deep learning",
    r"computer vision",
    r"natural language processing",
    r"\bnlp\b",
    r"\bllm\b",
    r"generative ai",
    r"\bmlops\b",
    r"quantitative research",
    r"\bstatistician\b",
]


def build_pattern(keywords=None):
    keywords = keywords or DEFAULT_KEYWORDS
    return re.compile("|".join(keywords), re.IGNORECASE)


def is_relevant(title, pattern=None):
    if not title or not isinstance(title, str):
        return False
    pattern = pattern or build_pattern()
    return bool(pattern.search(title))


def filter_relevant(df, keywords=None, title_col="title"):
    """Return only the rows whose title matches one of the relevance keywords."""
    pattern = build_pattern(keywords)
    return df[df[title_col].apply(lambda t: is_relevant(t, pattern))].copy()
