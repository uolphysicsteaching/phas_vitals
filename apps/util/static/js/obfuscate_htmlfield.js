(function () {
    "use strict";

    const prefix = "ROT13+B64:";

    function rot13(value) {
        return value.replace(/[A-Za-z]/g, function (character) {
            const code = character.charCodeAt(0);
            const first = code <= 90 ? 65 : 97;
            return String.fromCharCode(first + ((code - first + 13) % 26));
        });
    }

    function utf8Base64(value) {
        const bytes = new TextEncoder().encode(value);
        let binary = "";
        bytes.forEach(function (byte) {
            binary += String.fromCharCode(byte);
        });
        return btoa(binary);
    }

    document.addEventListener("submit", function (event) {
        const fields = event.target.querySelectorAll(".obfuscate_html");
        if (!fields.length) {
            return;
        }

        if (window.tinymce) {
            window.tinymce.triggerSave();
        }

        fields.forEach(function (field) {
            const value = field.value || "";
            if (!value.startsWith(prefix)) {
                field.value = prefix + rot13(utf8Base64(value));
            }
        });
    }, true);
})();
