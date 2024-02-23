# -*- coding: utf-8 -*-
"""Common Form Classes."""
# Python imports
import os

try:
    # external imports
    import magic
except ImportError:
    magic = None

# Python imports
from mimetypes import guess_type

# Django imports
from django import forms


def get_mime(content):
    """Get the mime type of the current file as a string.

    if content is None, use self.content as the file.
    """
    if content is None or not content:
        return ""

    try:
        with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as mimemagic:
            for chunk in content.chunks():
                mime = mimemagic.id_buffer(chunk)
                break
    except AttributeError:
        mime = guess_type(content.name)[0]
    except TypeError:
        for chunk in content.chunks():
            mime = magic.from_buffer(chunk, mime=True)
            break

    return mime


class MultipleFileInput(forms.ClearableFileInput):
    """Override the fil widget to allow multiple files."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Use the MultipleFileWiodget to handle single or multiple file uploads."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ExtFileField(MultipleFileField):
    """
    Same as forms.FileField, but you can specify a file extension whitelist.

    >>> from django.core.files.uploadedfile import SimpleUploadedFile
    >>>
    >>> t = ExtFileField(ext_whitelist=(".pdf", ".txt"))
    >>>
    >>> t.clean(SimpleUploadedFile('filename.pdf', 'Some File Content'))
    >>> t.clean(SimpleUploadedFile('filename.txt', 'Some File Content'))
    >>>
    >>> t.clean(SimpleUploadedFile('filename.exe', 'Some File Content'))
    Traceback (most recent call last):
    ...
    ValidationError: [u'Not allowed filetype!']
    """

    def __init__(self, *args, **kwargs):
        """Create form and setup allowed extensions."""
        ext_whitelist = kwargs.pop("ext_whitelist")
        self.ext_whitelist = [i.lower() for i in ext_whitelist]

        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        """Enforce files matching whitelist."""
        data = super().clean(*args, **kwargs)
        if not isinstance(data, list):
            data = [data]
        for item in data:
            filename = item.name
            ext = os.path.splitext(filename)[1]
            ext = ext.lower()
            if ext not in self.ext_whitelist:
                raise forms.ValidationError(f"{ext} is not allowed filetype!")


class FileSelectForm(forms.Form):
    """Form class for secting a file of allowed mime-type."""

    _pass_files = [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "text/csv",
        "application/zip",
        "application/csv",
        "text/plain",
    ]

    spreadsheet = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={
                "multiple": False,
                "style": "display: none;",
                "data-form-data": '{"csrfmiddlewaretoken": "{{ csrf_token }}"}',
            }
        )
    )

    def clean_spreadsheet(self):
        """Check mimetype of file is allowed."""
        content = self.cleaned_data.get("spreadsheet", False)
        filetype = self.get_mime(content)
        if filetype and filetype not in self._pass_files:
            raise forms.ValidationError(
                "File is not a valid type {} not in {}".format(filetype, ",".join(self._pass_files))
            )
        return content

    @classmethod
    def get_mime(cls, content):
        """Get the mime type of the current file as a string.

        if content is None, use self.content as the file.
        """
        return get_mime(content)
