.. _label-vital-pass-logic:

VITAL Pass/Fail Logic
=====================

This page describes the data model used to define pass conditions for a VITAL, and the step-by-step
logic executed by :meth:`~vitals.models.VITAL.check_vital` to determine whether a student has passed
a given VITAL.

Data Model Overview
-------------------

A **VITAL** (*Verifiable Indicator of Threshold Ability and Learning*) is a learning outcome
associated with a module. The relationship between a VITAL and the tests used to assess it is
encoded in the :class:`~vitals.models.VITAL_Test_Map` model. Each mapping record carries four
fields that control how a test contributes to a VITAL pass decision:

``necessary`` *(BooleanField, default* ``False`` *)*
    When ``True``, this test is a *necessary* condition for the VITAL. All necessary tests of a
    given condition type must be satisfied before the VITAL can be awarded on that condition alone.

``sufficient`` *(BooleanField, default* ``True`` *)*
    When ``True``, satisfying this test alone is *sufficient* to award the VITAL, regardless of
    any other mappings.

``condition`` *(CharField, choices* ``"pass"`` *or* ``"attempt"`` *)*
    Defines what action by the student satisfies the mapping:

    * ``"pass"`` – the student must achieve a passing score on the test.
    * ``"attempt"`` – the student need only make an attempt at the test (any recorded result
      counts), without needing to pass.

``required_fractrion`` *(FloatField, default* ``1.0`` *)*
    Only meaningful when ``condition="attempt"`` and ``necessary=True``. The sum of
    ``required_fractrion`` (note: the field name contains a typo in the codebase) across all
    *necessary/attempt* mappings gives the minimum number (or fraction) of those tests that
    must be attempted for the VITAL to be awarded on that condition.

The pass/fail outcome for a specific student is stored in a :class:`~vitals.models.VITAL_Result`
record, with a ``passed`` boolean field and an optional ``date_passed`` timestamp.

check_vital Logic
-----------------

The :meth:`~vitals.models.VITAL.check_vital` method evaluates whether a student (``user``) has
satisfied the conditions for a VITAL, then calls :meth:`~vitals.models.VITAL.passed` to record the
result. The method works through the following steps in order; the first condition that is satisfied
terminates the check.

Step 1 – Sufficient Test Passed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    sufficient = self.tests_mappings.filter(sufficient=True)
    if user.test_results.filter(
            test__vitals_mappings__in=sufficient.all(), passed=True
    ).count() > 0:
        return self.passed(user)

All ``VITAL_Test_Map`` records for this VITAL where ``sufficient=True`` are retrieved (this
includes both ``condition="pass"`` and ``condition="attempt"`` mappings). If the student has **at
least one** ``Test_Score`` record for any of these tests where ``passed=True``, the VITAL is
awarded.

.. note::

   The ``condition`` field is not used in this check. A mapping with ``sufficient=True`` and
   ``condition="attempt"`` is treated in the same way as one with ``condition="pass"``: the
   student must have a *passing* result rather than merely an *attempted* result.

Step 2 – All Necessary/Pass Tests Passed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    necessary = self.tests_mappings.filter(necessary=True, condition="pass").distinct()
    if (
        necessary.count() > 0
        and user.test_results.filter(
                test__vitals_mappings__in=necessary.all(), passed=True
        ).distinct().count() == necessary.count()
    ):
        return self.passed(user)

The mappings where ``necessary=True`` and ``condition="pass"`` are retrieved. If there is at least
one such mapping, and the number of distinct passing ``Test_Score`` records the student has for
those tests equals the total number of necessary/pass mappings, the VITAL is awarded.

In plain terms: **every** test that is marked as both *necessary* and requiring a *pass* must
have been passed.

Step 3 – Sufficient Necessary/Attempt Tests Attempted
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    necessary = self.tests_mappings.filter(necessary=True, condition="attempt").distinct()
    needed = necessary.aggregate(needed=models.Sum("required_fractrion"))["needed"]
    if (
        necessary.count() > 0
        and user.test_results.filter(
                test__vitals_mappings__in=necessary.all()
        ).distinct().count() >= needed
    ):
        return self.passed(user)

The mappings where ``necessary=True`` and ``condition="attempt"`` are retrieved. The minimum
required number of tests is calculated by summing the ``required_fractrion`` field
(note: typo in field name) across all those mappings. If there is at least one such mapping, and
the number of distinct ``Test_Score`` records the student has for those tests (regardless of pass
or fail) is greater than or equal to that sum, the VITAL is awarded.

In plain terms: the student must have **attempted** at least the required number of tests that
are marked as *necessary* with an *attempt* condition.

Step 4 – No Test Results at All
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    if user.test_results.filter(
            test__vitals_mappings__in=self.tests_mappings.all()
    ).count() == 0:
        return False

If the student has no ``Test_Score`` records for *any* test linked to this VITAL, the method
returns ``False`` immediately **without** updating the student's ``VITAL_Result`` record. No fail
is recorded; the student is simply treated as not yet having engaged with the VITAL.

Step 5 – Default: Record as Not Passed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    return self.passed(user, False)

If none of the pass conditions above were met, and the student does have at least one test result
for this VITAL, the :meth:`~vitals.models.VITAL.passed` method is called with ``passed=False``.
This creates or updates the student's ``VITAL_Result`` to record a failure.

Summary Table
-------------

The following table summarises every combination of ``necessary``, ``sufficient``, and
``condition`` that appears in :meth:`~vitals.models.VITAL.check_vital`, and what must be true for
that mapping type to contribute to a VITAL pass:

.. list-table::
   :header-rows: 1
   :widths: 12 12 12 64

   * - ``necessary``
     - ``sufficient``
     - ``condition``
     - Behaviour in ``check_vital``
   * - –
     - ``True``
     - ``"pass"``
     - Passing this test alone is sufficient to award the VITAL (Step 1).
   * - –
     - ``True``
     - ``"attempt"``
     - **Also** requires ``passed=True`` due to Step 1 treating all sufficient mappings
       identically, regardless of ``condition``.
   * - ``True``
     - –
     - ``"pass"``
     - All mappings of this type must be passed; checked collectively in Step 2.
   * - ``True``
     - –
     - ``"attempt"``
     - A minimum number of these tests (determined by the sum of ``required_fractrion``,
       the fraction field — note the typo in the field name) must be attempted; checked
       collectively in Step 3.

Flow Diagram
------------

::

    check_vital(user)
         │
         ▼
    Any sufficient test passed? ──► YES ──► VITAL awarded (passed)
         │
         NO
         │
         ▼
    All necessary/pass tests passed? ──► YES ──► VITAL awarded (passed)
         │
         NO
         │
         ▼
    Enough necessary/attempt tests attempted? ──► YES ──► VITAL awarded (passed)
         │
         NO
         │
         ▼
    Any test results at all? ──► NO ──► return False (no result recorded)
         │
         YES
         │
         ▼
    VITAL recorded as not passed (failed)
