from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


class Expense(models.Model):
    PAYMENT_CASH = "cash"
    PAYMENT_UPI = "upi"
    PAYMENT_CREDIT_CARD = "credit_card"
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, "Cash"),
        (PAYMENT_UPI, "UPI"),
        (PAYMENT_CREDIT_CARD, "Credit Card"),
    ]
    PAYMENT_CHOICES_DICT = dict(PAYMENT_CHOICES)
    CATEGORY_ENTERTAINMENT = "entertainment"
    CATEGORY_GROCERY = "grocery"
    CATEGORY_FOOD = "food"
    CATEGORY_STATIONERY = "stationery"
    CATEGORY_TRANSPORT = "transport"
    CATEGORY_HEALTH = "health"
    CATEGORY_RENT = "rent"
    CATEGORY_EDUCATION = "education"
    CATEGORY_BILLS = "bills"
    CATEGORY_SHOPPING = "shopping"
    CATEGORY_OTHERS = "others"
    CATEGORY_CHOICES = [
        (CATEGORY_ENTERTAINMENT, "Entertainment"),
        (CATEGORY_GROCERY, "Grocery"),
        (CATEGORY_FOOD, "Food"),
        (CATEGORY_STATIONERY, "Stationery"),
        (CATEGORY_TRANSPORT, "Transport"),
        (CATEGORY_HEALTH, "Health"),
        (CATEGORY_RENT, "Rent"),
        (CATEGORY_EDUCATION, "Education"),
        (CATEGORY_BILLS, "Bills"),
        (CATEGORY_SHOPPING, "Shopping"),
        (CATEGORY_OTHERS, "Others"),
    ]
    CATEGORY_CHOICES_DICT = dict(CATEGORY_CHOICES)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=80, choices=CATEGORY_CHOICES, default=CATEGORY_OTHERS)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_UPI)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def __str__(self):
        return f"{self.title} - {self.amount}"


class CreditCardBillPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_card_bill_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-created_at"]

    def __str__(self):
        return f"Credit bill paid: {self.amount}"


class Loan(models.Model):
    LOAN_TAKEN = "taken"
    LOAN_GIVEN = "given"
    LOAN_TYPE_CHOICES = [
        (LOAN_TAKEN, "Loan Taken"),
        (LOAN_GIVEN, "Loan Given"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loans")
    counterparty = models.CharField(max_length=120)
    loan_type = models.CharField(max_length=10, choices=LOAN_TYPE_CHOICES)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual interest rate in %")
    tenure_months = models.PositiveIntegerField(default=12)
    start_date = models.DateField(default=timezone.localdate)
    emi_enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self):
        return f"{self.get_loan_type_display()} - {self.counterparty}"

    @property
    def monthly_interest_rate(self):
        return Decimal(self.annual_interest_rate) / Decimal("1200")

    @property
    def total_interest(self):
        rate = Decimal(self.annual_interest_rate) / Decimal("100")
        years = Decimal(self.tenure_months) / Decimal("12")
        total = Decimal(self.principal_amount) * rate * years
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def total_payable(self):
        return (Decimal(self.principal_amount) + self.total_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def emi_amount(self):
        if not self.emi_enabled or self.tenure_months == 0:
            return Decimal("0.00")
        principal = Decimal(self.principal_amount)
        monthly_rate = self.monthly_interest_rate
        months = Decimal(self.tenure_months)
        if monthly_rate == 0:
            emi = principal / months
        else:
            factor = (Decimal("1") + monthly_rate) ** int(self.tenure_months)
            emi = principal * monthly_rate * factor / (factor - Decimal("1"))
        return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def paid_amount(self):
        total_paid = self.payments.aggregate(total=models.Sum("amount"))["total"]
        return (total_paid or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def remaining_amount(self):
        remaining = self.total_payable - self.paid_amount
        if remaining < 0:
            return Decimal("0.00")
        return remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def next_emi_due_date(self):
        if not self.emi_enabled:
            return None
        paid_installments = self.payments.count()
        month_offset = paid_installments + 1
        year = self.start_date.year + ((self.start_date.month - 1 + month_offset - 1) // 12)
        month = ((self.start_date.month - 1 + month_offset - 1) % 12) + 1
        day = min(self.start_date.day, 28)
        return date(year, month, day)


class LoanPayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-created_at"]

    def __str__(self):
        return f"{self.loan.counterparty} payment - {self.amount}"
