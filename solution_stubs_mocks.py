#!/usr/bin/env python3
"""
=============================================================================
SOLUTION FILE: BankLite — Stubs & Mocks Exercise
=============================================================================

This file contains the complete, explained solution to all four tasks.
Each test includes a comment explaining WHY it's written the way it is —
not just what it does.

READ AFTER completing the exercise yourself. Every shortcut you avoid
now pays compound interest later.
=============================================================================
"""

import unittest
from unittest.mock import MagicMock, patch, call, ANY

# ── Import the production code ──────────────────────────────────────────────
# These classes live in banklite.py (provided as starter code in the exercise).
# Importing them here keeps the test file focused on tests, not production logic.
from banklite import (
    Transaction,         # dataclass: tx_id, user_id, amount, currency, status
    FraudCheckResult,    # dataclass: approved, risk_score, reason
    PaymentGateway,      # interface: charge(tx) -> bool
    FraudDetector,       # interface: check(tx) -> FraudCheckResult
    EmailClient,         # interface: send_receipt(...), send_fraud_alert(...)
    AuditLog,            # interface: record(event, tx_id, details)
    TransactionRepository, # interface: find_by_user(user_id) -> List[Transaction]
    PaymentProcessor,    # SUT for Task 1
    FraudAwareProcessor, # SUT for Task 2
    StatementBuilder,    # SUT for Task 3
)


# =============================================================================
# TASK 1 SOLUTION: PaymentProcessor
# =============================================================================
# APPROACH: PaymentProcessor has two collaborators — gateway (returns bool)
# and audit (records events). We stub the gateway return value and mock the
# audit to verify it's called correctly. The gateway can also be mocked for
# "not called" assertions, but its main job here is stubbing a bool.
# =============================================================================

