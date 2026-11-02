"""profiles/frontend.next-web/enforcement diff 규칙 — 설치한 그대로(.template 접미를 뗀 복사본) 임시 git 저장소에서 실행한다.

근거 결정: raw 값은 디자인 속성별로 막고 alias 변수 임의 값과 이유 있는 예외는 허용(DEC-2026-10-31-05),
무효화는 저장 훅 안에서 다른 도메인·정확한 detail 키까지 허용하되 컴포넌트 직접 호출은 금지, 키는 기능별 팩토리 하나
(DEC-2026-10-31-06), Feature Block 이름에 Block·Container·Partial 접미 금지(DEC-2026-10-31-02).
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENF = ROOT / "profiles" / "frontend.next-web" / "enforcement"
NODE = shutil.which("node")

# (줄, 위반이어야 하는가)
RAW_VIEW = [
    ("export function OrderRawView() {", False),
    ("  return (", False),
    ("    <>", False),
    # 디자인 속성별 raw 값 — 위반
    ('      <div className="bg-[#ff0000]" />', True),                      # 색
    ('      <div className="text-[rgb(1,2,3)]" />', True),                 # 색
    ('      <div className="p-[13px]" />', True),                          # 간격
    ('      <div className="mt-[7px]" />', True),                          # 간격
    ('      <div className="gap-[10px]" />', True),                        # 간격
    ('      <div className="text-[15px]" />', True),                       # 글꼴 크기
    ('      <div className="leading-[22px]" />', True),                    # 줄 높이
    ('      <div className="rounded-[6px]" />', True),                     # 반경
    ('      <div className="shadow-[0_1px_2px_rgba(0,0,0,0.2)]" />', True),  # 그림자
    ('      <div className="z-[60]" />', True),                            # z-index
    ('      <div className="bg-blue-500" />', True),                       # 팔레트 스케일
    ("      <div style={{ color: '#333' }} />", True),
    ("      <div style={{ padding: 12 }} />", True),
    ("      <div style={{ fontSize: '14px' }} />", True),
    ("      <div style={{ borderRadius: 4 }} />", True),
    ("      <div style={{ boxShadow: '0 1px 2px rgba(0,0,0,.2)' }} />", True),
    ("      <div style={{ zIndex: 60 }} />", True),
    # 이유 없는 예외 표식, 만료된 예외 표식 — 여전히 위반
    ('      <div className="p-[13px]" /> {/* @strata:token-exception until 2099-12-31 */}', True),
    ('      <div className="p-[14px]" /> {/* @strata:token-exception 옛 화면 until 2000-01-01 */}', True),
    # alias 변수 임의 값 — 허용
    ('      <div className="bg-[var(--surface-raised)]" />', False),
    ('      <div className="p-[--space-3]" />', False),
    ('      <div className="bg-(--surface-raised) p-(--space-3)" />', False),
    ('      <div className="text-[length:var(--font-sm)]" />', False),
    ("      <div style={{ padding: 'var(--space-3)' }} />", False),
    ("      <div style={{ margin: 0 }} />", False),
    # 디자인 속성이 아닌 계산·측정 치수 — 허용
    ("      <div style={{ width: measuredWidth, top: offset, height: 480 }} />", False),
    # 이유를 단 예외(같은 줄, 앞 줄) — 허용
    ('      <div className="p-[13px]" /> {/* @strata:token-exception ResizeObserver 측정값 until 2099-12-31 */}', False),
    ("      {/* @strata:token-exception 가상 스크롤 행 간격 until 2099-12-31 */}", False),
    ("      <div style={{ padding: 12 }} />", False),
    # 런타임 계산·측정값의 영구 예외(@strata:computed 이유) — 허용, 이유 없으면 위반, 팔레트 클래스에는 효력 없음 (DEC-2026-10-31-05)
    ("      <div style={{ padding: gutter }} className=\"gap-[18px]\" /> {/* @strata:computed 행 높이에서 계산한 간격 */}", False),
    ("      {/* @strata:computed 열 너비 합에서 계산 */}", False),
    ("      <div style={{ zIndex: 61 }} />", False),
    ("      <div className=\"gap-[19px]\" /> {/* @strata:computed */}", True),
    ("      <div className=\"bg-red-500\" /> {/* @strata:computed 상태색 */}", True),
    # 산문 속 12px — 허용
    ("      <p>Use 12px spacing as in the legacy layout</p>", False),
    ("      // legacy layout used 12px gaps", False),
    ("      {note('the old card had 12px padding')}", False),
    ("    </>", False),
    ("  );", False),
    ("}", False),
]

FILES = {
    "src/features/order/OrderRawView.tsx": "\n".join(t for t, _ in RAW_VIEW) + "\n",
    # 컴포넌트에서 직접 무효화 — 위반
    "src/features/order/OrderListSection.tsx": (
        "export function OrderListSection() {\n"
        "  const onDone = () => queryClient.invalidateQueries({ queryKey: orderKeys.lists() });\n"
        "  return null;\n"
        "}\n"
    ),
    # 저장 훅 밖의 .ts 에서 무효화 — 위반
    "src/features/order/orderTableActions.ts": (
        "export const refresh = () => queryClient.invalidateQueries({ queryKey: orderKeys.all });\n"
    ),
    # 저장 훅이 다른 도메인 키·정확한 detail 키를 무효화 — 허용
    "src/features/order/useOrderSubmitMutation.ts": (
        "export function useOrderSubmitMutation(id: number) {\n"
        "  return useMutation({\n"
        "    mutationFn: submitOrder,\n"
        "    onSuccess: () => {\n"
        "      queryClient.invalidateQueries({ queryKey: historyKeys.lists() });\n"
        "      queryClient.invalidateQueries({ queryKey: organizationKeys.detail(id) });\n"
        "    },\n"
        "  });\n"
        "}\n"
    ),
    # 키 팩토리 밖의 인라인 queryKey — 위반
    "src/features/order/useOrderQuery.ts": (
        "export const useOrderQuery = (id: number) => useQuery({ queryKey: ['order', id], queryFn });\n"
    ),
    # 키 팩토리 안 — 허용
    "src/features/order/order.keys.ts": (
        "export const orderListQuery = (p: P) => ({ queryKey: ['shop', 'order', 'list', p] });\n"
    ),
    "src/features/history/keys.ts": (
        "export const historyListQuery = () => ({ queryKey: ['shop', 'history', 'list'] });\n"
    ),
    "src/features/audit/queryKeys.ts": (
        "export const auditListQuery = () => ({ queryKey: ['shop', 'audit', 'list'] });\n"
    ),
    # CSS 선언의 디자인 속성 raw 값 — 1·3행 위반, 토큰 정의(커스텀 속성)·변수 참조·기하 치수는 허용
    "src/features/order/order.module.css": (
        ".card { padding: 13px; }\n"
        ".card { padding: var(--space-3); --space-local: 12px; width: 320px; }\n"
        ".badge { color: #ff0000; }\n"
    ),
    # 금지 접미 — 위반 / Section — 허용
    "src/features/order/OrderMailBlock.tsx": "export function OrderMailBlock() {\n  return null;\n}\n",
    "src/features/order/OrderSummarySection.tsx": "export function OrderSummarySection() {\n  return null;\n}\n",
}

LINE_RE = re.compile(r"^(\S+):(\d+)\s+\[([\w-]+)\]")


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


@unittest.skipIf(NODE is None, "node 가 없다")
class NextWebDiffRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = Path(cls.tmp.name)
        # README 적용 1단계: .template 접미를 떼고 프로젝트 루트로 복사
        shutil.copy(ENF / "check-diff-rules.cjs.template", p / "check-diff-rules.cjs")
        shutil.copy(ENF / "diff-rules.json.template", p / "diff-rules.json")
        # 기준선에 이미 있던 raw 값은 신규 라인이 아니라서 검사하지 않는다
        (p / "src").mkdir()
        (p / "src" / "legacy.tsx").write_text('export const L = () => <div className="p-[13px]" />;\n')
        subprocess.run(["git", "init", "-q", "-b", "main", str(p)], check=True)
        _git(p, "add", "-A")
        _git(p, "commit", "-qm", "base")
        _git(p, "checkout", "-q", "-b", "feature")
        for rel, body in FILES.items():
            f = p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(body)
        _git(p, "add", "-A")
        _git(p, "commit", "-qm", "feature")
        # README 적용 3단계의 명령 그대로
        r = subprocess.run([NODE, "check-diff-rules.cjs", "--base-ref", "main"], cwd=p,
                           capture_output=True, text=True)
        cls.rc, cls.out = r.returncode, r.stdout + r.stderr
        cls.hits = set()
        for line in cls.out.splitlines():
            m = LINE_RE.match(line)
            if m:
                cls.hits.add((m.group(1), int(m.group(2)), m.group(3)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _lines(self, rel):
        return {ln for f, ln, _ in self.hits if f == rel}

    def _rules(self, rel):
        return {rule for f, _, rule in self.hits if f == rel}

    def test_exit_code_is_violation(self):
        self.assertEqual(self.rc, 1, self.out)

    def test_raw_values_flagged_per_property_and_exceptions_allowed(self):
        expected = {i for i, (_, bad) in enumerate(RAW_VIEW, start=1) if bad}
        got = self._lines("src/features/order/OrderRawView.tsx")
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        self.assertEqual((missing, extra), ([], []),
                         "놓친 줄: " + "; ".join(RAW_VIEW[i - 1][0].strip() for i in missing)
                         + " | 오탐 줄: " + "; ".join(RAW_VIEW[i - 1][0].strip() for i in extra))

    def test_legacy_line_not_checked(self):
        self.assertEqual(self._lines("src/legacy.tsx"), set())

    def test_css_design_properties(self):
        self.assertEqual(self._lines("src/features/order/order.module.css"), {1, 3}, self.out)

    def test_component_invalidate_flagged(self):
        self.assertIn("no-component-invalidate", self._rules("src/features/order/OrderListSection.tsx"))
        self.assertIn("no-component-invalidate", self._rules("src/features/order/orderTableActions.ts"))

    def test_mutation_hook_may_invalidate_other_domain_and_detail_keys(self):
        self.assertEqual(self._lines("src/features/order/useOrderSubmitMutation.ts"), set(), self.out)

    def test_inline_query_key_only_inside_key_factory(self):
        self.assertIn("no-inline-query-key", self._rules("src/features/order/useOrderQuery.ts"))
        for rel in ("src/features/order/order.keys.ts", "src/features/history/keys.ts",
                    "src/features/audit/queryKeys.ts"):
            self.assertEqual(self._lines(rel), set(), rel)

    def test_forbidden_component_suffix(self):
        self.assertTrue(self._rules("src/features/order/OrderMailBlock.tsx"), self.out)
        self.assertEqual(self._lines("src/features/order/OrderSummarySection.tsx"), set())


if __name__ == "__main__":
    unittest.main()
