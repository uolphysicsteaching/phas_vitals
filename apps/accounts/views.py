"""View classes for the accounts app."""
# Python imports
from collections import namedtuple

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.template import loader
from django.views.generic import FormView, TemplateView

# external imports
import matplotlib.pyplot as plt
import numpy as np
from util.http import svg_data
from util.spreadsheet import TutorReportSheet, save_virtual_workbook
from util.views import IsStudentViewixin, IsSuperuserViewMixin

# app imports
from .forms import TutorSelectForm
from .models import Account

TEMPLATE_PATH = settings.PROJECT_ROOT_PATH / "run" / "templates" / "Tutor_Report.xlsx"

ImageData = namedtuple("ImageData", ["data", "alt"], defaults=["", ""])


def pie_chart(data, colours):
    """Make a Pie chart for the student dashboard."""
    fig, ax = plt.subplots()
    fig.set_figwidth(4.5)
    _, texts = ax.pie(list(data.values()), labels=list(data.keys()), colors=colours, labeldistance=0.3)
    for text in texts:
        text.set_bbox({"facecolor": (1, 1, 1, 0.75), "edgecolor": (1, 1, 1, 0.25)})
    data = svg_data(fig, base64=True)
    plt.close()
    return data


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
    """View class to provide students with summary."""

    template_name = "accounts/summary.html"

    def get_context_data(self, **kwargs):
        """Get data for the student view."""
        if "username" in self.kwargs:
            user = Account.objects.get(username=self.kwargs["username"])
        else:
            user = Account.objects.get(number=self.kwargs["number"])
        modules = user.modules.all()
        VITALS = user.VITALS.model.objects.filter(module__in=modules).order_by("module", "start_date")
        Tests = user.tests.model.homework.filter(module__in=modules).order_by("release_date")
        Labs = user.tests.model.labs.filter(module__in=modules).order_by("release_date")

        test_scores = {}
        for test in Tests:
            try:
                test_scores[test] = user.test_results.get(test=test)
            except ObjectDoesNotExist:
                new_tr = user.test_results.model(user=user, test=test, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                test_scores[test] = new_tr
        lab_scores = {}
        for lab in Labs:
            try:
                lab_scores[lab] = user.test_results.get(test=lab)
            except ObjectDoesNotExist:
                new_tr = user.test_results.model(user=user, test=lab, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                lab_scores[lab] = new_tr
        vitals_results = {}
        for vital in VITALS:
            try:
                vitals_results[vital.module] = vitals_results.get(vital.module, []) + [
                    user.vital_results.get(vital=vital)
                ]
            except ObjectDoesNotExist:
                new_vr = user.vital_results.model(user=user, vital=vital, passed=False)
                vitals_results[vital.module] = vitals_results.get(vital.module, []) + [new_vr]
        context = super().get_context_data(**kwargs)
        context |= {
            "user": user,
            "modules": modules,
            "VITALS": VITALS,
            "Tests": Tests,
            "Labs": Labs,
            "scores": test_scores,
            "lab_scores": lab_scores,
            "vitals_results": vitals_results,
            "tab": self.kwargs.get("selected_tab", "#tests"),
            "tutorial_plot": self.tutorial_plot(user),
            "homework_plot": self.homework_plot(test_scores),
            "lab_plot": self.homework_plot(lab_scores),
            "vitals_plot": self.vitals_plot(vitals_results),
        }
        return context

    def tutorial_plot(self, student):
        """Make piechart for a student's engagement scores."""
        data = {}
        colours = []
        scores = student.engagement_scores()
        for (score, label), col in zip(
            settings.TUTORIAL_MARKS, ["silver", "tomato", "springgreen", "mediumseagreen", "forestgreen"]
        ):
            if count := scores[np.isclose(scores, score)].size:
                data[label] = count
                colours.append(col)
        alt = "Tutproal attendance" + " ".join([f"{label}:{count}" for label, count in data.items()])
        return ImageData(pie_chart(data, colours), alt)

    def homework_plot(self, test_scores):
        """Make a pie chart of test statuses."""
        data = {}
        colours = []
        for test, test_score in test_scores.items():
            if test.status == "Not Started":
                continue
            try:
                attempted = test_score.attempts.count()
            except ValueError:  # New test_score
                attempted = 0
            for label, (attempts, colour) in settings.TESTS_ATTEMPTS_PROFILE[test_score.standing].items():
                if attempts <= attempted:
                    if label not in data:
                        colours.append(colour)
                    data[label] = data.get(label, 0) + 1
                    break
        alt = "Homework results" + " ".join([f"{label}:{count}" for label, count in data.items()])
        return ImageData(pie_chart(data, colours), alt)

    def vitals_plot(self, vitals_results):
        """Make a pier chart for passing vitals."""
        data = {}
        colours = []
        status = []
        for results in vitals_results.values():
            for result in results:
                status.append(result.status)
        status = np.array(status)
        for stat, (label, colour) in settings.VITALS_RESULTS_MAPPING.items():
            if count := status[status == stat].size:
                data[label] = count
                colours.append(colour)
        alt = "VITALs results" + " ".join([f"{label}:{count}" for label, count in data.items()])
        return ImageData(pie_chart(data, colours), alt)
