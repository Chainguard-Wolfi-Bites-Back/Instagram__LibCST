# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import ast
import builtins
import dataclasses
import functools
import sys
from typing import cast, Dict, List, Optional, Sequence, Set, Tuple, Union

from typing_extensions import TypeAlias

import libcst as cst
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand


@functools.lru_cache()
def _empty_module() -> cst.Module:
    return cst.parse_module("")


def _code_for_node(node: cst.CSTNode) -> str:
    return _empty_module().code_for_node(node)


def _ast_for_statement(node: cst.CSTNode) -> ast.stmt:
    """
    Get the type-comment-enriched python AST for a node.

    If there are illegal type comments, this can return a SyntaxError.
    In that case, return the same node with no type comments (which will
    cause this codemod to ignore it).
    """
    code = _code_for_node(node)
    try:
        return ast.parse(code, type_comments=True).body[-1]
    except SyntaxError:
        return ast.parse(code, type_comments=False).body[-1]


def _parse_type_comment(
    type_comment: Optional[str],
) -> Optional[ast.expr]:
    """
    Attempt to parse a type comment. If it is None or if it fails to parse,
    return None.
    """
    if type_comment is None:
        return None
    try:
        # pyre-ignore[16]: the ast module stubs do not have full details
        return ast.parse(type_comment, "<type_comment>", "eval").body
    except SyntaxError:
        return None


def _annotation_for_statement(
    node: cst.CSTNode,
) -> Optional[ast.expr]:
    return _parse_type_comment(_ast_for_statement(node).type_comment)


def _parse_func_type_comment(
    func_type_comment: Optional[str],
) -> Optional["ast.FunctionType"]:
    if func_type_comment is None:
        return None
    return cast(
        ast.FunctionType,
        ast.parse(func_type_comment, "<func_type_comment>", "func_type"),
    )


@functools.lru_cache()
def _builtins() -> Set[str]:
    return set(dir(builtins))


def _is_builtin(annotation: str) -> bool:
    return annotation in _builtins()


def _convert_annotation(raw: str) -> cst.Annotation:
    # Convert annotation comments to string annotations to be safe,
    # otherwise runtime errors would be common.
    #
    # Special-case builtins to reduce the amount of quoting noise.
    #
    # NOTE: we could potentially detect more cases for skipping quotes
    # using ScopeProvider, which would make the output prettier.
    if _is_builtin(raw):
        return cst.Annotation(annotation=cst.Name(value=raw))
    else:
        return cst.Annotation(annotation=cst.SimpleString(f'"{raw}"'))


def _is_type_comment(comment: Optional[cst.Comment]) -> bool:
    """
    Determine whether a comment is a type comment.

    Unfortunately, to strip type comments in a location-invariant way requires
    finding them from pure libcst data. We only use this in function defs, where
    the precise cst location of the type comment cna be hard to predict.
    """
    if comment is None:
        return False
    value = comment.value[1:].strip()
    if not value.startswith("type:"):
        return False
    suffix = value.removeprefix("type:").strip().split()
    if len(suffix) > 0 and suffix[0] == "ignore":
        return False
    return True


class _FailedToApplyAnnotation:
    pass


class _ArityError(Exception):
    pass


UnpackedBindings: TypeAlias = Union[cst.BaseExpression, List["UnpackedBindings"]]
UnpackedAnnotations: TypeAlias = Union[str, List["UnpackedAnnotations"]]
TargetAnnotationPair: TypeAlias = Tuple[cst.BaseExpression, str]


