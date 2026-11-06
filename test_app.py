import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import app


class RenderTest(unittest.TestCase):
    def test_greets_in_the_language_asked(self):
        self.assertTrue(app.render("ta", "Anya").startswith("Vanakkam, Anya!"))
        self.assertTrue(app.render("en", "Sam").startswith("Hello, Sam!"))

    def test_unknown_language_falls_back_to_namaste(self):
        self.assertTrue(app.render("xx", "Ravi").startswith("Namaste, Ravi!"))

    def test_names_are_cleaned_and_clipped(self):
        self.assertEqual(app.clean_name("<script>alert(1)</script>"), "scriptalert1script")
        self.assertEqual(len(app.clean_name("x" * 200)), 40)
        self.assertEqual(app.clean_name("###"), "friend")

    def test_health(self):
        self.assertEqual(app.health(), "ok\n")


class OtlpTest(unittest.TestCase):
    def test_payload_has_the_service_and_pod_and_severity(self):
        import logging
        rec = logging.LogRecord("namaste", logging.ERROR, "x", 1, "boom %s", ("now",), None)
        body = app.otlp_payload([rec])
        attrs = {a["key"]: a["value"]["stringValue"] for a in body["resourceLogs"][0]["resource"]["attributes"]}
        self.assertEqual(attrs["service.name"], app.SERVICE)
        self.assertIn("k8s.pod.name", attrs)
        out = body["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        self.assertEqual((out["severityText"], out["severityNumber"], out["body"]["stringValue"]), ("ERROR", 17, "boom now"))


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def test_routes(self):
        self.assertEqual(self.get("/health"), (200, "ok\n"))
        status, body = self.get("/hello?lang=bn&name=Rima")
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith("Nomoshkar, Rima!"))
        self.assertEqual(self.get("/nope")[0], 404)

    def test_boom_logs_an_error_and_answers_500(self):
        with self.assertLogs("namaste", level="ERROR") as cm:
            status, _ = self.get("/boom?order=A-17")
        self.assertEqual(status, 500)
        self.assertIn("A-17", cm.output[0])


if __name__ == "__main__":
    unittest.main()
