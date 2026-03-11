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

``condition`` *(CharField, choices* ``"pass"`` *or* ``"attempt"`` *)*
    Defines what action by the student satisfies the mapping:

    * ``"pass"`` – the student must achieve a passing score on the test.
    * ``"attempt"`` – the student need only make an attempt at the test (any recorded result
      counts), without needing to pass.

``sufficient`` *(BooleanField, default* ``True`` *)*
    When ``True``, satisfying this test alone is *sufficient* to award the VITAL, regardless of
    any other mappings.

``necessary`` *(BooleanField, default* ``False`` *)*
    When ``True``, this test is a *necessary* condition for the VITAL. Unless a *sufficient* condition is
    met, all *necessary* conditions must be met for the VITAL to be awarded.

``required_fractrion`` *(FloatField, default* ``1.0`` *)*
    Unless a *sufficient* requirement is met, then the sum of all *required_fraction* fields of all conditions that
    are met must be equal or greater than 1.0 for the VITAL to be awarded.

Thus, a *sufficient* condition being met definitely awards the VITAL. A *necessary* condition not being met definitely
results in the VITAL not being awarded. A sum of *required_fraction* of met conditions must be greater or equal to 1.0 for
the VITAL to be awarded. *NB* Floating point conditions should be evaluated with a tolerance of 0.001 to allow for rounding
errors.

The pass/fail outcome for a specific student is stored in a :class:`~vitals.models.VITAL_Result`
record, with a ``passed`` boolean field and an optional ``date_passed`` timestamp.

check_vital Logic
-----------------

The :meth:`~vitals.models.VITAL.check_vital` method evaluates whether a student (``user``) has
satisfied the conditions for a VITAL, then calls :meth:`~vitals.models.VITAL.passed` to record the
result. The method works through the following steps in order; the first condition that is satisfied
terminates the check.

The method begins by fetching two sets of test IDs for the student from the database:

* **passed tests** – tests in this VITAL's mappings where the student has ``Test_Score.passed = True``
* **attempted tests** – tests in this VITAL's mappings where the student has any ``Test_Score`` record

A helper then determines whether a single mapping is *met* based on those sets:

::

    def is_met(mapping):
        if mapping.condition == "pass":
            return mapping.test_id in user_passed_test_ids
        return mapping.test_id in user_attempted_test_ids

Step 1 – Sufficient Condition Met
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    if any(m.sufficient and is_met(m) for m in all_mappings):
        return self.passed(user)

If **any** mapping with ``sufficient=True`` is met (according to its own ``condition`` field), the
VITAL is awarded immediately.

.. note::

   Unlike the previous implementation, ``condition`` is now respected for sufficient mappings.
   A mapping with ``sufficient=True`` and ``condition="attempt"`` is satisfied by any attempt,
   not just a passing result.

Step 2 – No Test Results
^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    if not user_attempted_test_ids:
        return False

If the student has no ``Test_Score`` records for *any* test linked to this VITAL, the method
returns ``False`` immediately **without** updating the student's ``VITAL_Result`` record. No fail
is recorded; the student is simply treated as not yet having engaged with the VITAL.

Step 3 – Necessary Condition Not Met
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    necessary_mappings = [m for m in all_mappings if m.necessary]
    if (
        len(necessary_mappings) > 0
        and sum(1 for m in necessary_mappings if is_met(m)) != len(necessary_mappings)
    ):
        return self.passed(user, False)

The number of necessary mappings that are *positively met* (i.e. the student actively satisfied the
mapping's ``condition``) is compared against the total number of necessary mappings. The VITAL is
blocked and the student recorded as not having passed unless that count equals the total.

.. note::

   A necessary test for which the student has **no result at all** is explicitly *not* positively
   met and therefore reduces the met count, causing the block to fire exactly as it would for a
   test that was attempted but not passed.

Step 4 – Required-Fraction Sum
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    met_sum = sum(m.required_fractrion for m in all_mappings if is_met(m))
    if met_sum >= 1.0 - TOLERANCE:
        return self.passed(user)

The ``required_fractrion`` values (note: typo preserved from field name) of all *met* mappings
are summed. If the total is at least 1.0 (within a floating-point tolerance of 0.001), the VITAL
is awarded. This allows several partial-credit mappings to combine to form a complete pass.

Step 5 – Default: Record as Not Passed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    return self.passed(user, False)

If none of the award conditions above were met, the :meth:`~vitals.models.VITAL.passed` method is
called with ``passed=False``. This creates or updates the student's ``VITAL_Result`` to record a
failure.

Summary Table
-------------

The following table summarises how each combination of ``sufficient``, ``necessary``, and
``condition`` is evaluated by :meth:`~vitals.models.VITAL.check_vital`:

.. list-table::
   :header-rows: 1
   :widths: 12 12 12 64

   * - ``sufficient``
     - ``necessary``
     - ``condition``
     - Behaviour in ``check_vital``
   * - ``True``
     - –
     - ``"pass"``
     - Any passing result for this test immediately awards the VITAL (Step 1).
   * - ``True``
     - –
     - ``"attempt"``
     - Any attempt at this test (pass or fail) immediately awards the VITAL (Step 1).
   * - –
     - ``True``
     - ``"pass"``
     - This test must be passed; if not, the award is blocked (Step 3).
   * - –
     - ``True``
     - ``"attempt"``
     - This test must be attempted; if not, the award is blocked (Step 3).
   * - –
     - –
     - ``"pass"`` or ``"attempt"``
     - Contributes its ``required_fractrion`` to the running total when met; VITAL awarded
       when the total reaches 1.0 (Step 4).

Flow Diagram
------------

::

    check_vital(user)
         │
         ▼
    Any sufficient mapping met (respecting condition)? ──► YES ──► VITAL awarded
         │
         NO
         │
         ▼
    Any test results at all? ──► NO ──► return False (no result recorded)
         │
         YES
         │
         ▼
    Any necessary mapping NOT met? ──► YES ──► VITAL recorded as not passed
         │
         NO
         │
         ▼
    Sum of required_fractrion for met conditions >= 1.0? ──► YES ──► VITAL awarded
         │
         NO
         │
         ▼
    VITAL recorded as not passed