class AnnotationSpreader:
    """
    Utilities to help with lining up tuples of types from type comments with
    the tuples of values with which they should be associated.
    """

    @staticmethod
    def unpack_annotation(
        expression: ast.expr,
    ) -> UnpackedAnnotations:
        if isinstance(expression, ast.Tuple):
            return [
                AnnotationSpreader.unpack_annotation(elt) for elt in expression.elts
            ]
        else:
            return ast.unparse(expression)

    @staticmethod
    def unpack_target(
        target: cst.BaseExpression,
    ) -> UnpackedBindings:
        """
        Take a (non-function-type) type comment and split it into
        components. A type comment body should always be either a single
        type or a tuple of types.

        We work with strings for annotations because without detailed scope
        analysis that is the safest option for codemods.
        """
        if isinstance(target, cst.Tuple):
            return [
                AnnotationSpreader.unpack_target(element.value)
                for element in target.elements
            ]
        else:
            return target

    @staticmethod
    def annotated_bindings(
        bindings: UnpackedBindings,
        annotations: UnpackedAnnotations,
    ) -> List[Tuple[cst.BaseAssignTargetExpression, str]]:
        if isinstance(annotations, list):
            if isinstance(bindings, list) and len(bindings) == len(annotations):
                # The arities match, so we return the flattened result of
                # mapping annotated_bindings over each pair.
                out: List[Tuple[cst.BaseAssignTargetExpression, str]] = []
                for binding, annotation in zip(bindings, annotations):
                    out.extend(
                        AnnotationSpreader.annotated_bindings(binding, annotation)
                    )
                return out
            else:
                # Either mismatched lengths, or multi-type and one-target
                raise _ArityError()
        elif isinstance(bindings, list):
            # multi-target and one-type
            raise _ArityError()
        else:
            assert isinstance(bindings, cst.BaseAssignTargetExpression)
            return [(bindings, annotations)]

    @staticmethod
    def type_declaration(
        binding: cst.BaseAssignTargetExpression,
        raw_annotation: str,
    ) -> cst.AnnAssign:
        return cst.AnnAssign(
            target=binding,
            annotation=_convert_annotation(raw=raw_annotation),
            value=None,
        )

    @staticmethod
    def type_declaration_statements(
        bindings: UnpackedBindings,
        annotations: UnpackedAnnotations,
        leading_lines: Sequence[cst.EmptyLine],
    ) -> List[cst.SimpleStatementLine]:
        return [
            cst.SimpleStatementLine(
                body=[
                    AnnotationSpreader.type_declaration(
                        binding=binding,
                        raw_annotation=raw_annotation,
                    )
                ],
                leading_lines=leading_lines if i == 0 else [],
            )
            for i, (binding, raw_annotation) in enumerate(
                AnnotationSpreader.annotated_bindings(
                    bindings=bindings,
                    annotations=annotations,
                )
            )
        ]


def convert_Assign(
    node: cst.Assign,
    annotation: ast.expr,
) -> Union[
    _FailedToApplyAnnotation,
    cst.AnnAssign,
    List[Union[cst.AnnAssign, cst.Assign]],
]:
    # zip the type and target information tother. If there are mismatched
    # arities, this is a PEP 484 violation (technically we could use
    # logic beyond the PEP to recover some cases as typing.Tuple, but this
    # should be rare) so we give up.
    try:
        annotations = AnnotationSpreader.unpack_annotation(annotation)
        annotated_targets = [
            AnnotationSpreader.annotated_bindings(
                bindings=AnnotationSpreader.unpack_target(target.target),
                annotations=annotations,
            )
            for target in node.targets
        ]
    except _ArityError:
        return _FailedToApplyAnnotation()
    if len(annotated_targets) == 1 and len(annotated_targets[0]) == 1:
        # We can convert simple one-target assignments into a single AnnAssign
        binding, raw_annotation = annotated_targets[0][0]
        return cst.AnnAssign(
            target=binding,
            annotation=_convert_annotation(raw=raw_annotation),
            value=node.value,
            semicolon=node.semicolon,
        )
    else:
        # For multi-target assigns (regardless of whether they are using tuples
        # on the LHS or multiple `=` tokens or both), we need to add a type
        # declaration per individual LHS target.
        type_declarations = [
            AnnotationSpreader.type_declaration(binding, raw_annotation)
            for annotated_bindings in annotated_targets
            for binding, raw_annotation in annotated_bindings
        ]
        return [
            *type_declarations,
            node,
        ]


@dataclasses.dataclass(frozen=True)
class FunctionTypeInfo:
    arguments: Dict[str, Optional[str]]
    returns: Optional[str]

    def is_empty(self) -> bool:
        return self.returns is None and self.arguments == {}

    @classmethod
    def from_cst(
        cls,
        node_cst: cst.FunctionDef,
    ) -> "FunctionTypeInfo":
        """
        Using the `ast` type comment extraction logic, get type information
        for a function definition.

        To understand edge case behavior see the `leave_FunctionDef` docstring.
        """
        node_ast = cast(ast.FunctionDef, _ast_for_statement(node_cst))
        # Note: this is guaranteed to have the correct arity.
        args = [
            *node_ast.args.posonlyargs,
            *node_ast.args.args,
            *(
                []
                if node_ast.args.vararg is None
                else [
                    node_ast.args.vararg,
                ]
            ),
            *node_ast.args.kwonlyargs,
            *(
                []
                if node_ast.args.kwarg is None
                else [
                    node_ast.args.kwarg,
                ]
            ),
        ]
        try:
            func_type_annotation = _parse_func_type_comment(node_ast.type_comment)
        except SyntaxError:
            # On unparsable function type annotations, ignore type information
            return cls({}, None)
        if func_type_annotation is None:
            return cls(
                arguments={
                    arg.arg: arg.type_comment
                    for arg in args
                    if arg.type_comment is not None
                },
                returns=None,
            )
        else:
            argtypes = func_type_annotation.argtypes
            returns = ast.unparse(func_type_annotation.returns)
            if (
                len(argtypes) == 1
                and isinstance(argtypes[0], ast.Constant)
                # pyre-ignore [16] Pyre cannot refine constant indexes (yet!)
                and argtypes[0].value is Ellipsis
            ):
                # Only use the return type if the comment was like `(...) -> R`
                return cls(
                    arguments={arg.arg: arg.type_comment for arg in args},
                    returns=returns,
                )
            elif len(argtypes) == len(args):
                # Merge the type comments, preferring inline comments where available
                return cls(
                    arguments={
                        arg.arg: arg.type_comment or ast.unparse(from_func_type)
                        for arg, from_func_type in zip(args, argtypes)
                    },
                    returns=returns,
                )
            else:
                # On arity mismatches, ignore the type information
                return cls({}, None)


