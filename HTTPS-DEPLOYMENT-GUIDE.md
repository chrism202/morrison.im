# HTTPS Deployment Guide for morrison.im

This guide walks through deploying morrison.im with HTTPS support using CloudFront and S3.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Domain name (morrison.im) with access to DNS settings
- Existing content ready to upload (index.html, projects.json, etc.)

## Important Notes

⚠️ **Certificate Region Requirement**: ACM certificates for CloudFront **must** be created in `us-east-1` region, regardless of where your stack is deployed.

## Deployment Steps

### Step 1: Deploy the CloudFormation Stack

Choose deployment based on your AWS region:

#### Option A: Deploy in us-east-1 (Simplest)

```bash
aws cloudformation deploy \
  --template-file s3-cloudfront-https-template.yaml \
  --stack-name morrison-im-hosting \
  --region us-east-1 \
  --parameter-overrides \
    DomainName=morrison.im \
    BucketName=morrison-im-site \
    IncludeWWW=false \
    PriceClass=PriceClass_100
```

#### Option B: Deploy in Another Region (Requires Manual Certificate)

If deploying outside us-east-1, you'll need to:

1. **First**, create ACM certificate manually in us-east-1:
   ```bash
   aws acm request-certificate \
     --domain-name morrison.im \
     --validation-method DNS \
     --region us-east-1
   ```

2. **Then**, comment out the `SSLCertificate` resource in the template and add a parameter for certificate ARN

3. **Finally**, deploy with the certificate ARN parameter

### Step 2: Validate DNS for Certificate

After stack creation, AWS will wait for DNS validation:

1. Get the certificate validation records:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name morrison-im-hosting \
     --query 'Stacks[0].Outputs'
   ```

2. Check certificate status:
   ```bash
   # Get certificate ARN from stack outputs first
   aws acm describe-certificate \
     --certificate-arn <CERTIFICATE_ARN> \
     --region us-east-1
   ```

3. Add the CNAME record shown in the output to your DNS provider (this validates domain ownership)

4. Wait for certificate status to change to `ISSUED` (can take 5-30 minutes)

### Step 3: Upload Website Content

Once the stack is created:

```bash
# Upload index.html
aws s3 cp index.html s3://morrison-im-site/ \
  --content-type "text/html" \
  --cache-control "public, max-age=3600"

# Upload projects.json
aws s3 cp projects.json s3://morrison-im-site/ \
  --content-type "application/json" \
  --cache-control "public, max-age=300"

# If you have other assets (CSS, JS, images), upload them too
```

### Step 4: Configure DNS Records

Get the CloudFront distribution domain from stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name morrison-im-hosting \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionDomainName`].OutputValue' \
  --output text
```

Then create DNS records at your domain registrar:

#### If Using Route 53:

```bash
# This will be something like d1234abcd.cloudfront.net
DISTRIBUTION_DOMAIN=$(aws cloudformation describe-stacks \
  --stack-name morrison-im-hosting \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionDomainName`].OutputValue' \
  --output text)

# Create A record (IPv4)
# Use Route 53 console or CLI to create ALIAS record pointing morrison.im to CloudFront
```

#### If Using Another DNS Provider:

Add these records:
- **Type**: CNAME
- **Name**: morrison.im (or @)
- **Value**: `<cloudfront-distribution-domain>` (e.g., d1234abcd.cloudfront.net)
- **TTL**: 300

**Note**: Some DNS providers require you to use ANAME or ALIAS records for root domains. Check your provider's documentation.

### Step 5: Test HTTPS Access

After DNS propagates (5-60 minutes):

```bash
# Test HTTP (should redirect to HTTPS)
curl -I http://morrison.im

# Test HTTPS
curl -I https://morrison.im

# Check in browser
open https://morrison.im
```

## Update GitHub Sync Lambda

Update your GitHub sync Lambda to write to the new bucket:

```bash
aws cloudformation deploy \
  --template-file packaged-github-sync.yml \
  --stack-name GitHubSync \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    SiteBucketName=morrison-im-site \
    ProjectsObjectKey=projects.json \
    GitHubUsername=chrism202 \
    GitHubTokenSecretArn=<your-secret-arn> \
    RepoLimit=5
```

## Invalidating CloudFront Cache

When you update content, you may need to invalidate CloudFront cache:

```bash
# Get distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name morrison-im-hosting \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
  --output text)

# Invalidate all files
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"

# Or invalidate specific files
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/index.html" "/projects.json"
```

## Cost Optimization

The template uses `PriceClass_100` (US, Canada, Europe only) for lower costs. If you need global coverage:

- Change `PriceClass` parameter to `PriceClass_200` or `PriceClass_All`

## Troubleshooting

### Certificate Stuck in "Pending Validation"

- Verify you added the DNS validation CNAME record
- Check DNS propagation: `dig _<random-string>.<domain>`
- DNS validation can take up to 30 minutes

### 403 Forbidden Errors

- Ensure files were uploaded to S3 bucket
- Check bucket policy allows CloudFront access
- Verify Origin Access Control is properly configured

### DNS Not Resolving

- DNS changes can take up to 48 hours to propagate globally
- Test with: `dig morrison.im` or `nslookup morrison.im`
- Try flushing local DNS cache

### Update the Lambda IAM Role

The GitHub Sync Lambda needs permission to write to the new bucket. Update its IAM role if needed:

```yaml
# Add to Lambda's IAM role policy
- Effect: Allow
  Action:
    - s3:PutObject
    - s3:PutObjectAcl
  Resource:
    - arn:aws:s3:::morrison-im-site/*
```

## Stack Outputs Reference

After successful deployment:

```bash
aws cloudformation describe-stacks \
  --stack-name morrison-im-hosting \
  --query 'Stacks[0].Outputs'
```

Key outputs:
- `BucketName`: S3 bucket to upload content to
- `DistributionId`: CloudFront distribution ID (for cache invalidation)
- `DistributionDomainName`: CloudFront domain (for DNS records)
- `WebsiteURL`: Final HTTPS URL
- `CertificateArn`: SSL certificate ARN

## Migration from Old S3 Website Hosting

If you have an existing S3 website bucket:

1. Deploy new stack with a different bucket name
2. Copy content from old bucket to new bucket
3. Update DNS to point to CloudFront
4. Test thoroughly
5. Delete old stack once confirmed working

```bash
# Copy content from old bucket
aws s3 sync s3://old-bucket-name s3://morrison-im-site
```
