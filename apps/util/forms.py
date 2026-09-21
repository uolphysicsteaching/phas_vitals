# -*- coding: utf-8 -*-
"""Common Form Classes."""
# Python imports
import base64
import binascii
import codecs
import os
from copy import deepcopy

try:
    # external imports
    import magic
except ImportError:
    magic = None

# Python imports
from mimetypes import guess_type

# Django imports
from django import forms
from django.db.models import Count

# external imports
import nh3
from minerva.models import Module

OBFUSCATED_HTML_PREFIX = "ROT13+B64:"


def sanitize_rich_html(value):
    """Sanitise rich text using the application's server-owned HTML policy."""
    attributes = deepcopy(nh3.ALLOWED_ATTRIBUTES)
    attributes["div"] = {"class"}
    attributes["pre"] = {"class"}
    attributes["span"] = {"style"}
    return nh3.clean(value, tags=set(nh3.ALLOWED_TAGS) | {"footer"}, attributes=attributes)


class ObfuscatedCharField(forms.CharField):
    """Decode and sanitise rich text obfuscated for transport through the WAF."""

    default_error_messages = {
        "invalid_obfuscated_html": "Invalid encoded rich-text value.",
    }

    def to_python(self, value):
        """Decode marked values and sanitise all submitted rich text."""
        value = super().to_python(value)
        if not value:
            return value
        if not value.startswith(OBFUSCATED_HTML_PREFIX):
            return sanitize_rich_html(value)

        payload = value[len(OBFUSCATED_HTML_PREFIX) :]
        try:
            encoded = codecs.decode(payload, "rot_13").encode("ascii")
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (ValueError, binascii.Error, TypeError, UnicodeError) as error:
            raise forms.ValidationError(
                self.error_messages["invalid_obfuscated_html"],
                code="invalid_obfuscated_html",
            ) from error
        return sanitize_rich_html(decoded)


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
        """Construct multiuple upload file form and set default widget argument."""
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        """Clean for either single or multiple files."""
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ExtFileField(MultipleFileField):
    """Same as forms.FileField, but you can specify a file extension whitelist.

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


class UploadGradecentreForm(forms.Form):
    """Provide a form for uploading a zip file and a spreadsheet excel file."""

    module = forms.ModelChoiceField(Module.objects.annotate(ntests=Count("tests")).exclude(ntests=0))

    gradecentre = MultipleFileField()

    def __init__(self, **kwargs):
        """Remove the instance keyword."""
        kwargs.pop("instance", None)  #
        super().__init__(**kwargs)
