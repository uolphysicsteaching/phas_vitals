# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.template import loader
from django.views.generic import FormView, TemplateView

# external imports
from util.spreadsheet import TutorReportSheet, save_virtual_workbook
from util.views import IsStudentViewixin, IsSuperuserViewMixin

# app imports
from .forms import TutorSelectForm
from .models import Account

TEMPLATE_PATH = settings.PROJECT_ROOT_PATH / "run" / "templates" / "Tutor_Report.xlsx"


class TutorGroupEmailsView(IsSuperuserViewMixin, FormView):
    """Select tutprs to send progress spreadsheets to."""

    form_class = TutorSelectForm
    template_name = "accounts/tutor_emails.html"
    success_url = "/util/tools/"

    def form_valid(selfr, form):
        """Process list of tutors and send emails."""
        tutors = form.cleaned_data["apt"]
        template = loader.get_template("email/tutor-report.txt")
        for tutor in tutors:
            update = TutorReportSheet(TEMPLATE_PATH, tutor=tutor)
            contents = save_virtual_workbook(update.workbook)
            context = {"tutor": tutor}
            message = template.render(context)  # nosemgrep
            to = (tutor.email,)
            sender = settings.DEFAULT_FROM_EMAIL
            subject = "Physics and Astronomy VITALs Tutorial Update"
            email = EmailMessage(subject=subject, body=message, from_email=sender, to=to)
            email.attach(f"{tutor.initials}.xlsx", contents, "application/vnd.ms-excel")
            email.send()
        return super().form_valid(form)


class StudentSummaryView(IsStudentViewixin, TemplateView):
    template_name = "accounts/summary.html"

    def get_context_data(self, **kwargs):
        """Get data for the student view."""
        if "username" in self.kwargs:
            user = Account.objects.get(username=self.kwargs["username"])
        else:
            user = Account.objects.get(number=self.kwargs["number"])
        modules = user.modules.all()
        VITALS = user.VITALS.model.objects.filter(module__in=modules).order_by("module", "start_date")
        Tests = user.tests.model.objects.filter(module__in=modules).order_by("release_date")
        test_scores = {}
        for test in Tests:
            try:
                test_scores[test] = user.test_results.get(test=test)
            except ObjectDoesNotExist:
                new_tr = user.test_results.model(user=user, test=test, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                test_scores[test] = new_tr
        vitals_results = {}
        for vital in VITALS:
            try:
                vitals_results[vital.module] = vitals_results.get(vital.module, []) + [
                    user.vital_results.get(vital=vital)
                ]
            except ObjectDoesNotExist:
                new_vr = user.vitals_result.model(user=user, vital=vital, passed=False)
                vitals_results[vital] = vitals_results.get(vital.module, []) + [new_vr]
        context = super().get_context_data(**kwargs)
        context |= {
            "user": user,
            "modules": modules,
            "VITALS": VITALS,
            "Tests": Tests,
            "scores": test_scores,
            "vitals_results": vitals_results,
        }
        return context
