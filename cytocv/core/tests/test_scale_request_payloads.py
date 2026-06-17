from __future__ import annotations

import json
from uuid import uuid4

from django.test import SimpleTestCase

from core.services.scale_request_payloads import (
    parse_file_scale_map_payload,
    parse_file_scale_revert_payload,
)


class ScaleRequestPayloadTests(SimpleTestCase):
    def test_scale_map_payload_preserves_empty_contract(self):
        parsed, error, status = parse_file_scale_map_payload(
            "",
            active_uuid_set=set(),
        )

        self.assertEqual(parsed, {})
        self.assertIsNone(error)
        self.assertEqual(status, 200)

    def test_scale_map_payload_preserves_error_contracts(self):
        active_uuid = str(uuid4())
        unavailable_uuid = str(uuid4())

        cases = (
            (
                "{bad-json",
                "Invalid per-file scale payload.",
                400,
            ),
            (
                json.dumps(["not", "an", "object"]),
                "Per-file scale payload must be a JSON object.",
                400,
            ),
            (
                json.dumps({"not-a-uuid": 1.0}),
                "Per-file scale payload contains an invalid UUID.",
                400,
            ),
            (
                json.dumps({unavailable_uuid: 1.0}),
                "Per-file scale payload contains unavailable files.",
                403,
            ),
            (
                json.dumps({active_uuid: "not-numeric"}),
                "Per-file scale values must be numeric.",
                400,
            ),
            (
                json.dumps({active_uuid: 0}),
                "Per-file scale values must be greater than 0.",
                400,
            ),
        )

        for raw_payload, expected_error, expected_status in cases:
            with self.subTest(raw_payload=raw_payload):
                parsed, error, status = parse_file_scale_map_payload(
                    raw_payload,
                    active_uuid_set={active_uuid},
                )

                self.assertEqual(parsed, {})
                self.assertEqual(error, expected_error)
                self.assertEqual(status, expected_status)

    def test_scale_map_payload_preserves_valid_override_contract(self):
        active_uuid = str(uuid4())

        parsed, error, status = parse_file_scale_map_payload(
            json.dumps({active_uuid.upper(): {"effective_um_per_px": "0.25"}}),
            active_uuid_set={active_uuid},
        )

        self.assertEqual(parsed, {active_uuid: 0.25})
        self.assertIsNone(error)
        self.assertEqual(status, 200)

    def test_scale_revert_payload_preserves_empty_contract(self):
        parsed, error, status = parse_file_scale_revert_payload(
            "",
            active_uuid_set=set(),
        )

        self.assertEqual(parsed, set())
        self.assertIsNone(error)
        self.assertEqual(status, 200)

    def test_scale_revert_payload_preserves_error_contracts(self):
        active_uuid = str(uuid4())
        unavailable_uuid = str(uuid4())

        cases = (
            (
                "{bad-json",
                "Invalid scale revert payload.",
                400,
            ),
            (
                json.dumps({"not": "an array"}),
                "Scale revert payload must be a JSON array.",
                400,
            ),
            (
                json.dumps(["not-a-uuid"]),
                "Scale revert payload contains an invalid UUID.",
                400,
            ),
            (
                json.dumps([unavailable_uuid]),
                "Scale revert payload contains unavailable files.",
                403,
            ),
        )

        for raw_payload, expected_error, expected_status in cases:
            with self.subTest(raw_payload=raw_payload):
                parsed, error, status = parse_file_scale_revert_payload(
                    raw_payload,
                    active_uuid_set={active_uuid},
                )

                self.assertEqual(parsed, set())
                self.assertEqual(error, expected_error)
                self.assertEqual(status, expected_status)

    def test_scale_revert_payload_preserves_valid_revert_contract(self):
        active_uuid = str(uuid4())

        parsed, error, status = parse_file_scale_revert_payload(
            json.dumps([active_uuid.upper()]),
            active_uuid_set={active_uuid},
        )

        self.assertEqual(parsed, {active_uuid})
        self.assertIsNone(error)
        self.assertEqual(status, 200)
