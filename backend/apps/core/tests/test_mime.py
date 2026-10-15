from django.test import SimpleTestCase

from apps.core.mime import detect_mime


class DetectMimeTests(SimpleTestCase):
    def test_recognises_common_types(self):
        cases = {
            b"\xff\xd8\xff\xe0" + b"0" * 20: "image/jpeg",
            b"\x89PNG\r\n\x1a\n" + b"0" * 20: "image/png",
            b"GIF89a" + b"0" * 20: "image/gif",
            b"RIFF\x00\x00\x00\x00WEBPVP8 ": "image/webp",
            b"\x00\x00\x00\x18ftypmp42" + b"0" * 8: "video/mp4",
            b"RIFF\x00\x00\x00\x00WAVEfmt ": "audio/wav",
            b"OggS" + b"0" * 20: "audio/ogg",
        }
        for header, mime in cases.items():
            self.assertEqual(detect_mime(header), mime)

    def test_unknown_content_is_none(self):
        self.assertIsNone(detect_mime(b"just some text pretending to be a photo"))
