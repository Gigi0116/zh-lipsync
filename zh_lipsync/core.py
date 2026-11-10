"""Audio (+ optional script / subtitles) -> mouth-shape timeline."""
import os

from . import __version__
from .align import (SR, align, build_cues, energy_db, fix_silent_units, merge_english_words, respread_unmatched,
                    snap, timing_error, transcribe, trim_silence, voiced_mask, words_to_keys)
from .text import keys_of, script_units
from .visemes import SHAPES, english_shapes


def load_audio(path):
    from faster_whisper import decode_audio
    return decode_audio(path, SR)


def recognize(audio, model='small', device='cpu', compute_type='int8', offline=False, language='zh'):
    """[(word, start, end)] from faster-whisper."""
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device=device, compute_type=compute_type, local_files_only=offline)
    return transcribe(m, audio, language=language)


def lipsync(audio, words, lines=None, text=None):
    """Build the timeline.

    audio : float32 mono 16 kHz samples (see load_audio)
    words : recognizer word timestamps [(word, start, end)] (see recognize)
    lines : optional [{'id', 'text', 'start', 'end'}] from subtitles; each line is aligned only to the speech
            inside its own time range, so a mistake in one line never shifts the next one
    text  : optional script without times (aligned as a whole)
    With neither, the recognized words themselves are used as the script."""
    hyp = words_to_keys(words, keys_of)
    if lines:
        groups = [(ln, script_units(ln['text'], ln.get('id', str(i)))) for i, ln in enumerate(lines)]
    else:
        src = text if text is not None else ''.join(w for w, _, _ in words)
        groups = [({'id': 'all', 'start': None, 'end': None}, script_units(src, 'all'))]
    units, line_stats, raw = [], [], []
    for ln, us in groups:
        if not us:
            continue
        lo, hi = ln.get('start'), ln.get('end')
        sub = hyp if lo is None else [h for h in hyp if lo - 0.3 <= (h[1] + h[2]) / 2 <= hi + 0.3]
        timed = align([u['key'] for u in us], sub, lo=lo, hi=hi)
        for u, (s, e, m) in zip(us, timed):
            raw.append({'s': s, 'e': e})
            if lo is not None:   # never leave the line's own time range
                s, e = min(max(s, lo), hi - 0.03), max(min(e, hi), lo + 0.03)
                e = max(e, s + 0.03)
            units.append(dict(u, s=s, e=e, matched=m))
        line_stats.append({'id': ln.get('id'), 'start': lo, 'end': hi, 'syllables': len(us),
                           'matched_ratio': round(sum(m for _, _, m in timed) / len(us), 3)})
    db = energy_db(audio)
    vo = voiced_mask(db)
    timing = {'recognizer_raw': timing_error(raw, db)}
    respread_unmatched(units, vo)
    trim_silence(units, vo)
    fix_silent_units(units, vo)
    snap(units, db)
    timing['after_cleanup'] = timing_error(units, db)
    units = merge_english_words(units, english_shapes)
    cues = build_cues(units)
    n_syl = sum(x['syllables'] for x in line_stats)
    return {
        'format': 'zh-lipsync', 'version': 1, 'generator': f'zh-lipsync {__version__}',
        'duration': round(len(audio) / SR, 3), 'shapes': list(SHAPES),
        'matched_ratio': round(sum(x['syllables'] * x['matched_ratio'] for x in line_stats) / max(1, n_syl), 3),
        'timing_error': timing,
        'cues': cues,
        'syllables': [{'text': u['text'], 'start': round(u['s'], 3), 'end': round(u['e'], 3), 'zhuyin': u['zhuyin'],
                       'shape': u['shape'][1], 'matched': u['matched'], 'line': u['line']} for u in units],
        'lines': line_stats,
    }


# ---------------------------------------------------------------- inputs

def _srt_time(x):
    h, m, s = x.strip().replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def read_srt(path):
    with open(path, encoding='utf-8-sig') as f:
        blocks = [b for b in f.read().replace('\r', '').split('\n\n') if b.strip()]
    lines = []
    for b in blocks:
        rows = [x for x in b.split('\n') if x.strip()]
        k = next((i for i, x in enumerate(rows) if '-->' in x), None)
        if k is None:
            continue
        s, e = (_srt_time(x) for x in rows[k].split('-->'))
        lines.append({'id': rows[0].strip() if k else str(len(lines) + 1), 'text': ''.join(rows[k + 1:]),
                      'start': s, 'end': e})
    return lines


def read_lines_json(path):
    """[{text, start, end}] or {"lines": [...]} with optional id."""
    import json
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    items = data['lines'] if isinstance(data, dict) else data
    return [{'id': it.get('id', str(i)), 'text': it['text'], 'start': it['start'], 'end': it['end']}
            for i, it in enumerate(items)]


def read_words_json(path):
    """[[word, start, end], ...] or {"words": [{"word", "start", "end"}]}."""
    import json
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    items = data['words'] if isinstance(data, dict) else data
    return [tuple(it) if isinstance(it, list) else (it['word'], it['start'], it['end']) for it in items]


# ---------------------------------------------------------------- outputs

# Rhubarb Lip Sync mouth shapes (A..H, X), for tools that already read that format.
RHUBARB = {'n': 'A', 'i': 'B', 'e': 'C', 'a': 'D', 'o': 'E', 'u': 'F'}


def to_rhubarb(result, sound_file=''):
    cues = result['cues']
    mouth = []
    for k, c in enumerate(cues):
        end = cues[k + 1]['t'] if k + 1 < len(cues) else result['duration']
        if end > c['t']:
            mouth.append({'start': c['t'], 'end': round(end, 3), 'value': 'X' if (c['shape'] == 'n' and end - c['t'] > 0.3)
                          else RHUBARB[c['shape']]})
    return {'metadata': {'soundFile': os.path.basename(sound_file), 'duration': result['duration']}, 'mouthCues': mouth}
