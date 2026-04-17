import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CreditCardBillPaymentForm, ExpenseForm, LoanForm, LoanPaymentForm, LoginForm, SignUpForm
from .models import CreditCardBillPayment, Expense, Loan, LoanPayment


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("login")
    return render(request, "expense/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard")
    return render(request, "expense/login.html", {"form": form})


def _period_bounds(period):
    today = timezone.localdate()
    if period == "daily":
        return today, today
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period == "monthly":
        start = today.replace(day=1)
        return start, today
    if period == "yearly":
        start = today.replace(month=1, day=1)
        return start, today
    return None, None


def _build_prediction(expenses):
    monthly_totals = (
        expenses.annotate(month=TruncMonth("expense_date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    values = [Decimal(item["total"]) for item in monthly_totals]
    if not values:
        return Decimal("0.00"), Decimal("0.00")
    if len(values) == 1:
        return values[0], values[0] * Decimal("12")
    growth_steps = [values[i] - values[i - 1] for i in range(1, len(values))]
    predicted_next_month = values[-1] + (sum(growth_steps) / Decimal(len(growth_steps)))
    if predicted_next_month < 0:
        predicted_next_month = Decimal("0.00")
    return predicted_next_month.quantize(Decimal("0.01")), (predicted_next_month * Decimal("12")).quantize(Decimal("0.01"))


def _chart_data(expenses):
    chart_rows = (
        expenses.annotate(month=TruncMonth("expense_date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    return [{"label": row["month"].strftime("%b %Y"), "total": float(row["total"])} for row in chart_rows]


def _payment_chart_data(expenses):
    rows = expenses.values("payment_method").annotate(total=Sum("amount")).order_by("payment_method")
    return [{"label": Expense.PAYMENT_CHOICES_DICT.get(row["payment_method"], row["payment_method"]), "total": float(row["total"])} for row in rows]


def _category_chart_data(expenses):
    rows = expenses.values("category").annotate(total=Sum("amount")).order_by("-total")[:7]
    return [{"label": Expense.CATEGORY_CHOICES_DICT.get(row["category"], row["category"]), "total": float(row["total"])} for row in rows]


def _simple_pdf_bytes(title, lines):
    def esc(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = ["BT", "/F1 14 Tf", "50 800 Td", f"({esc(title)}) Tj", "/F1 10 Tf", "0 -20 Td"]
    for line in lines[:52]:
        content_lines.extend([f"({esc(line)}) Tj", "0 -14 Td"])
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="ignore")

    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    objects.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj")
    objects.append(f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj")
    objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj + b"\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("latin-1")
    )
    return bytes(pdf)


def _table_pdf_bytes(title, generated_on, username, summary_rows, headers, rows):
    def esc(text):
        return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    max_rows = 28
    safe_rows = rows[:max_rows]

    page_w = 595
    page_h = 842
    left = 38
    right = page_w - 38
    table_top = 655
    row_h = 17
    total_rows = 1 + len(safe_rows)
    table_bottom = table_top - (row_h * total_rows)
    col_x = [left, 68, 138, 284, 390, 475, right]

    c = []
    c.append("BT /F2 16 Tf 38 804 Td ({}) Tj ET".format(esc(title)))
    c.append("BT /F1 10 Tf 38 784 Td (Generated: {}) Tj ET".format(esc(generated_on)))
    c.append("BT /F1 10 Tf 38 768 Td (User: {}) Tj ET".format(esc(username)))

    y = 744
    c.append("BT /F2 11 Tf 38 {} Td (Summary) Tj ET".format(y))
    y -= 16
    for label, value in summary_rows:
        c.append("BT /F1 10 Tf 44 {} Td ({}: {}) Tj ET".format(y, esc(label), esc(value)))
        y -= 14

    c.append("0.40 w")
    for i in range(total_rows + 1):
        y_line = table_top - (i * row_h)
        c.append(f"{left} {y_line} m {right} {y_line} l S")
    for x in col_x:
        c.append(f"{x} {table_top} m {x} {table_bottom} l S")

    header_y = table_top - 12
    for idx, header in enumerate(headers):
        c.append(
            "BT /F2 9 Tf {} {} Td ({}) Tj ET".format(
                col_x[idx] + 3,
                header_y,
                esc(header),
            )
        )

    for r_index, row in enumerate(safe_rows):
        y_text = table_top - ((r_index + 1) * row_h) - 12
        for c_index, value in enumerate(row):
            c.append(
                "BT /F1 8 Tf {} {} Td ({}) Tj ET".format(
                    col_x[c_index] + 3,
                    y_text,
                    esc(value),
                )
            )

    stream = "\n".join(c).encode("latin-1", errors="ignore")

    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >> endobj"
    )
    objects.append(f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj")
    objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.append(b"6 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj + b"\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("latin-1"))
    return bytes(pdf)


def _bar_data(data):
    if not data:
        return []
    max_total = max(item["total"] for item in data) or 1
    grand_total = sum(item["total"] for item in data) or 1
    out = []
    for item in data:
        width = max(6, int((item["total"] / max_total) * 100))
        share = round((item["total"] / grand_total) * 100, 1)
        out.append(
            {
                "label": item["label"],
                "total": round(item["total"], 2),
                "width": width,
                "share": share,
            }
        )
    return out


@login_required
def dashboard(request):
    expenses = Expense.objects.filter(user=request.user)
    loans = Loan.objects.filter(user=request.user)
    recent_expenses = expenses[:5]
    recent_bills = CreditCardBillPayment.objects.filter(user=request.user)[:5]

    daily_start, daily_end = _period_bounds("daily")
    weekly_start, weekly_end = _period_bounds("weekly")
    monthly_start, monthly_end = _period_bounds("monthly")
    yearly_start, yearly_end = _period_bounds("yearly")

    total_daily = expenses.filter(expense_date__range=(daily_start, daily_end)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_weekly = expenses.filter(expense_date__range=(weekly_start, weekly_end)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_monthly = expenses.filter(expense_date__range=(monthly_start, monthly_end)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_yearly = expenses.filter(expense_date__range=(yearly_start, yearly_end)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    loan_remaining_total = sum((loan.remaining_amount for loan in loans), Decimal("0.00"))
    credit_spent_total = expenses.filter(payment_method=Expense.PAYMENT_CREDIT_CARD).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    credit_paid_total = CreditCardBillPayment.objects.filter(user=request.user).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    credit_outstanding = max(Decimal("0.00"), credit_spent_total - credit_paid_total)
    total_balance_view = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    predicted_next_month, predicted_next_year = _build_prediction(expenses)
    monthly_chart_data = _bar_data(_chart_data(expenses))
    payment_chart_data = _bar_data(_payment_chart_data(expenses))
    category_chart_data = _bar_data(_category_chart_data(expenses))
    active_loans = [loan for loan in loans if loan.remaining_amount > 0]
    active_loans.sort(key=lambda loan: loan.next_emi_due_date or timezone.localdate())
    upcoming_loans = [loan for loan in active_loans if loan.next_emi_due_date][:4]
    loan_taken_total = sum(
        (loan.remaining_amount for loan in loans if loan.loan_type == Loan.LOAN_TAKEN),
        Decimal("0.00"),
    )
    loan_given_total = sum(
        (loan.remaining_amount for loan in loans if loan.loan_type == Loan.LOAN_GIVEN),
        Decimal("0.00"),
    )
    monthly_budget_target = predicted_next_month if predicted_next_month > 0 else total_monthly
    spent_ratio = Decimal("0.00")
    if monthly_budget_target > 0:
        spent_ratio = min(Decimal("100.00"), (total_monthly / monthly_budget_target) * Decimal("100"))
    spent_ratio = round(spent_ratio, 1)
    spent_angle = round(float(spent_ratio) * 3.6, 1)
    goal_remaining = max(Decimal("0.00"), monthly_budget_target - total_monthly)
    period_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekly_values = [Decimal("0.00")] * 7
    for expense in expenses.filter(expense_date__range=(weekly_start, weekly_end)):
        weekly_values[expense.expense_date.weekday()] += expense.amount
    max_weekly_value = max(weekly_values) if any(weekly_values) else Decimal("1.00")
    weekly_activity = []
    for index, value in enumerate(weekly_values):
        weekly_activity.append(
            {
                "label": period_labels[index],
                "total": value.quantize(Decimal("0.01")),
                "height": max(14, int((value / max_weekly_value) * 100)) if value else 14,
            }
        )

    return render(
        request,
        "expense/dashboard.html",
        {
            "total_daily": total_daily,
            "total_weekly": total_weekly,
            "total_monthly": total_monthly,
            "total_yearly": total_yearly,
            "total_balance_view": total_balance_view,
            "loan_remaining_total": loan_remaining_total,
            "loan_taken_total": loan_taken_total,
            "loan_given_total": loan_given_total,
            "expense_count": expenses.count(),
            "credit_spent_total": credit_spent_total,
            "credit_outstanding": credit_outstanding,
            "predicted_next_month": predicted_next_month,
            "predicted_next_year": predicted_next_year,
            "monthly_chart_data": monthly_chart_data,
            "payment_chart_data": payment_chart_data,
            "category_chart_data": category_chart_data,
            "recent_expenses": recent_expenses,
            "recent_bills": recent_bills,
            "upcoming_loans": upcoming_loans,
            "monthly_budget_target": monthly_budget_target.quantize(Decimal("0.01")) if monthly_budget_target else Decimal("0.00"),
            "goal_remaining": goal_remaining.quantize(Decimal("0.01")),
            "spent_ratio": spent_ratio,
            "spent_angle": spent_angle,
            "weekly_activity": weekly_activity,
            "dashboard_timestamp": timezone.localtime().strftime("%I:%M %p | %d %b %Y"),
        },
    )


@login_required
def expense_create(request):
    form = ExpenseForm(request.POST or None, initial={"expense_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        if expense.payment_method == Expense.PAYMENT_CREDIT_CARD_BILL:
            CreditCardBillPayment.objects.create(
                user=request.user,
                amount=expense.amount,
                paid_on=expense.expense_date,
                notes=expense.notes,
            )
            return redirect("credit_bill_list")
        expense.user = request.user
        expense.save()
        return redirect("expense_period_list", period="monthly")
    return render(request, "expense/form.html", {"form": form, "title": "Add Expense"})


def _month_weeks(year, month, week_start=0):
    """
    Return list of (week_num, start_date, end_date) for the month.
    week_start: 0=Monday, 6=Sunday
    """
    from calendar import monthrange
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    weeks = []
    week_num = 1
    current = first_day
    # Find the end of the first week
    first_weekday = current.weekday()  # 0=Monday
    if first_weekday != week_start:
        # End of first week is the first week_start+6 or last day
        days_to_end = (7 - (first_weekday - week_start)) % 7
        week_end = min(current + timedelta(days=days_to_end), last_day)
    else:
        week_end = min(current + timedelta(days=6), last_day)
    weeks.append((week_num, current, week_end))
    week_num += 1
    current = week_end + timedelta(days=1)
    # Full weeks
    while current <= last_day:
        week_end = min(current + timedelta(days=6), last_day)
        weeks.append((week_num, current, week_end))
        week_num += 1
        current = week_end + timedelta(days=1)
    return weeks


def _get_week_navigation(year, month, selected_week):
    """Generate previous and next week navigation URLs."""
    if selected_week > 1:
        prev_week = selected_week - 1
        prev_month = month
        prev_year = year
    else:
        prev_week = 4
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year = year - 1

    if selected_week < 4:
        next_week = selected_week + 1
        next_month = month
        next_year = year
    else:
        next_week = 1
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year = year + 1

    return {
        "prev": {"year": prev_year, "month": prev_month, "week": prev_week},
        "next": {"year": next_year, "month": next_month, "week": next_week},
    }


@login_required
def expense_period_list(request, period):
    start, end = _period_bounds(period)
    if start is None:
        return HttpResponseForbidden("Invalid period.")

    period_label = period.capitalize()
    current_date = timezone.localdate()
    current_year = current_date.year
    year_options = list(range(2020, current_year + 2))
    month_options = [(i, calendar.month_name[i]) for i in range(1, 13)]
    # week_options will be dynamically set based on the number of weeks in the month
    week_options = []

    selected_year = start.year
    selected_month = start.month
    selected_week = 1
    selected_day = start

    if period == "daily":
        date_str = request.GET.get("date")
        if date_str:
            try:
                selected_day = date.fromisoformat(date_str)
                start = end = selected_day
                period_label = selected_day.strftime("%d %B %Y")
            except ValueError:
                return HttpResponseForbidden("Invalid date selection.")
    elif period == "weekly":
        year_str = request.GET.get("year")
        month_str = request.GET.get("month")
        week_str = request.GET.get("week")
        if year_str and month_str and week_str:
            try:
                selected_year = int(year_str)
                selected_month = int(month_str)
                selected_week = int(week_str)
                weeks = _month_weeks(selected_year, selected_month)
                week_options = list(range(1, len(weeks) + 1))
                if 1 <= selected_week <= len(weeks):
                    start, end = weeks[selected_week - 1][1], weeks[selected_week - 1][2]
                    period_label = f"Week {selected_week} - {start.strftime('%d %b')} to {end.strftime('%d %b %Y')}"
                else:
                    return HttpResponseForbidden("Invalid week selection.")
            except ValueError:
                return HttpResponseForbidden("Invalid week selection.")
        else:
            selected_week = 1
            weeks = _month_weeks(selected_year, selected_month)
            week_options = list(range(1, len(weeks) + 1))
            if weeks:
                start, end = weeks[0][1], weeks[0][2]
                period_label = f"Week 1 - {start.strftime('%d %b')} to {end.strftime('%d %b %Y')}"
    elif period == "monthly":
        year_str = request.GET.get("year")
        month_str = request.GET.get("month")
        if year_str and month_str:
            try:
                selected_year = int(year_str)
                selected_month = int(month_str)
                start = date(selected_year, selected_month, 1)
                last_day = calendar.monthrange(selected_year, selected_month)[1]
                end = date(selected_year, selected_month, last_day)
                period_label = start.strftime("%B %Y")
            except ValueError:
                return HttpResponseForbidden("Invalid month selection.")
    elif period == "yearly":
        year_str = request.GET.get("year")
        if year_str:
            try:
                selected_year = int(year_str)
                start = date(selected_year, 1, 1)
                end = date(selected_year, 12, 31)
                period_label = str(selected_year)
            except ValueError:
                return HttpResponseForbidden("Invalid year selection.")

    expenses = Expense.objects.filter(user=request.user, expense_date__range=(start, end))
    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    # Generate month weeks and navigation for weekly view
    month_weeks = _month_weeks(selected_year, selected_month)
    week_options = list(range(1, len(month_weeks) + 1))
    week_navigation = _get_week_navigation(selected_year, selected_month, selected_week)

    return render(
        request,
        "expense/expense_period_list.html",
        {
            "expenses": expenses,
            "period": period,
            "period_label": period_label,
            "total": total,
            "start": start,
            "end": end,
            "year_options": year_options,
            "month_options": month_options,
            "week_options": week_options,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "selected_week": selected_week,
            "selected_day": selected_day,
            "month_weeks": month_weeks,
            "week_navigation": week_navigation,
        },
    )


@login_required
def expense_create_period(request, period):
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        return HttpResponseForbidden("Invalid period.")
    initial_date = timezone.localdate()
    if period == "weekly":
        initial_date = initial_date - timedelta(days=initial_date.weekday())
    if period == "monthly":
        initial_date = initial_date.replace(day=1)
    if period == "yearly":
        initial_date = initial_date.replace(month=1, day=1)
    form = ExpenseForm(request.POST or None, initial={"expense_date": initial_date})
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        if expense.payment_method == Expense.PAYMENT_CREDIT_CARD_BILL:
            CreditCardBillPayment.objects.create(
                user=request.user,
                amount=expense.amount,
                paid_on=expense.expense_date,
                notes=expense.notes,
            )
            return redirect("credit_bill_list")
        expense.user = request.user
        expense.save()
        return redirect("expense_period_list", period=period)
    return render(request, "expense/form.html", {"form": form, "title": f"Add {period.capitalize()} Expense"})


@login_required
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if expense.user != request.user:
        return HttpResponseForbidden("You cannot edit this expense.")
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("expense_period_list", period="monthly")
    return render(request, "expense/form.html", {"form": form, "title": "Update Expense"})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if expense.user != request.user:
        return HttpResponseForbidden("You cannot delete this expense.")
    if request.method == "POST":
        expense.delete()
        return redirect("expense_period_list", period="monthly")
    return render(request, "expense/confirm_delete.html", {"object": expense, "title": "Delete Expense"})


@login_required
def loan_list(request):
    loans = Loan.objects.filter(user=request.user)
    return render(request, "expense/loan_list.html", {"loans": loans})


@login_required
def loan_create(request):
    form = LoanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        loan = form.save(commit=False)
        loan.user = request.user
        loan.save()
        return redirect("loan_list")
    return render(request, "expense/form.html", {"form": form, "title": "Add Loan"})


@login_required
def loan_update(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if loan.user != request.user:
        return HttpResponseForbidden("You cannot edit this loan.")
    form = LoanForm(request.POST or None, instance=loan)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("loan_list")
    return render(request, "expense/form.html", {"form": form, "title": "Update Loan"})


@login_required
def loan_delete(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if loan.user != request.user:
        return HttpResponseForbidden("You cannot delete this loan.")
    if request.method == "POST":
        loan.delete()
        return redirect("loan_list")
    return render(request, "expense/confirm_delete.html", {"object": loan, "title": "Delete Loan"})


@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if loan.user != request.user:
        return HttpResponseForbidden("You cannot view this loan.")
    payment_form = LoanPaymentForm(request.POST or None)
    if request.method == "POST" and payment_form.is_valid():
        payment = payment_form.save(commit=False)
        payment.loan = loan
        payment.save()
        return redirect("loan_detail", pk=loan.pk)
    return render(
        request,
        "expense/loan_detail.html",
        {"loan": loan, "payments": loan.payments.all(), "payment_form": payment_form},
    )


@login_required
def loan_payment_delete(request, pk):
    payment = get_object_or_404(LoanPayment, pk=pk)
    if payment.loan.user != request.user:
        return HttpResponseForbidden("You cannot delete this payment.")
    loan_id = payment.loan_id
    if request.method == "POST":
        payment.delete()
        return redirect("loan_detail", pk=loan_id)
    return render(request, "expense/confirm_delete.html", {"object": payment, "title": "Delete Loan Payment"})


@login_required
def credit_bill_list(request):
    credit_expenses = Expense.objects.filter(user=request.user, payment_method=Expense.PAYMENT_CREDIT_CARD).order_by("-expense_date", "-created_at")
    payments = CreditCardBillPayment.objects.filter(user=request.user).order_by("-paid_on", "-created_at")
    credit_spent = credit_expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    credit_paid = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    credit_outstanding = max(Decimal("0.00"), credit_spent - credit_paid)
    return render(
        request,
        "expense/credit_bill_list.html",
        {
            "credit_expenses": credit_expenses,
            "payments": payments,
            "credit_spent": credit_spent,
            "credit_paid": credit_paid,
            "credit_outstanding": credit_outstanding,
        },
    )


@login_required
def credit_bill_create(request):
    form = CreditCardBillPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        bill = form.save(commit=False)
        bill.user = request.user
        bill.save()
        return redirect("credit_bill_list")
    return render(request, "expense/form.html", {"form": form, "title": "Pay Credit Card Bill"})


@login_required
def credit_bill_delete(request, pk):
    bill = get_object_or_404(CreditCardBillPayment, pk=pk)
    if bill.user != request.user:
        return HttpResponseForbidden("You cannot delete this bill payment.")
    if request.method == "POST":
        bill.delete()
        return redirect("credit_bill_list")
    return render(request, "expense/confirm_delete.html", {"object": bill, "title": "Delete Bill Payment"})


@login_required
def reports(request):
    expenses = Expense.objects.filter(user=request.user)
    chart_data = _bar_data(_chart_data(expenses))
    payment_chart_data = _bar_data(_payment_chart_data(expenses))
    category_chart_data = _bar_data(_category_chart_data(expenses))
    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return render(
        request,
        "expense/reports.html",
        {
            "chart_data": chart_data,
            "payment_chart_data": payment_chart_data,
            "category_chart_data": category_chart_data,
            "total": total,
        },
    )


@login_required
def export_pdf(request):
    expenses = list(Expense.objects.filter(user=request.user).order_by("-expense_date", "-id")[:45])
    total_expense = sum((item.amount for item in expenses), Decimal("0.00"))
    credit_spent = sum(
        (item.amount for item in expenses if item.payment_method == Expense.PAYMENT_CREDIT_CARD),
        Decimal("0.00"),
    )
    credit_paid = (
        CreditCardBillPayment.objects.filter(user=request.user).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    )
    credit_outstanding = max(Decimal("0.00"), credit_spent - credit_paid)

    now_text = timezone.localtime().strftime("%Y-%m-%d %H:%M")
    summary_rows = [
        ("Total Entries", str(len(expenses))),
        ("Total Expense", f"INR {total_expense:.2f}"),
        ("Credit Card Spent", f"INR {credit_spent:.2f}"),
        ("Credit Bills Paid", f"INR {credit_paid:.2f}"),
        ("Credit Outstanding", f"INR {credit_outstanding:.2f}"),
    ]

    headers = ["No", "Date", "Title", "Category", "Payment", "Amount"]
    table_rows = []
    for idx, item in enumerate(expenses, start=1):
        table_rows.append(
            [
                str(idx),
                str(item.expense_date),
                item.title[:24],
                item.get_category_display()[:14],
                item.get_payment_method_display()[:12],
                f"INR {item.amount:.2f}",
            ]
        )

    pdf = _table_pdf_bytes(
        title="PaisaPlanner Expense Report",
        generated_on=now_text,
        username=request.user.username,
        summary_rows=summary_rows,
        headers=headers,
        rows=table_rows,
    )
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="paisaplanner-report.pdf"'
    return response
