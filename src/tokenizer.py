"""Shared NFC Unicode tokenization; positions are zero-based."""
import unicodedata
import regex

TOKEN = regex.compile(r"[\p{L}\p{N}][\p{L}\p{M}\p{N}]*")
TELUGU = regex.compile(r"\A[\p{Script=Telugu}\p{M}]+\Z")

def tokenize(text):
    return TOKEN.findall(unicodedata.normalize('NFC', text))

def is_telugu(term):
    return bool(TELUGU.fullmatch(term) and regex.search(r'\p{Script=Telugu}', term))
