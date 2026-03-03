from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("expenses/<str:period>/", views.expense_period_list, name="expense_period_list"),
    path("expenses/add/<str:period>/", views.expense_create_period, name="expense_create_period"),
    path("expenses/<int:pk>/edit/", views.expense_update, name="expense_update"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("loans/", views.loan_list, name="loan_list"),
    path("loans/add/", views.loan_create, name="loan_create"),
    path("loans/<int:pk>/", views.loan_detail, name="loan_detail"),
    path("loans/<int:pk>/edit/", views.loan_update, name="loan_update"),
    path("loans/<int:pk>/delete/", views.loan_delete, name="loan_delete"),
    path("loan-payments/<int:pk>/delete/", views.loan_payment_delete, name="loan_payment_delete"),
    path("credit-bills/", views.credit_bill_list, name="credit_bill_list"),
    path("credit-bills/add/", views.credit_bill_create, name="credit_bill_create"),
    path("credit-bills/<int:pk>/delete/", views.credit_bill_delete, name="credit_bill_delete"),
    path("reports/", views.reports, name="reports"),
    path("reports/export-pdf/", views.export_pdf, name="export_pdf"),
]
