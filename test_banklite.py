import unittest
from unittest.mock import MagicMock, patch, call, ANY
from banklite import * 

def setUp(self):
    self.gateway = MagicMock()
    self.audit   = MagicMock()
    self.proc    = PaymentProcessor(self.gateway, self.audit)

def _make_tx(self, amount=100.00, tx_id="TX-001", user_id=1):
        return Transaction(tx_id=tx_id, user_id=user_id, amount=amount)

#Successful charge
def test_successful_charge (self):
    self.gateway.charge.return_value = True


#Declined charge

#Zero amount

#Negative Amount

#Amount Exceeds limit

#Audit on success

#Audit on decline

#Audit not called on valid input