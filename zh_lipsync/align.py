"""Timing: speech recognizer word timestamps -> per-syllable times, cleaned up with the audio energy."""
import difflib

import numpy as np

SR = 16000
HOP = 0.01

GAP_CLOSE = 0.08       # close the mouth when two syllables are further apart than this
MIN_SEG = 2 / 30       # shortest shape segment (2 frames at 30 fps); shorter ones merge into the previous one
DIPHTHONG_MIN = 0.20   # split ㄞ/ㄠ into two shapes only when the syllable is at least this long
LIP_CLOSE = 2 / 30     # closed lips before ㄅㄆㄇ (only when the syllable is >= 0.15 s)
SNAP_PAUSE = 0.20      # snap pause edges to the voiced/unvoiced boundary within this range
SNAP_DIP = 0.08        # snap syllable boundaries to the nearest energy dip within this range
TRIM_EDGE = 0.10       # trim >= 0.10 s of silence at the start/end of a syllable (shorter is usually a fricative)
TRIM_INNER = 0.12      # >= 0.12 s of silence inside a syllable is a pause; punctuation decides which side it belongs to


# ---------------------------------------------------------------- audio

def energy_db(audio, hop=HOP, win=0.03):
    h, w = int(SR * hop), int(SR * win)
    pad = np.pad(audio.astype(np.float64), (w // 2, w // 2))
    cs = np.concatenate([[0.0], np.cumsum(pad ** 2)])
    n = len(audio) // h
    idx = np.arange(n) * h
    rms = np.sqrt((cs[idx + w] - cs[idx]) / w)
    db = 20 * np.log10(rms + 1e-6)
    return np.convolve(db, np.ones(3) / 3, mode='same')


def voiced_mask(db):
    return db > np.percentile(db, 90) - 25


def _edges(vo):
    on = [i * HOP for i in range(1, len(vo)) if vo[i] and not vo[i - 1]]
    off = [i * HOP for i in range(1, len(vo)) if not vo[i] and vo[i - 1]]
    return on, off


# ---------------------------------------------------------------- recognizer

def transcribe(model, audio, language='zh', prompt='以下是普通話的句子。'):
    """[(text, start, end)] word timestamps from faster-whisper."""
    segs, _ = model.transcribe(audio, language=language, beam_size=5, word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False, initial_prompt=prompt)
    return [(w.word, w.start, w.end) for seg in segs for w in (seg.words or [])]


def words_to_keys(words, keys_of):
    """Split recognizer words into per-syllable keys, sharing each word's time evenly."""
    out = []
    for text, s, e in words:
        ks = keys_of(text)
        for k, key in enumerate(ks):
            out.append((key, s + k * (e - s) / len(ks), s + (k + 1) * (e - s) / len(ks), text))
    return out


def align(ref_keys, hyp, lo=None, hi=None):
    """ref_keys: [key]; hyp: [(key, s, e, ...)] -> [(s, e, matched)] per ref key.
    Unmatched runs are interpolated between their neighbours (lo/hi: the line's own start/end, if known)."""
    sm = difflib.SequenceMatcher(a=ref_keys, b=[h[0] for h in hyp], autojunk=False)
    times = [None] * len(ref_keys)
    for a0, b0, n in sm.get_matching_blocks():
        for k in range(n):
            times[a0 + k] = (hyp[b0 + k][1], hyp[b0 + k][2])
    matched = [t is not None for t in times]
    n, i = len(ref_keys), 0
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        if i > 0:
            s = times[i - 1][1]
        elif lo is not None:
            s = lo
        else:
            s = times[j][0] - 0.2 * (j - i) if j < n else 0.0
        if j < n:
            e = times[j][0]
        elif hi is not None and hi > s:
            e = hi
        else:
            e = s + 0.2 * (j - i)
        step = max(e - s, 0.01 * (j - i)) / (j - i)
        for k in range(i, j):
            times[k] = (s + (k - i) * step, s + (k - i + 1) * step)
        i = j
    return [(s, e, m) for (s, e), m in zip(times, matched)]


# ---------------------------------------------------------------- clean-up with audio energy

def respread_unmatched(units, vo):
    """Unmatched syllables are spread over the voiced part of their time span only (never into a pause)."""
    n, i = len(units), 0
    while i < n:
        if units[i]['matched']:
            i += 1
            continue
        j = i
        while j < n and not units[j]['matched'] and units[j]['line'] == units[i]['line']:
            j += 1
        a, b = max(0, int(units[i]['s'] / HOP)), min(len(vo), int(units[j - 1]['e'] / HOP))
        idx = [k for k in range(a, b) if vo[k]]
        if len(idx) >= 3 * (j - i):
            per = len(idx) / (j - i)
            for m in range(i, j):
                k0 = idx[int((m - i) * per)]
                k1 = idx[min(len(idx) - 1, int((m - i + 1) * per) - 1)]
                units[m]['s'], units[m]['e'] = k0 * HOP, (k1 + 1) * HOP
        i = j


def trim_silence(units, vo):
    """Recognizers often stretch a syllable over the following/preceding pause. Pull syllables back to voiced audio."""
    n = len(units)
    for k, c in enumerate(units):
        a, b = max(0, int(round(c['s'] / HOP))), min(len(vo), int(round(c['e'] / HOP)))
        seg = vo[a:b]
        if b - a < 2 or not seg.any():
            continue
        idx = np.flatnonzero(seg)
        a2 = a + idx[0] if idx[0] * HOP >= TRIM_EDGE else a
        b2 = a + idx[-1] + 1 if (len(seg) - idx[-1] - 1) * HOP >= TRIM_EDGE else b
        runs, r = [], None
        for m in range(a2, b2):
            if not vo[m] and r is None:
                r = m
            elif vo[m] and r is not None:
                runs.append((r, m))
                r = None
        runs = [x for x in runs if (x[1] - x[0]) * HOP >= TRIM_INNER]
        if runs:
            r0, r1 = max(runs, key=lambda x: x[1] - x[0])
            after = k == n - 1 or units[k + 1]['line'] != c['line'] or units[k + 1]['pause_before']
            if c['pause_before'] and not after:
                a2 = r1
            elif after and not c['pause_before']:
                b2 = r0
            else:
                a2, b2 = (r1, b2) if (b2 - r1) >= (r0 - a2) else (a2, r0)
        if (b2 - a2) * HOP >= 0.04:
            c['s'], c['e'] = a2 * HOP, b2 * HOP


def fix_silent_units(units, vo, reach=0.4):
    """A syllable lying entirely in silence is moved, together with its neighbours, into the nearest voiced audio."""
    n, R, ctx = len(units), int(reach / HOP), int(0.15 / HOP)
    for k in range(n):
        c = units[k]
        a, b = max(0, int(c['s'] / HOP)), min(len(vo), int(c['e'] / HOP))
        if vo[a:b].sum() >= 4:
            continue
        nxt = next((m for m in range(a, min(len(vo), b + R)) if vo[m]), None)
        prv = next((m for m in range(b - 1, max(-1, a - 1 - R), -1) if vo[m]), None)
        before_sil, after_sil = not vo[max(0, a - ctx):a].any(), not vo[b:b + ctx].any()
        if before_sil and not after_sil:
            forward = nxt is not None
        elif after_sil and not before_sil:
            forward = prv is None and nxt is not None
        else:
            forward = nxt is not None and (prv is None or nxt - b <= a - prv)
        if forward:
            v, m = nxt * HOP, k
            while m < n - 1 and units[m]['line'] == c['line'] and units[m]['e'] < v + 0.08 * (m - k + 1):
                m += 1
            if units[m]['line'] != c['line'] or units[m]['e'] <= v + 0.04 * (m - k + 1):
                continue
            step = (units[m]['e'] - v) / (m - k + 1)
            for q in range(k, m + 1):
                units[q]['s'], units[q]['e'] = v + (q - k) * step, v + (q - k + 1) * step
        elif prv is not None:
            v, m = (prv + 1) * HOP, k
            while m > 0 and units[m]['line'] == c['line'] and units[m]['s'] > v - 0.08 * (k - m + 1):
                m -= 1
            if units[m]['line'] != c['line'] or units[m]['s'] >= v - 0.04 * (k - m + 1):
                continue
            base = units[m]['s']
            step = (v - base) / (k - m + 1)
            for q in range(m, k + 1):
                units[q]['s'], units[q]['e'] = base + (q - m) * step, base + (q - m + 1) * step


def snap(units, db):
    """Snap pause edges to voiced/unvoiced boundaries and syllable boundaries to energy dips."""
    on, off = _edges(voiced_mask(db))
    n = len(units)
    for k, c in enumerate(units):
        if c['s'] < 0.05:
            continue
        if (k == 0 or c['s'] - units[k - 1]['e'] > 0.15) and on:
            x = min(on, key=lambda x: abs(x - c['s']))
            if abs(x - c['s']) <= SNAP_PAUSE and x < c['e'] - 0.06:
                c['s'] = x
        if (k == n - 1 or units[k + 1]['s'] - c['e'] > 0.15) and off:
            x = min(off, key=lambda x: abs(x - c['e']))
            if abs(x - c['e']) <= SNAP_PAUSE and x > c['s'] + 0.06:
                c['e'] = x
    for k in range(1, n):
        a, b = units[k - 1], units[k]
        if b['s'] - a['e'] > 0.15 or a['s'] < 0.05:
            continue
        mid = (a['e'] + b['s']) / 2
        i0, i1 = max(1, int((mid - SNAP_DIP) / HOP)), min(len(db) - 2, int((mid + SNAP_DIP) / HOP))
        mins = [i for i in range(i0, i1 + 1) if db[i] <= db[i - 1] and db[i] <= db[i + 1]]
        if mins:
            x = min((i * HOP for i in mins), key=lambda x: abs(x - mid))
            if a['s'] + 0.06 < x < b['e'] - 0.06:
                a['e'] = b['s'] = x


def timing_error(units, db):
    """Proxy timing error (no hand labels): distance of pause edges to voiced/unvoiced boundaries,
    and of syllable boundaries to the nearest energy dip."""
    on, off = _edges(voiced_mask(db))
    t_max = len(db) * HOP
    pause, dips = [], []
    for k, c in enumerate(units):
        if c['s'] < 0.05 or c['e'] > t_max - 0.05:
            continue
        if (k == 0 or c['s'] - units[k - 1]['e'] > 0.15) and on:
            pause.append(c['s'] - min(on, key=lambda x: abs(x - c['s'])))
        if (k == len(units) - 1 or units[k + 1]['s'] - c['e'] > 0.15) and off:
            pause.append(c['e'] - min(off, key=lambda x: abs(x - c['e'])))
    for k in range(1, len(units)):
        if units[k]['s'] - units[k - 1]['e'] > 0.15:
            continue
        b = (units[k - 1]['e'] + units[k]['s']) / 2
        i0, i1 = max(1, int((b - 0.15) / HOP)), min(len(db) - 2, int((b + 0.15) / HOP))
        mins = [i for i in range(i0, i1 + 1) if db[i] <= db[i - 1] and db[i] <= db[i + 1]]
        if mins:
            dips.append(min((i * HOP - b for i in mins), key=abs))

    def stat(v):
        if not v:
            return None
        a = np.abs(v)
        return {'n': len(v), 'median_abs_ms': round(float(np.median(a)) * 1000),
                'p90_abs_ms': round(float(np.percentile(a, 90)) * 1000), 'mean_signed_ms': round(float(np.mean(v)) * 1000)}
    return {'pause_edges': stat(pause), 'syllable_boundaries': stat(dips)}


# ---------------------------------------------------------------- shapes over time

def merge_english_words(units, english_shapes):
    """Letters of an English word read as a word (App, Google ...) become that word's shape sequence."""
    out, i, n = [], 0, len(units)
    while i < n:
        c = units[i]
        if not c.get('word'):
            out.append(c)
            i += 1
            continue
        j = i + 1
        while j < n and units[j].get('word_id') == c['word_id']:
            j += 1
        seq = english_shapes(c['word'])
        if seq is None:          # acronym: spelled letter by letter
            out.extend(units[i:j])
            i = j
            continue
        clusters, st = [], i     # letters split by a pause: use the longest cluster as the word's time
        for q in range(i + 1, j + 1):
            if q == j or units[q]['s'] - units[q - 1]['e'] >= 0.15:
                clusters.append((units[st]['s'], units[q - 1]['e']))
                st = q
        s, e = max(clusters, key=lambda x: x[1] - x[0])
        nlip = seq.count('n')
        lip = min(LIP_CLOSE, (e - s) / len(seq))
        vdur = ((e - s) - nlip * lip) / max(1, len(seq) - nlip)
        t = s
        for k, v in enumerate(seq):
            d = lip if v == 'n' else vdur
            out.append(dict(c, text=c['word'] if k == 0 else '', zhuyin=None, s=t, e=t + d,
                            matched=all(x['matched'] for x in units[i:j]), shape=(False, v, None)))
            t += d
        i = j
    return out


def build_cues(units, t0=0.0, t1=None):
    """Timed units -> [{'t', 'shape'}]: the shape holds until the next cue. Always ends closed ('n')."""
    t1 = float('inf') if t1 is None else t1
    segs = []
    for c in units:
        s, e = c['s'], c['e']
        if e <= t0 or s >= t1:
            continue
        lips, main, tail = c['shape']
        if lips and e - s >= 0.15:
            segs.append((s, s + LIP_CLOSE, 'n'))
            s += LIP_CLOSE
        d = e - s
        if tail and d >= DIPHTHONG_MIN:
            segs.append((s, s + 0.6 * d, main))
            segs.append((s + 0.6 * d, e, tail))
        else:
            segs.append((s, e, main))
    out = []
    for s, e, v in segs:
        if out and s - out[-1][1] > GAP_CLOSE:
            out.append((out[-1][1], s, 'n'))
        elif out and s > out[-1][1]:
            out[-1] = (out[-1][0], s, out[-1][2])
        out.append((s, e, v))
    merged = []
    for s, e, v in out:
        short = e - s < MIN_SEG and not (v == 'n' and e - s >= LIP_CLOSE - 1e-6)
        if merged and (short or merged[-1][2] == v):
            merged[-1] = (merged[-1][0], e, merged[-1][2])
        else:
            merged.append((s, e, v))
    cues = [{'t': round(max(s, t0) - t0, 3), 'shape': v} for s, e, v in merged if e > t0]
    if merged:
        cues.append({'t': round(min(merged[-1][1], t1) - t0, 3), 'shape': 'n'})
    if cues and cues[0]['t'] > 0:
        cues.insert(0, {'t': 0.0, 'shape': 'n'})
    out = []
    for c in cues:   # drop repeats (e.g. silence followed by a ㄅㄆㄇ lip closure)
        if not out or out[-1]['shape'] != c['shape']:
            out.append(c)
    return out