class TestPaymentProcessor(unittest.TestCase):

    def setUp(self):
        # setUp() is called automatically before EACH test method.
        # Creating fresh MagicMocks here ensures that call_count,
        # call_args_list, and return_value settings never bleed between tests.
        self.gateway = MagicMock()  # stands in for the real PaymentGateway
        self.audit   = MagicMock()  # stands in for the real AuditLog
        # Inject both doubles via constructor (dependency injection pattern).
        # The processor never knows it's talking to a mock, not a real service.
        self.proc    = PaymentProcessor(self.gateway, self.audit)

    def _make_tx(self, amount=100.00, tx_id="TX-001", user_id=1):
        """Helper: build a Transaction. Keeps test setup DRY.
        Default values mean each test only specifies what it cares about."""
        return Transaction(tx_id=tx_id, user_id=user_id, amount=amount)

    # ── Return value tests (state verification via stubs) ──────────────────

    def test_process_returns_success_when_gateway_charges(self):
        """
        WHY: The most basic happy-path test. Stub the gateway to return True
        and verify the processor maps that to the string "success".
        This is state verification — we only care about the return value.
        """
        # STUB: configure what the gateway returns when called.
        # MagicMock.charge is auto-created; return_value sets its return.
        self.gateway.charge.return_value = True
        tx = self._make_tx()  # create a minimal valid transaction

        result = self.proc.process(tx)  # call the method under test

        # State verification: assert on the return value, not on calls made.
        self.assertEqual(result, "success")

    def test_process_returns_declined_when_gateway_rejects(self):
        """
        WHY: The other branch of the charge outcome. Stub False, expect
        "declined". Mirrors the previous test but exercises the else branch.
        """
        self.gateway.charge.return_value = False  # stub: gateway says no
        tx = self._make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "declined")

    # ── Validation tests (ValueError paths) ───────────────────────────────

    def test_process_raises_on_zero_amount(self):
        """
        WHY: Boundary value — exactly zero is invalid. We also assert the
        gateway was never called, proving validation short-circuits before
        any external call. This is the critical isolation check.
        """
        tx = self._make_tx(amount=0.00)  # zero amount — should be rejected

        # assertRaises as context manager: the block must raise ValueError.
        # If it doesn't raise, or raises a different exception, the test fails.
        with self.assertRaises(ValueError):
            self.proc.process(tx)

        # Negative assertions: nothing external should be touched on bad input.
        # This proves the guard clause runs BEFORE any side-effects.
        self.gateway.charge.assert_not_called()
        self.audit.record.assert_not_called()

    def test_process_raises_on_negative_amount(self):
        """
        WHY: Negative amounts are a common bug source. Test both sides of the
        zero boundary.
        """
        tx = self._make_tx(amount=-50.00)  # negative — equally invalid

        with self.assertRaises(ValueError):
            self.proc.process(tx)

        # Gateway must be untouched — we never charge for invalid transactions.
        self.gateway.charge.assert_not_called()

    def test_process_raises_when_amount_exceeds_limit(self):
        """
        WHY: Boundary value at MAX_AMOUNT. 10,000 is valid; 10,001 is not.
        Testing at 10_001.00 catches the > vs >= distinction in the condition.
        """
        tx = self._make_tx(amount=10_001.00)  # one cent over the limit

        with self.assertRaises(ValueError):
            self.proc.process(tx)

    def test_process_accepts_amount_at_max_limit(self):
        """
        WHY: The complement to the above. Exactly 10,000 should NOT raise.
        This "should succeed" test catches off-by-one errors.
        """
        self.gateway.charge.return_value = True  # stub: charge succeeds
        tx = self._make_tx(amount=10_000.00)  # exactly at the limit

        result = self.proc.process(tx)  # must NOT raise

        self.assertEqual(result, "success")  # normal processing continues

    # ── Audit mock tests (behaviour verification) ──────────────────────────

    def test_audit_records_charged_event_on_success(self):
        """
        WHY: This is mock / behaviour verification. The audit log's job is
        to receive specific calls. We don't care about its return value;
        we care that it was called with the right arguments.

        assert_called_once_with() checks: called exactly once, with these
        exact positional and keyword arguments.
        """
        self.gateway.charge.return_value = True  # stub: charge succeeds
        # Use a specific tx_id and amount so we can assert on the exact args.
        tx = self._make_tx(tx_id="TX-999", amount=250.00)

        self.proc.process(tx)  # run the method — produces the side-effect

        # MOCK assertion: did the audit receive the right call?
        # "CHARGED" = event name, "TX-999" = tx id, {"amount": 250.00} = details
        self.audit.record.assert_called_once_with(
            "CHARGED", "TX-999", {"amount": 250.00}
        )

    def test_audit_records_declined_event_on_failure(self):
        """
        WHY: Mirrors the above but for the decline branch. Both success and
        decline must produce an audit record — just with different event names.
        """
        self.gateway.charge.return_value = False  # stub: gateway declines
        tx = self._make_tx(tx_id="TX-888", amount=75.00)

        self.proc.process(tx)

        # The event name changes to "DECLINED" — everything else is the same.
        self.audit.record.assert_called_once_with(
            "DECLINED", "TX-888", {"amount": 75.00}
        )

    def test_audit_not_called_when_validation_fails(self):
        """
        WHY: Proves that the audit is clean — no partial writes when an
        exception is raised. This is critical for data integrity guarantees.
        """
        tx = self._make_tx(amount=-1.00)  # invalid — will raise

        with self.assertRaises(ValueError):
            self.proc.process(tx)

        # The audit should have zero calls — no partial record was written.
        self.audit.record.assert_not_called()


# =============================================================================
# TASK 2 SOLUTION: FraudAwareProcessor
# =============================================================================
# APPROACH: This class has FOUR collaborators. We need to:
#   1. Stub the detector to return controlled FraudCheckResult objects
#   2. Stub the gateway to return True/False
#   3. Mock the mailer to verify email calls
#   4. Mock the audit to verify audit records
#
# The key insight: verify that each collaborator is called (or NOT called)
# in each scenario. The "not called" assertions are often more important
# than the "called" ones.
# =============================================================================

