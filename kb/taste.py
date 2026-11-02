"""kb taste — taste notes and expression notes of the design pack (planning/design-stage, DEC-2026-11-01-10 · 11).

Pack-side tools. They never read task files; the contract-side `kb design check` never reads these notes (DEC-09).

A taste note belongs to one project or one brand, never to a person:
  $STRATA_VAULT/projects/<p>/design/taste.md        scope: project, owner: <p>
  $STRATA_VAULT/designs/<brand>/taste.md            scope: brand,   owner: <brand>
Four sections, every line in the person's words:
  ## 취향   - #tag 문장 — 승격 YYYY-MM-DD · 근거 [[brief-a]] [[brief-b]] [[brief-c]]
  ## 신호   - YYYY-MM-DD 반응|고름 #tag [[brief]] — "그 사람의 말"
  ## 추론   - [추론] #tag 문장 — YYYY-MM-DD           (the agent's inference; never a taste line until promoted)
  ## 거절   - YYYY-MM-DD #tag [[brief]] — "그 사람의 말" — 이유: …
A tag whose signals and rejections come from three or more different briefs is a promotion candidate. The check shows
candidates; only the person promotes (writes the taste line). Repeats inside one brief count once.

An expression note (expression.md beside the taste note) has one '## 원값' section and one '## 기법: <name>' section per
technique, each a readable paragraph followed by one ```yaml block:
  원값:  primitives: {color.surface: "#f2f4f7", opacity.glass: 0.6, blur.glass: 16px, …}
  기법:  derive: {glass.fill: "alpha(color.surface, opacity.glass)", …}
         layers: [{fill: glass.fill, blur: blur.glass}, …]       names only — no raw values
         relations: ["contrast(color.ink, glass.fill, color.page) >= 4.5", "lightness(glass.edge) > lightness(glass.fill)"]
Functions: lighten(c, d) · darken(c, d) move OKLCH lightness by d; alpha(c, a) sets opacity (0..1);
contrast(a, b[, on]) is the WCAG 2 ratio, a translucent colour composited over `on` first; lightness(c) is OKLCH L.

  python3 -m kb taste check       [taste.md …]        (default: every taste note in the vault)
  python3 -m kb taste expression  <expression.md> …   [--show]
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import yaml

TASTE_SECTIONS = ("취향", "신호", "추론", "거절")
PROMOTE_AT = 3
SIGNAL = re.compile(r'^- (\d{4}-\d{2}-\d{2}) (반응|고름) #(\S+) \[\[([^\]]+)\]\] — "(.+)"\s*$')
REJECT = re.compile(r'^- (\d{4}-\d{2}-\d{2}) #(\S+) \[\[([^\]]+)\]\] — "(.+)" — 이유: (\S.*)$')
INFER = re.compile(r"^- \[추론\] #(\S+) .+ — (\d{4}-\d{2}-\d{2})\s*$")
TASTE = re.compile(r"^- #(\S+) .+ — 승격 (\d{4}-\d{2}-\d{2}) · 근거 ((?:\[\[[^\]]+\]\]\s*)+)$")
LINK = re.compile(r"\[\[([^\]]+)\]\]")

LABEL = {
    "not-taste": "type 이 design-taste 가 아님",
    "place": "자리가 projects/<p>/design/taste.md 나 designs/<brand>/taste.md 가 아님 — 사람 단위 노트는 만들지 않는다",
    "scope": "scope·owner 가 자리와 맞지 않음",
    "sections": "절이 취향·신호·추론·거절 넷이 아님",
    "bad-signal": "신호 줄 형식: - YYYY-MM-DD 반응|고름 #tag [[brief]] — \"원문\"",
    "bad-reject": "거절 줄 형식: - YYYY-MM-DD #tag [[brief]] — \"원문\" — 이유: …",
    "bad-infer": "추론 줄 형식: - [추론] #tag 문장 — YYYY-MM-DD",
    "bad-taste": "취향 줄 형식: - #tag 문장 — 승격 YYYY-MM-DD · 근거 [[brief]] …",
    "infer-leak": "추론 표시가 추론 절 밖에 있음 — 추론은 승격 전에는 취향이 아니다",
    "thin-taste": f"취향 줄의 근거가 서로 다른 브리프 {PROMOTE_AT} 곳 미만이거나 그 태그의 신호에 없음",
}


# -- reading ---------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            try:
                fm = yaml.safe_load(text[4:end]) or {}
            except yaml.YAMLError:
                fm = {}
            return (fm if isinstance(fm, dict) else {}), text[end + 4:].lstrip("\n")
    return {}, text


def sections(body: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for line in body.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def _items(lines: list[str]) -> list[str]:
    return [l.rstrip() for l in lines if l.startswith("- ")]


# -- taste notes -----------------------------------------------------------

def place_of(path: Path, vault: Path | None) -> tuple[str, str] | None:
    """(scope, owner) the path allows, or None when the place is wrong."""
    try:
        rel = path.resolve().relative_to(vault.resolve()) if vault else None
    except ValueError:
        rel = None
    parts = rel.parts if rel else path.parts[-4:]
    if len(parts) >= 4 and parts[-4] == "projects" and parts[-2] == "design" and parts[-1] == "taste.md":
        return "project", parts[-3]
    if len(parts) >= 3 and parts[-3] == "designs" and parts[-1] == "taste.md":
        return "brand", parts[-2]
    return None


def check_taste(path: Path, vault: Path | None = None) -> tuple[list[tuple[str, str]], list[str]]:
    """(problems as (kind, detail), promotion candidate lines)."""
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    probs: list[tuple[str, str]] = []
    if fm.get("type") != "design-taste":
        probs.append(("not-taste", str(fm.get("type"))))
    place = place_of(path, vault)
    if place is None:
        probs.append(("place", str(path)))
    elif (fm.get("scope"), str(fm.get("owner"))) != place:
        probs.append(("scope", f"scope={fm.get('scope')} owner={fm.get('owner')}, 자리는 {place[0]} {place[1]}"))
    sec = sections(body)
    if tuple(sec) != TASTE_SECTIONS:
        probs.append(("sections", " · ".join(sec) or "없음"))
    briefs: dict[str, set[str]] = {}
    for line in _items(sec.get("신호", [])):
        m = SIGNAL.match(line)
        if not m:
            probs.append(("bad-signal", line)); continue
        briefs.setdefault(m.group(3), set()).add(m.group(4))
    for line in _items(sec.get("거절", [])):
        m = REJECT.match(line)
        if not m:
            probs.append(("bad-reject", line)); continue
        briefs.setdefault(m.group(2), set()).add(m.group(3))
    for line in _items(sec.get("추론", [])):
        if not INFER.match(line):
            probs.append(("bad-infer", line))
    for name in ("취향", "신호", "거절"):
        for line in _items(sec.get(name, [])):
            if "[추론]" in line:
                probs.append(("infer-leak", f"{name}: {line}"))
    promoted = set()
    for line in _items(sec.get("취향", [])):
        if "[추론]" in line:
            continue
        m = TASTE.match(line)
        if not m:
            probs.append(("bad-taste", line)); continue
        tag, refs = m.group(1), set(LINK.findall(m.group(3)))
        promoted.add(tag)
        known = briefs.get(tag, set())
        if len(refs) < PROMOTE_AT or not refs <= known:
            probs.append(("thin-taste", f"#{tag}: 근거 {len(refs)} 곳, 신호에 없는 근거 {sorted(refs - known)}"))
    cands = [f"#{t}: 브리프 {len(b)} 곳 ({' '.join(sorted(b))}) — 사람이 승격·보류·버림을 고른다"
             for t, b in sorted(briefs.items()) if len(b) >= PROMOTE_AT and t not in promoted]
    return probs, cands


def vault_taste_notes(vault: Path) -> list[Path]:
    out = list((vault / "projects").glob("*/design/taste.md")) + list((vault / "designs").glob("*/taste.md"))
    for p in vault.rglob("taste.md"):              # a taste note anywhere else is reported for its place
        if ".kb" not in p.parts and p not in out:
            fm, _ = split_frontmatter(p.read_text(encoding="utf-8"))
            if fm.get("type") == "design-taste":
                out.append(p)
    return sorted(out)


# -- colour ----------------------------------------------------------------

HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class Color:
    __slots__ = ("r", "g", "b", "a")

    def __init__(self, r: float, g: float, b: float, a: float = 1.0):
        self.r, self.g, self.b, self.a = r, g, b, a

    @classmethod
    def parse(cls, s: str) -> "Color":
        h = HEX.match(s.strip()).group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        v = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
        return cls(*v)

    def hex(self) -> str:
        cs = [self.r, self.g, self.b] + ([self.a] if self.a < 1 else [])
        return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in cs)

    def __repr__(self) -> str:
        return self.hex()


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_oklab(c: Color) -> tuple[float, float, float]:
    r, g, b = _lin(c.r), _lin(c.g), _lin(c.b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def from_oklab(L: float, A: float, B: float, alpha: float = 1.0) -> Color:
    l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return Color(*(max(0.0, min(1.0, _gam(max(0.0, x)))) for x in (r, g, b)), alpha)


def lightness(c: Color) -> float:
    return to_oklab(c)[0]


def shift(c: Color, d: float) -> Color:
    """Move OKLCH lightness by d, keeping hue and chroma (clamped into sRGB)."""
    L, A, B = to_oklab(c)
    return from_oklab(max(0.0, min(1.0, L + d)), A, B, c.a)


def over(fg: Color, bg: Color) -> Color:
    a = fg.a
    return Color(fg.r * a + bg.r * (1 - a), fg.g * a + bg.g * (1 - a), fg.b * a + bg.b * (1 - a), 1.0)


def luminance(c: Color) -> float:
    return 0.2126 * _lin(c.r) + 0.7152 * _lin(c.g) + 0.0722 * _lin(c.b)


def contrast(a: Color, b: Color, on: Color | None = None) -> float:
    if on is not None:
        a, b = (over(a, on) if a.a < 1 else a), (over(b, on) if b.a < 1 else b)
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# -- expression notes ------------------------------------------------------

class ExprError(Exception):
    pass


TOKEN = re.compile(r"\s*(?:(?P<num>-?\d+(?:\.\d+)?)(?![\w.])|(?P<name>[A-Za-z_][\w.\-]*)|(?P<hex>#[0-9a-fA-F]+)|(?P<op>[(),]))")
FUNCS = {"lighten": 2, "darken": 2, "alpha": 2, "contrast": (2, 3), "lightness": 1}
REL = re.compile(r"^(?P<lhs>.+?)\s*(?P<op>>=|<=|>|<|==)\s*(?P<rhs>.+)$")


def tokenize(s: str) -> list[tuple[str, str]]:
    out, i = [], 0
    while i < len(s):
        m = TOKEN.match(s, i)
        if not m or m.end() == i:
            if s[i:].strip() == "":
                break
            raise ExprError(f"읽을 수 없는 식: {s[i:]!r}")
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        i = m.end()
    return out


def parse(s: str):
    """AST: ('num', x) | ('ref', name) | ('raw', hex) | ('call', fn, [args])."""
    toks = tokenize(s)
    pos = 0

    def node():
        nonlocal pos
        if pos >= len(toks):
            raise ExprError(f"식이 끝남: {s!r}")
        kind, v = toks[pos]; pos += 1
        if kind == "num":
            return ("num", float(v))
        if kind == "hex":
            return ("raw", v)
        if kind == "name":
            if pos < len(toks) and toks[pos] == ("op", "("):
                if v not in FUNCS:
                    raise ExprError(f"모르는 함수: {v}")
                pos += 1
                args = []
                while True:
                    args.append(node())
                    k2, v2 = toks[pos] if pos < len(toks) else ("", "")
                    pos += 1
                    if v2 == ")":
                        break
                    if v2 != ",":
                        raise ExprError(f"쉼표나 닫는 괄호가 필요함: {s!r}")
                n = FUNCS[v]
                if len(args) not in (n if isinstance(n, tuple) else (n,)):
                    raise ExprError(f"{v} 의 인자 수가 맞지 않음: {s!r}")
                return ("call", v, args)
            return ("ref", v)
        raise ExprError(f"예상하지 못한 {v!r}: {s!r}")

    tree = node()
    if pos != len(toks):
        raise ExprError(f"식 뒤에 남은 것이 있음: {s!r}")
    return tree


def refs(tree) -> set[str]:
    if tree[0] == "ref":
        return {tree[1]}
    if tree[0] == "call":
        return set().union(*(refs(a) for a in tree[2]))
    return set()


def raws(tree) -> list[str]:
    if tree[0] == "raw":
        return [tree[1]]
    if tree[0] == "call":
        return [r for a in tree[2] for r in raws(a)]
    return []


def literal(v):
    """A primitive value: Color, float, or the string as written (dimensions, font names)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    if HEX.match(s):
        return Color.parse(s)
    return s


