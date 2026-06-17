import typer
import boto3
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from tfstate import debug


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URI: {uri}. Expected s3://bucket/key format.")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI: {uri}. Expected s3://bucket/key format.")
    return bucket, key


def pull(
    s3_uri: str,
    output: Optional[Path] = None,
    profile: Optional[str] = None,
    region: Optional[str] = None,
) -> None:
    debug.logger.debug("Pulling state from S3: %s", s3_uri)
    try:
        bucket, key = parse_s3_uri(s3_uri)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region

    try:
        session = boto3.Session(**session_kwargs)
        s3 = session.client("s3")
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
    except Exception as e:
        debug.exit_with_traceback(e)

    if output:
        output.write_text(content)
        typer.echo(f"State saved to {output}")
    else:
        typer.echo(content)


if __name__ == "__main__":
    typer.run(pull)