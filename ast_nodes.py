from dataclasses import dataclass


@dataclass
class Program:
    statements: list


@dataclass
class Declaration:
    var_type: str
    name: str
    expr: object
    line: int


@dataclass
class Assignment:
    name: str
    expr: object
    line: int


@dataclass
class IfStmt:
    condition: object
    body: list
    line: int


@dataclass
class WhileStmt:
    condition: object
    body: list
    line: int


@dataclass
class PrintStmt:
    expr: object
    line: int


@dataclass
class BinaryOp:
    op: str
    left: object
    right: object
    line: int


@dataclass
class Identifier:
    name: str
    line: int


@dataclass
class Number:
    value: str
    line: int


@dataclass
class StringLit:
    value: str
    line: int


@dataclass
class BoolLit:
    value: bool
    line: int


@dataclass
class Cast:
    target_type: str
    expr: object
    line: int