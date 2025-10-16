# morrison.im

Personal landing site for Chris Morrison — a streamlined hub for current experiments, a running stream of product ideas, and live project highlights sourced straight from GitHub.

## What’s inside

- **Static front-end**: One-page experience (`index.html`) with lightweight CSS, responsive layout, and independent scroll columns for the stream and projects feeds.
- **Stream of Consciousness**: A curated set of notes and product ideas that show up as hard-coded posts while longer-form publishing gets built out.
- **Projects in Motion**: Automatically refreshed cards powered by an AWS Lambda that pulls the five most recently updated repositories from GitHub and drops a `projects.json` into the site’s S3 bucket.
- **Infrastructure as Code**: CloudFormation/SAM template (`github-sync-template.yml`) provisions the sync Lambda, EventBridge schedule, IAM, and Secrets Manager integration.

## Deployment workflow

1. **Static hosting**: Upload `index.html`, `projects.json`, and supporting assets to the public S3 bucket (CloudFront optional). The site is completely static and S3-ready.
2. **GitHub sync**:
   - Store a GitHub Personal Access Token in Secrets Manager (`GitHubTokenSecretArn`).
   - Deploy the stack:
     ```bash
     aws cloudformation package \
       --template-file github-sync-template.yml \
       --s3-bucket <packaging-bucket> \
       --output-template-file packaged-github-sync.yml

     aws cloudformation deploy \
       --template-file packaged-github-sync.yml \
       --stack-name GitHubSync \
       --capabilities CAPABILITY_IAM \
       --parameter-overrides \
         SiteBucketName=<site-bucket> \
         ProjectsObjectKey=projects.json \
         GitHubUsername=<github-user> \
         GitHubTokenSecretArn=<secret-arn> \
         RepoLimit=5
     ```
   - Lambda runs on the configured schedule (default: daily) and writes the JSON payload to the site bucket, keeping the projects list fresh without a redeploy.
3. **Local edits**: Update the stream posts or styling in `index.html`, regenerate the packaged template if the Lambda changes, and repeat the deployment steps.

## Development notes

- The front-end uses no build tooling; edit HTML/CSS directly for rapid iteration.
- `projects.json` in the repo is a placeholder so local previews work even before the Lambda runs.
- Logs for the sync job live in CloudWatch (`/aws/lambda/GitHubSync-GithubSync`). Failures surface there and in the Lambda console.

## Future extensions

- Pipe long-form writing and micro-posts from a headless CMS or GitHub Issues.
- Expand the projects feed with release notes, open milestone stats, or live demos.
- Add a proper design system.

> Snapshot of where the work is today. 

