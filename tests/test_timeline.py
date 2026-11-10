"""Timeline building without any audio model. Run: python -m unittest discover -s tests"""
import unittest

import numpy as np

from zh_lipsync.align import SR, align, build_cues, merge_english_words
from zh_lipsync.core import lipsync, to_rhubarb
from zh_lipsync.text import script_units
from zh_lipsync.visemes import english_shapes


def timed(text, times):
    us = script_units(text)
    for u, (s, e) in zip(us, times):
        u.update(s=s, e=e, matched=True)
    return us


class Cues(unittest.TestCase):
    def test_gap_closes_mouth_and_timeline_ends_closed(self):
        cues = build_cues(timed('他他', [(0.0, 0.3), (0.6, 0.9)]))
        self.assertEqual([(c['t'], c['shape']) for c in cues], [(0.0, 'a'), (0.3, 'n'), (0.6, 'a'), (0.9, 'n')])

    def test_bilabial_closes_lips_first(self):
        cues = build_cues(timed('媽', [(0.5, 0.8)]))
        self.assertEqual([c['shape'] for c in cues], ['n', 'a', 'n'])
        self.assertAlmostEqual(cues[1]['t'], 0.5 + 2 / 30, places=3)

    def test_long_diphthong_is_split(self):
        self.assertEqual([c['shape'] for c in build_cues(timed('好', [(0.0, 0.4)]))], ['a', 'o', 'n'])
        self.assertEqual([c['shape'] for c in build_cues(timed('好', [(0.0, 0.15)]))], ['a', 'n'])

    def test_english_word_becomes_word_shapes(self):
        us = merge_english_words(timed('App', [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3)]), english_shapes)
        self.assertEqual([u['shape'][1] for u in us], ['e', 'n'])

    def test_align_interpolates_unmatched(self):
        out = align(['a', 'b', 'c'], [('a', 0.0, 0.1, ''), ('c', 0.5, 0.6, '')])
        self.assertEqual([m for _, _, m in out], [True, False, True])
        self.assertAlmostEqual(out[1][0], 0.1)
        self.assertAlmostEqual(out[1][1], 0.5)


class EndToEnd(unittest.TestCase):
    def test_synthetic_audio_with_given_word_times(self):
        # two "syllables" of tone separated by silence; word times as a recognizer would give them
        t = np.arange(int(SR * 1.2)) / SR
        audio = (0.3 * np.sin(2 * np.pi * 220 * t) * (((t > 0.1) & (t < 0.4)) | ((t > 0.7) & (t < 1.0)))).astype(np.float32)
        res = lipsync(audio, [('他', 0.1, 0.4), ('好', 0.7, 1.0)], text='他，好。')
        self.assertEqual(res['matched_ratio'], 1.0)
        shapes = [c['shape'] for c in res['cues']]
        self.assertEqual(shapes[0], 'n')
        self.assertIn('a', shapes)
        self.assertEqual(shapes[-1], 'n')
        silent = [c for c in res['cues'] if 0.45 < c['t'] < 0.65]
        self.assertTrue(all(c['shape'] == 'n' for c in silent))
        rh = to_rhubarb(res, 'x.wav')
        self.assertTrue(all(c['value'] in 'ABCDEFX' for c in rh['mouthCues']))


if __name__ == '__main__':
    unittest.main()
