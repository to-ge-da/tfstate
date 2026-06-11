import typer
import boto3
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


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
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
) -> None:
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
        typer.echo(f"Error fetching from S3: {e}", err=True)
        raise typer.Exit(1)

    if output:
        output.write_text(content)
        typer.echo(f"State saved to {output}")
    else:
        typer.echo(content)


if __name__ == "__main__":
    typer.run(pull)