class ConvertTypeComments(VisitorBasedCodemodCommand):
    """
    Codemod that converts type comments into Python 3.6+ style
    annotations.

    We can handle type comments in the following statement types:
    - Assign
      - This is converted into a single AnnAssign when possible
      - In more complicated cases it will produce multiple AnnAssign
        nodes with no value (i.e. "type declaration" statements)
        followed by an Assign
    - For and With
      - We prepend both of these with type declaration statements.
    - FunctionDef
      - We apply all the types we can find. If we find several:
        - We prefer any existing annotations to type comments
        - For parameters, we prefer inline type comments to
          function-level type comments if we find both.

    We always apply the type comments as quoted annotations, unless
    we know that it refers to a builtin. We do not guarantee that
    the resulting string annotations would parse, but they should
    never cause failures at module import time.

    We attempt to:
    - Always strip type comments for statements where we successfully
      applied types.
    - Never strip type comments for statements where we failed to
      apply types.

    There are many edge case possible where the arity of a type
    hint (which is either a tuple or a func_type) might not match
    the code. In these cases we generally give up:
    - For Assign, For, and With, we require that every target of
      bindings (e.g. a tuple of names being bound) must have exactly
      the same arity as the comment.
      - So, for example, we would skip an assignment statement such as
        ``x = y, z = 1, 2  # type: int, int`` because the arity
        of ``x`` does not match the arity of the hint.
    - For FunctionDef, we do *not* check arity of inline parameter
      type comments but we do skip the transform if the arity of
      the function does not match the function-level comment.
    """

    # Finding the location of a type comment in a FunctionDef is difficult.
    #
    # As a result, if when visiting a FunctionDef header we are able to
    # successfully extrct type information then we aggressively strip type
    # comments until we reach the first statement in the body.
    #
    # Once we get there we have to stop, so that we don't unintentionally remove
    # unprocessed type comments.
    #
    # This state handles tracking everything we need for this.
    function_type_info_stack: List[FunctionTypeInfo]
    function_body_stack: List[cst.BaseSuite]
    aggressively_strip_type_comments: bool

    def __init__(self, context: CodemodContext) -> None:
        if (sys.version_info.major, sys.version_info.minor) < (3, 9):
            # The ast module did not get `unparse` until Python 3.9,
            # or `type_comments` until Python 3.8
            #
            # For earlier versions of python, raise early instead of failing
            # later. It might be possible to use libcst parsing and the
            # typed_ast library to support earlier python versions, but this is
            # not a high priority.
            raise NotImplementedError(
                "You are trying to run ConvertTypeComments, but libcst "
                + "needs to be running with Python 3.9+ in order to "
                + "do this. Try using Python 3.9+ to run your codemod. "
                + "Note that the target code can be using Python 3.6+, "
                + "it is only libcst that needs a new Python version."
            )
        super().__init__(context)
        self.function_type_info_stack = []
        self.function_body_stack = []
        self.aggressively_strip_type_comments = False

    def _strip_TrailingWhitespace(
        self,
        node: cst.TrailingWhitespace,
    ) -> cst.TrailingWhitespace:
        return node.with_changes(
            whitespace=cst.SimpleWhitespace(
                ""
            ),  # any whitespace came before the comment, so strip it.
            comment=None,
        )

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> Union[cst.SimpleStatementLine, cst.FlattenSentinel]:
        """
        Convert any SimpleStatementLine containing an Assign with a
        type comment into a one that uses a PEP 526 AnnAssign.
        """
        # determine whether to apply an annotation
        assign = updated_node.body[-1]
        if not isinstance(assign, cst.Assign):  # only Assign matters
            return updated_node
        annotation = _annotation_for_statement(original_node)
        if annotation is None:
            return updated_node
        # At this point have a single-line Assign with a type comment.
        # Convert it to an AnnAssign and strip the comment.
        converted = convert_Assign(
            node=assign,
            annotation=annotation,
        )
        if isinstance(converted, _FailedToApplyAnnotation):
            # We were unable to consume the type comment, so return the
            # original code unchanged.
            # TODO: allow stripping the invalid type comments via a flag
            return updated_node
        elif isinstance(converted, cst.AnnAssign):
            # We were able to convert the Assign into an AnnAssign, so
            # we can update the node.
            return updated_node.with_changes(
                body=[*updated_node.body[:-1], converted],
                trailing_whitespace=self._strip_TrailingWhitespace(
                    updated_node.trailing_whitespace,
                ),
            )
        elif isinstance(converted, list):
            # We need to inject two or more type declarations.
            #
            # In this case, we need to split across multiple lines, and
            # this also means we'll spread any multi-statement lines out
            # (multi-statement lines are PEP 8 violating anyway).
            #
            # We still preserve leading lines from before our transform.
            new_statements = [
                *(
                    statement.with_changes(
                        semicolon=cst.MaybeSentinel.DEFAULT,
                    )
                    for statement in updated_node.body[:-1]
                ),
                *converted,
            ]
            if len(new_statements) < 2:
                raise RuntimeError("Unreachable code.")
            return cst.FlattenSentinel(
                [
                    updated_node.with_changes(
                        body=[new_statements[0]],
                        trailing_whitespace=self._strip_TrailingWhitespace(
                            updated_node.trailing_whitespace,
                        ),
                    ),
                    *(
                        cst.SimpleStatementLine(body=[statement])
                        for statement in new_statements[1:]
                    ),
                ]
            )
        else:
            raise RuntimeError(f"Unhandled value {converted}")

    def leave_For(
        self,
        original_node: cst.For,
        updated_node: cst.For,
    ) -> Union[cst.For, cst.FlattenSentinel]:
        """
        Convert a For with a type hint on the bound variable(s) to
        use type declarations.
        """
        # Type comments are only possible when the body is an indented
        # block, and we need this refinement to work with the header,
        # so we check and only then extract the type comment.
        body = updated_node.body
        if not isinstance(body, cst.IndentedBlock):
            return updated_node
        annotation = _annotation_for_statement(original_node)
        if annotation is None:
            return updated_node
        # Zip up the type hint and the bindings. If we hit an arity
        # error, abort.
        try:
            type_declarations = AnnotationSpreader.type_declaration_statements(
                bindings=AnnotationSpreader.unpack_target(updated_node.target),
                annotations=AnnotationSpreader.unpack_annotation(annotation),
                leading_lines=updated_node.leading_lines,
            )
        except _ArityError:
            return updated_node
        # There is no arity error, so we can add the type delaration(s)
        return cst.FlattenSentinel(
            [
                *type_declarations,
                updated_node.with_changes(
                    body=body.with_changes(
                        header=self._strip_TrailingWhitespace(body.header)
                    ),
                    leading_lines=[],
                ),
            ]
        )

    def leave_With(
        self,
        original_node: cst.With,
        updated_node: cst.With,
    ) -> Union[cst.With, cst.FlattenSentinel]:
        """
        Convert a With with a type hint on the bound variable(s) to
        use type declarations.
        """
        # Type comments are only possible when the body is an indented
        # block, and we need this refinement to work with the header,
        # so we check and only then extract the type comment.
        body = updated_node.body
        if not isinstance(body, cst.IndentedBlock):
            return updated_node
        annotation = _annotation_for_statement(original_node)
        if annotation is None:
            return updated_node
        # PEP 484 does not attempt to specify type comment semantics for
        # multiple with bindings (there's more than one sensible way to
        # do it), so we make no attempt to handle this
        targets = [
            item.asname.name for item in updated_node.items if item.asname is not None
        ]
        if len(targets) != 1:
            return updated_node
        target = targets[0]
        # Zip up the type hint and the bindings. If we hit an arity
        # error, abort.
        try:
            type_declarations = AnnotationSpreader.type_declaration_statements(
                bindings=AnnotationSpreader.unpack_target(target),
                annotations=AnnotationSpreader.unpack_annotation(annotation),
                leading_lines=updated_node.leading_lines,
            )
        except _ArityError:
            return updated_node
        # There is no arity error, so we can add the type delaration(s)
        return cst.FlattenSentinel(
            [
                *type_declarations,
                updated_node.with_changes(
                    body=body.with_changes(
                        header=self._strip_TrailingWhitespace(body.header)
                    ),
                    leading_lines=[],
                ),
            ]
        )

    # Handle function definitions -------------------------

    # **Implementation Notes**
    #
    # It is much harder to predict where exactly type comments will live
    # in function definitions than in Assign / For / With.
    #
    # As a result, we use two different patterns:
    # (A) we aggressively strip out type comments from whitespace between the
    #     start of a function define and the start of the body, whenever we were
    #     able to extract type information. This is done via mutable state and the
    #     usual visitor pattern.
    # (B) we also manually reach down to the first statement inside of the
    #     funciton body and aggressively strip type comments from leading
    #     whitespaces

    def visit_FunctionDef(
        self,
        node: cst.FunctionDef,
    ) -> None:
        """
        Set up the data we need to handle function definitions:
        - Parse the type comments.
        - Store the resulting function type info on the stack, where it will
          remain until we use it in `leave_FunctionDef`
        - Set that we are aggressively stripping type comments, which will
          remain true until we visit the body.
        """
        function_type_info = FunctionTypeInfo.from_cst(node)
        self.aggressively_strip_type_comments = not function_type_info.is_empty()
        self.function_type_info_stack.append(function_type_info)
        self.function_body_stack.append(node.body)

    def leave_TrailingWhitespace(
        self,
        original_node: cst.TrailingWhitespace,
        updated_node: cst.TrailingWhitespace,
    ) -> Union[cst.TrailingWhitespace]:
        "Aggressively remove type comments when in header if we extracted types."
        if self.aggressively_strip_type_comments and _is_type_comment(
            updated_node.comment
        ):
            return cst.TrailingWhitespace()
        else:
            return updated_node

    def leave_EmptyLine(
        self,
        original_node: cst.EmptyLine,
        updated_node: cst.EmptyLine,
    ) -> Union[cst.EmptyLine, cst.RemovalSentinel]:
        "Aggressively remove type comments when in header if we extracted types."
        if self.aggressively_strip_type_comments and _is_type_comment(
            updated_node.comment
        ):
            return cst.RemovalSentinel.REMOVE
        else:
            return updated_node

    def visit_FunctionDef_body(
        self,
        node: cst.FunctionDef,
    ) -> None:
        "Turn off aggressive type comment removal when we've leaved the header."
        self.aggressively_strip_type_comments = False

    def leave_IndentedBlock(
        self,
        original_node: cst.IndentedBlock,
        updated_node: cst.IndentedBlock,
    ) -> cst.IndentedBlock:
        "When appropriate, strip function type comment from the function body."
        # abort unless this is the body of a function we are transforming
        if len(self.function_body_stack) == 0:
            return updated_node
        if original_node is not self.function_body_stack[-1]:
            return updated_node
        if self.function_type_info_stack[-1].is_empty():
            return updated_node
        # The comment will be in the body header if it was on the same line
        # as the colon.
        if _is_type_comment(updated_node.header.comment):
            updated_node = updated_node.with_changes(
                header=cst.TrailingWhitespace(),
            )
        # The comment will be in a leading line of the first body statement
        # if it was on the first line after the colon.
        first_statement = updated_node.body[0]
        if not hasattr(first_statement, "leading_lines"):
            return updated_node
        return updated_node.with_changes(
            body=[
                first_statement.with_changes(
                    leading_lines=[
                        line
                        # pyre-ignore[16]: we refined via `hasattr`
                        for line in first_statement.leading_lines
                        if not _is_type_comment(line.comment)
                    ]
                ),
                *updated_node.body[1:],
            ]
        )

    # Methods for adding type annotations ----
    #
    # By the time we get here, all type comments should already be stripped.

    def leave_Param(
        self,
        original_node: cst.Param,
        updated_node: cst.Param,
    ) -> cst.Param:
        # ignore type comments if there's already an annotation
        if updated_node.annotation is not None:
            return updated_node
        # find out if there's a type comment and apply it if so
        function_type_info = self.function_type_info_stack[-1]
        raw_annotation = function_type_info.arguments.get(updated_node.name.value)
        if raw_annotation is not None:
            return updated_node.with_changes(
                annotation=_convert_annotation(raw=raw_annotation)
            )
        else:
            return updated_node

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        self.function_body_stack.pop()
        function_type_info = self.function_type_info_stack.pop()
        if updated_node.returns is None and function_type_info.returns is not None:
            return updated_node.with_changes(
                returns=_convert_annotation(raw=function_type_info.returns)
            )
        else:
            return updated_node
