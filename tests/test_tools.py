from backend.tools import expense_validate,receipt_extract
def test_hotel_requires_approved_policy():
    r=expense_validate("hotel",8500,"M6",1)
    assert r["status"]=="approved_policy_required"
    assert r["eligible_amount"] is None
def test_receipt():
    assert receipt_extract("Hotel ABC\nDate 2026-11-01\nTotal INR 8500")["amount"]==8500
