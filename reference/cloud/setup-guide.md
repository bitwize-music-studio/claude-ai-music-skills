# Cloud Storage Setup Guide

Complete setup instructions for uploading promo videos to Cloudflare R2 or AWS S3.

## Overview

The `/bitwize-music:cloud-uploader` skill uploads promo videos to cloud storage for hosting, sharing, and CDN distribution. Both Cloudflare R2 and AWS S3 are supported.

## Provider Comparison

| Feature | Cloudflare R2 | AWS S3 |
|---------|---------------|--------|
| Egress fees | None | Yes (varies by region) |
| S3-compatible | Yes | Native |
| CDN | Built-in | CloudFront (extra) |
| Free tier | 10 GB storage, 10M requests/month | 5 GB, 20K GET, 2K PUT |
| Best for | High-traffic content | AWS ecosystem |

**Recommendation:** R2 for most users (no egress fees = free downloads).

---

## Cloudflare R2 Setup

### Step 1: Create R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your account
3. Go to **R2** in left sidebar
4. Click **Create bucket**
5. Enter bucket name (e.g., `promo-videos`)
6. Choose location hint (optional, for performance)
7. Click **Create bucket**

### Step 2: Create API Token

1. In R2 section, click **Manage R2 API Tokens**
2. Click **Create API token**
3. Configure:
   - **Token name:** `bitwize-music-uploader`
   - **Permissions:** Object Read & Write
   - **Specify bucket(s):** Select your bucket (or All buckets)
   - **TTL:** Optional (leave blank for no expiry)
4. Click **Create API Token**
5. **IMPORTANT:** Copy and save the credentials immediately:
   - Access Key ID
   - Secret Access Key
   - You cannot view these again!

### Step 3: Get Account ID

1. Go to R2 overview page
2. Copy your **Account ID** from the right sidebar
   - Format: 32-character hex string

### Step 4: Configure Plugin

Add to `~/.bitwize-music/config.yaml`:

```yaml
cloud:
  enabled: true
  provider: "r2"

  r2:
    account_id: "your-32-char-account-id"
    access_key_id: "your-access-key-id"
    secret_access_key: "your-secret-access-key"
    bucket: "promo-videos"

  public_read: false  # Set true for public URLs
```

### Step 5: Enable Public Access (Optional)

If you want public URLs for your videos:

1. Go to your bucket in R2 dashboard
2. Click **Settings** tab
3. Under **Public access**, click **Allow Access**
4. Note the public URL format: `https://{bucket}.{account-id}.r2.dev/`

Or use a custom domain:
1. Click **Connect Domain**
2. Enter your domain (e.g., `cdn.yoursite.com`)
3. Follow DNS setup instructions

---

## AWS S3 Setup

### Step 1: Create S3 Bucket

