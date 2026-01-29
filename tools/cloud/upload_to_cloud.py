#!/usr/bin/env python3
"""
Cloud Uploader for Promo Videos

Uploads promo videos and album content to Cloudflare R2 or AWS S3 buckets.
Both use S3-compatible API via boto3.

Requirements:
    - boto3 (pip install boto3)
    - pyyaml (pip install pyyaml)
    - Cloud credentials configured in ~/.bitwize-music/config.yaml

Usage:
    # Upload all promos for an album
    python upload_to_cloud.py my-album

    # Upload only track promos
    python upload_to_cloud.py my-album --type promos

    # Upload only album sampler
    python upload_to_cloud.py my-album --type sampler

    # Dry run (preview what would upload)
    python upload_to_cloud.py my-album --dry-run

    # Specify custom audio root
    python upload_to_cloud.py my-album --audio-root /path/to/audio
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import mimetypes

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 not installed. Run: pip install boto3")
    sys.exit(1)


def load_config() -> Dict[str, Any]:
    """Load bitwize-music config file."""
    config_path = Path.home() / ".bitwize-music" / "config.yaml"
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        print("Run /bitwize-music:configure to set up your configuration.")
        sys.exit(1)

    with open(config_path) as f:
        return yaml.safe_load(f)


def get_s3_client(config: Dict[str, Any]) -> Any:
    """Create S3 client based on provider configuration."""
    cloud_config = config.get("cloud", {})
    provider = cloud_config.get("provider", "r2")

    if provider == "r2":
        r2_config = cloud_config.get("r2", {})
        account_id = r2_config.get("account_id")
        access_key = r2_config.get("access_key_id")
        secret_key = r2_config.get("secret_access_key")

        if not all([account_id, access_key, secret_key]):
            print("Error: R2 credentials not configured in ~/.bitwize-music/config.yaml")
            print("Required fields: cloud.r2.account_id, cloud.r2.access_key_id, cloud.r2.secret_access_key")
            sys.exit(1)

        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    elif provider == "s3":
        s3_config = cloud_config.get("s3", {})
        region = s3_config.get("region", "us-east-1")
        access_key = s3_config.get("access_key_id")
        secret_key = s3_config.get("secret_access_key")

        if not all([access_key, secret_key]):
            print("Error: S3 credentials not configured in ~/.bitwize-music/config.yaml")
            print("Required fields: cloud.s3.access_key_id, cloud.s3.secret_access_key")
            sys.exit(1)

        return boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    else:
        print(f"Error: Unknown cloud provider '{provider}'. Supported: r2, s3")
        sys.exit(1)


def get_bucket_name(config: Dict[str, Any]) -> str:
    """Get bucket name from config."""
    cloud_config = config.get("cloud", {})
    provider = cloud_config.get("provider", "r2")

    if provider == "r2":
        bucket = cloud_config.get("r2", {}).get("bucket")
    else:
        bucket = cloud_config.get("s3", {}).get("bucket")

    if not bucket:
        print(f"Error: Bucket name not configured in cloud.{provider}.bucket")
        sys.exit(1)

    return bucket


def find_album_path(config: Dict[str, Any], album_name: str, audio_root_override: Optional[str] = None) -> Path:
    """Find the album directory in audio_root.

    Tries multiple path patterns in order:
    1. {audio_root}/{artist}/{album}  (documented flat structure)
    2. {audio_root}/{album}           (override already includes artist)
    3. Glob search for {album} anywhere under audio_root (handles
       mirrored content structure like artists/{artist}/albums/{genre}/{album})
    """
    if audio_root_override:
        audio_root = Path(audio_root_override).expanduser()
    else:
        audio_root = Path(config["paths"]["audio_root"]).expanduser()

    artist = config["artist"]["name"]
    checked = []

    # Try standard flat path: {audio_root}/{artist}/{album}
    album_path = audio_root / artist / album_name
    checked.append(str(album_path))
    if album_path.exists():
        return album_path

    # Try direct path (override already includes artist)
    album_path_direct = audio_root / album_name
    checked.append(str(album_path_direct))
    if album_path_direct.exists():
        return album_path_direct

    # Glob search as fallback (handles genre folders, mirrored structures)
    matches = sorted(audio_root.rglob(album_name))
    album_matches = [m for m in matches if m.is_dir()]
    if len(album_matches) == 1:
        return album_matches[0]
    elif len(album_matches) > 1:
        print(f"Error: Multiple directories named '{album_name}' found:")
        for m in album_matches:
            print(f"  - {m}")
        print(f"\nUse --audio-root to point directly at the parent directory.")
        sys.exit(1)

    print(f"Error: Album '{album_name}' not found.")
    print(f"Checked:")
    for path in checked:
        print(f"  - {path}")
    print(f"Also searched recursively under: {audio_root}")
    print(f"\nExpected structure: {audio_root}/{artist}/{album_name}/")
    sys.exit(1)


def get_files_to_upload(album_path: Path, upload_type: str) -> List[Path]:
    """Get list of files to upload based on type."""
    files = []

    if upload_type in ("promos", "all"):
        promo_dir = album_path / "promo_videos"
        if promo_dir.exists():
            files.extend(sorted(promo_dir.glob("*.mp4")))
        else:
            print(f"Warning: promo_videos directory not found at {promo_dir}")

    if upload_type in ("sampler", "all"):
        sampler = album_path / "album_sampler.mp4"
        if sampler.exists():
            files.append(sampler)
        else:
            print(f"Warning: album_sampler.mp4 not found at {sampler}")

    return files


def get_content_type(file_path: Path) -> str:
    """Get MIME type for file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def upload_file(
    s3_client: Any,
    bucket: str,
    file_path: Path,
    s3_key: str,
    public_read: bool = False,
    dry_run: bool = False,
) -> bool:
    """Upload a single file to S3/R2."""
    file_size = file_path.stat().st_size
    content_type = get_content_type(file_path)

    if dry_run:
        print(f"  [DRY RUN] Would upload: {file_path.name}")
        print(f"             -> s3://{bucket}/{s3_key}")
        print(f"             Size: {format_size(file_size)}, Type: {content_type}")
        return True

    try:
        extra_args = {"ContentType": content_type}
        if public_read:
            extra_args["ACL"] = "public-read"

        print(f"  Uploading: {file_path.name} ({format_size(file_size)})...", end=" ", flush=True)

        s3_client.upload_file(
            str(file_path),
            bucket,
            s3_key,
            ExtraArgs=extra_args,
        )

        print("OK")
        return True

    except ClientError as e:
        print(f"FAILED")
        print(f"    Error: {e}")
        return False
    except NoCredentialsError:
        print(f"FAILED")
        print("    Error: AWS credentials not found")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Upload promo videos to Cloudflare R2 or AWS S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s my-album                    # Upload all promos + sampler
    %(prog)s my-album --type promos      # Just track promos
    %(prog)s my-album --type sampler     # Just album sampler
    %(prog)s my-album --dry-run          # Preview what would upload
        """,
    )

    parser.add_argument("album", help="Album name (directory name in audio_root)")
    parser.add_argument(
        "--type",
        choices=["promos", "sampler", "all"],
        default="all",
        help="What to upload: promos (track videos), sampler (album sampler), all (default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be uploaded without actually uploading",
    )
    parser.add_argument(
        "--audio-root",
        help="Override audio_root from config (for custom paths)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Set uploaded files as public-read (default: private)",
    )

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Check if cloud is enabled
    cloud_config = config.get("cloud", {})
    if not cloud_config.get("enabled", False):
        print("Error: Cloud uploads not enabled in config.")
        print("Add 'cloud.enabled: true' to ~/.bitwize-music/config.yaml")
        print("See /reference/cloud/setup-guide.md for setup instructions.")
        sys.exit(1)

    # Get cloud settings
    provider = cloud_config.get("provider", "r2")
    public_read = args.public or cloud_config.get("public_read", False)

    # Find album
    album_path = find_album_path(config, args.album, args.audio_root)
    artist = config["artist"]["name"]

    print(f"Cloud Uploader")
    print(f"==============")
    print(f"Provider: {provider.upper()}")
    print(f"Album: {args.album}")
    print(f"Artist: {artist}")
    print(f"Path: {album_path}")
    print(f"Upload type: {args.type}")
    print(f"Public access: {public_read}")
    if args.dry_run:
        print(f"Mode: DRY RUN (no actual uploads)")
    print()

    # Get files to upload
    files = get_files_to_upload(album_path, args.type)

    if not files:
        print("No files found to upload.")
        print()
        print("Expected files:")
        if args.type in ("promos", "all"):
            print(f"  - {album_path}/promo_videos/*.mp4")
        if args.type in ("sampler", "all"):
            print(f"  - {album_path}/album_sampler.mp4")
        print()
        print("Generate videos with: /bitwize-music:promo-director " + args.album)
        sys.exit(1)

    print(f"Found {len(files)} file(s) to upload:")
    for f in files:
        print(f"  - {f.name} ({format_size(f.stat().st_size)})")
    print()

    # Create S3 client and get bucket
    if not args.dry_run:
        s3_client = get_s3_client(config)
    else:
        s3_client = None

    bucket = get_bucket_name(config)

    # Upload files
    print("Uploading...")
    successful = 0
    failed = 0

    for file_path in files:
        # All promo content goes in the promos folder (track promos + album sampler)
        s3_key = f"{artist}/{args.album}/promos/{file_path.name}"

        if upload_file(s3_client, bucket, file_path, s3_key, public_read, args.dry_run):
            successful += 1
        else:
            failed += 1

    print()
    print(f"Upload complete!")
    print(f"  Successful: {successful}")
    if failed:
        print(f"  Failed: {failed}")
    print()

    # Show URLs if public
    if public_read and not args.dry_run:
        print("Public URLs:")
        if provider == "r2":
            account_id = cloud_config.get("r2", {}).get("account_id")
            # R2 public URL format (if public access enabled on bucket)
            print(f"  Note: Enable public access on R2 bucket to get public URLs")
            print(f"  Bucket URL pattern: https://{bucket}.{account_id}.r2.dev/")
        else:
            region = cloud_config.get("s3", {}).get("region", "us-east-1")
            print(f"  https://{bucket}.s3.{region}.amazonaws.com/{artist}/{args.album}/")

    if args.dry_run:
        print("This was a dry run. Run without --dry-run to actually upload.")


if __name__ == "__main__":
    main()
