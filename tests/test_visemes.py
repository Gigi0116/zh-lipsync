"""Fixed zhuyin -> mouth-shape table. Run: python -m unittest discover -s tests"""
import unittest

from zh_lipsync.text import keys_of, script_units
from zh_lipsync.visemes import english_shapes, shapes_for_zhuyin, word_vowels


def shapes(text):
    return [(u['text'], u['shape']) for u in script_units(text)]


class ZhuyinTable(unittest.TestCase):
    CASES = {
        # char: (close lips first, main shape, diphthong tail)
        '他': (False, 'a', None), '看': (False, 'a', None), '光': (False, 'a', None),
        '在': (False, 'a', 'i'), '快': (False, 'a', 'i'), '好': (False, 'a', 'o'), '要': (False, 'a', 'o'),
        '的': (False, 'e', None), '人': (False, 'e', None), '也': (False, 'e', None), '先': (False, 'e', None),
        '一': (False, 'i', None), '心': (False, 'i', None), '是': (False, 'i', None), '字': (False, 'i', None),
        '我': (False, 'o', None), '有': (False, 'o', None), '就': (False, 'o', None),
        '去': (False, 'u', None), '同': (False, 'u', None), '用': (False, 'u', None),
        '不': (True, 'u', None), '媽': (True, 'a', None), '美': (True, 'e', None), '跑': (True, 'a', 'o'),
    }

    def test_table(self):
        for ch, want in self.CASES.items():
            with self.subTest(ch=ch):
                self.assertEqual(script_units(ch)[0]['shape'], want)

    def test_traditional_and_simplified_agree(self):
        self.assertEqual([s for _, s in shapes('驗證碼')], [s for _, s in shapes('验证码')])

    def test_polyphone_in_context(self):
        # 銀行 = háng (ㄏㄤˊ -> a), 行走 = xíng (ㄒㄧㄥˊ -> i)
        self.assertEqual(script_units('銀行')[1]['shape'][1], 'a')
        self.assertEqual(script_units('行走')[0]['shape'][1], 'i')

    def test_unknown_final_falls_back_to_half_open(self):
        self.assertEqual(shapes_for_zhuyin(None), (False, 'e', None))


class Script(unittest.TestCase):
    def test_punctuation_marks_pauses(self):
        us = script_units('你好，世界。')
        self.assertEqual([u['pause_before'] for u in us], [True, False, True, False])

    def test_digits_are_read(self):
        self.assertEqual([u['text'] for u in script_units('2026')], list('二零二六'))

    def test_matching_keys_are_toneless_pinyin(self):
        self.assertEqual(keys_of('驗證 App'), ['yan', 'zheng', 'a', 'p', 'p'])
        self.assertEqual(keys_of('验证'), keys_of('驗證'))


class English(unittest.TestCase):
    def test_words_and_acronyms(self):
        self.assertEqual(english_shapes('App'), ['e', 'n'])
        self.assertEqual(english_shapes('Google'), ['u', 'e'])
        self.assertIsNone(english_shapes('CISA'))      # acronym: spelled out
        self.assertEqual(word_vowels('demo'), ['e', 'o'])
        self.assertEqual(word_vowels('make'), ['n', 'a'])


if __name__ == '__main__':
    unittest.main()
