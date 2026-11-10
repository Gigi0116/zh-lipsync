"""Script text -> timed units. Matching between the script and the speech recognizer is done on
toneless pinyin, so traditional/simplified differences and homophone mis-recognitions still match."""
import re

from pypinyin import Style, lazy_pinyin

from .visemes import DIGIT_NAMES, PUNCT, is_han, shapes_for_letter, shapes_for_zhuyin, zhuyin_of

_WORD_RE = re.compile(r'[A-Za-z]+|\d|[㐀-鿿豈-﫿]|\S', re.S)


def keys_of(text):
    """Matching keys for recognizer output: toneless pinyin per Han char, lowercase letters, digits as pinyin."""
    text = re.sub(r'\d', lambda m: DIGIT_NAMES[int(m.group())], text)
    out = []
    for tok in _WORD_RE.findall(text):
        if tok.isascii() and tok.isalpha():
            out.extend(tok.lower())
        elif is_han(tok):
            out.append(tok)
    if not out:
        return []
    han = ''.join(t for t in out if not t.isascii())
    py = iter(lazy_pinyin(han, style=Style.NORMAL)) if han else iter(())
    return [t if t.isascii() else next(py) for t in out]


def script_units(text, line_id=None):
    """One unit per spoken syllable / letter of `text`:
    {text, key, zhuyin, shape: (lips, main, tail), pause_before, word, word_id, line}."""
    norm = re.sub(r'\d', lambda m: DIGIT_NAMES[int(m.group())], text)
    zy = zhuyin_of(norm)
    keys = keys_of(norm)
    units, pending, ki = [], True, 0
    i = 0
    while i < len(norm):
        ch = norm[i]
        if ch.isascii() and ch.isalpha():
            j = i
            while j < len(norm) and norm[j].isascii() and norm[j].isalpha():
                j += 1
            word = norm[i:j]
            for k, letter in enumerate(word):
                units.append({'text': letter, 'key': keys[ki], 'zhuyin': None, 'shape': shapes_for_letter(letter),
                              'pause_before': pending and k == 0, 'word': word, 'word_id': (line_id, i), 'line': line_id})
                ki += 1
            pending = False
            i = j
            continue
        if is_han(ch):
            units.append({'text': ch, 'key': keys[ki], 'zhuyin': zy[i], 'shape': shapes_for_zhuyin(zy[i]),
                          'pause_before': pending, 'word': None, 'word_id': None, 'line': line_id})
            ki += 1
            pending = False
        elif ch in PUNCT:
            pending = True
        i += 1
    return units

