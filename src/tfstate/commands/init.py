import typer
import boto3
import traceback
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from rich.status import Status

from tfstate.parser import parse_state_file, parse_state_json, StateParseError
from tfstate.state_store import set_state, set_terraform_mode, set_workspace
from tfstate.session import save_session
from tfstate.output import print_init, console


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


def download_from_s3(uri: str, profile: Optional[str], region: Optional[str]) -> tuple[str, str]:
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


def generate_backend_tf(
    bucket: str, key: str, region: Optional[str], profile: Optional[str]
) -> str:
    lines = [
        "terraform {",
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
    s3_uri: str, profile: Optional[str], region: Optional[str], workspace: Optional[str] = None
) -> tuple[str, dict]:
    bucket, key = parse_s3_uri(s3_uri)

    workspace_path = workspace or tempfile.mkdtemp(prefix="tfstate-")

    backend_tf_path = Path(workspace_path) / "backend.tf"
    backend_tf_path.write_text(generate_backend_tf(bucket, key, region, profile))

    env = None
    if profile:
        env = {"AWS_PROFILE": profile}

    with Status("Initializing Terraform backend...", console=console):
        result = subprocess.run(
            ["terraform", "init"],
            cwd=workspace_path,
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

    return workspace_path, backend_config


def init_local_terraform_backend(local_path: Path, workspace: str) -> tuple[str, dict]:
    workspace_path = Path(workspace)
    shutil.copy2(local_path, workspace_path / "terraform.tfstate")

    with Status("Initializing Terraform backend...", console=console):
        result = subprocess.run(
            ["terraform", "init"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        raise RuntimeError(f"terraform init failed:\n{result.stderr}")

    backend_config = {
        "backend": "local",
        "path": str(workspace_path / "terraform.tfstate"),
    }

    return workspace, backend_config


def resolve_workspace(output: Optional[str]) -> tuple[str, bool]:
    if output:
        output_path = Path(output).resolve()
        if not output_path.parent.exists():
            raise ValueError(
                f"Parent directory of '{output}' does not exist. "
                "Create it first or choose a different path."
            )
        if output_path.exists():
            if any(output_path.iterdir()):
                raise ValueError(
                    f"Workspace directory '{output}' exists and is not empty. "
                    "Choose a different path or remove it."
                )
            console.print(f"[yellow]Reusing existing empty directory: {output_path}[/yellow]")
        else:
            output_path.mkdir()
        return str(output_path), True
    return tempfile.mkdtemp(prefix="tfstate-"), False


def init(
    state_path: str,
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    debug: bool = typer.Option(False, "--debug", help="Show full stack traces"),
    terraform: bool = typer.Option(False, "--terraform", help="Initialize real Terraform backend"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Custom workspace directory"),
) -> None:
    try:
        if is_s3_uri(state_path):
            content, source = download_from_s3(state_path, profile, region)
            backend = "S3"
            state = parse_state_json(content)

            if terraform:
                if not check_terraform_installed():
                    raise RuntimeError(
                        "terraform binary not found. Is Terraform installed and in PATH?"
                    )
                workspace, _ = resolve_workspace(output)
                workspace, backend_config = init_terraform_backend(
                    state_path, profile, region, workspace=workspace
                )
                set_terraform_mode(workspace, backend_config)
                set_state(state, source, backend)
                set_workspace(workspace)
                save_session(state, source, backend, terraform_mode=True, workspace=workspace)
                print_init(state, source, backend, terraform_mode=True, workspace=workspace)
            else:
                set_state(state, source, backend)
                ws = None
                if output:
                    ws, _ = resolve_workspace(output)
                    (Path(ws) / "state.json").write_text(content)
                    set_workspace(ws)
                save_session(state, source, backend, workspace=ws)
                print_init(state, source, backend, workspace=ws)
        else:
            content, source = load_local_file(state_path)
            backend = "local"
            state = parse_state_file(Path(state_path))

            if terraform:
                if not check_terraform_installed():
                    raise RuntimeError(
                        "terraform binary not found. Is Terraform installed and in PATH?"
                    )
                workspace, _ = resolve_workspace(output)
                workspace, backend_config = init_local_terraform_backend(
                    Path(state_path), workspace
                )
                set_terraform_mode(workspace, backend_config)
                set_state(state, source, backend)
                set_workspace(workspace)
                save_session(state, source, backend, terraform_mode=True, workspace=workspace)
                print_init(state, source, backend, terraform_mode=True, workspace=workspace)
            else:
                set_state(state, source, backend)
                ws = None
                if output:
                    ws, _ = resolve_workspace(output)
                    (Path(ws) / "state.json").write_text(content)
                    set_workspace(ws)
                save_session(state, source, backend, workspace=ws)
                print_init(state, source, backend, workspace=ws)

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
