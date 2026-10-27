import pytest

from orders import Customer, order_total, place_order


def test_active_customer_order_is_accepted():
    store = []
    order = place_order(Customer("C1", "Active"), 200, store)
    assert order["total"] == 200 and len(store) == 1


@pytest.mark.parametrize("amount,expected", [(999.99, 999.99), (1500, 1350.0)])
def test_discount_threshold(amount, expected):
    assert order_total(amount) == expected


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        order_total(-1)
