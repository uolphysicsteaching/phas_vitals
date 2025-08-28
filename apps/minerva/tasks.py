# -*- coding: utf-8 -*-
"""Celery taks for the minerva app."""
# Python imports
import logging
from datetime import datetime, time
from functools import partial
from pathlib import Path

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone as tz

# external imports
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from accounts.models import Account
from celery import shared_task
from constance import config
from minerva.models import Module, Test_Score

# app imports
from phas_vitals import celery_app
from phas_vitals.tasks import PHASTask

# app imports
from .models import GradebookColumn

logger = logging.getLogger("celery_tasks")

update_all_users = celery_app.signature("accounts.tasks.update_all_users")


@shared_task
def import_gradebook():
    """Import a spreadsheet of the full Minerva gradebook download."""
    logger.debug("Running gradebook import")
    # Really do stuff
    imported_modules = []
    for module in Module.objects.all():
        logger.debug(f"Attempting to import {module.key}")
        if not module.data_ready:
            logger.debug(f"Module {module.key} data not ready.")
        logger.debug(f"Cleaning up dead columns and creating new ones.")
        module.remove_columns_not_in_json()
        try:
            GradebookColumn.create_or_update_from_json(module)
        except OSError:  # Probably no JSON File
            continue
        if module.update_from_json() is None:
            logger.info(f"Failed import for {module.name}")
        else:
            imported_modules.append(module.key)
            config.LAST_MINERVA_UPDATE = module.json_updated
            logger.debug(f"Imported {module.key} {module.json_updated}")

    logger.debug("Updated constance.config")
    update_all_users.delay()
    return imported_modules


@shared_task()
def take_time_series(module_code="PHAS1000"):
    """Load DataFrames and add new row for the current date."""
    datapath = Path(settings.MEDIA_ROOT) / "data"
    attrs = ["activity_score", "tests_score", "labs_score", "coding_score", "vitals_score", "engagement"]
    try:
        module = Module.objects.get(code=module_code)
    except ObjectDoesNotExist:
        logger.debug("Failed to run time series collection for module {module_code}")
    data = module.students.all()
    date = datetime.combine(tz.now().date(), time(0, 0, 0))
    for attr in attrs:
        if (filepath := (datapath / f"time_series_{attr}.xlsx")).exists():
            df = pd.read_excel(filepath).set_index("Date")
        else:
            df = pd.DataFrame(columns=["Date"]).set_index("Date")
        row = {entry.number: getattr(entry, attr, np.nan) for entry in data}
        if date in df.index:  # Check for double running on the same day!
            for k, v in row.items():
                df.loc[date, k] = v
        else:
            row["Date"] = date
            row_df = pd.DataFrame([row]).set_index("Date")
            df = pd.concat((df, row_df))
        df.to_excel(filepath)
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
    pth = Path(settings.MEDIA_ROOT) / "data"
    attrs = {
        "activity_score": "Overall Activity",
        "tests_score": "Homework Assignments",
        "labs_score": "Lab Activities",
        "coding_score": "Code Tasks",
        "vitals_score": "VITALs Progress",
        "engagement": "Tutorial Enghagement",
    }
    for key, label in attrs.items():
        datafile = pth / f"time_series_{key}.xlsx"
        data = pd.read_excel(datafile).set_index("Date")
        inactive = set([x[0] for x in Account.objects.filter(is_active=False).values_list("number")])
        ignore = list(set(data.columns) & inactive)
        data = data.drop(labels=ignore, axis="columns")

        plt.close("all")
        anim, fig = _prepare(data, label)

        ani = animation.FuncAnimation(fig, anim, len(data.index), interval=500, repeat_delay=1500)

        ani.save(pth / f"{key}.gif")
