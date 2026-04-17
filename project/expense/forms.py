from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import CreditCardBillPayment, Expense, Loan, LoanPayment


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False, max_length=150)

    class Meta:
        model = User
        fields = ("first_name", "username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].help_text = ""
        self.fields["username"].help_text = ""
        self.fields["email"].help_text = ""
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""
        self.fields["first_name"].widget.attrs.update({"placeholder": "Your name"})
        self.fields["username"].widget.attrs.update({"placeholder": "Choose a username"})
        self.fields["email"].widget.attrs.update({"placeholder": "name@example.com"})
        self.fields["password1"].widget.attrs.update({"placeholder": "Create a password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Confirm password"})


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your password"}
        )


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None, format=None):
        base_attrs = {"class": "form-control", "type": "date"}
        if attrs:
            base_attrs.update(attrs)
        super().__init__(attrs=base_attrs, format=format)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            classes = f"{existing} form-control".strip()
            if isinstance(field.widget, forms.CheckboxInput):
                classes = f"{existing} form-check-input".strip()
            elif isinstance(field.widget, (forms.Select,)):
                classes = f"{existing} form-select".strip()
            elif isinstance(field.widget, forms.Textarea):
                classes = f"{existing} form-control min-h-[120px]".strip()
            field.widget.attrs["class"] = classes
            if name == "payment_method":
                field.help_text = "Credit Card adds to card spending; Credit Card Bill Payment reduces your credit due."
            if name == "notes":
                field.widget.attrs.setdefault("placeholder", "Optional notes")


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense
        fields = ["title", "category", "amount", "expense_date", "payment_method", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Dinner, Groceries, Petrol..."}),
            "category": forms.Select(),
            "amount": forms.NumberInput(attrs={"placeholder": "0.00", "step": "0.01"}),
            "expense_date": DateInput(),
            "payment_method": forms.Select(),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class CreditCardBillPaymentForm(StyledModelForm):
    class Meta:
        model = CreditCardBillPayment
        fields = ["amount", "paid_on", "notes"]
        widgets = {
            "amount": forms.NumberInput(attrs={"placeholder": "0.00", "step": "0.01"}),
            "paid_on": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class LoanForm(StyledModelForm):
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
            "counterparty": forms.TextInput(attrs={"placeholder": "Person or bank name"}),
            "loan_type": forms.Select(),
            "principal_amount": forms.NumberInput(attrs={"placeholder": "0.00", "step": "0.01"}),
            "annual_interest_rate": forms.NumberInput(attrs={"placeholder": "0.00", "step": "0.01"}),
            "tenure_months": forms.NumberInput(attrs={"placeholder": "12"}),
            "start_date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class LoanPaymentForm(StyledModelForm):
    class Meta:
        model = LoanPayment
        fields = ["amount", "paid_on", "notes"]
        widgets = {
            "amount": forms.NumberInput(attrs={"placeholder": "0.00", "step": "0.01"}),
            "paid_on": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
