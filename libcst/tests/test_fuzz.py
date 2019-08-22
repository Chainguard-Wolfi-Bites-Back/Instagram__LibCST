# Copyright (c) Zac Hatfield-Dodds
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict
"""
Fuzz-tests for libCST, by Zac Hatfield-Dodds (zac@hypothesis.works)

For Hypothesis documentation, see https://hypothesis.readthedocs.io/
For my Python code generator, see https://pypi.org/project/hypothesmith/
"""

import os
import unittest
from datetime import timedelta

import hypothesis
from hypothesmith import from_grammar

import libcst


# If in doubt, you should use these "unit test" settings.  They tune the timeouts
# and example-reproduction behaviour for these tests' unusually large inputs.
hypothesis.settings.register_profile(
    name="settings-for-unit-tests",
    print_blob=True,
    deadline=timedelta(seconds=10),
    suppress_health_check=[hypothesis.HealthCheck.too_slow],
)
hypothesis.settings.load_profile("settings-for-unit-tests")
# When the test settings stop finding new bugs, you can run `python test_fuzz.py`
# to find more.  We turn the number of examples up, and skip the initial "reuse"
# phase in favor of looking for new bugs... but put everything we find in the
# database so it will be replayed next time we use the normal settings.
hypothesis.settings.register_profile(
    name="settings-for-fuzzing",
    parent=hypothesis.settings.get_profile("settings-for-unit-tests"),
    max_examples=100_000,
    phases=(hypothesis.Phase.generate, hypothesis.Phase.shrink),
)


class FuzzTest(unittest.TestCase):
    """Fuzz-tests based on Hypothesis and Hypothesmith."""

    @unittest.skipUnless(
        bool(os.environ.get("HYPOTHESIS", False)), "Hypothesis not requested"
    )
    @hypothesis.given(source_code=from_grammar(start="file_input"))
    def test_parsing_compilable_module_strings(self, source_code: str) -> None:
        """The `from_grammar()` strategy generates strings from Python's grammar.

        This has a bunch of weird edge cases because "strings accepted by Cpython"
        isn't actually the same set as "strings accepted by the grammar", and for
        a few other weird reasons you can ask Zac about if you're interested.

        Valid values for ``start`` are ``"single_input"``, ``"file_input"``, or
        ``"eval_input"``; respectively a single interactive statement, a module or
        sequence of commands read from a file, and input for the eval() function.

        .. warning::
            DO NOT EXECUTE CODE GENERATED BY THE `from_grammar()` STRATEGY.

            It could do literally anything that running Python code is able to do,
            including changing, deleting, or uploading important data.  Arbitrary
            code can be useful, but "arbitrary code execution" can be very, very bad.
        """
        self.reject_invalid_code(source_code, mode="exec")
        tree = libcst.parse_module(source_code)
        self.assertEqual(source_code, tree.code)

    @unittest.skipUnless(
        bool(os.environ.get("HYPOTHESIS", False)), "Hypothesis not requested"
    )
    @hypothesis.given(source_code=from_grammar(start="eval_input").map(str.strip))
    def test_parsing_compilable_expression_strings(self, source_code: str) -> None:
        """Much like statements, but for expressions this time.

        We change the start production of the grammar, the compile mode,
        and the libCST parse function, but codegen is as for statements.
        """
        self.reject_invalid_code(source_code, mode="eval")
        try:
            tree = libcst.parse_expression(source_code)
        except Exception:
            hypothesis.reject()
        else:
            self.assertEqual(source_code, libcst.Module([]).code_for_node(tree))

    @unittest.skipUnless(
        bool(os.environ.get("HYPOTHESIS", False)), "Hypothesis not requested"
    )
    @hypothesis.given(
        source_code=from_grammar(start="single_input").map(
            lambda s: s.replace("\n", "") + "\n"
        )
    )
    def test_parsing_compilable_statement_strings(self, source_code: str) -> None:
        """Just like the above, but for statements.

        We change the start production of the grammar, the compile mode,
        the libCST parse function, and the codegen method.
        """
        self.reject_invalid_code(source_code, mode="single")
        try:
            tree = libcst.parse_statement(source_code)
        except Exception:
            hypothesis.reject()
        else:
            self.assertEqual(source_code, libcst.Module([]).code_for_node(tree))

    @staticmethod
    def reject_invalid_code(source_code: str, mode: str) -> None:
        """Input validation helper shared by modules, statements, and expressions."""
        # We start by compiling our source code to byte code, and rejecting inputs
        # where this fails.  This is to guard against spurious failures due to
        # e.g. `eval` only being a keyword in Python 3.7
        assert mode in {"eval", "exec", "single"}
        hypothesis.note(source_code)
        try:
            compile(source_code, "<string>", mode)
        except Exception:
            # We're going to check here that libCST also rejects this string.
            # If so it's a test failure; if not we reject this input so Hypothesis
            # spends as little time as possible exploring invalid code.
            # (usually I'd use a custom mutator, but this is free so...)
            parser = dict(
                eval=libcst.parse_expression,
                exec=libcst.parse_module,
                single=libcst.parse_statement,
            )
            try:
                tree = parser[mode](source_code)
                msg = f"libCST parsed a string rejected by compile() into {tree!r}"
                assert False, msg
            except Exception:
                hypothesis.reject()
            assert False, "unreachable"


if __name__ == "__main__":
    hypothesis.settings.load_profile("settings-for-fuzzing")
    unittest.main()
