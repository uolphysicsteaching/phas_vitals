# Django imports
from django.conf import settings
from django.core.mail import EmailMessage
from django.template import loader
from django.views.generic import FormView
from util.views import IsSuperuserViewMixin
from util.spreadsheet import TutorReportSheet, save_virtual_workbook

from .forms import TutorSelectForm

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
            message = template.render(context)
            to = (tutor.email,)
            sender = settings.DEFAULT_FROM_EMAIL
            subject = "Physics and Astronomy VITALs Tutorial Update"
            email = EmailMessage(subject=subject, body=message, from_email=sender, to=to)
            email.attach(f"{tutor.initials}.xlsx", contents, "application/vnd.ms-excel")
            email.send()
        return super().form_valid(form)
