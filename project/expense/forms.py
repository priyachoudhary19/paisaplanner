from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import CreditCardBillPayment, Expense, Loan, LoanPayment


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class DateInput(forms.DateInput):
    input_type = "date"


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["title", "category", "amount", "expense_date", "payment_method", "notes"]
        widgets = {
            "expense_date": DateInput(),
        }


class CreditCardBillPaymentForm(forms.ModelForm):
    class Meta:
        model = CreditCardBillPayment
        fields = ["amount", "paid_on", "notes"]
        widgets = {
            "paid_on": DateInput(),
        }


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = [
            "counterparty",
            "loan_type",
            "principal_amount",
            "annual_interest_rate",
            "tenure_months",
            "start_date",
            "emi_enabled",
            "notes",
        ]
        widgets = {
            "start_date": DateInput(),
        }


class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = ["amount", "paid_on", "notes"]
        widgets = {
            "paid_on": DateInput(),
        }
