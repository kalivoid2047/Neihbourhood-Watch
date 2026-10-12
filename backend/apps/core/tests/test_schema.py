from django.test import TestCase
from rest_framework.test import APIClient


class SchemaEndpointTests(TestCase):
    def test_schema_endpoint_exposes_openapi_metadata(self):
        response = APIClient().get("/api/schema/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["openapi"], "3.0.3")
        self.assertIn("/api/health/", payload["paths"])
        self.assertIn("bearerAuth", payload["components"]["securitySchemes"])

