import unittest
from unittest.mock import MagicMock, patch, call, ANY
from banklite import * 

class TestPaymentProcessor(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.audit   = MagicMock()
        self.proc    = PaymentProcessor(self.gateway, self.audit)

    def _make_tx(self, amount=100.00, tx_id="TX-001", user_id=1):
            return Transaction(tx_id=tx_id, user_id=user_id, amount=amount)

    #Successful charge
    def test_successful_charge (self):
        self.gateway.charge.return_value = True
        tx = self._make_tx()
        result = self.proc.process(tx)
        self.assertEqual(result, "success")

    #Declined charge
    def test_unsuccessful_charge (self):
        self.gateway.charge.return_value = False
        tx = self._make_tx()
        result = self.proc.process(tx)
        self.assertEqual(result, "declined")

    #Zero amount
    def test_zero_amount_charge (self):
        tx = self._make_tx(amount=0.00)
        with self.assertRaises(ValueError):
            self.proc.process(tx)
        self.gateway.charge.assert_not_called()
        self.audit.record.assert_not_called()

    #Negative Amount
    def test_negative_amount_charge (self):
        tx = self._make_tx(amount=-100.00)
        with self.assertRaises(ValueError):
            self.proc.process(tx)

    #Amount Exceeds limit
    def test_exceeding_amount_charge (self):
        tx = self._make_tx(amount=10_500.00)
        with self.assertRaises(ValueError):
            self.proc.process(tx)

    #Amount at limit
    def test_max_amount_charge (self):
        self.gateway.charge.return_value = True
        tx = self._make_tx(amount=10_000.00)
        result = self.proc.process(tx)  
        self.assertEqual(result, "success")  

    #Audit on success
    def test_successful_audit (self):
        tx = self._make_tx(tx_id="TX-001", amount=1_000.00)
        self.proc.process(tx)
        self.audit.record.assert_called_once_with(
            "CHARGED", "TX-001", {"amount": 1_000.00}
        )

    #Audit on decline
    def test_unsuccessful_audit (self):
        self.gateway.charge.return_value = False
        tx = self._make_tx(tx_id="TX-002", amount=100.00)
        self.proc.process(tx)
        self.audit.record.assert_called_once_with(
            "DECLINED", "TX-002", {"amount": 100.00}
        )

    #Audit not called on valid input
    def test_audit_not_properly_called (self):
        tx = self._make_tx(amount=-1.00)
        with self.assertRaises(ValueError):
            self.proc.process(tx)
        self.audit.record.assert_not_called()