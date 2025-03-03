"""View classes for the accounts app."""

# Python imports
from collections import namedtuple
from pathlib import Path

# Django imports
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import HttpResponse
from django.template import loader
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from django.views.generic.base import TemplateResponseMixin

# external imports
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dal import autocomplete
from util.http import buffer_to_base64, svg_data
from util.spreadsheet import TutorReportSheet, save_virtual_workbook
from util.views import (
    FormListView,
    IsStaffViewMixin,
    IsStudentViewixin,
    IsSuperuserViewMixin,
    MultiFormMixin,
    ProcessMultipleFormsView,
)

# app imports
from .forms import (
    AllStudentSelectForm,
    CohortFilterActivityScoresForm,
    ToggleActiveForm,
    TutorSelectForm,
)
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
    plt.tight_layout()
    data = svg_data(fig, base64=True)
    plt.close()
    return data


class ChangePasswordView(PasswordChangeView):
    """Implement a minimal change password for admin user accounts."""

    form_class = PasswordChangeForm
    success_url = reverse_lazy("home")
    template_name = "change_password.html"


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
        VITALS = user.VITALS.model.objects.filter(module__in=modules).order_by("module", "start_date", "VITAL_ID")
        Tests = user.tests.model.homework.filter(module__in=modules).order_by("release_date", "name")
        Labs = user.tests.model.labs.filter(module__in=modules).order_by("release_date", "name")
        Code_tasks = user.tests.model.code_tasks.filter(module__in=modules).order_by("release_date", "name")

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
        required = {}
        for test in user.required_tests.all():
            try:
                required[test] = user.test_results.get(test=test)
            except ObjectDoesNotExist:
                new_tr = user.test_results.model(user=user, test=test, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                required[test] = new_tr
        for lab in Labs:
            try:
                lab_scores[lab] = user.test_results.get(test=lab)
            except ObjectDoesNotExist:
                new_tr = user.test_results.model(user=user, test=lab, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                lab_scores[lab] = new_tr
        code_scores = {}
        for code in Code_tasks:
            try:
                code_scores[code] = user.test_results.get(test=code)
            except ObjectDoesNotExist:
                new_tr = user.test_results.model(user=user, test=code, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                code_scores[code] = new_tr
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
            "Code_tasks": Code_tasks,
            "required": required,
            "scores": test_scores,
            "lab_scores": lab_scores,
            "code_scores": code_scores,
            "vitals_results": vitals_results,
            "tab": self.kwargs.get("selected_tab", "#tests"),
            "tutorial_plot": self.tutorial_plot(user),
            "homework_plot": self.homework_plot(test_scores),
            "lab_plot": self.homework_plot(lab_scores, what="Lab"),
            "code_plot": self.homework_plot(code_scores, what="Code Tasks"),
            "vitals_plot": self.vitals_plot(vitals_results),
        }
        return context

    def tutorial_plot(self, student):
        """Make piechart for a student's engagement scores."""
        data = {}
        colours = []
        scores = student.engagement_scores()
        for (score, label, _), col in zip(
            settings.TUTORIAL_MARKS, ["silver", "tomato", "springgreen", "mediumseagreen", "forestgreen"]
        ):
            if count := scores[np.isclose(scores, score)].size:
                data[label] = count
                colours.append(col)
        alt = "Tutproal attendance" + " ".join([f"{label}:{count}" for label, count in data.items()])
        return ImageData(pie_chart(data, colours), alt)

    def homework_plot(self, test_scores, what="Homework"):
        """Make a pie chart of test statuses."""
        data = {}
        colours = []
        for test, test_score in test_scores.items():
            if test.status == "Not Started" and test_score.standing == "Missing":
                continue
            try:
                attempted = test_score.attempts.count()
            except ValueError:  # New test_score
                attempted = 0
            for label, (attempts, colour) in settings.TESTS_ATTEMPTS_PROFILE[test_score.standing].items():
                if attempts < 0 or attempts >= attempted:
                    if label not in data:
                        colours.append(colour)
                    data[label] = data.get(label, 0) + 1
                    break
        alt = f"{what} results" + " ".join([f"{label}:{count}" for label, count in data.items()])
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


class StudentAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete lookup for VITALs."""

    def get_queryset(self):
        """Filter the returned objects based on the query parameter."""
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Account.objects.none()

        qs = Account.objects.filter(is_staff=False)

        if self.q:
            qs = qs.filter(
                Q(last_name__icontains=self.q) | Q(first_name__icontains=self.q) | Q(username__icontains=self.q)
            ).order_by("last_name")
        return qs


class StaffAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete lookup for VITALs."""

    def get_queryset(self):
        """Filter the returned objects based on the query parameter."""
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Account.objects.none()

        qs = Account.objects.filter(is_staff=True)

        if self.q:
            qs = qs.filter(
                Q(last_name__icontains=self.q) | Q(first_name__icontains=self.q) | Q(username__icontains=self.q)
            ).order_by("last_name")
        return qs


class CohortFilterActivityScoresView(IsSuperuserViewMixin, FormListView):
    """Produce a list of students according to criteria based on their activity etc. scorfe."""

    form_class = CohortFilterActivityScoresForm
    template_name = "accounts/admin/activity_score_list.html"
    model = Account
    context_object_name = "students"

    def get_queryset(self):
        """Return either a filtered queryset, or empty queryset depending on form."""
        if not self.form.is_valid():
            return self.model.objects.none()

        data = self.form.cleaned_data
        query_arg = {f"{data['what']}__{data['how']}": data["value"]}
        return self.model.students.filter(modules=data["module"], **query_arg).distinct().order_by(data["what"])


class CohortFilterActivityScoresExportView(CohortFilterActivityScoresView):
    """Make an excel spreadsheet from the filtered list of students."""

    def render_to_response(self, context, **response_kwargs):
        """Render the object list to a pandas dataframe and then output as Excel."""
        fields = {
            "number": "SID",
            "first_name": "First Name",
            "last_name": "Last Name",
            "email": "Email",
            "programme__name": "Programme",
            "tests_score": "Homework",
            "labs_score": "Labs",
            "coding_score": "Code Taks",
            "vitals_score": "VITALs",
            "engagement": "Tutorial Engagement",
            "activity_score": "Overall Activity",
        }
        form = self.form.cleaned_data
        data = context["students"].values(*list(fields.keys()))
        df = pd.DataFrame(data)
        df.rename(columns=fields, inplace=True)
        df.set_index("SID", inplace=True)
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response[
            "Content-Disposition"
        ] = f"attachment; filename=Output_{form['what']}_{form['how']}_{form['value']:.1f}.xlsx"

        df.to_excel(response)
        return response


class CohortScoresOverview(IsStaffViewMixin, TemplateView):
    """A Template view that makes some plots."""

    template_name = "accounts/admin/summary_plots.html"

    def get_context_data(self, **kwargs):
        """Get data for the student view."""
        return self._load_gif_data(super().get_context_data(**kwargs))

    def _prepare_plot(self):
        """Get aset of axes ready for plotting."""
        fig = plt.figure()
        ax = fig.add_subplot(111)
        return fig, ax

    def _load_gif_data(self, context):
        """Load pre-prepared gif data."""
        attrs = {
            "activity_score": "Overall Activity",
            "tests_score": "Homework Assignments",
            "labs_score": "Lab Activities",
            "coding_score": "Code Tasks",
            "vitals_score": "VITALs Progress",
            "engagement": "Tutorial Enghagement",
        }

        for attr, label in attrs.items():
            if (data := (Path(settings.MEDIA_ROOT) / "data" / f"{attr}.gif")).exists():
                with open(data, "rb") as buffer:
                    context[f"{attr}_plot"] = ImageData(data=buffer_to_base64(buffer, "image/gif"), alt=label)
            else:
                context[f"{attr}_plot"] = data
        context["plot"] = ImageData(data=svg_data(self.mod_cdf(), base64=True), alt="Summary Student Scores")
        return context

    def mod_cdf(self, figure=None, ax=None):
        """Make a cumulative distribution plot."""
        if figure is None:
            figure, ax = self._prepare_plot()
        else:
            plt.sca(ax)

        scorenames = {
            "tests_score": "Tests",
            "labs_score": "Labs",
            "coding_score": "Coding",
            "vitals_score": "VITALs",
            "engagement": "Tutorial",
            "activity_score": "Overall",
        }
        # TODO: Modify to work with different modules.
        data = pd.DataFrame(Account.students.filter(modules__code="PHAS1000").values(*scorenames.keys())).fillna(
            value=np.NaN
        )

        x = np.linspace(0, 101, 102)
        for ix, (k, label) in enumerate(scorenames.items()):
            entries = data[k].loc[~np.isnan(data[k])]  # Remove bad marks
            if len(entries) < 4:  # Insufficient entries to compute a cdf
                continue
            y = np.array([100 * len(entries[entries >= ix]) / len(entries) for ix in x])
            plt.step(x, y, linewidth=2, label=f"{label}")
        ax.legend(fontsize="small", loc="upper right")
        ax.set_xlabel("Student Mark %")
        ax.set_ylabel("% students getting this mark or better")
        ax.set_title("Scores Cumulative Distribution")
        return figure


class CohortProgressionOverview(IsStaffViewMixin, TemplateView):
    """A Template view that makes some plots."""

    template_name = "accounts/admin/summary_progression_plots.html"

    def get_context_data(self, **kwargs):
        """Get data for the student view."""
        sids = [x.number for x in Account.students.filter(tutorial_group__tutor=self.request.user)]
        return self._load_gif_data(super().get_context_data(**kwargs), sids)

    def _load_gif_data(self, context, sids=None):
        """Load pre-prepared gif data."""
        attrs = {
            "activity_score": "Overall Activity",
            "tests_score": "Homework Assignments",
            "labs_score": "Lab Activities",
            "coding_score": "Code Tasks",
            "vitals_score": "VITALs Progress",
            "engagement": "Tutorial Enghagement",
        }

        for attr, label in attrs.items():
            if (data := (Path(settings.MEDIA_ROOT) / "data" / f"time_series_{attr}.xlsx")).exists():
                df = pd.read_excel(data).set_index("Date")
                inactive = set([x[0] for x in Account.objects.filter(is_active=False).values_list("number")])
                ignore = list(set(df.columns) & inactive)
                df = df.drop(labels=ignore, axis="columns")
                ax = df.plot(kind="line", c=(0, 0, 0, 0.05), linewidth=10)
                ax.set_title(f"{label} Progression")
                ax.set_ylabel("% score")
                ax.set_xlabel("Date")
                ax.get_legend().remove()
                ax.set_ylim(-5, 105)
                if sids:  # Highlight my students
                    for line in ax.lines:
                        if int(line.get_label()) in sids:
                            line.set_color((1.0, 0, 0, 0.25))
                            line.set_zorder(len(ax.lines) + 1)
                context[f"{attr}_plot"] = ImageData(data=svg_data(None, base64=True), alt=f"{label} Scores")
                plt.close()
            else:
                context[f"{attr}_plot"] = data
        return context


class DeactivateStudentView(IsSuperuserViewMixin, MultiFormMixin, TemplateResponseMixin, ProcessMultipleFormsView):
    """View to locate a student recortd and then edit to set account activity flag."""

    form_classes = {"search": AllStudentSelectForm, "update": ToggleActiveForm}
    success_urls = {"search": "", "update": ""}
    template_name = "accounts/admin/toggle_ative.html"
    user = None

    def search_form_valid(self, form):
        """Process the user search form being valid."""
        self.user = form.cleaned_data["user"]
        return self.render_to_response(self.get_context_data(forms=self._forms))

    def update_form_valid(self, form):
        """Save the updated user instance."""
        try:
            self.user = Account.objects.get(username=form.cleaned_data["username"])
        except ObjectDoesNotExist:
            form.errors.add(f"{form.cleaned_data['username']} not a valid username.")
            return self.form_invalid(form)
        self.user.is_active = form.cleaned_data["is_active"]
        self.user.save()
        return self.render_to_response(self.get_context_data(forms=self._forms))

    def create_update_form(self, **kwargs):
        """Force use of the existing user account to load fields."""
        if self.user:
            kwargs["data"] = {
                "username": self.user.username,
                "number": self.user.number,
                "display_name": self.user.display_name,
                "is_active": self.user.is_active,
            }
            kwargs["initial"] = kwargs["data"]
        return ToggleActiveForm(**kwargs)

    def create_search_form(self, **kwargs):
        """Force use of existing user object to populate."""
        if self.user:
            kwargs["data"] = {"user": self.user}
            kwargs["initial"] = kwargs["data"]
        return AllStudentSelectForm(**kwargs)
