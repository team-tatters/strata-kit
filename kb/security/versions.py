"""Version comparison for the matcher (order 2026.11.03-02 task-02): Debian/Ubuntu package versions (dpkg algorithm:
epoch, upstream, revision, with ~ sorting before everything), PEP 440-ish and semver-ish dotted versions, and a
range test (introduced ≤ v < fixed, or v ≤ last_affected). Unparsable input gives None, never a silent False."""
from __future__ import annotations

import re


def _deb_order(c: str) -> int:
    if c == "~":
        return -1
    if c.isdigit():
        return 0
    if c.isalpha():
        return ord(c)
    return ord(c) + 256


def _deb_cmp_part(a: str, b: str) -> int:
    while a or b:
        # non-digit prefix
        ia = 0
        while ia < len(a) and not a[ia].isdigit():
            ia += 1
        ib = 0
        while ib < len(b) and not b[ib].isdigit():
            ib += 1
        pa, pb = a[:ia], b[:ib]
        a, b = a[ia:], b[ib:]
        for x, y in zip(pa.ljust(max(len(pa), len(pb)), "\0"), pb.ljust(max(len(pa), len(pb)), "\0")):
            ox = -2 if x == "\0" else _deb_order(x)
            oy = -2 if y == "\0" else _deb_order(y)
            if x == "\0" and y == "~":
                return 1
            if y == "\0" and x == "~":
                return -1
            if ox != oy:
                return -1 if ox < oy else 1
        # digit prefix
        ia = 0
        while ia < len(a) and a[ia].isdigit():
            ia += 1
        ib = 0
        while ib < len(b) and b[ib].isdigit():
            ib += 1
        na, nb = int(a[:ia] or 0), int(b[:ib] or 0)
        a, b = a[ia:], b[ib:]
        if na != nb:
            return -1 if na < nb else 1
    return 0


def deb_cmp(a: str, b: str) -> int:
    def split(v: str):
        epoch, rest = (v.split(":", 1) + [None])[:2] if ":" in v else ("0", v)
        if rest is None:
            rest = v
        up, rev = rest.rsplit("-", 1) if "-" in rest else (rest, "0")
        return int(epoch) if epoch.isdigit() else 0, up, rev
    ea, ua, ra = split(a)
    eb, ub, rb = split(b)
    if ea != eb:
        return -1 if ea < eb else 1
    c = _deb_cmp_part(ua, ub)
    return c if c else _deb_cmp_part(ra, rb)


_SEM = re.compile(r"^v?(\d+(?:\.\d+)*)([A-Za-z]+\d*|[-+.][0-9A-Za-z.+-]*)?$")


def dotted_cmp(a: str, b: str) -> int | None:
    """1.2.10 > 1.2.9; a pre-release suffix (rc1, b7, -beta) sorts before the plain version; None when unparsable."""
    ma, mb = _SEM.match(str(a).strip()), _SEM.match(str(b).strip())
    if not ma or not mb:
        return None
    na = [int(x) for x in ma.group(1).split(".")]
    nb = [int(x) for x in mb.group(1).split(".")]
    n = max(len(na), len(nb))
    na += [0] * (n - len(na))
    nb += [0] * (n - len(nb))
    if na != nb:
        return -1 if na < nb else 1
    sa, sb = ma.group(2) or "", mb.group(2) or ""
    pre_a = bool(sa) and not sa.startswith("+")
    pre_b = bool(sb) and not sb.startswith("+")
    if pre_a != pre_b:
        return -1 if pre_a else 1
    return (sa > sb) - (sa < sb)


def cmp(a: str, b: str, scheme: str = "dotted") -> int | None:
    if scheme == "deb":
        try:
            return deb_cmp(str(a), str(b))
        except (ValueError, IndexError):
            return None
    return dotted_cmp(a, b)


def in_range(version: str, introduced: str | None, fixed: str | None, last_affected: str | None = None, scheme: str = "dotted") -> bool | None:
    """True when introduced ≤ version and (version < fixed or version ≤ last_affected); None when a comparison fails."""
    if introduced not in (None, "0", ""):
        c = cmp(version, introduced, scheme)
        if c is None:
            return None
        if c < 0:
            return False
    if fixed:
        c = cmp(version, fixed, scheme)
        return None if c is None else c < 0
    if last_affected:
        c = cmp(version, last_affected, scheme)
        return None if c is None else c <= 0
    return True
