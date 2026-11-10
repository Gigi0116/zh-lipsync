"""zh-lipsync command line."""
import argparse
import json
import sys

from . import __version__


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='zh-lipsync',
        description='Mandarin speech -> mouth-shape timeline (a/i/u/e/o/n) for 2D avatars. 中文語音 → 嘴型時間軸。')
    ap.add_argument('audio', help='audio file (wav/mp3/m4a ... anything ffmpeg/PyAV can read)')
    src = ap.add_mutually_exclusive_group()
    src.add_argument('--srt', help='subtitles with line timings (.srt) - best accuracy')
    src.add_argument('--lines', help='JSON lines with timings: [{"text", "start", "end"}]')
    src.add_argument('--text', help='plain-text script without timings (UTF-8 file)')
    ap.add_argument('--words', help='use existing word timestamps JSON instead of running Whisper')
    ap.add_argument('--dump-words', help='save the Whisper word timestamps here (re-run later with --words)')
    ap.add_argument('-o', '--out', help='output JSON (default: print to stdout)')
    ap.add_argument('--format', choices=['zh-lipsync', 'rhubarb'], default='zh-lipsync')
    ap.add_argument('--model', default='small', help='faster-whisper model (tiny/base/small/medium/large-v3 ...)')
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--compute-type', default='int8')
    ap.add_argument('--offline', action='store_true', help='do not download models (use the local cache only)')
    ap.add_argument('--version', action='version', version=f'zh-lipsync {__version__}')
    a = ap.parse_args(argv)

    from .core import lipsync, load_audio, read_lines_json, read_srt, read_words_json, recognize, to_rhubarb
    audio = load_audio(a.audio)
    if a.words:
        words = read_words_json(a.words)
    else:
        words = recognize(audio, model=a.model, device=a.device, compute_type=a.compute_type, offline=a.offline)
        if a.dump_words:
            with open(a.dump_words, 'w', encoding='utf-8') as f:
                json.dump({'words': [[w, round(s, 3), round(e, 3)] for w, s, e in words]}, f, ensure_ascii=False)
    lines = read_srt(a.srt) if a.srt else read_lines_json(a.lines) if a.lines else None
    text = None
    if a.text:
        with open(a.text, encoding='utf-8') as f:
            text = f.read()
    res = lipsync(audio, words, lines=lines, text=text)
    out = to_rhubarb(res, a.audio) if a.format == 'rhubarb' else res
    s = json.dumps(out, ensure_ascii=False, indent=1)
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(s)
        print(f"{len(res['cues'])} cues, {len(res['syllables'])} syllables, matched {res['matched_ratio']:.1%} -> {a.out}",
              file=sys.stderr)
    else:
        print(s)
    return 0


if __name__ == '__main__':
    sys.exit(main())
