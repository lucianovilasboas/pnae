from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.students.models import Student

from .models import Delivery, DeliveryStatus, DeliveryType, Distribution, DistributionStatus


def _campus_scope(user):
    """Campus efetivo do usuário; None = administrador global (todos)."""
    return getattr(user, "campus", None)


@login_required
def home(request):
    campus = _campus_scope(request.user)

    current = Distribution.objects.filter(status=DistributionStatus.OPEN)
    if campus is not None:
        current = current.filter(campus=campus)
    current = current.order_by("-opened_at").first()

    context = {"current_distribution": current, "summary": None}
    if current is not None:
        students = Student.objects.filter(campus=current.campus, active=True)
        valid = Delivery.objects.filter(
            distribution=current,
            delivery_type=DeliveryType.REGULAR,
            status=DeliveryStatus.VALIDA,
        )
        extras = Delivery.objects.filter(
            distribution=current,
            delivery_type=DeliveryType.EXCEDENTE,
            status=DeliveryStatus.VALIDA,
        )
        eligible = students.count()
        regular_valid = valid.count()
        context["summary"] = {
            "eligible": eligible,
            "regularValid": regular_valid,
            "extrasValid": extras.count(),
            "pending": eligible - regular_valid,
        }

    return render(request, "home.html", context)