class TestFraudAwareProcessor(unittest.TestCase):

    def setUp(self):
        # Four fresh mocks — one per collaborator.
        # Using keyword arguments when constructing the processor makes the
        # test setup self-documenting: you can see which mock plays which role.
        self.gateway  = MagicMock()  # stubs charge() True/False
        self.detector = MagicMock()  # stubs check() → FraudCheckResult
        self.mailer   = MagicMock()  # mock: we'll assert on send_* calls
        self.audit    = MagicMock()  # mock: we'll assert on record() calls
        self.proc = FraudAwareProcessor(
            gateway=self.gateway,
            detector=self.detector,
            mailer=self.mailer,
            audit=self.audit,
        )

    def _safe_result(self, risk_score=0.1):
        """Returns a FraudCheckResult below the block threshold (< 0.75).
        Using a helper avoids repeating the dataclass constructor in every test."""
        return FraudCheckResult(approved=True, risk_score=risk_score)

    def _fraud_result(self, risk_score=0.9):
        """Returns a FraudCheckResult AT or ABOVE the block threshold (>= 0.75)."""
        return FraudCheckResult(approved=False, risk_score=risk_score, reason="Suspicious")

    def _make_tx(self, tx_id="TX-F01", user_id=42, amount=500.00):
        # Minimal transaction factory with sensible defaults
        return Transaction(tx_id=tx_id, user_id=user_id, amount=amount)

    # ── Fraud blocking tests ───────────────────────────────────────────────

    def test_high_risk_returns_blocked(self):
        """
        WHY: Core fraud path — the method should return "blocked" when
        the risk score is above the threshold.
        """
        # Stub: make the detector report a high-risk transaction
        self.detector.check.return_value = self._fraud_result(risk_score=0.9)
        tx = self._make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "blocked")  # return value: state verification

    def test_high_risk_does_not_charge_the_card(self):
        """
        WHY: MOST IMPORTANT TEST IN THIS CLASS. If a fraudulent transaction
        slips through and charges the card, that's a real-money mistake.
        assert_not_called() is the guard here.
        """
        self.detector.check.return_value = self._fraud_result()
        tx = self._make_tx()

        self.proc.process(tx)

        # The gateway.charge method must never be invoked for fraud transactions.
        # This negative assertion is the entire point of this test.
        self.gateway.charge.assert_not_called()

    def test_exactly_at_threshold_is_treated_as_fraud(self):
        """
        WHY: Boundary value test. The condition is >= 0.75. Testing at exactly
        0.75 catches the common bug of writing > instead of >=.
        """
        # 0.75 is the boundary — must be treated as fraud (>= not >)
        self.detector.check.return_value = self._fraud_result(risk_score=0.75)
        tx = self._make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "blocked")
        self.gateway.charge.assert_not_called()  # still no charge at boundary

    def test_just_below_threshold_is_not_blocked(self):
        """
        WHY: The complement to the above. 0.749 is just under the threshold
        and should proceed normally (not be blocked). Tests the other side
        of the boundary.
        """
        # 0.749 is below 0.75 — should pass through to the gateway
        self.detector.check.return_value = self._safe_result(risk_score=0.749)
        self.gateway.charge.return_value = True  # stub: charge succeeds
        tx = self._make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "success")  # NOT blocked

    def test_fraud_alert_email_sent_with_correct_args(self):
        """
        WHY: Behaviour verification — not only that the email was sent, but
        that it was sent to the right user with the right tx_id.
        assert_called_once_with() catches wrong argument bugs.
        """
        self.detector.check.return_value = self._fraud_result()
        # Specific user_id and tx_id so we can assert on the exact values
        tx = self._make_tx(tx_id="TX-FRAUD", user_id=77)

        self.proc.process(tx)

        # Verify the mailer received the correct (user_id, tx_id) pair.
        # An alert sent to the wrong user would be a serious privacy violation.
        self.mailer.send_fraud_alert.assert_called_once_with(77, "TX-FRAUD")

    def test_fraud_audit_records_blocked_event(self):
        """
        WHY: The audit must record the risk score for compliance reasons.
        Verify the exact arguments including the details dict.
        """
        self.detector.check.return_value = self._fraud_result(risk_score=0.88)
        tx = self._make_tx(tx_id="TX-BLK")

        self.proc.process(tx)

        # The third argument is a dict — assert on the whole dict, not just
        # the key, to catch cases where extra fields are accidentally included.
        self.audit.record.assert_called_once_with(
            "BLOCKED", "TX-BLK", {"risk": 0.88}
        )

    # ── Success path tests ────────────────────────────────────────────────

    def test_low_risk_successful_charge_returns_success(self):
        # Arrange: both detector (safe) and gateway (success) stubbed
        self.detector.check.return_value = self._safe_result()   # risk = 0.1
        self.gateway.charge.return_value = True                  # charge succeeds
        tx = self._make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "success")

    def test_receipt_email_sent_on_successful_charge(self):
        """
        WHY: After a successful charge, the user must receive a receipt.
        We verify the exact args (user_id, tx_id, amount) because a receipt
        with the wrong amount is a support ticket.
        """
        self.detector.check.return_value = self._safe_result()
        self.gateway.charge.return_value = True
        # Specific values so we can assert the mailer receives them exactly
        tx = self._make_tx(tx_id="TX-OK", user_id=5, amount=123.45)

        self.proc.process(tx)

        # Verify all three arguments: wrong user, tx, or amount would be caught
        self.mailer.send_receipt.assert_called_once_with(5, "TX-OK", 123.45)

    def test_fraud_alert_not_sent_on_successful_charge(self):
        """
        WHY: On a clean transaction, no fraud alert should go out.
        This is an example where assert_not_called() prevents false positives
        — you might accidentally call the wrong mailer method.
        """
        self.detector.check.return_value = self._safe_result()
        self.gateway.charge.return_value = True
        tx = self._make_tx()

        self.proc.process(tx)

        # send_fraud_alert is the WRONG channel for a clean transaction.
        # Asserting it's not called catches the bug where both methods fire.
        self.mailer.send_fraud_alert.assert_not_called()

    def test_low_risk_declined_charge_returns_declined(self):
        # Risk check passes, but the bank declines the charge
        self.detector.check.return_value = self._safe_result()
        self.gateway.charge.return_value = False  # stub: bank says no
        tx = self._make_tx()

        result = self.proc.process(tx)

        self.assertEqual(result, "declined")

    def test_receipt_not_sent_on_declined_charge(self):
        """
        WHY: No receipt for failed charges. Sending a receipt for a declined
        card would be extremely confusing for the user.
        """
        self.detector.check.return_value = self._safe_result()
        self.gateway.charge.return_value = False  # charge fails
        tx = self._make_tx()

        self.proc.process(tx)

        # No receipt for a declined charge — assert_not_called is the guard
        self.mailer.send_receipt.assert_not_called()

    # ── Error path tests ──────────────────────────────────────────────────

    def test_fraud_detector_connection_error_propagates(self):
        """
        WHY: When the fraud detector is unavailable, we cannot safely
        process the transaction (we'd be flying blind). The exception
        should propagate and NO charge should be attempted.

        side_effect raises the exception when the mock is called.
        """
        # side_effect as an exception instance: every call to check() raises.
        # This simulates the fraud API being offline.
        self.detector.check.side_effect = ConnectionError("Fraud API is down")
        tx = self._make_tx()

        with self.assertRaises(ConnectionError):
            self.proc.process(tx)

        # Prove the exception aborted processing before any charge was attempted
        self.gateway.charge.assert_not_called()
        self.mailer.send_receipt.assert_not_called()


