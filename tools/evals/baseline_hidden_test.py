"""Hidden check for the baseline comparison (tools/evals/run_baseline.sh): decision 0003 of the baseline-ledger fixture."""
import unittest
from ledger.account import Account


class HiddenNoNegativeBalance(unittest.TestCase):
    def test_over_refund_is_rejected_not_clamped(self):
        a = Account("5")
        with self.assertRaises(ValueError):
            a.refund("7")
        self.assertEqual(str(a.balance), "5")
