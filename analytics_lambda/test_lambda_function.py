
import json
import unittest
from datetime import datetime, timezone

from lambda_function import handler


class FakeTable:
    def __init__(self):
        self.items = {}

    def update_item(self, **kwargs):
        key = kwargs["Key"]
        values = kwargs["ExpressionAttributeValues"]

        item = self.items.setdefault(
            (key["event_date"], key["metric_key"]),
            {
                **key,
                "count": 0,
                "expires_at": values[":expires"],
            },
        )

        item["count"] += values[":one"]

        return {"Attributes": {"count": item["count"]}}


class FakeDynamoDB:
    def __init__(self):
        self.table_instance = FakeTable()

    def Table(self, name):
        return self.table_instance


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDynamoDB()
        self.now = datetime(
            2026, 10, 28, 12, 0, tzinfo=timezone.utc
        )

    def invoke(self, body, query=None, headers=None):
        event = {
            "body": json.dumps(body),
            "headers": headers or {},
            "queryStringParameters": query,
        }
        result = handler(
            event, None, dynamodb=self.db, now=self.now
        )
        return result["statusCode"], json.loads(result["body"])

    def test_valid_project_click_increments(self):
        status, first = self.invoke({
            "event_name": "project_click",
            "project": "words2motion",
        })
        _, second = self.invoke({
            "event_name": "project_click",
            "project": "words2motion",
        })

        self.assertEqual(status, 200)
        self.assertEqual(first["count"], 1)
        self.assertEqual(second["count"], 2)

    def test_invalid_project_does_not_write(self):
        status, _ = self.invoke({
            "event_name": "project_click",
            "project": "unknown-project",
        })

        self.assertEqual(status, 400)
        self.assertEqual(len(self.db.table_instance.items), 0)

    def test_self_traffic_is_excluded(self):
        status, result = self.invoke(
            {"event_name": "project_click", "project": "words2motion"},
            query={"exclude": "1"},
        )

        self.assertEqual(status, 200)
        self.assertFalse(result["accepted"])
        self.assertEqual(len(self.db.table_instance.items), 0)

    def test_bot_is_excluded(self):
        status, result = self.invoke(
            {"event_name": "project_click", "project": "words2motion"},
            headers={"User-Agent": "Googlebot/2.1"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(result["reason"], "bot_filtered")
        self.assertEqual(len(self.db.table_instance.items), 0)

    def test_invalid_json_is_rejected(self):
        result = handler(
            {
                "body": "{invalid",
                "headers": {},
                "queryStringParameters": None,
            },
            None,
            dynamodb=self.db,
            now=self.now,
        )

        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(len(self.db.table_instance.items), 0)


if __name__ == "__main__":
    unittest.main()
