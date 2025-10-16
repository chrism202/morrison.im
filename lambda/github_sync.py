import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib import request, error

import boto3

SECRETS_CLIENT = boto3.client("secretsmanager")
S3_CLIENT = boto3.client("s3")

_cached_secret: str | None = None


def _load_token(secret_arn: str) -> str:
    global _cached_secret
    if _cached_secret:
        return _cached_secret

    response = SECRETS_CLIENT.get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("Secret does not contain a SecretString payload.")

    secret_value = secret_string.strip()
    if not secret_value:
        raise RuntimeError("GitHub token secret is empty.")

    if secret_value.startswith("{"):
        try:
            payload = json.loads(secret_value)
            candidate_value: str | None = None

            if isinstance(payload, dict):
                for key in ("token", "Token", "PAT", "pat", "github_token", "githubToken", "value"):
                    candidate = payload.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        candidate_value = candidate.strip()
                        break

                if candidate_value is None:
                    for value in payload.values():
                        if isinstance(value, str) and value.strip():
                            candidate_value = value.strip()
                            break
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, str) and item.strip():
                        candidate_value = item.strip()
                        break

            if candidate_value is None:
                raise RuntimeError(
                    "Secret JSON found but no token field detected. "
                    "Expected keys: token, github_token, pat."
                )

            secret_value = candidate_value
        except json.JSONDecodeError:
            pass

    _cached_secret = secret_value
    return secret_value


def _github_request(url: str, token: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "morrison-im-lambda-sync",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"token {token}",
    }
    req = request.Request(url, headers=headers)

    try:
        with request.urlopen(req, timeout=10) as response:
            charset = response.headers.get_content_charset("utf-8")
            payload = response.read().decode(charset)
            return json.loads(payload)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc


def _transform_repo(raw: Dict[str, Any]) -> Dict[str, Any]:
    pushed_at = raw.get("pushed_at")
    last_push = pushed_at if isinstance(pushed_at, str) else None

    return {
        "repo": raw.get("full_name"),
        "displayName": raw.get("name"),
        "summary": raw.get("description"),
        "description": raw.get("description"),
        "htmlUrl": raw.get("html_url"),
        "homepage": raw.get("homepage"),
        "stars": raw.get("stargazers_count"),
        "language": raw.get("language"),
        "topics": raw.get("topics", []),
        "lastPush": last_push,
        "sync": {
            "status": "ok",
            "statusMessage": None,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        },
    }


def build_payload(repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "aws-lambda",
        "projects": [_transform_repo(repo) for repo in repos],
    }


def put_to_s3(bucket: str, key: str, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    S3_CLIENT.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
    )


def lambda_handler(event, context):
    username = os.environ["GITHUB_USERNAME"]
    bucket = os.environ["SITE_BUCKET_NAME"]
    key = os.environ.get("PROJECTS_OBJECT_KEY", "projects.json")
    secret_arn = os.environ["GITHUB_TOKEN_SECRET_ARN"]
    repo_limit = int(os.environ.get("REPO_LIMIT", "5"))

    token = _load_token(secret_arn)
    api_url = (
        f"https://api.github.com/users/{username}/repos"
        "?per_page=100&sort=updated"
    )

    repos = _github_request(api_url, token)
    if not isinstance(repos, list):
        raise RuntimeError("Unexpected payload from GitHub API.")

    sorted_repos = sorted(
        repos,
        key=lambda item: item.get("pushed_at", ""),
        reverse=True,
    )
    top_repos = sorted_repos[:repo_limit]

    payload = build_payload(top_repos)
    put_to_s3(bucket, key, payload)

    return {
        "status": "ok",
        "bucket": bucket,
        "key": key,
        "count": len(top_repos),
    }
