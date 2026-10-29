
import os
import json
import base64
import time
from datetime import datetime, timezone

TABLE_NAME = os.environ.get(
    "ANALYTICS_TABLE",
    "portfolio-analytics-daily"
)

# Only these values can become metric keys.
ALLOWED_PROJECTS = {
    "words2motion",
    "github",
    "aws-portfolio",
}

ALLOWED_SECTIONS = {
    "about",
    "projects",
    "skills",
    "contact",
}

BOT_SIGNATURES = (
    "bot",
    "crawler",
    "spider",
    "slurp",
    "facebookexternalhit",
    "preview",
    "headlesschrome",
    "lighthouse",
    "pingdom",
    "uptimerobot",
)


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(payload),
    }


def handler(event, context, dynamodb=None, now=None):
    """
    API Gateway HTTP API -> Lambda -> DynamoDB.

    dynamodb and now are injectable for local testing.
    Production calls use the AWS SDK and current UTC time.
    """
    if dynamodb is None:
        import boto3
        dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(TABLE_NAME)

    headers = {
        key.lower(): value
        for key, value in (event.get("headers") or {}).items()
    }

    query = event.get("queryStringParameters") or {}

    # Match the existing portfolio's self-traffic opt-out.
    if query.get("exclude") == "1":
        return response(200, {"accepted": False, "reason": "excluded"})

    user_agent = headers.get("user-agent", "").lower()
    if any(signature in user_agent for signature in BOT_SIGNATURES):
        return response(200, {"accepted": False, "reason": "bot_filtered"})

    raw_body = event.get("body") or "{}"

    if event.get("isBase64Encoded"):
        try:
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        except Exception:
            return response(400, {"error": "Invalid request body"})

    try:
        data = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return response(400, {"error": "Body must be valid JSON"})

    if not isinstance(data, dict):
        return response(400, {"error": "Body must be a JSON object"})

    event_name = data.get("event_name")

    if event_name == "project_click":
        project = data.get("project")

        if project not in ALLOWED_PROJECTS:
            return response(400, {"error": "Invalid project"})

        metric_key = f"project_click#{project}"

    elif event_name == "section_click":
        section = data.get("section")

        if section not in ALLOWED_SECTIONS:
            return response(400, {"error": "Invalid section"})

        metric_key = f"section_click#{section}"

    else:
        return response(400, {"error": "Invalid event_name"})

    current_time = now or datetime.now(timezone.utc)
    event_date = current_time.strftime("%Y-%m-%d")
    expires_at = int(current_time.timestamp()) + (90 * 24 * 60 * 60)

    result = table.update_item(
        Key={
            "event_date": event_date,
            "metric_key": metric_key,
        },
        UpdateExpression=(
            "SET #count = if_not_exists(#count, :zero) + :one, "
            "expires_at = if_not_exists(expires_at, :expires)"
        ),
        ExpressionAttributeNames={
            "#count": "count",
        },
        ExpressionAttributeValues={
            ":zero": 0,
            ":one": 1,
            ":expires": expires_at,
        },
        ReturnValues="UPDATED_NEW",
    )

    return response(200, {
        "accepted": True,
        "event_date": event_date,
        "metric_key": metric_key,
        "count": int(result["Attributes"]["count"]),
    })
