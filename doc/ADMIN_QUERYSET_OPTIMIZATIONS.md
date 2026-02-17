# Admin Interface Queryset Optimizations

## Overview

This document describes the queryset optimizations applied to Django admin interfaces to resolve N+1 query issues
and improve performance when viewing list pages in the admin.

## Problem Statement

Django admin list views can suffer from the "N+1 query problem" where:

1. One query fetches the main objects to display (e.g., 50 Test_Score records).
2. For each object, additional queries are made to fetch related objects (e.g., user, test, module).
3. This results in 1 + (N × R) queries, where N is the number of objects and R is the number of relations accessed.

For example, displaying 50 Test_Score records with user and test relationships would generate:
- 1 query for Test_Score objects
- 50 queries for User objects
- 50 queries for Test objects
- 50 queries for Module objects (via Test.module)
= **151 total queries** for a single page!

## Solution

Django provides two main methods for optimising related object access:

### 1. `select_related()` for ForeignKey and OneToOneField

Use `select_related()` to perform SQL JOINs and fetch related objects in a single query.

```python
# Before (N+1 queries)
Test_Score.objects.all()  # Access to test_score.user triggers 1 query per row

# After (1 query with JOINs)
Test_Score.objects.select_related('user', 'test', 'test__module')
```

### 2. `prefetch_related()` for ManyToManyField and reverse ForeignKey

Use `prefetch_related()` to fetch related objects in separate optimised queries.

```python
# Before (N+1 queries)
Module.objects.all()  # Access to module.students triggers 1 query per row

# After (2 queries total)
Module.objects.prefetch_related('students')
```

## Implementation in Admin Classes

Django admin provides `list_select_related` and `list_prefetch_related` attributes to automatically optimise
list view queries:

```python
@admin.register(Test_Score)
class Test_ScoreAdmin(ImportExportModelAdmin):
    list_display = ('user', 'test', 'status', 'score', 'passed')
    list_select_related = ('user', 'test', 'test__module')  # Optimise ForeignKey access
```

## Optimizations Applied

### apps/minerva/admin.py

#### ModuleAdmin
- **Added**: `list_select_related = ('year', 'parent_module', 'module_leader')`
- **Impact**: Reduces queries when displaying module list with year and leader information

#### TestAdmin
- **Added**: `list_select_related = ('module', 'category')`
- **Impact**: Eliminates N+1 queries when displaying test list with module and category

#### TestCategoryAdmin
- **Added**: `list_select_related = ('module',)`
- **Impact**: Optimises module access in category list

#### GradebookColumnAdmin
- **Added**: `list_select_related = ('module', 'test', 'category')`
- **Impact**: Critical fix - eliminates triple N+1 cascade (module → test → category)

#### Test_ScoreAdmin
- **Added**: `list_select_related = ('user', 'test', 'test__module')`
- **Impact**: Optimises user and test access with nested module relationship

#### Test_AttemptAdmin
- **Added**: `list_select_related = ('test_entry', 'test_entry__user', 'test_entry__test', 'test_entry__test__module')`
- **Impact**: Optimises nested relationships through test_entry

#### ModuleEnrollmentAdmin
- **Added**: `list_select_related = ('module', 'student', 'status')`
- **Impact**: Eliminates N+1 queries for all three foreign keys

#### ModuleListFilter (Filter Optimization)
- **Changed**: From `[(x.code, str(x)) for x in Module.objects.all()]`
- **To**: `Module.objects.all().values_list('code', 'name')`
- **Impact**: Avoids loading full model instances for filter options

### apps/vitals/admin.py

#### VITALAdmin
- **Added**: `list_select_related = ('module',)`
- **Impact**: Optimises module access in VITAL list

#### VITAL_Test_MapAdmin
- **Added**: `list_select_related = ('test', 'test__module', 'vital', 'vital__module')`
- **Impact**: Optimises double cascade through test and vital to their modules

#### VITAL_ResultAdmin
- **Added**: `list_select_related = ('vital', 'vital__module', 'user')`
- **Impact**: Optimises vital and user access with nested module relationship

#### VITALListFilter (Filter Optimization)
- **Changed**: From `[(vital.VITAL_ID, str(vital)) for vital in res.all()]`
- **To**: `values_list('VITAL_ID', 'name')` with formatted display
- **Impact**: Avoids loading full VITAL instances for filter options

### apps/accounts/admin.py

#### AccountAdmin
- **Added**: `list_select_related = ('year', 'programme', 'section')`
- **Impact**: Optimises account list display with related year, programme and section

#### TermDateAdmin
- **Added**: `list_select_related = ('cohort',)`
- **Impact**: Optimises cohort access in term date list

#### StudentListFilter (Filter Optimization)
- **Changed**: From `[(user.username, user.display_name) for user in res.all()]`
- **To**: `values_list('username', 'first_name', 'last_name')` with formatted display
- **Impact**: Avoids loading full Account instances for filter options

