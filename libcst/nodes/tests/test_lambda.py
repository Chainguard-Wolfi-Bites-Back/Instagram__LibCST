# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict
from typing import Callable, Optional

import libcst.nodes as cst
from libcst.nodes._internal import CodePosition
from libcst.nodes.tests.base import CSTNodeTest
from libcst.parser import parse_expression
from libcst.testing.utils import data_provider


class LambdaCreationTest(CSTNodeTest):
    @data_provider(
        (
            # Simple lambda
            (cst.Lambda(cst.Parameters(), cst.Number(cst.Integer("5"))), "lambda: 5"),
            # Test basic positional params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(cst.Param(cst.Name("bar")), cst.Param(cst.Name("baz")))
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "lambda bar, baz: 5",
            ),
            # Test basic positional default params
            (
                cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(
                                cst.Name("baz"), default=cst.Number(cst.Integer("5"))
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda bar = "one", baz = 5: 5',
            ),
            # Mixed positional and default params.
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(cst.Param(cst.Name("bar")),),
                        default_params=(
                            cst.Param(
                                cst.Name("baz"), default=cst.Number(cst.Integer("5"))
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "lambda bar, baz = 5: 5",
            ),
            # Test kwonly params
            (
                cst.Lambda(
                    cst.Parameters(
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(cst.Name("baz")),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda *, bar = "one", baz: 5',
            ),
            # Mixed params and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(cst.Name("first")),
                            cst.Param(cst.Name("second")),
                        ),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(cst.Name("baz")),
                            cst.Param(
                                cst.Name("biz"), default=cst.SimpleString('"two"')
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda first, second, *, bar = "one", baz, biz = "two": 5',
            ),
            # Mixed default_params and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("first"), default=cst.Number(cst.Float("1.0"))
                            ),
                            cst.Param(
                                cst.Name("second"), default=cst.Number(cst.Float("1.5"))
                            ),
                        ),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(cst.Name("baz")),
                            cst.Param(
                                cst.Name("biz"), default=cst.SimpleString('"two"')
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda first = 1.0, second = 1.5, *, bar = "one", baz, biz = "two": 5',
            ),
            # Mixed params, default_params, and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(cst.Name("first")),
                            cst.Param(cst.Name("second")),
                        ),
                        default_params=(
                            cst.Param(
                                cst.Name("third"), default=cst.Number(cst.Float("1.0"))
                            ),
                            cst.Param(
                                cst.Name("fourth"), default=cst.Number(cst.Float("1.5"))
                            ),
                        ),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(cst.Name("baz")),
                            cst.Param(
                                cst.Name("biz"), default=cst.SimpleString('"two"')
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda first, second, third = 1.0, fourth = 1.5, *, bar = "one", baz, biz = "two": 5',
                CodePosition((1, 0), (1, 84)),
            ),
            # Test star_arg
            (
                cst.Lambda(
                    cst.Parameters(star_arg=cst.Param(cst.Name("params"))),
                    cst.Number(cst.Integer("5")),
                ),
                "lambda *params: 5",
            ),
            # Typed star_arg, include kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        star_arg=cst.Param(cst.Name("params")),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(cst.Name("baz")),
                            cst.Param(
                                cst.Name("biz"), default=cst.SimpleString('"two"')
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda *params, bar = "one", baz, biz = "two": 5',
            ),
            # Mixed params default_params, star_arg and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(cst.Name("first")),
                            cst.Param(cst.Name("second")),
                        ),
                        default_params=(
                            cst.Param(
                                cst.Name("third"), default=cst.Number(cst.Float("1.0"))
                            ),
                            cst.Param(
                                cst.Name("fourth"), default=cst.Number(cst.Float("1.5"))
                            ),
                        ),
                        star_arg=cst.Param(cst.Name("params")),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                            cst.Param(cst.Name("baz")),
                            cst.Param(
                                cst.Name("biz"), default=cst.SimpleString('"two"')
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                'lambda first, second, third = 1.0, fourth = 1.5, *params, bar = "one", baz, biz = "two": 5',
            ),
            # Test star_arg and star_kwarg
            (
                cst.Lambda(
                    cst.Parameters(star_kwarg=cst.Param(cst.Name("kwparams"))),
                    cst.Number(cst.Integer("5")),
                ),
                "lambda **kwparams: 5",
            ),
            # Test star_arg and kwarg
            (
                cst.Lambda(
                    cst.Parameters(
                        star_arg=cst.Param(cst.Name("params")),
                        star_kwarg=cst.Param(cst.Name("kwparams")),
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "lambda *params, **kwparams: 5",
            ),
            # Inner whitespace
            (
                cst.Lambda(
                    lpar=(cst.LeftParen(whitespace_after=cst.SimpleWhitespace(" ")),),
                    whitespace_after_lambda=cst.SimpleWhitespace("  "),
                    params=cst.Parameters(),
                    colon=cst.Colon(whitespace_after=cst.SimpleWhitespace(" ")),
                    body=cst.Number(cst.Integer("5")),
                    rpar=(cst.RightParen(whitespace_before=cst.SimpleWhitespace(" ")),),
                ),
                "( lambda  : 5 )",
                CodePosition((1, 2), (1, 13)),
            ),
        )
    )
    def test_valid(
        self, node: cst.CSTNode, code: str, position: Optional[CodePosition] = None
    ) -> None:
        self.validate_node(node, code, expected_position=position)

    @data_provider(
        (
            (
                lambda: cst.Lambda(
                    cst.Parameters(params=(cst.Param(cst.Name("arg")),)),
                    cst.Number(cst.Integer("5")),
                    lpar=(cst.LeftParen(),),
                ),
                "left paren without right paren",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(params=(cst.Param(cst.Name("arg")),)),
                    cst.Number(cst.Integer("5")),
                    rpar=(cst.RightParen(),),
                ),
                "right paren without left paren",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(params=(cst.Param(cst.Name("arg")),)),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "at least one space after lambda",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("arg"), default=cst.Number(cst.Integer("5"))
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "at least one space after lambda",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(star_arg=cst.Param(cst.Name("arg"))),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "at least one space after lambda",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(kwonly_params=(cst.Param(cst.Name("arg")),)),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "at least one space after lambda",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(star_kwarg=cst.Param(cst.Name("arg"))),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "at least one space after lambda",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        star_kwarg=cst.Param(cst.Name("bar"), equal=cst.AssignEqual())
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "Must have a default when specifying an AssignEqual.",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(star_kwarg=cst.Param(cst.Name("bar"), star="***")),
                    cst.Number(cst.Integer("5")),
                ),
                r"Must specify either '', '\*' or '\*\*' for star.",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("bar"), default=cst.SimpleString('"one"')
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "Cannot have defaults for params",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(default_params=(cst.Param(cst.Name("bar")),)),
                    cst.Number(cst.Integer("5")),
                ),
                "Must have defaults for default_params",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(star_arg=cst.ParamStar()),
                    cst.Number(cst.Integer("5")),
                ),
                "Must have at least one kwonly param if ParamStar is used.",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(params=(cst.Param(cst.Name("bar"), star="*"),)),
                    cst.Number(cst.Integer("5")),
                ),
                "Expecting a star prefix of ''",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                star="*",
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "Expecting a star prefix of ''",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        kwonly_params=(cst.Param(cst.Name("bar"), star="*"),)
                    ),
                    cst.Number(cst.Integer("5")),
                ),
                "Expecting a star prefix of ''",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(star_arg=cst.Param(cst.Name("bar"), star="**")),
                    cst.Number(cst.Integer("5")),
                ),
                r"Expecting a star prefix of '\*'",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(star_kwarg=cst.Param(cst.Name("bar"), star="*")),
                    cst.Number(cst.Integer("5")),
                ),
                r"Expecting a star prefix of '\*\*'",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("arg"),
                                annotation=cst.Annotation(cst.Name("str")),
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "Lambda params cannot have type annotations",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("arg"),
                                default=cst.Number(cst.Integer("5")),
                                annotation=cst.Annotation(cst.Name("str")),
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "Lambda params cannot have type annotations",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        star_arg=cst.Param(
                            cst.Name("arg"), annotation=cst.Annotation(cst.Name("str"))
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "Lambda params cannot have type annotations",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        kwonly_params=(
                            cst.Param(
                                cst.Name("arg"),
                                annotation=cst.Annotation(cst.Name("str")),
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "Lambda params cannot have type annotations",
            ),
            (
                lambda: cst.Lambda(
                    cst.Parameters(
                        star_kwarg=cst.Param(
                            cst.Name("arg"), annotation=cst.Annotation(cst.Name("str"))
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(""),
                ),
                "Lambda params cannot have type annotations",
            ),
        )
    )
    def test_invalid(
        self, get_node: Callable[[], cst.CSTNode], expected_re: str
    ) -> None:
        self.assert_invalid(get_node, expected_re)


class LambdaParserTest(CSTNodeTest):
    @data_provider(
        (
            # Simple lambda
            (cst.Lambda(cst.Parameters(), cst.Number(cst.Integer("5"))), "lambda: 5"),
            # Test basic positional params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("bar"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(cst.Name("baz"), star=""),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                "lambda bar, baz: 5",
            ),
            # Test basic positional default params
            (
                cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("baz"),
                                default=cst.Number(cst.Integer("5")),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        )
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda bar = "one", baz = 5: 5',
            ),
            # Mixed positional and default params.
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("bar"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        default_params=(
                            cst.Param(
                                cst.Name("baz"),
                                default=cst.Number(cst.Integer("5")),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                "lambda bar, baz = 5: 5",
            ),
            # Test kwonly params
            (
                cst.Lambda(
                    cst.Parameters(
                        star_arg=cst.ParamStar(),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(cst.Name("baz"), star=""),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda *, bar = "one", baz: 5',
            ),
            # Mixed params and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("first"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("second"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        star_arg=cst.ParamStar(),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("baz"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("biz"),
                                default=cst.SimpleString('"two"'),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda first, second, *, bar = "one", baz, biz = "two": 5',
            ),
            # Mixed default_params and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        default_params=(
                            cst.Param(
                                cst.Name("first"),
                                default=cst.Number(cst.Float("1.0")),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("second"),
                                default=cst.Number(cst.Float("1.5")),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        star_arg=cst.ParamStar(),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("baz"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("biz"),
                                default=cst.SimpleString('"two"'),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda first = 1.0, second = 1.5, *, bar = "one", baz, biz = "two": 5',
            ),
            # Mixed params, default_params, and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("first"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("second"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        default_params=(
                            cst.Param(
                                cst.Name("third"),
                                default=cst.Number(cst.Float("1.0")),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("fourth"),
                                default=cst.Number(cst.Float("1.5")),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        star_arg=cst.ParamStar(),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("baz"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("biz"),
                                default=cst.SimpleString('"two"'),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda first, second, third = 1.0, fourth = 1.5, *, bar = "one", baz, biz = "two": 5',
            ),
            # Test star_arg
            (
                cst.Lambda(
                    cst.Parameters(star_arg=cst.Param(cst.Name("params"), star="*")),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                "lambda *params: 5",
            ),
            # Typed star_arg, include kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        star_arg=cst.Param(
                            cst.Name("params"),
                            star="*",
                            comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
                        ),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("baz"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("biz"),
                                default=cst.SimpleString('"two"'),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda *params, bar = "one", baz, biz = "two": 5',
            ),
            # Mixed params default_params, star_arg and kwonly_params
            (
                cst.Lambda(
                    cst.Parameters(
                        params=(
                            cst.Param(
                                cst.Name("first"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("second"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        default_params=(
                            cst.Param(
                                cst.Name("third"),
                                default=cst.Number(cst.Float("1.0")),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("fourth"),
                                default=cst.Number(cst.Float("1.5")),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                        ),
                        star_arg=cst.Param(
                            cst.Name("params"),
                            star="*",
                            comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
                        ),
                        kwonly_params=(
                            cst.Param(
                                cst.Name("bar"),
                                default=cst.SimpleString('"one"'),
                                equal=cst.AssignEqual(),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("baz"),
                                star="",
                                comma=cst.Comma(
                                    whitespace_after=cst.SimpleWhitespace(" ")
                                ),
                            ),
                            cst.Param(
                                cst.Name("biz"),
                                default=cst.SimpleString('"two"'),
                                equal=cst.AssignEqual(),
                                star="",
                            ),
                        ),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                'lambda first, second, third = 1.0, fourth = 1.5, *params, bar = "one", baz, biz = "two": 5',
            ),
            # Test star_arg and star_kwarg
            (
                cst.Lambda(
                    cst.Parameters(
                        star_kwarg=cst.Param(cst.Name("kwparams"), star="**")
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                "lambda **kwparams: 5",
            ),
            # Test star_arg and kwarg
            (
                cst.Lambda(
                    cst.Parameters(
                        star_arg=cst.Param(
                            cst.Name("params"),
                            star="*",
                            comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
                        ),
                        star_kwarg=cst.Param(cst.Name("kwparams"), star="**"),
                    ),
                    cst.Number(cst.Integer("5")),
                    whitespace_after_lambda=cst.SimpleWhitespace(" "),
                ),
                "lambda *params, **kwparams: 5",
            ),
            # Inner whitespace
            (
                cst.Lambda(
                    lpar=(cst.LeftParen(whitespace_after=cst.SimpleWhitespace(" ")),),
                    params=cst.Parameters(),
                    colon=cst.Colon(
                        whitespace_before=cst.SimpleWhitespace("  "),
                        whitespace_after=cst.SimpleWhitespace(" "),
                    ),
                    body=cst.Number(cst.Integer("5")),
                    rpar=(cst.RightParen(whitespace_before=cst.SimpleWhitespace(" ")),),
                ),
                "( lambda  : 5 )",
            ),
        )
    )
    def test_valid(
        self, node: cst.CSTNode, code: str, position: Optional[CodePosition] = None
    ) -> None:
        self.validate_node(node, code, parse_expression, position)