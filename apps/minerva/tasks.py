# -*- coding: utf-8 -*-
"""Celery taks for the minerva app."""
# Python imports
import logging
from datetime import datetime, time
from functools import partial
from traceback import format_exc

# Django imports
from django.utils import timezone as tz

# external imports
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from accounts.models import Account, Cohort, School
from celery import shared_task
from constance import config
from minerva.models import Module

# app imports
from phas_vitals import celery_app

# app imports
from . import json
from .models import GradebookColumn, SummaryScore, TestCategory

logger = logging.getLogger("celery_tasks")

update_all_users = celery_app.signature("accounts.tasks.update_all_users")


@shared_task
def import_module_list():
    """Periodic task to update the list of modules we're reading."""
    mod_list = [x for x in json.get_blob_list() if x.endswith("Course.json")]
    for mod_json in mod_list:
        data = json.get_blob_by_name(mod_json)[0]
        year, crn, code = data["courseId"].split("_")
        year = Cohort.objects.get(name=year)
        school = School.from_code(code[:4])
        crn = data["courseId"].split("_")[1]
        name = " ".join(data["name"].split(" ")[1:-1])
        mod, _ = Module.objects.get_or_create(uuid=data["uuid"], courseId=crn, year=year, code=code)
        mod.name = name
        mod.school = school
        mod.level = int(mod.code[4])
        mod.semester = int(data["name"].split(" ")[0][-2])
        mod.save()
        mod.update_from_json(categories=True, tests=True, enrollments=True, columns=True, grades=True)


@shared_task
def import_gradebook():
    """Import a spreadsheet of the full Minerva gradebook download."""
    logger.debug("Running gradebook import")
    # Really do stuff
    imported_modules = []
    bad_modules = []
    for module in Module.objects.select_related("year", "school").all():
        logger.debug(f"Attempting to import {module.key}")
        if not module.data_ready:
            logger.debug(f"Module {module.key} data not ready or not being recorded.")
            continue
        try:
            if (
                module.update_from_json(categories=True, tests=True, enrollments=True, columns=True, grades=True)
                is None
            ):
                logger.info(f"Failed import for {module.name}")
            else:
                imported_modules.append(module.key)
                logger.debug(f"Imported {module.key} {module.json_updated}")
        except Exception as error:
            bad_modules.append(f"Issues processing json for {module=} - {format_exc()}")
            logger.debug(bad_modules[-1])

    logger.debug("Updated constance.config")
    update_all_users.delay()
    if bad_modules:
        return bad_modules
    logger.debug("Updated constance.config")
    config.LAST_MINERVA_UPDATE = module.json_updated

    return imported_modules


@shared_task()
def take_time_series():
    """Load DataFrames and add new row for the current date."""
    date = datetime.combine(tz.now().date(), time(0, 0, 0))
    for category in TestCategory.objects.filter(dashboard_plot=True):
        data = SummaryScore.objects.filter(category=category)
        if category.xlsx.exists():
            df = pd.read_excel(category.xlsx).set_index("Date")
        else:
            category.datadir.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(columns=["Date"]).set_index("Date")
        row = {entry.student.number: entry.score for entry in data}
        if date in df.index:  # Check for double running on the same day!
            for k, v in row.items():
                df.loc[date, k] = v
        else:
            row["Date"] = date
            row_df = pd.DataFrame([row]).set_index("Date")
            df = pd.concat((df, row_df))
        df.to_excel(category.xlsx)
    make_gifs.delay()


def _prepare(data, label):
    """Prepare the plot for animation."""
    row = data.iloc[0]
    axes = row.hist(bins=np.linspace(0, 100, 21), label=row.name.strftime("%Y/%m/%d"))
    fig = plt.gcf()
    axes.set_title(label)
    axes.set_ylim(0, len(row))
    axes.set_ylabel("Number of students")
    axes.set_xlabel("Overall % score")
    legend = axes.legend(loc=1)
    anim = partial(_animate, axes=axes, data=data, legend=legend)
    return anim, fig


def _animate(frame, axes, data, legend):
    """Update the patches height for the next frame."""
    n, _ = np.histogram(data.iloc[frame], bins=np.linspace(0, 100, 21))
    for newh, rect in zip(n, axes.patches):
        rect.set_height(newh)
    legend.get_texts()[0].set_text(data.iloc[frame].name.strftime("%Y/%m/%d"))
    return axes


@shared_task()
def make_gifs():
    """Create an animated gif from the activity data."""
    for category in TestCategory.objects.filter(dashboard_plot=True):
        if not (category.xlsx).exists():
            continue
        data = pd.read_excel(category.xlsx).set_index("Date")
        inactive = set([x[0] for x in Account.objects.filter(is_active=False).values_list("number")])
        ignore = list(set(data.columns) & inactive)
        data = data.drop(labels=ignore, axis="columns")

        plt.close("all")
        anim, fig = _prepare(data, f"{category.module.code}:{category.label}")

        ani = animation.FuncAnimation(fig, anim, len(data.index), interval=500, repeat_delay=1500)

        ani.save(category.gif)
