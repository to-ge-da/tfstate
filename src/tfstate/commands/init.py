import typer
import boto3
import traceback
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from tfstate.parser import parse_state_file, parse_state_json, StateParseError
from tfstate.state_store import set_state, set_terraform_mode
from tfstate.output import print_init


def is_s3_uri(path: str) -> bool:
    parsed = urlparse(path)
    return parsed.scheme == "s3"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URI: {uri}. Expected s3://bucket/key format.")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI: {uri}. Expected s3://bucket/key format.")
    return bucket, key


def download_from_s3(
    uri: str, profile: Optional[str], region: Optional[str]
) -> tuple[str, str]:
    bucket, key = parse_s3_uri(uri)

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
        error_msg = str(e)
        if "NoSuchBucket" in error_msg or "NoSuchKey" in error_msg:
            raise RuntimeError(f"State file not found: {uri}")
        if "AccessDenied" in error_msg or "UnauthorizedAccess" in error_msg:
            raise RuntimeError(f"Access denied: {uri}. Check your AWS credentials.")
        if "InvalidAccessKeyId" in error_msg or "SignatureDoesNotMatch" in error_msg:
            raise RuntimeError("Authentication failed. Check your AWS credentials.")
        raise RuntimeError(f"Failed to download from S3: {error_msg}")

    return content, uri


def load_local_file(path: str) -> tuple[str, str]:
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"State file not found: {path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")
    try:
        content = file_path.read_text()
    except OSError as e:
        raise RuntimeError(f"Cannot read file: {e}")
    return content, str(file_path)


def check_terraform_installed() -> bool:
    return shutil.which("terraform") is not None


def generate_backend_tf(bucket: str, key: str, region: Optional[str], profile: Optional[str]) -> str:
    lines = [
        'terraform {',
        '  backend "s3" {',
        f'    bucket = "{bucket}"',
        f'    key    = "{key}"',
    ]
    if region:
        lines.append(f'    region = "{region}"')
    if profile:
        lines.append(f'    profile = "{profile}"')
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def init_terraform_backend(
    s3_uri: str, profile: Optional[str], region: Optional[str]
) -> tuple[str, dict]:
    bucket, key = parse_s3_uri(s3_uri)

    workspace = tempfile.mkdtemp(prefix="tfstate-")

    backend_tf_path = Path(workspace) / "backend.tf"
    backend_tf_path.write_text(generate_backend_tf(bucket, key, region, profile))

    env = None
    if profile:
        env = {"AWS_PROFILE": profile}

    result = subprocess.run(
        ["terraform", "init"],
        cwd=workspace,
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"terraform init failed:\n{result.stderr}")

    backend_config = {
        "bucket": bucket,
        "key": key,
        "region": region,
        "profile": profile,
    }

    return workspace, backend_config


def init(
    state_path: str,
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    debug: bool = typer.Option(False, "--debug", help="Show full stack traces"),
    terraform: bool = typer.Option(False, "--terraform", help="Initialize real Terraform backend"),
) -> None:
    try:
        if is_s3_uri(state_path):
            content, source = download_from_s3(state_path, profile, region)
            backend = "S3"
            state = parse_state_json(content)

            if terraform:
                if not check_terraform_installed():
                    raise RuntimeError("terraform binary not found. Is Terraform installed and in PATH?")
                workspace, backend_config = init_terraform_backend(state_path, profile, region)
                set_terraform_mode(workspace, backend_config)
                print_init(state, source, backend, terraform_mode=True)
            else:
                set_state(state, source)
                print_init(state, source, backend)
        else:
            content, source = load_local_file(state_path)
            backend = "local"
            state = parse_state_file(Path(state_path))
            set_state(state, source)
            print_init(state, source, backend)

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except StateParseError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        if debug:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(init)
