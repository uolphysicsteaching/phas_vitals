"""View classes for the accounts app."""

# Python imports
from collections import namedtuple
from functools import partial
from pathlib import Path

# Django imports
from django.apps import apps
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
from htmx_views.views import HTMXProcessMixin
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
    StudentSelectForm,
    ToggleActiveForm,
    ToggleVITALForm,
    TutorSelectForm,
)
from .models import Account

TEMPLATE_PATH = settings.PROJECT_ROOT_PATH / "run" / "templates" / "Tutor_Report.xlsx"

ImageData = namedtuple("ImageData", ["data", "alt"], defaults=["", ""])


def pie_chart(data, colours):
    """Make a Pie chart for the student dashboard."""
    if any([x > 0 for x in data.values()]):
        fig, ax = plt.subplots()
        fig.set_figwidth(4.5)
        _, texts = ax.pie(list(data.values()), labels=list(data.keys()), colors=colours, labeldistance=0.3)
        for text in texts:
            text.set_bbox({"facecolor": (1, 1, 1, 0.75), "edgecolor": (1, 1, 1, 0.25)})
        plt.tight_layout()
    else:
        fig = plt.figure()
        fig.set_figwidth(4.5)
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


class StudentSummaryPageView(IsStudentViewixin, HTMXProcessMixin, TemplateView):
    """View class to provide one page of the student summary."""

    def get_template_names(self):
        """Swich templates based on the page we're looking at."""
        match self.kwargs.get("category", "dashboard"):
            case "dashboard":
                return "accounts/parts/summary_plots.html"
            case "vitals":
                return "accounts/parts/summary_vitals.html"
            case "required_work":
                return "accounts/parts/summary_required.html"
            case _:
                return "accounts/parts/summary_category.html"

    def get_context_data_function(self, **kwargs):
        """Return a handler for get_context_data.

        If the parent method doesn't work, then divert to our general category handler.
        """
        handler = super().get_context_data_function(**kwargs)
        if not handler:
            handler = getattr(self, "get_context_data_category")
        return handler

    def get_context_data(self, **kwargs):
        """Get data for the student view."""
        if "username" in self.kwargs:
            self.user = (
                Account.objects.filter(username=self.kwargs["username"])
                .prefetch_related("test_results", "vital_results")
                .first()
            )
        else:
            self.user = (
                Account.objects.filter(number=self.kwargs["number"])
                .prefetch_related("test_results", "vital_results")
                .first()
            )
        self.modules = self.user.modules.all()
        # TODO - make this work for multiple modules and update template
        categories = []

        TestCategory = apps.get_model("minerva", "TestCategory")
        categories = {x.tag: x for x in TestCategory.objects.filter(module__in=self.modules, in_dashboard=True)}
        category = self.kwargs.get("category", "dashboard")
        self.category = categories.get(category)

        context = super().get_context_data(**kwargs)
        context |= {
            "user": self.user,
            "modules": self.modules,
            "categories": categories.values(),
            "category": self.category,
        }
        return context

    def get_context_data_vitals(self, **kwargs):
        """Get the context data for the tests page only."""
        context = super().get_context_data(**kwargs)
        VITALS = self.user.VITALS.model.objects.filter(module__in=self.modules).order_by(
            "module", "start_date", "VITAL_ID"
        )
        vitals_results = {}
        for vital in VITALS:
            try:
                vitals_results[vital.module] = vitals_results.get(vital.module, []) + [
                    self.user.vital_results.get(vital=vital)
                ]
            except ObjectDoesNotExist:
                new_vr = self.user.vital_results.model(user=self.user, vital=vital, passed=False)
                vitals_results[vital.module] = vitals_results.get(vital.module, []) + [new_vr]
        context |= {
            "VITALS": VITALS,
            "vitals_results": vitals_results,
            "tab": self.kwargs.get("selected_tab", "#vitals"),
        }
        return context

    def get_context_data_required_work(self, **kwargs):
        """Get the context data for the tests page only."""
        context = super().get_context_data(**kwargs)
        required = {}
        for test in self.user.required_tests.all():
            try:
                required[test] = self.user.test_results.get(test=test)
            except ObjectDoesNotExist:
                new_tr = self.user.test_results.model(user=self.user, test=test, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                required[test] = new_tr
        context |= {
            "required": required,
            "tab": self.kwargs.get("selected_tab", "#required"),
        }
        return context

    def get_context_data_dashboard(self, **kwargs):
        """Get data for the student view."""
        context = super().get_context_data(**kwargs)
        # get my categories for pie charts.
        TestCategory = apps.get_model("minerva", "testcategory")
        cat_ids = set(
            [x[0] for x in self.user.summary_scores.filter(category__dashboard_plot=True).values_list("category")]
        )
        categories = {
            x.text: x for x in TestCategory.objects.filter(pk__in=cat_ids, dashboard_plot=True).order_by("order")
        }
        context["plot_categories"] = list(categories.values())
        context["plots"] = {}
        context["scores"] = {}
        for category in categories.values():
            plotter = getattr(self, f"{category.tag}_plot", partial(self.test_plot, category.text))
            context["plots"][category.tag] = plotter()
            context["scores"][category.tag] = self.user.category_score(category.text)

        context |= {
            "user": self.user,
            "tab": self.kwargs.get("selected_tab", "#tests"),
        }
        return context

    def get_context_data_category(self, **kwargs):
        """Get the context data for the tests page only."""
        context = super().get_context_data(**kwargs)
        Tests = self.user.tests.model.objects.filter(
            module__in=self.modules, category__text=self.category.text
        ).order_by("release_date", "name")
        test_scores = {}
        for test in Tests:
            try:
                test_scores[test] = self.user.test_results.get(test=test)
            except ObjectDoesNotExist:
                new_tr = self.user.test_results.model(user=self.user, test=test, passed=False, score=None)
                new_tr.test_status = new_tr.manual_test_satus
                new_tr.standing = "Missing"
                test_scores[test] = new_tr
        context |= {
            "tests": Tests,
            "scores": test_scores,
            "tab": self.kwargs.get("selected_tab", f"{self.category.hashtag}"),
        }
        return context

    def tutorial_plot(self):
        """Make piechart for a student's engagement scores."""
        data = {}
        colours = []
        scores = self.user.engagement_scores()
        for (score, label, _), col in zip(
            settings.TUTORIAL_MARKS, ["silver", "tomato", "springgreen", "mediumseagreen", "forestgreen"]
        ):
            if count := scores[np.isclose(scores, score)].size:
                data[label] = count
                colours.append(col)
        alt = "Tutproal attendance" + " ".join([f"{label}:{count}" for label, count in data.items()])
        return ImageData(pie_chart(data, colours), alt)

    def test_plot(self, category_name):
        """Make a pie chart plot from the summary_scores."""
        data = {}
        colours = {}
        # Get all summary scores with the same category label and merge them 0 allows for multiple modules
        # with the same category labels.
        for ss in self.user.summary_scores.filter(category__text=category_name):
            for k, value in ss.data.get("data", {}).items():
                data[k] = data.get(k, 0) + value
                colours[k] = ss.data.get("colours", {}).get(k, "white")
        colours = [colours.get(x, "white") for x in data]
        alt = f"{category_name.title()} results" + " ".join([f"{label}:{count}" for label, count in data.items()])
        try:
            image = pie_chart(data, colours)
        except ValueError:
            image = bytes([])
        return ImageData(image, alt)


class StudentSummaryView(IsStudentViewixin, TemplateView):
    """View class to provide students with summary."""

    template_name = "accounts/summary.html"

    def get_context_data(self, **kwargs):
        """Get data for the student view."""
        if "username" in self.kwargs:
            self.user = (
                Account.objects.filter(username=self.kwargs["username"])
                .prefetch_related("test_results", "vital_results")
                .first()
            )
        else:
            self.user = (
                Account.objects.filter(number=self.kwargs["number"])
                .prefetch_related("test_results", "vital_results")
                .first()
            )
        modules = self.user.modules.all()
        # TODO - make this work for multiple modules and update template
        TestCategory = apps.get_model("minerva", "testcategory")
        categories = {}
        for category in TestCategory.objects.filter(module__in=modules, in_dashboard=True).order_by("order"):
            category.path = f"/accounts/detail/{self.user.number}/{category.tag}/"
            categories[category.text] = (
                category  # NB template needs to only use category attributes that are not module dependent.
            )

        context = super().get_context_data(**kwargs)
        context |= {
            "user": self.user,
            "modules": modules,
            "categories": categories,
            "dashboard_path": f"/accounts/detail/{self.user.number}/dashboard/",
            "tab": "dashboard",
        }
        return context


class StudentAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete lookup for VITALs."""

    def get_queryset(self):
        """Filter the returned objects based on the query parameter."""
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Account.objects.none()

        qs = Account.objects.filter(is_staff=False)

        if self.q:
            try:
                qq = int(self.q)
                qs = qs.filter(Q(number=qq))
            except (ValueError, TypeError):
                qs = qs.filter(
                    Q(last_name__icontains=self.q) | Q(first_name__icontains=self.q) | Q(username__icontains=self.q)
                )
        return qs.order_by("last_name")


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
        if data["what"] == "activity_score":
            query_arg = {f"activity_score__{data['how']}": data["value"]}
            return self.model.students.filter(modules=data["module"], **query_arg).distinct().order_by(data["what"])
        TestCategory = apps.get_model("minerva", "testcategory")
        SummaryScore = apps.get_model("minerva", "summaryscore")
        if cat := TestCategory.objects.filter(module=data["module"], text=data["what"]).first():
            query_args = {"category": cat, f"score__{data['how']}": data["value"]}
            student_ids = set([x[0] for x in SummaryScore.objects.filter(**query_args).values_list("student")])
            return self.model.objects.filter(pk__in=student_ids)
        return self.model.objects.none()


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
        response["Content-Disposition"] = (
            f"attachment; filename=Output_{form['what']}_{form['how']}_{form['value']:.1f}.xlsx"
        )

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


class StudentRecordView(IsSuperuserViewMixin, FormView):
    """Lookup an individual student and redirect to their dashboard."""

    form_class = AllStudentSelectForm
    template_name = "accounts/admin/search_student_dashboard.html"

    def form_valid(self, form):
        """Record the user from the form."""
        self.user = form.cleaned_data["user"]
        return super().form_valid(self)

    def get_success_url(self):
        """Return the dasjboard view for the student."""
        return f"/accounts/detail/{self.user.number}/#dashboard"


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


class AwardVITALView(IsSuperuserViewMixin, MultiFormMixin, TemplateResponseMixin, ProcessMultipleFormsView):
    """View to locate a student recortd and then edit to set account activity flag."""

    form_classes = {"search": StudentSelectForm, "update": ToggleVITALForm}
    success_urls = {"search": "", "update": ""}
    template_name = "accounts/admin/toggle_vital.html"
    user = None
    vital = None

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

        self.vital = form.cleaned_data["VITAL"]
        vr, _ = Account.vital_results.field.model.objects.get_or_create(user=self.user, vital=self.vital)
        if not vr.passed and form.cleaned_data["passed"]:
            self.user.override_vitals = True
            self.user.save()
        vr.passed = form.cleaned_data["passed"]
        vr.save()

        return self.render_to_response(self.get_context_data(forms=self._forms))

    def create_update_form(self, **kwargs):
        """Force use of the existing user account to load fields."""
        if self.user:
            kwargs["data"] = {
                "username": self.user.username,
                "number": self.user.number,
                "display_name": self.user.display_name,
            }
        if self.vital:
            vr, _ = Account.vital_results.field.model.objects.get_or_create(user=self.user, vital=self.vital)
            kwargs.update({"vital": self.vital, "passed": vr.passed})
        kwargs["initial"] = kwargs.get("data", {})
        return ToggleVITALForm(**kwargs)

    def create_search_form(self, **kwargs):
        """Force use of existing user object to populate."""
        if self.user:
            kwargs["data"] = {"user": self.user}
            kwargs["initial"] = kwargs["data"]
        return StudentSelectForm(**kwargs)