1. Log in to [AWS Console](https://console.aws.amazon.com)
2. Go to **S3** service
3. Click **Create bucket**
4. Configure:
   - **Bucket name:** `your-promo-videos` (globally unique)
   - **AWS Region:** Choose closest to your audience
   - **Object Ownership:** ACLs disabled (recommended)
   - **Block Public Access:** Keep enabled unless you need public URLs
5. Click **Create bucket**

### Step 2: Create IAM User

1. Go to **IAM** service
2. Click **Users** → **Create user**
3. Configure:
   - **User name:** `bitwize-music-uploader`
   - **Access type:** Programmatic access
4. Click **Next: Permissions**

### Step 3: Create IAM Policy

1. Click **Attach policies directly**
2. Click **Create policy**
3. Use JSON editor:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

4. Replace `your-bucket-name` with your actual bucket name
5. Click **Next** → **Create policy**
6. Name it `BitwizeMusicUploaderPolicy`

### Step 4: Attach Policy and Create Keys

1. Back on the user creation page, refresh and select your new policy
2. Click **Next** → **Create user**
3. Click on the user name
4. Go to **Security credentials** tab
5. Click **Create access key**
6. Choose **Application running outside AWS**
7. **IMPORTANT:** Download or copy:
   - Access key ID
   - Secret access key

### Step 5: Configure Plugin

Add to `~/.bitwize-music/config.yaml`:

```yaml
cloud:
  enabled: true
  provider: "s3"

  s3:
    region: "us-west-2"  # Your bucket's region
    access_key_id: "AKIAIOSFODNN7EXAMPLE"
    secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    bucket: "your-promo-videos"

  public_read: false
```

### Step 6: Enable Public Access (Optional)

If you need public URLs:

1. Go to bucket → **Permissions** tab
2. Edit **Block public access** → Uncheck all → Save
3. Add bucket policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::your-bucket-name/*"
        }
    ]
}
```

Public URL format: `https://{bucket}.s3.{region}.amazonaws.com/{path}`

---

## Testing Your Setup

### 1. Verify Config

```bash
cat ~/.bitwize-music/config.yaml | grep -A 15 "cloud:"
```

### 2. Test Connection (Dry Run)

```bash
cd /path/to/claude-ai-music-skills
python3 tools/cloud/upload_to_cloud.py test-album --dry-run
```

If credentials work, you'll see what would be uploaded.

### 3. Test Actual Upload

Create a test file and upload:

```bash
# Create test album structure
mkdir -p ~/test-audio/artist/test-album/promo_videos
echo "test" > ~/test-audio/artist/test-album/promo_videos/test.mp4

# Upload
python3 tools/cloud/upload_to_cloud.py test-album --audio-root ~/test-audio

# Verify in dashboard
```

---

## Configuration Reference

### Full Config Example

```yaml
cloud:
  # Master switch - set to true to enable uploads
  enabled: true

  # Provider: "r2" or "s3"
  provider: "r2"

  # Cloudflare R2 settings
  r2:
    account_id: "abc123def456..."
    access_key_id: "your-r2-access-key"
    secret_access_key: "your-r2-secret-key"
    bucket: "promo-videos"

  # AWS S3 settings (ignored if provider is r2)
  s3:
    region: "us-west-2"
    access_key_id: "AKIAIOSFODNN7EXAMPLE"
    secret_access_key: "wJalrXUtnFEMI/..."
    bucket: "my-promo-bucket"

  # Upload settings
  public_read: false  # Default ACL for uploads
```

### Config Fields

| Field | Required | Description |
|-------|----------|-------------|
| `cloud.enabled` | Yes | Must be `true` to enable uploads |
| `cloud.provider` | Yes | `r2` or `s3` |
| `cloud.{provider}.bucket` | Yes | Bucket name |
| `cloud.r2.account_id` | R2 only | Your Cloudflare account ID |
| `cloud.{provider}.access_key_id` | Yes | API access key |
| `cloud.{provider}.secret_access_key` | Yes | API secret key |
| `cloud.s3.region` | S3 only | AWS region (e.g., `us-west-2`) |
| `cloud.public_read` | No | Default `false`. Set `true` for public uploads |

---

## Security Best Practices

### Credential Storage

1. **Never commit credentials to git**
   - `.bitwize-music/` is in your home directory (not in repo)
   - If you put config elsewhere, ensure it's gitignored

2. **Restrict file permissions**
   ```bash
   chmod 600 ~/.bitwize-music/config.yaml
   ```

3. **Use minimal permissions**
   - Only grant write access to specific bucket
   - Don't use root/admin credentials

### API Token Best Practices

**For R2:**
- Scope token to specific bucket(s)
- Consider setting TTL for auto-expiry
- Rotate tokens periodically

**For S3:**
- Use IAM policy with least privilege
- Never use AWS root account keys
- Enable MFA for IAM user (optional)
- Consider using IAM roles for EC2/Lambda

---

## Troubleshooting

### "Invalid credentials" / "Access Denied"

1. Verify credentials are correct (no extra spaces)
2. Check provider matches config (`r2` vs `s3`)
3. For R2: Verify account_id is correct
4. For S3: Verify region matches bucket location
5. Test credentials with provider's CLI tool

### "Bucket not found"

1. Verify bucket name is spelled correctly
2. For S3: Bucket names are globally unique - ensure you own it
3. Check bucket exists in the correct account

### "Connection timeout"

1. Check internet connection
2. For R2: Verify endpoint URL is correct
3. For S3: Verify region is correct

### "No such file or directory"

1. Generate promo videos first: `/bitwize-music:promo-director album`
2. Check album path: `{audio_root}/artists/{artist}/albums/{genre}/{album}/`
3. Verify artist name in config

### R2 public URL not working

1. Enable public access on bucket (Settings → Allow Access)
2. Or set up custom domain
3. Files uploaded before enabling public access may need re-upload

---

## Usage Examples

### Basic Upload

```bash
/bitwize-music:cloud-uploader my-album
```

### Preview First (Recommended)

```bash
/bitwize-music:cloud-uploader my-album --dry-run
```

### Upload with Public Access

```bash
/bitwize-music:cloud-uploader my-album --public
```

### Upload Only Specific Content

```bash
# Just track promos
/bitwize-music:cloud-uploader my-album --type promos

# Just album sampler
/bitwize-music:cloud-uploader my-album --type sampler
```

---

## Related Documentation

- `/skills/cloud-uploader/SKILL.md` - Skill documentation
- `/skills/promo-director/SKILL.md` - Generate promo videos first
- `/reference/promotion/promo-workflow.md` - Full promo workflow
