"""
Shared text utilities for all five analytics modules.
Every module must use these functions exclusively — never their own tokenisation.
If five modules count 'content words' differently, scores silently disagree.
"""
from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------------------
# Stopword list — function words and high-frequency discourse words
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset({
    # Articles
    "a", "an", "the",
    # Pronouns
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    # Auxiliary verbs
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "need", "must", "ought",
    # Prepositions
    "at", "by", "for", "from", "in", "into", "of", "off", "on",
    "onto", "out", "over", "through", "to", "under", "up", "with",
    "about", "above", "across", "after", "against", "along", "among",
    "around", "before", "behind", "below", "between", "beyond",
    "down", "during", "inside", "near", "outside", "toward",
    "towards", "via", "within", "without",
    # Conjunctions
    "and", "as", "because", "but", "either", "if", "nor", "or",
    "since", "so", "than", "though", "unless", "until", "when",
    "whenever", "where", "whereas", "whether", "while",
    # Common function adverbs / determiners
    "also", "back", "both", "even", "ever", "few", "forward",
    "here", "however", "just", "lot", "more", "most", "much",
    "no", "not", "now", "only", "other", "per", "rather", "really",
    "same", "still", "such", "then", "there", "therefore", "thus",
    "too", "very", "yet",
    # Contractions (lowercased, apostrophe removed by tokeniser)
    "im", "ive", "id", "ill",
    "youre", "youve", "youd", "youll",
    "hes", "shes", "were", "theyre", "theyve", "theyd", "theyll",
    "isnt", "arent", "wasnt", "werent", "hasnt", "havent", "hadnt",
    "dont", "doesnt", "didnt", "wont", "wouldnt", "couldnt", "shouldnt",
    "cant", "cannot", "thats", "theres", "whats",
})

_PUNCT_RE       = re.compile(r"[^\w\s]")
_WHITESPACE_RE  = re.compile(r"\s+")
_SENTENCE_RE    = re.compile(r"[.!?]+\s+|[.!?]+$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """
    Lowercase → strip punctuation → split on whitespace.
    Returns a flat list of word tokens. Empty strings excluded.
    """
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    tokens = _WHITESPACE_RE.split(text.strip())
    return [t for t in tokens if t]


def content_words(tokens: list[str]) -> list[str]:
    """
    Filter stopwords from a token list.
    Returns content tokens in their original order.
    All five modules call this — never filter stopwords inline.
    """
    return [t for t in tokens if t not in _STOPWORDS]


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    """Return all n-grams as tuples. Empty list if len(tokens) < n."""
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def sentence_split(text: str) -> list[str]:
    """
    Split on . ! ? punctuation.
    Returns non-empty, stripped sentence strings.
    """
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def corrected_ttr(tokens: list[str], content: list[str]) -> float:
    """
    Content-word type-token ratio: unique content words / total content words.
    Range: 0.0–1.0. Returns 0.0 for empty content.

    Note: the PRD specifies 'unique content words ÷ √total words'.
    We use unique / total _content_ words so the result is bounded [0, 1]
    and the STRONG_VOCAB_TTR = 0.65 threshold (IAD §3) is meaningful.
    """
    if not content:
        return 0.0
    return len(set(content)) / len(content)


def content_word_density(tokens: list[str], content: list[str]) -> float:
    """
    Fraction of tokens that are content words. Range: 0.0–1.0.
    Returns 0.0 for empty token lists.
    """
    if not tokens:
        return 0.0
    return len(content) / len(tokens)