# =============================================================================
# TASK 3 SOLUTION: StatementBuilder
# =============================================================================
# APPROACH: This is a pure data-transformation class. It has ONE collaborator
# (TransactionRepository) and zero side-effects. This makes it a perfect
# stub scenario — control the repo's return value, assert on the dict output.
#
# There are NO mock assertions here (no assert_called_*).
# That's intentional. This is state verification, not behaviour verification.
# =============================================================================

class TestStatementBuilder(unittest.TestCase):

    def setUp(self):
        # Single collaborator: the repository.
        # We stub find_by_user to return a controlled list of transactions.
        self.repo    = MagicMock()
        self.builder = StatementBuilder(self.repo)

    def test_empty_transaction_list_returns_zero_totals(self):
        """
        WHY: Base case. When a user has no transactions, the statement
        should be well-formed with zero values (not None, not missing keys).
        """
        # Stub: repository returns an empty list for this user
        self.repo.find_by_user.return_value = []

        result = self.builder.build(user_id=1)

        # All three keys must exist and have sensible zero-state values
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total_charged"], 0.0)
        self.assertIsInstance(result["transactions"], list)  # not None

    def test_only_success_transactions_are_counted_in_total(self):
        """
        WHY: The contract says only "success" status contributes to
        total_charged. We stub a mix of statuses and verify the filter works.
        """
        # Stub with a realistic mix: 2 success, 1 declined, 1 pending
        txs = [
            Transaction("TX1", 10, 100.00, status="success"),
            Transaction("TX2", 10,  50.00, status="declined"),  # must be excluded
            Transaction("TX3", 10, 200.00, status="success"),
            Transaction("TX4", 10,  75.00, status="pending"),   # must be excluded
        ]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=10)

        self.assertEqual(result["total_charged"], 300.00)  # 100 + 200 only
        self.assertEqual(result["count"], 4)               # ALL transactions in count

    def test_all_success_transactions_summed(self):
        """
        WHY: Verifies the sum calculation when all transactions are successful.
        """
        txs = [
            Transaction("TX1", 2, 99.99,  status="success"),
            Transaction("TX2", 2,  0.01,  status="success"),  # tiny amount
            Transaction("TX3", 2, 450.00, status="success"),
        ]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=2)

        self.assertEqual(result["total_charged"], 550.00)  # 99.99 + 0.01 + 450

    def test_total_is_rounded_to_two_decimal_places(self):
        """
        WHY: Floating point arithmetic can produce values like 10.559999999999.
        The round(total, 2) in the implementation should handle this.
        """
        # These amounts produce a floating-point imprecision when summed raw
        txs = [
            Transaction("TX1", 3, 10.555, status="success"),
            Transaction("TX2", 3,  0.005, status="success"),
        ]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=3)

        self.assertEqual(result["total_charged"], 10.56)  # 10.555 + 0.005, rounded

    def test_transactions_list_is_returned_unchanged(self):
        """
        WHY: The statement includes the raw transaction list for rendering.
        Verify it's the exact same list object (no transformation).
        """
        txs = [Transaction("TX1", 4, 100.00, status="success")]
        self.repo.find_by_user.return_value = txs

        result = self.builder.build(user_id=4)

        self.assertIs(result["transactions"], txs)


