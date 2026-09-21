"""Tests for obfuscated rich-text form transport."""

# Python imports
import base64
import codecs

# Django imports
from django import forms
from django.test import SimpleTestCase

# external imports
from tutorial.forms import MeetingForm, MeetingQuestionForm
from tutorial.models import Meeting, Question
from util.forms import OBFUSCATED_HTML_PREFIX, ObfuscatedCharField
from util.widgets import ObfuscatedTinyMCE


def encode_for_transport(value):
    """Encode a value using the browser transport protocol."""
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return OBFUSCATED_HTML_PREFIX + codecs.encode(encoded, "rot_13")


class ObfuscatedCharFieldTests(SimpleTestCase):
    """Test rich-text decoding, validation and sanitisation."""

    def test_encoded_and_plain_values_use_same_sanitiser(self):
        """Apply the same allowlist regardless of transport encoding."""
        field = ObfuscatedCharField()
        value = '<p data-remove="yes">Hello<script>alert(1)</script></p>'

        self.assertEqual(field.clean(encode_for_transport(value)), field.clean(value))
        self.assertEqual(field.clean(value), "<p>Hello</p>")

    def test_unicode_round_trip(self):
        """Decode UTF-8 text without losing non-ASCII characters."""
        field = ObfuscatedCharField()
        value = "<p>Café — 測試 🚀</p>"

        self.assertEqual(field.clean(encode_for_transport(value)), value)

    def test_malformed_marked_value_is_rejected(self):
        """Reject a marker followed by an invalid payload."""
        field = ObfuscatedCharField()

        with self.assertRaisesMessage(forms.ValidationError, "Invalid encoded rich-text value."):
            field.clean(f"{OBFUSCATED_HTML_PREFIX}not-valid-base64!")

    def test_dangerous_links_are_removed(self):
        """Remove unsafe URL schemes from submitted links."""
        field = ObfuscatedCharField()

        self.assertEqual(
            field.clean('<a href="javascript:alert(1)">click</a>'),
            '<a rel="noopener noreferrer">click</a>',
        )


class ObfuscatedHTMLFieldTests(SimpleTestCase):
    """Test the model-to-form field bridge and widget media."""

    def test_model_field_uses_obfuscated_form_field_and_widget(self):
        """Generate the decoder and marked TinyMCE widget from the model."""
        field = Meeting._meta.get_field("notes").formfield()

        self.assertIsInstance(field, ObfuscatedCharField)
        self.assertIsInstance(field.widget, ObfuscatedTinyMCE)
        self.assertIn("obfuscate_html", field.widget.attrs["class"])
        self.assertIn("js/obfuscate_htmlfield.js", field.widget.media._js)

    def test_all_rich_text_forms_use_obfuscated_fields(self):
        """Protect generated and explicitly declared rich-text form fields."""
        question_field = Question._meta.get_field("text").formfield()

        self.assertIsInstance(MeetingForm().fields["notes"], ObfuscatedCharField)
        self.assertIsInstance(question_field, ObfuscatedCharField)
        self.assertIsInstance(MeetingQuestionForm().fields["text"], ObfuscatedCharField)