### apps/tutorial/admin.py

#### TutorialAssignmentAdmin
- **Added**: `list_select_related = ('tutorial', 'tutorial__tutor', 'student')`
- **Impact**: Optimises tutorial and student access with nested tutor relationship

#### TutorialAdmin
- **Added**: `list_select_related = ('tutor', 'cohort')`
- **Impact**: Optimises tutor and cohort access in tutorial list

#### SessionAdmin
- **Added**: `list_select_related = ('cohort',)`
- **Impact**: Optimises cohort access in session list

#### AttendanceAdmin
- **Added**: `list_select_related = ('student', 'session', 'session__cohort', 'type')`
- **Impact**: Optimises multiple relationships including nested cohort

#### MeetingAttendanceAdmin
- **Added**: `list_select_related = ('student', 'meeting', 'meeting__cohort', 'tutor')`
- **Impact**: Optimises attendance list with nested meeting relationships

#### MeetingAdmin
- **Added**: `list_select_related = ('cohort',)`
- **Impact**: Optimises cohort access in meeting list

#### TutorialListFilter (Filter Optimization)
- **Changed**: From `[(x.code, x) for x in res]`
- **To**: `values_list('code', 'code')`
- **Impact**: Avoids loading full Tutorial instances for filter options

### apps/util/admin.py

#### StudentListFilter (Filter Optimization)
- **Changed**: From `[(user.username, user.display_name) for user in res.all()]`
- **To**: `values_list('username', 'first_name', 'last_name')` with formatted display
- **Impact**: Avoids loading full Account instances for filter options

#### StaffListFilter (Filter Optimization)
- **Changed**: From `[(user.username, user.display_name) for user in res.all()]`
- **To**: `values_list('username', 'first_name', 'last_name')` with formatted display
- **Impact**: Avoids loading full Account instances for filter options

## Performance Impact

### Expected Query Reduction

For a typical admin list page with 50 items:

| Admin Class | Before | After | Reduction |
|------------|--------|-------|-----------|
| GradebookColumnAdmin | 151 | 1 | 99.3% |
| Test_ScoreAdmin | 151 | 1 | 99.3% |
| Test_AttemptAdmin | 201 | 1 | 99.5% |
| ModuleEnrollmentAdmin | 151 | 1 | 99.3% |
| VITAL_Test_MapAdmin | 201 | 1 | 99.5% |
| VITAL_ResultAdmin | 151 | 1 | 99.3% |
| MeetingAttendanceAdmin | 201 | 1 | 99.5% |

### Filter Optimization Impact

List filters are loaded on every page view, so optimising them is particularly important:

| Filter | Before | After | Impact |
|--------|--------|-------|--------|
| StudentListFilter | N+1 queries (1 per student) | 1 query | Constant time |
| StaffListFilter | N+1 queries (1 per staff) | 1 query | Constant time |
| ModuleListFilter | N+1 queries (1 per module) | 1 query | Constant time |
| VITALListFilter | N+1 queries (1 per VITAL) | 1 query | Constant time |
| TutorialListFilter | N+1 queries (1 per tutorial) | 1 query | Constant time |

## Testing

To verify these optimisations:

1. Enable Django Debug Toolbar in development:
   ```python
   # settings/dev.py
   INSTALLED_APPS += ['debug_toolbar']
   MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
   ```

2. Visit admin list pages and check the SQL panel to verify query counts.

3. Alternative: Enable query logging:
   ```python
   # settings/dev.py
   LOGGING = {
       'version': 1,
       'handlers': {
           'console': {
               'class': 'logging.StreamHandler',
           },
       },
       'loggers': {
           'django.db.backends': {
               'handlers': ['console'],
               'level': 'DEBUG',
           },
       },
   }
   ```

## Best Practices

1. **Always use `list_select_related` for ForeignKey fields in `list_display`**
   - Include nested relationships with double-underscore notation (e.g., `'test__module'`)

2. **Use `list_prefetch_related` for ManyToManyField and reverse ForeignKey**
   - Example: `list_prefetch_related = ('students', 'team_members')`

3. **Optimise list filters with `values_list()`**
   - Avoid iterating over full model instances
   - Only fetch the fields needed for display

4. **Chain relationships efficiently**
   - `select_related('test__module__year')` is more efficient than three separate queries

5. **Profile before optimising**
   - Use Django Debug Toolbar to identify actual N+1 issues
   - Don't prematurely optimise without evidence

## Further Reading

- [Django select_related() documentation](https://docs.djangoproject.com/en/4.2/ref/models/querysets/#select-related)
- [Django prefetch_related() documentation](https://docs.djangoproject.com/en/4.2/ref/models/querysets/#prefetch-related)
- [Django Admin list_select_related documentation](https://docs.djangoproject.com/en/4.2/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_select_related)
- [Database access optimisation](https://docs.djangoproject.com/en/4.2/topics/db/optimization/)