# =============================================================================
# TASK 4 SOLUTION: Stretch Challenges
# =============================================================================

class TestStretchChallenges(unittest.TestCase):
    """
    Answers to the three design questions from Task 4.
    """

    # ── Question A: Could you accidentally turn stubs into mocks? ──────────

    def test_A_wrong_way_stub_used_as_mock(self):
        """
        This is an EXAMPLE OF A MISTAKE — what to avoid.

        If you use a mock assertion on a stub scenario, your test becomes
        over-specified. It will break if the internal implementation changes
        (e.g., if the number of calls to find_by_user changes from 1 to 2
        for caching reasons) even though the output is still correct.

        The StatementBuilder tests should ONLY assert on result["total_charged"]
        etc., NOT on how many times the repo was called.

        The following assertion is technically valid but WRONG for this class:
        """
        repo = MagicMock()
        repo.find_by_user.return_value = []
        builder = StatementBuilder(repo)

        builder.build(user_id=1)

        # ← THIS IS OVER-SPECIFICATION. Don't do this for a stub scenario.
        # repo.find_by_user.assert_called_once_with(1)
        #
        # EXPLANATION: The test should care about the RESULT (total_charged, count),
        # not HOW MANY TIMES the repo was called internally. Using mock assertions
        # here makes the test fragile and tied to implementation details.
        pass  # Intentionally no mock assertion

    # ── Question B: spec= constrains the mock ──────────────────────────────

    def test_B_spec_mock_prevents_nonexistent_method_calls(self):
        """
        WHY spec= matters:
        A plain MagicMock() lets you call ANY attribute/method — including
        ones that don't exist on the real class. This can hide bugs where
        you're asserting on the wrong method name.

        spec=PaymentGateway constrains the mock to only expose methods that
        exist on PaymentGateway. Calling a nonexistent method raises AttributeError.
        """
        # Spec-constrained mock
        constrained_gateway = MagicMock(spec=PaymentGateway)
        constrained_gateway.charge.return_value = True

        proc = PaymentProcessor(constrained_gateway, MagicMock())
        tx   = Transaction("TX-SPEC", 1, 100.00)
        result = proc.process(tx)

        self.assertEqual(result, "success")

        # This would raise AttributeError — good! Catches typo bugs.
        # constrained_gateway.chargee()  # ← AttributeError: 'chargee' not in spec

        # Verify we're calling the real method name
        constrained_gateway.charge.assert_called_once_with(tx)

    # ── Question C: When you're forced to use @patch ───────────────────────

    def test_C_when_patch_is_necessary(self):
        """
        @patch is necessary when you CANNOT control the collaborator through
        the constructor — e.g., when the class instantiates its dependency
        internally, or when it imports a module-level function directly.

        Example: imagine FraudAwareProcessor was written like this (bad design):

            class BadProcessor:
                def process(self, tx):
                    detector = FraudDetector()   # ← instantiated internally!
                    result = detector.check(tx)
                    ...

        With constructor injection (the good design we have), we can just
        pass a mock in. But with BadProcessor, we'd HAVE to use @patch.

        Real situations where you're forced to use @patch:
        1. Third-party code that creates its own DB connections internally
        2. Module-level globals (e.g., a shared requests.Session)
        3. datetime.now() or random.random() — these can't be injected easily
        4. Legacy code you can't refactor

        The lesson: PREFER constructor injection. Use @patch as a last resort.
        """
        # Demonstrating @patch for patching a module-level import.
        # (In our codebase we use injection, so this is illustrative.)
        pass


