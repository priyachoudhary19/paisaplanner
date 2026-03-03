from django.contrib import admin

from .models import CreditCardBillPayment, Expense, Loan, LoanPayment

admin.site.register(Expense)
admin.site.register(CreditCardBillPayment)
admin.site.register(Loan)
admin.site.register(LoanPayment)
