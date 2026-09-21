"""Custom form widgets shared across applications."""

# Django imports
from django import forms

# external imports
from tinymce.widgets import TinyMCE


class ObfuscatedTinyMCE(TinyMCE):
    """Mark a TinyMCE textarea for submit-time HTML obfuscation."""

    def __init__(self, content_language=None, attrs=None, mce_attrs=None):
        """Add the obfuscation selector while preserving caller attributes."""
        attrs = {} if attrs is None else attrs.copy()
        classes = attrs.get("class", "").split()
        if "obfuscate_html" not in classes:
            classes.append("obfuscate_html")
        attrs["class"] = " ".join(classes)
        super().__init__(content_language=content_language, attrs=attrs, mce_attrs=mce_attrs)

    @property
    def media(self):
        """Include TinyMCE's assets followed by the submit-time encoder."""
        return super().media + forms.Media(js=("js/obfuscate_htmlfield.js",))