# =============================================================================
# TASK 4 SOLUTION: CheckoutService with Spies
# =============================================================================
# APPROACH: FeeCalculator is a pure, side-effect-free class we own.
# CheckoutService delegates to it. We use a spy so:
#   1. Real fee maths executes — we can assert the receipt values are correct
#   2. Call arguments are recorded — we can verify proper delegation
#
# This lets us test BOTH the wiring (CheckoutService calls FeeCalculator
# with the right args) AND the correctness (the real formula produces the
# right fee) in one test pass — something a mock alone cannot do.
# =============================================================================

# Add FeeCalculator and CheckoutService to banklite.py as shown in the exercise.
# The classes are reproduced here for self-contained running.

class FeeCalculator:
    BASE_FEE_RATE  = 0.029
    FIXED_FEE      = 0.30
    INTL_SURCHARGE = 0.015

    def processing_fee(self, amount: float, currency: str = "USD") -> float:
        rate = self.BASE_FEE_RATE
        if currency != "USD":
            rate += self.INTL_SURCHARGE
        return round(amount * rate + self.FIXED_FEE, 2)

    def net_amount(self, amount: float, currency: str = "USD") -> float:
        fee = self.processing_fee(amount, currency)
        return round(amount - fee, 2)


class CheckoutService:
    def __init__(self, fee_calc: FeeCalculator, gateway):
        self._fee_calc = fee_calc
        self._gateway  = gateway

    def checkout(self, tx: Transaction) -> dict:
        fee    = self._fee_calc.processing_fee(tx.amount, tx.currency)
        net    = self._fee_calc.net_amount(tx.amount, tx.currency)
        status = "success" if self._gateway.charge(tx) else "declined"
        return {"tx_id": tx.tx_id, "amount": tx.amount,
                "fee": fee, "net": net, "status": status}


