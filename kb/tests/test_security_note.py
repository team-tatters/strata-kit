"""Security core, order 2026.11.03-02 task-04 (spec AC5·AC8·AC9): the note has the date and four sections; a pair seen on
two consecutive days appears on day two only under open items with its first day; a failed layer is named at the top;
every line carries the source → record → match link set; a closed pair appears once under closed items; blind targets
are listed; a missed day gets the one-line note; more than forty lines fold the advisories."""
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb.security import note as N  # noqa: E402
from kb.security.sources import record  # noqa: E402
from kb.security.store import Store  # noqa: E402

D1, D2, D3 = "2026-11-03", "2026-11-04", "2026-11-05"


def m(day, target, vuln, rid, grade="urgent", reason="cvss_v3 9.8 ≥ 9.0 (default)", in_range=True):
    return {"id": f"{day}:{target}|{vuln}", "target_ref": target, "record_id": rid, "vuln_id": vuln, "matched_by": "identifier",
            "version_in_range": in_range, "grade": grade, "reason": reason, "sort_key": [0, 0.1, 9.8, 0], "detail": {"target_version": "1.0"}}


class LineTest(unittest.TestCase):
    def test_line_lists_the_versions_at_risk(self):
        x = m(D1, "demo/repo/next", "CVE-1", "nvd:CVE-1")
        x["detail"] = {"target_version": "15.2.4", "target_versions": {"15.2.4": True, "15.2.6": True, "15.5.28": False}}
        self.assertIn("demo/repo/next@15.2.4, 15.2.6 ·", N._line(x, {}, D1))
        x["detail"] = {"target_version": "1.0"}
        self.assertIn("demo/repo/next@1.0 ·", N._line(x, {}, D1))


class NoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "security").mkdir()
        self.store = Store(self.vault / ".kb" / "security.sqlite")
        self.store.upsert_records([
            record("nvd:CVE-1", "vuln", "general-db", "nvd", vuln_id="CVE-1", title="thing one", source_url="https://nvd/CVE-1", scores={"cvss_v3": 9.8, "cvss_v4": None, "cna": None, "vendor": None}, epss=0.1),
            record("osv:X", "vuln", "ecosystem", "osv", vuln_id="CVE-2", title="thing two", source_url="https://osv/X", scores={"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": None}),
        ], collected_at=D1 + "T08:00:00")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def day(self, day, matches, layers=None, blind=None):
        for x in matches:
            if x["version_in_range"] is not False and x["grade"] != "filtered":
                self.store.touch_first_seen(x["target_ref"], x["vuln_id"], day)
        self.store.replace_matches(day, matches)
        self.store.save_run(day, day + "T08:30:00", day + "T08:31:00", layers or {"general-db": "ok", "ecosystem": "ok", "os-vendor": "ok", "trend": "ok"}, {}, None)
        return N.build(self.vault, day, self.store, blind or [])

    def test_two_consecutive_days_sections_links_and_failed_layer(self):
        t1 = self.day(D1, [m(D1, "demo/dev/lib", "CVE-1", "nvd:CVE-1"), m(D1, "demo/dev/lib2", "CVE-2", "osv:X", "advisory", "no-score")],
                      blind=[{"target_ref": "demo/dev/redis", "kind": "image", "version": "7", "reason": "식별자도 수동 연결도 없음"}])
        for sec in ("## 새 항목", "## 미조치", "## 닫힌 항목", "## 눈이 없는 대상"):
            self.assertIn(sec, t1)
        self.assertIn("date: '2026-11-03'", t1.replace('"', "'"))
        new = t1.split("## 새 항목")[1].split("## 미조치")[0]
        self.assertIn("demo/dev/lib@1.0 · CVE-1", new)
        self.assertIn("[원문](https://nvd/CVE-1)", new)
        self.assertIn(f"[레코드](../matches/{D1}.yaml#records.nvd:CVE-1)", new)
        self.assertIn(f"[대조](../matches/{D1}.yaml#{D1}:demo/dev/lib|CVE-1)", new)
        self.assertIn("점수 없는 항목 1", t1)
        self.assertNotIn("demo/dev/lib2", new)                # no-score goes to the folded list, not to new items
        self.assertIn("demo/dev/redis", t1.split("## 눈이 없는 대상")[1])
        t2 = self.day(D2, [m(D2, "demo/dev/lib", "CVE-1", "nvd:CVE-1")], layers={"general-db": "ok", "ecosystem": "failed", "os-vendor": "ok", "trend": "ok"})
        new2 = t2.split("## 새 항목")[1].split("## 미조치")[0]
        open2 = t2.split("## 미조치")[1].split("## 닫힌 항목")[0]
        self.assertIn("없음.", new2)
        self.assertNotIn("CVE-1", new2)
        self.assertIn("CVE-1", open2)
        self.assertIn(f"처음 {D1}", open2)
        self.assertIn("오늘 보지 못한 층: ecosystem", t2)
        self.assertIn("layers_failed:\n- ecosystem", t2)

    def test_closed_item_shows_once_then_disappears(self):
        self.day(D1, [m(D1, "demo/dev/lib", "CVE-1", "nvd:CVE-1")])
        self.store.set_closed("demo/dev/lib", "CVE-1", D2, "projects/infra/tasks/x/_order.yaml")
        t2 = self.day(D2, [m(D2, "demo/dev/lib", "CVE-1", "nvd:CVE-1")])
        closed = t2.split("## 닫힌 항목")[1].split("## 눈이 없는 대상")[0]
        self.assertIn("CVE-1", closed)
        self.assertIn("[오더](projects/infra/tasks/x/_order.yaml)", closed)
        self.assertNotIn("CVE-1", t2.split("## 미조치")[1].split("## 닫힌 항목")[0])
        t3 = self.day(D3, [])
        self.assertNotIn("CVE-1", t3.split("# 보안 노트")[1].split("<details>")[0])

    def test_store_round_trips_version_in_range_as_bool(self):
        self.store.replace_matches(D1, [m(D1, "demo/dev/a", "CVE-1", "nvd:CVE-1", in_range=False), m(D1, "demo/dev/b", "CVE-1", "nvd:CVE-1", in_range=None)])
        got = {x["target_ref"]: x["version_in_range"] for x in self.store.matches_on(D1)}
        self.assertIs(got["demo/dev/a"], False)
        self.assertIsNone(got["demo/dev/b"])

    def test_gap_note_and_folding(self):
        p = N.write_gap(self.vault, D3, "실행 기록 없음")
        self.assertIn("오늘은 보지 못했다", p.read_text(encoding="utf-8"))
        many = [m(D1, f"demo/dev/pkg{i}", f"CVE-{100 + i}", "osv:X", "advisory", "cvss_v3 5 < 9.0 (default)") for i in range(50)]
        many.append(m(D1, "demo/dev/lib", "CVE-1", "nvd:CVE-1"))
        t = self.day(D1, many)
        new = t.split("## 새 항목")[1].split("## 미조치")[0]
        self.assertIn("접었다", new)
        self.assertIn("**긴급** · demo/dev/lib", new)
        self.assertLess(new.count("\n- "), 5)

    def test_package_matches_sharing_a_notice_are_grouped(self):
        self.store.upsert_records([record("ubuntu-usn:USN-1", "vuln", "os-vendor", "ubuntu-usn", vuln_id="USN-1", title="OpenSSH vulnerabilities", source_url="https://usn/1",
                                          scores={"cvss_v3": 9.1, "cvss_v4": None, "cna": None, "vendor": None})], collected_at=D1 + "T08:00:00")
        t = self.day(D1, [m(D1, f"infra/gpu-server/{n}", "USN-1", "ubuntu-usn:USN-1") for n in ("openssh-server", "openssh-client", "ssh")])
        new = t.split("## 새 항목")[1].split("## 미조치")[0]
        self.assertEqual(new.count("\n- "), 1)
        self.assertIn("대상 3개", new)
        self.assertIn("infra/gpu-server", new)


if __name__ == "__main__":
    unittest.main()
