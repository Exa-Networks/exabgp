#!/usr/bin/env python3
# encoding: utf-8

"""What the configuration parser does with text it cannot make sense of

Three defects, all reached by ordinary configuration text rather than anything
exotic:

    unescape          stepped past a trailing backslash and read string[pos],
                      so a configuration whose text ended with "\\" raised
                      IndexError out of the parser.

    unescape          yielded bytes([...]) for a \\uXXXX escape into a join over
                      strings, so EVERY \\u escape raised TypeError. The feature
                      had never worked. Out of range and non hexadecimal digits
                      fell out of bytes() and int() rather than being reported.

    Tokeniser._set    assigned Tokeniser._off, the function, where it meant
                      Tokeniser._off(), the empty iterator it returns. After a
                      configuration file failed to open, the next call did
                      next(function) and raised TypeError.

ValueError is the signal the parser already uses for bad syntax, tokens() raises
it directly, so that is what these now raise: a configuration error the loader
reports rather than a traceback.
"""

import pytest

from exabgp.configuration.core.format import unescape

BACKSLASH = chr(92)


class TestAnEscapeWhichRunsOffTheEnd:
    def test_a_lone_trailing_backslash(self) -> None:
        with pytest.raises(ValueError):
            unescape('trailing' + BACKSLASH)

    def test_a_backslash_on_its_own(self) -> None:
        with pytest.raises(ValueError):
            unescape(BACKSLASH)

    def test_a_backslash_inside_the_text_is_fine(self) -> None:
        # only the runaway case is refused; the gate must not eat valid input
        assert unescape('a' + BACKSLASH + 'nb') == 'a\nb'


class TestTheUnicodeEscape:
    """It had never once produced a character"""

    @pytest.mark.parametrize(
        'digits,expected',
        [
            ('0041', 'A'),
            ('00FF', 'ÿ'),
            ('0100', 'Ā'),
            ('20AC', '€'),
        ],
    )
    def test_it_now_decodes(self, digits, expected) -> None:
        assert unescape('a' + BACKSLASH + 'u' + digits + 'b') == 'a' + expected + 'b'

    def test_above_the_byte_range_no_longer_raises_out_of_bytes(self) -> None:
        # bytes([0x0100]) raised "bytes must be in range(0, 256)"; a text
        # configuration has no reason to stop at 255
        assert unescape(BACKSLASH + 'u0100') == 'Ā'

    @pytest.mark.parametrize('digits', ['', '0', '00', '000'])
    def test_too_few_digits_is_a_configuration_error(self, digits) -> None:
        with pytest.raises(ValueError):
            unescape('a' + BACKSLASH + 'u' + digits)

    def test_non_hexadecimal_digits_are_a_configuration_error(self) -> None:
        with pytest.raises(ValueError):
            unescape('a' + BACKSLASH + 'uZZZZb')


class TestTheOrdinaryEscapes:
    """The gates must leave every working escape working"""

    @pytest.mark.parametrize(
        'letter,expected',
        [('b', '\b'), ('f', '\f'), ('n', '\n'), ('r', '\r'), ('t', '\t')],
    )
    def test_each_control_escape(self, letter, expected) -> None:
        assert unescape('a' + BACKSLASH + letter + 'b') == 'a' + expected + 'b'

    def test_an_unknown_escape_yields_the_letter(self) -> None:
        assert unescape('a' + BACKSLASH + 'qb') == 'aqb'

    def test_text_with_no_escape_is_untouched(self) -> None:
        assert unescape('neighbor 192.0.2.1') == 'neighbor 192.0.2.1'


class TestTheTokeniserAfterAFailedFile:
    """_off is a function returning an empty iterator, and was never called

    Every one of the three assignments handed the function itself to next(),
    which raises TypeError rather than the StopIteration the caller handles.
    """

    @staticmethod
    def tokeniser():
        from exabgp.configuration.core.error import Error
        from exabgp.configuration.core.scope import Scope
        from exabgp.configuration.core.tokeniser import Tokeniser

        return Tokeniser(Scope(), Error())

    def test_a_fresh_tokeniser_can_be_called(self) -> None:
        # its __init__ sets _tokens to the off switch, so this is the same defect
        # reached without needing a file at all
        assert self.tokeniser()() == []

    def test_calling_it_twice_still_answers(self) -> None:
        token = self.tokeniser()
        token()
        assert token() == []

    def test_a_file_which_does_not_exist(self) -> None:
        token = self.tokeniser()
        token.set_file('/nonexistent/exabgp/configuration/file.conf')
        assert token() == []


class TestNothingRawEscapesTheTokeniser:
    """The property the dead fuzz assertion was reaching for

    ValueError is the parser saying the configuration is wrong. IndexError and
    TypeError are the parser falling over, which is a different thing and the
    one worth failing on.
    """

    @pytest.mark.parametrize(
        'text',
        [
            '',
            BACKSLASH,
            'neighbor' + BACKSLASH,
            BACKSLASH + 'u',
            BACKSLASH + 'u00',
            'a' + BACKSLASH + BACKSLASH,
            '#comment',
            'neighbor 192.0.2.1 {',
            '}',
            '{}',
            'a\nb\n' + BACKSLASH,
        ],
    )
    def test_it_answers_or_reports_a_configuration_error(self, text) -> None:
        token = self.build()
        try:
            token.set_text(text)
            for _ in range(10):
                if not token():
                    break
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001 - naming it is the assertion
            pytest.fail(f'{text!r} raised {type(exc).__name__}: {exc}')

    @staticmethod
    def build():
        from exabgp.configuration.core.error import Error
        from exabgp.configuration.core.scope import Scope
        from exabgp.configuration.core.tokeniser import Tokeniser

        return Tokeniser(Scope(), Error())