class TestCheckoutServiceWithSpy(unittest.TestCase):

    def setUp(self):
        real_calc      = FeeCalculator()
        self.spy_calc  = MagicMock(wraps=real_calc)   # spy wraps real object
        self.gateway   = MagicMock()
        self.gateway.charge.return_value = True
        self.svc       = CheckoutService(self.spy_calc, self.gateway)

    def _usd_tx(self, amount=100.00):
        return Transaction("TX-USD", 1, amount, currency="USD")

    def _eur_tx(self, amount=200.00):
        return Transaction("TX-EUR", 1, amount, currency="EUR")

    # ── Real maths tests (state verification via spy) ─────────────────────

    def test_usd_processing_fee_is_correct(self):
        """
        WHY: Real FeeCalculator logic runs through the spy.
        We verify the receipt fee matches the real formula output.
        With a plain mock we'd only be testing that CheckoutService
        uses whatever the calculator returns — not that the formula is right.
        """
        receipt = self.svc.checkout(self._usd_tx(100.00))

        # 100 * 0.029 + 0.30 = 3.20
        self.assertEqual(receipt["fee"], 3.20)

    def test_international_fee_includes_surcharge(self):
        """
        WHY: EUR transactions must use BASE_FEE_RATE + INTL_SURCHARGE.
        The spy lets the real formula run so we can catch rate config bugs.
        """
        receipt = self.svc.checkout(self._eur_tx(200.00))

        # 200 * (0.029 + 0.015) + 0.30 = 200 * 0.044 + 0.30 = 9.10
        self.assertEqual(receipt["fee"], 9.10)

    def test_net_amount_is_amount_minus_fee(self):
        """
        WHY: Verify the net field is computed correctly end-to-end.
        Real subtraction runs; no hardcoded values needed.
        """
        receipt = self.svc.checkout(self._usd_tx(100.00))

        self.assertEqual(receipt["net"], round(100.00 - 3.20, 2))  # 96.80

    # ── Delegation tests (behaviour verification via spy) ─────────────────

    def test_processing_fee_called_with_correct_amount_and_currency(self):
        """
        WHY: Spy records the call so we can verify CheckoutService
        passes tx.amount and tx.currency — not some other value.
        """
        tx = self._usd_tx(250.00)
        self.svc.checkout(tx)

        self.spy_calc.processing_fee.assert_called_once_with(250.00, "USD")

    def test_net_amount_called_with_correct_amount_and_currency(self):
        tx = self._eur_tx(150.00)
        self.svc.checkout(tx)

        self.spy_calc.net_amount.assert_called_once_with(150.00, "EUR")

    def test_each_fee_method_called_exactly_once_per_checkout(self):
        """
        WHY: Guard against accidental double-calls. If CheckoutService
        called processing_fee twice, the customer might be double-charged.
        """
        self.svc.checkout(self._usd_tx(500.00))

        self.assertEqual(self.spy_calc.processing_fee.call_count, 1)
        self.assertEqual(self.spy_calc.net_amount.call_count, 1)

    def test_real_fee_value_flows_correctly_into_receipt(self):
        """
        WHY: In unittest.mock, a spy (MagicMock(wraps=real)) returns the real
        method's value directly from the call. The receipt dict contains those
        real formula outputs. Asserting on receipt["fee"] proves both that the
        real formula ran correctly AND that CheckoutService stored the value
        without any transformation, truncation, or rounding error.

        Note: spy_return is a pytest-mock feature (mocker.spy), not unittest.mock.
        In unittest.mock, capture the real return value from the result directly.
        """
        receipt = self.svc.checkout(self._usd_tx(1000.00))

        # Real formula: 1000 * 0.029 + 0.30 = 29.30
        self.assertEqual(receipt["fee"], 29.30)
        # Real formula: 1000 - 29.30 = 970.70
        self.assertEqual(receipt["net"], 970.70)

    # ── Partial spy with patch.object ─────────────────────────────────────

    def test_partial_spy_on_net_amount_only(self):
        """
        WHY: patch.object lets you spy on ONE method while leaving all
        others as-is. This is useful when you want surgical observation
        without replacing the whole object.

        Here: processing_fee runs unwatched (real); only net_amount is spied.
        """
        real_calc = FeeCalculator()
        svc       = CheckoutService(real_calc, self.gateway)
        tx        = self._usd_tx(500.00)

        with patch.object(real_calc, "net_amount",
                          wraps=real_calc.net_amount) as spy_net:
            receipt = svc.checkout(tx)

        # Delegation verified
        spy_net.assert_called_once_with(500.00, "USD")
        # Real result verified — 500 - (500*0.029 + 0.30) = 500 - 14.80 = 485.20
        # In unittest.mock, the real value is in the receipt dict directly
        self.assertEqual(receipt["net"], 485.20)

    # ── Contrast: mock for wiring-only verification ───────────────────────

    def test_contrast_mock_only_tests_wiring_not_formula(self):
        """
        WHY: This is the MOCK version of the same test.
        Notice what it CAN and CANNOT verify:

        CAN verify: CheckoutService uses the values from FeeCalculator.
        CANNOT verify: FeeCalculator's formula is actually correct.

        If FeeCalculator.processing_fee had a bug (e.g., used 0.29 instead
        of 0.029), this test would still pass — because it never runs the
        real formula.

        Use mocks for external/slow/dangerous collaborators.
        Use spies for owned, pure, fast collaborators where formula
        correctness also matters.
        """
        mock_calc = MagicMock()
        mock_calc.processing_fee.return_value = 5.00   # arbitrary hardcoded
        mock_calc.net_amount.return_value     = 95.00  # arbitrary hardcoded

        svc     = CheckoutService(mock_calc, self.gateway)
        receipt = svc.checkout(self._usd_tx(100.00))

        # Tests wiring: CheckoutService used whatever the calculator returned
        self.assertEqual(receipt["fee"],    5.00)
        self.assertEqual(receipt["net"],   95.00)
        self.assertEqual(receipt["status"], "success")
        mock_calc.processing_fee.assert_called_once()

        # NOTE: We have NO idea if the real fee formula is correct.
        # A spy test catches formula bugs; this test only catches wiring bugs.


# =============================================================================
# TASK 5 SOLUTION: Stretch Design Questions
# =============================================================================

