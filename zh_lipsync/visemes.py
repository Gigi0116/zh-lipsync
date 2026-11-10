"""Mandarin text -> mouth shapes (visemes).

Six shapes, named after the Japanese vowels most 2D avatar rigs already have:
    a  wide open      (ㄚ ㄢ ㄤ ...)
    i  spread         (ㄧ ㄧㄣ ㄧㄥ, and the apical vowel in 是/字/知)
    u  narrow round   (ㄨ ㄩ ㄨㄥ ...)
    e  half open      (ㄜ ㄝ ㄟ ㄣ ㄥ ㄧㄢ ...)
    o  round          (ㄛ ㄨㄛ ㄡ ㄧㄡ)
    n  closed lips    (silence, and the start of ㄅ ㄆ ㄇ)
"""
from pypinyin import Style, pinyin

SHAPES = ('a', 'i', 'u', 'e', 'o', 'n')

INITIALS = set('ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙ')
LIPS = set('ㄅㄆㄇ')          # bilabial initials: close the lips briefly before the vowel
TONES = 'ˊˇˋ˙'

# Zhuyin final -> (main shape, tail shape for diphthongs or None)
FINAL_SHAPE = {
    'ㄚ': ('a', None), 'ㄧㄚ': ('a', None), 'ㄨㄚ': ('a', None), 'ㄢ': ('a', None), 'ㄨㄢ': ('a', None),
    'ㄤ': ('a', None), 'ㄧㄤ': ('a', None), 'ㄨㄤ': ('a', None),
    'ㄞ': ('a', 'i'), 'ㄨㄞ': ('a', 'i'), 'ㄠ': ('a', 'o'), 'ㄧㄠ': ('a', 'o'),
    'ㄜ': ('e', None), 'ㄦ': ('e', None), 'ㄣ': ('e', None), 'ㄥ': ('e', None), 'ㄨㄣ': ('e', None),
    'ㄝ': ('e', None), 'ㄧㄝ': ('e', None), 'ㄩㄝ': ('e', None), 'ㄟ': ('e', None), 'ㄨㄟ': ('e', None),
    'ㄧㄢ': ('e', None), 'ㄩㄢ': ('e', None),
    'ㄧ': ('i', None), 'ㄧㄣ': ('i', None), 'ㄧㄥ': ('i', None), '': ('i', None),   # '' = apical vowel (是 字 知)
    'ㄛ': ('o', None), 'ㄨㄛ': ('o', None), 'ㄡ': ('o', None), 'ㄧㄡ': ('o', None), 'ㄧㄛ': ('o', None),
    'ㄨ': ('u', None), 'ㄩ': ('u', None), 'ㄨㄥ': ('u', None), 'ㄩㄥ': ('u', None), 'ㄩㄣ': ('u', None),
}

# English letters spelled out (acronyms such as CISA, FBI), as commonly read in Taiwan.
LETTER_SHAPE = {
    'a': ['e'], 'b': ['n', 'i'], 'c': ['i'], 'd': ['i'], 'e': ['i'], 'f': ['e', 'u'], 'g': ['i'], 'h': ['e'],
    'i': ['a', 'i'], 'j': ['e'], 'k': ['e'], 'l': ['e', 'o'], 'm': ['e', 'n'], 'n': ['e'], 'o': ['o'],
    'p': ['n', 'i'], 'q': ['i', 'u'], 'r': ['a'], 's': ['e'], 't': ['i'], 'u': ['i', 'u'], 'v': ['i'],
    'w': ['a', 'u'], 'x': ['e'], 'y': ['a', 'i'], 'z': ['i'],
}

# English words read as words (not spelled). Extend this for your own vocabulary.
WORD_SHAPES = {
    'app': ['e', 'n'], 'apple': ['e', 'n', 'o'], 'google': ['u', 'e'], 'passkey': ['n', 'a', 'i'],
    'passkeys': ['n', 'a', 'i'], 'iphone': ['a', 'i', 'o'], 'android': ['a', 'o'], 'fido': ['a', 'i', 'o'],
    'sim': ['i', 'n'], 'email': ['i', 'e'], 'line': ['a', 'i'], 'wifi': ['a', 'i'], 'youtube': ['u', 'u', 'n'],
    'facebook': ['e', 'u'], 'windows': ['i', 'o'], 'microsoft': ['a', 'o'], 'ok': ['o', 'e'],
}

PUNCT = set('，。、：；！？…—「」『』（）,.:;!?()')
DIGIT_NAMES = '零一二三四五六七八九'


def is_han(ch):
    return '㐀' <= ch <= '鿿' or '豈' <= ch <= '﫿'


try:   # optional: pypinyin's phrase dictionary is mostly simplified Chinese, so traditional text reads
    import opencc   # polyphones better after conversion (銀行 háng, 重複 chóng, 睡覺 jiào). pip install opencc
    _T2S = opencc.OpenCC('t2s')
except Exception:   # noqa: BLE001 - any import/config problem just means "no conversion"
    _T2S = None


def zhuyin_of(text):
    """Zhuyin for every character of `text` (phrase context resolves most polyphones). None for non-Han."""
    src = text
    if _T2S is not None:
        conv = _T2S.convert(text)
        if len(conv) == len(text):
            src = conv
    out = pinyin(src, style=Style.BOPOMOFO, errors=lambda x: [None] * len(x))
    return [z[0] if z else None for z in out]


def shapes_for_zhuyin(zhuyin):
    """(close_lips_first, main_shape, tail_shape_or_None) for one syllable in zhuyin."""
    if not zhuyin:
        return False, 'e', None
    z = zhuyin.strip(TONES)
    lips = bool(z) and z[0] in LIPS
    fin = z[1:] if z and z[0] in INITIALS else z
    main, tail = FINAL_SHAPE.get(fin, ('e', None))
    return lips, main, tail


def shapes_for_letter(letter):
    seq = LETTER_SHAPE.get(letter.lower(), ['e'])
    if seq[0] == 'n':
        return True, seq[1], None
    return False, seq[0], (seq[1] if len(seq) > 1 and seq[1] != 'n' else None)


def word_vowels(word):
    """Rough shape sequence for an English word that is not in WORD_SHAPES (vowel groups of the spelling)."""
    w = word.lower()
    if len(w) > 3 and w.endswith('e') and w[-2] not in 'aeiou':
        w = w[:-1]
    seq = ['n'] if w[0] in 'pbm' else []
    vow = {'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u', 'y': 'i', 'oo': 'u', 'ee': 'i', 'ea': 'i', 'ey': 'i',
           'ou': 'a', 'ai': 'e', 'ay': 'e', 'oa': 'o', 'ie': 'a'}
    k = 0
    while k < len(w):
        if w[k] in 'aeiouy' and not (k == 0 and w[k] == 'y'):
            g = w[k:k + 2] if w[k:k + 2] in vow else w[k]
            seq.append(vow[g])
            k += len(g)
        else:
            k += 1
    return seq or ['e']


def english_shapes(word):
    """Shape sequence for an English word, or None if it should be spelled letter by letter (acronyms)."""
    key = word.lower()
    if key in WORD_SHAPES:
        return list(WORD_SHAPES[key])
    if word.isupper() or len(word) == 1:
        return None
    return word_vowels(word)