def evaluate(tree, env: dict):
    kind = tree[0]
    if kind == "num":
        return tree[1]
    if kind == "raw":
        return Color.parse(tree[1])
    if kind == "ref":
        return env[tree[1]]
    fn, args = tree[1], [evaluate(a, env) for a in tree[2]]
    if fn in ("lighten", "darken", "alpha", "lightness") and not isinstance(args[0], Color):
        raise ExprError(f"{fn} 의 첫 인자가 색이 아님")
    if fn in ("lighten", "darken", "alpha") and not isinstance(args[1], float):
        raise ExprError(f"{fn} 의 둘째 인자가 수가 아님")
    if fn == "lighten":
        return shift(args[0], args[1])
    if fn == "darken":
        return shift(args[0], -args[1])
    if fn == "alpha":
        if not 0 <= args[1] <= 1:
            raise ExprError(f"투명도 {args[1]} 이 0~1 밖")
        c = args[0]
        return Color(c.r, c.g, c.b, args[1])
    if fn == "lightness":
        return lightness(args[0])
    if not all(isinstance(a, Color) for a in args):
        raise ExprError("contrast 의 인자가 색이 아님")
    return contrast(*args)


YAML_BLOCK = re.compile(r"```ya?ml\n(.*?)```", re.S)

XLABEL = {
    "not-expression": "type 이 design-expression 이 아님",
    "no-primitives": "'## 원값' 절이 없거나 primitives 가 없음",
    "no-block": "절에 YAML 블록이 하나가 아님",
    "no-text": "블록 앞에 사람이 읽는 문장이 없음",
    "bad-yaml": "YAML 을 읽을 수 없음",
    "bad-opacity": "투명도 원값이 0~1 밖",
    "unknown-ref": "없는 이름을 참조함",
    "raw-value": "기법이 원값 이름 대신 값을 직접 씀",
    "cycle": "유도 값이 서로를 참조함",
    "bad-expr": "식을 계산할 수 없음",
    "no-relations": "기법에 관계식이 없음 — 배색 판단은 관계로 적는다",
    "relation-fails": "관계식이 성립하지 않음",
}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_expression(path: Path) -> tuple[list[tuple[str, str]], dict[str, dict]]:
    """(problems, computed values per technique)."""
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    probs: list[tuple[str, str]] = []
    if fm.get("type") != "design-expression":
        probs.append(("not-expression", str(fm.get("type"))))
    sec = {k: "\n".join(v) for k, v in sections(body).items()}
    blocks: dict[str, dict] = {}
    for name, text in sec.items():
        if name != "원값" and not name.startswith("기법:"):
            continue
        found = YAML_BLOCK.findall(text)
        if len(found) != 1:
            probs.append(("no-block", name)); continue
        if not text.split("```", 1)[0].strip():
            probs.append(("no-text", name))
        try:
            d = yaml.safe_load(found[0]) or {}
        except yaml.YAMLError as e:
            probs.append(("bad-yaml", f"{name}: {e}".splitlines()[0])); continue
        blocks[name] = d if isinstance(d, dict) else {}
    prims_raw = (blocks.get("원값") or {}).get("primitives")
    if not isinstance(prims_raw, dict):
        probs.append(("no-primitives", str(path)))
        prims_raw = {}
    prims = {str(k): literal(v) for k, v in prims_raw.items()}
    for k, v in prims.items():
        if k.startswith("opacity.") and (not _num(v) or not 0 <= v <= 1):
            probs.append(("bad-opacity", f"{k}: {prims_raw[k]}"))
    computed: dict[str, dict] = {}
    for name, d in blocks.items():
        if name == "원값":
            continue
        derive = {str(k): str(v) for k, v in (d.get("derive") or {}).items()}
        layers = d.get("layers") or []
        relations = [str(r) for r in (d.get("relations") or [])]
        trees: dict[str, tuple] = {}
        for k, expr in derive.items():
            try:
                trees[k] = parse(expr)
            except ExprError as e:
                probs.append(("bad-expr", f"{name} {k}: {e}"))
        for k, t in trees.items():
            for r in raws(t):
                probs.append(("raw-value", f"{name} {k}: {r}"))
        names = set(prims) | set(derive)
        for k, t in trees.items():
            for r in sorted(refs(t) - names):
                probs.append(("unknown-ref", f"{name} {k}: {r}"))
        for i, layer in enumerate(layers if isinstance(layers, list) else []):
            for prop, v in (layer.items() if isinstance(layer, dict) else []):
                if _num(v) or (isinstance(v, str) and (HEX.match(v.strip()) or re.match(r"^-?\d", v.strip()))):
                    probs.append(("raw-value", f"{name} 겹 {i + 1} {prop}: {v}"))
                elif isinstance(v, str) and v not in names:
                    probs.append(("unknown-ref", f"{name} 겹 {i + 1} {prop}: {v}"))
        env: dict = dict(prims)
        state: dict[str, int] = {}

        def resolve(k: str, chain: tuple = ()) -> bool:
            if k in env:
                return True
            if k not in trees:
                return False
            if state.get(k) == 1:
                probs.append(("cycle", f"{name}: {' → '.join(chain + (k,))}"))
                return False
            state[k] = 1
            ok = all(resolve(r, chain + (k,)) for r in refs(trees[k]) if r not in prims)
            state[k] = 2
            if not ok:
                return False
            try:
                env[k] = evaluate(trees[k], env)
            except (ExprError, KeyError) as e:
                probs.append(("bad-expr", f"{name} {k}: {e}"))
                return False
            return True

        for k in trees:
            resolve(k)
        computed[name] = {k: env[k] for k in derive if k in env}
        if not relations:
            probs.append(("no-relations", name))
        for rel in relations:
            m = REL.match(rel)
            if not m:
                probs.append(("bad-expr", f"{name}: {rel}")); continue
            try:
                lt, rt = parse(m.group("lhs")), parse(m.group("rhs"))
                for r in raws(lt) + raws(rt):
                    probs.append(("raw-value", f"{name} 관계식: {r}"))
                missing = sorted((refs(lt) | refs(rt)) - set(env))
                if missing:
                    probs.append(("unknown-ref", f"{name} 관계식 {rel}: {', '.join(missing)}")); continue
                lv, rv = evaluate(lt, env), evaluate(rt, env)
            except ExprError as e:
                probs.append(("bad-expr", f"{name} {rel}: {e}")); continue
            if not (_num(lv) and _num(rv)):
                probs.append(("bad-expr", f"{name} {rel}: 양쪽이 수가 아님")); continue
            ok = {">=": lv >= rv, "<=": lv <= rv, ">": lv > rv, "<": lv < rv, "==": abs(lv - rv) < 1e-9}[m.group("op")]
            computed[name][rel] = round(lv, 3)
            if not ok:
                probs.append(("relation-fails", f"{name}: {rel} — 계산값 {lv:.3f}"))
    return probs, computed


# -- cli -------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb taste", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("paths", nargs="*")
    x = sub.add_parser("expression"); x.add_argument("paths", nargs="+"); x.add_argument("--show", action="store_true")
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    problems = 0
    if a.cmd == "check":
        files = [Path(p) for p in a.paths] if a.paths else (vault_taste_notes(vault) if vault else [])
        files = [f for f in files if f.suffix == ".md"]              # task files are never read
        for f in files:
            probs, cands = check_taste(f, vault)
            for k, d in probs:
                print(f"{f}: {LABEL[k]} — {d}")
            for line in cands:
                print(f"{f}: 승격 후보 {line}")
            problems += len(probs)
        print(f"취향 노트 {len(files)} · 문제 {problems}")
        return 1 if problems else 0
    files = [Path(p) for p in a.paths if p.endswith(".md")]
    for f in files:
        probs, comp = check_expression(f)
        for k, d in probs:
            print(f"{f}: {XLABEL[k]} — {d}")
        if a.show:
            for tech, vals in comp.items():
                print(f"{f}: {tech}")
                for k, v in vals.items():
                    print(f"    {k} = {v}")
        problems += len(probs)
    print(f"표현 노트 {len(files)} · 문제 {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
