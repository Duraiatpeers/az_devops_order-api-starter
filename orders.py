"""Business rules for the orders-api reference lab application."""
from dataclasses import dataclass

DISCOUNT_THRESHOLD = 1000.0   # orders at or above this amount get a discount
DISCOUNT_RATE = 0.10


class OrderRejected(Exception):
    """Raised when an order breaks a business rule."""


@dataclass
class Customer:
    customer_id: str
    status: str  # "Active" or "Inactive"


def order_total(amount: float) -> float:
    """Return the payable total after the volume discount."""
    if amount < 0:
        raise ValueError("amount must not be negative")
    if amount > DISCOUNT_THRESHOLD:
        return round(amount * (1 - DISCOUNT_RATE), 2)
    return round(amount, 2)


def place_order(customer: Customer, amount: float, store: list) -> dict:
    """Create an order and add it to the store."""
    order = {"id": len(store) + 1, "customer_id": customer.customer_id, "total": order_total(amount)}
    store.append(order)
    return order