class TestStretchChallenges(unittest.TestCase):

    def test_A_wrong_way_stub_used_as_mock(self):
        """
        QUESTION A: Could you accidentally turn StatementBuilder stubs into mocks?

        YES — and it's a common mistake. If you add mock assertions to the
        StatementBuilder tests, like verifying that find_by_user was called
        exactly once, you over-specify the test. It now breaks if the
        implementation calls the repo twice (e.g., for caching), even if
        the output is still correct.

        WRONG approach (don't do this):
            repo.find_by_user.assert_called_once_with(user_id)
            ← this ties the test to implementation detail, not behaviour

        CORRECT approach:
            self.assertEqual(result["total_charged"], expected_total)
            ← this tests the observable output only
        """
        repo    = MagicMock()
        repo.find_by_user.return_value = []
        builder = StatementBuilder(repo)

        builder.build(user_id=1)

        # Intentionally NOT asserting on repo.find_by_user calls.
        # The test cares about the result, not how many times the repo was hit.
        pass

    def test_B_spec_mock_prevents_nonexistent_method_calls(self):
        """
        QUESTION B: What does spec= prevent?

        MagicMock(spec=PaymentGateway) constrains the mock to only expose
        methods that actually exist on PaymentGateway. Calling a nonexistent
        method raises AttributeError immediately — catching typos at test time.

        Without spec=: mock.chargee() silently succeeds (returns a MagicMock).
        With spec=:    mock.chargee() raises AttributeError — bug caught!
        """
        constrained = MagicMock(spec=PaymentGateway)
        constrained.charge.return_value = True

        proc = PaymentProcessor(constrained, MagicMock())
        tx   = Transaction("TX-SPEC", 1, 100.00)
        result = proc.process(tx)

        self.assertEqual(result, "success")
        constrained.charge.assert_called_once_with(tx)

        # Uncommenting the next line would raise AttributeError:
        # constrained.chargee()  # ← typo caught by spec=

    def test_D_why_fraud_detector_needs_mock_not_spy(self):
        """
        QUESTION D: Could you use a spy for FraudDetector?

        NO — and here's why. FraudDetector.check() in production calls an
        external fraud API over the network. A spy passes calls through to
        the real object, which means the real network request would fire
        during the test. That violates the core principle of test isolation:
        - It would be slow (network latency)
        - It would be unreliable (API might be down)
        - It would cost money (many fraud APIs charge per call)
        - It would be non-deterministic (live risk scores change)

        The spy decision rule: "Is it safe, fast, and side-effect-free
        to run the real code here?" For FraudDetector: NO.
        Therefore: use a mock, not a spy.

        Contrast with FeeCalculator (Task 4): pure maths, no I/O,
        deterministic, free to call → spy is perfect.
        """
        # Demonstrating that FraudDetector.check raises if actually called
        # (because NotImplementedError is the sentinel for "external system"):
        real_detector = FraudDetector()
        tx = Transaction("TX-D", 1, 100.00)

        with self.assertRaises(NotImplementedError):
            real_detector.check(tx)  # ← proves calling it is dangerous

        # A spy would let this NotImplementedError reach our test.
        # A mock prevents it entirely — the right choice here.


# =============================================================================
# KEY TAKEAWAYS (read these after reviewing the solution)
# =============================================================================
#
# 1. STUBS control inputs. MOCKS verify outputs (calls/side-effects).
#    Don't add mock assertions to stub tests — it creates brittle tests.
#
# 2. assert_not_called() is often your most important assertion.
#    Proving that no unwanted side-effects occurred is half the contract.
#
# 3. Boundary value tests (exactly at threshold) catch the most bugs
#    with the fewest lines of code. Always test at, above, and below limits.
#
# 4. side_effect = SomeException forces the mock to raise on call.
#    This is how you test error-handling paths without a real failure.
#
# 5. spec= on MagicMock prevents phantom method calls and catches typos.
#    Use it whenever the interface is well-defined (which it always should be).
#
# 6. Constructor injection > @patch. Design your classes to receive
#    collaborators from outside — it makes them testable by default.
#
# 7. SPIES = MagicMock(wraps=real_obj). Real logic executes AND calls are
#    recorded. Use for pure, owned collaborators where formula correctness
#    also needs verification. In unittest.mock, capture real return values
#    directly from the call result — spy_return is a pytest-mock feature only.
#
# 8. PARTIAL SPIES via patch.object(obj, "method", wraps=obj.method) let
#    you observe just one method surgically without replacing the whole object.
#
# 9. The spy decision rule: "Is it safe, fast, and side-effect-free to
#    run the real code?" YES → spy. NO → mock.
#
# 10. Spies catch formula bugs. Mocks catch wiring bugs. A complete test
#     suite often needs both.
#
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
