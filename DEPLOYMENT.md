
# Deployment
Peachjam can be deployed to a server that has [Dokku](https://dokku.com/) installed. This allows for easy config based deployments using Docker containers.
The following steps outline the procedure to deploy a new Peachjam based application.

## Create an AWS S3 bucket

- [Create an AWS S3 bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html). The bucket
  does NOT need any special permissions or public access.
- [Create an IAM user](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html#id_users_create_console)
  and apply the inline policy below to grant the user read/write access to the bucket.
- **Note:** change `BUCKET` in the example policy to your bucket name:

IAM policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:ListAllMyBuckets"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::BUCKET",
                "arn:aws:s3:::BUCKET/*"
            ]
        }
    ]
}
```

## Create the dokku app

- SSH into the Dokku host and create the application as follows:

      dokku apps:create <app_name>

- Setup the domain for the application

      dokku domains:set <app_name> <domain_name>

## Configuration

- Add the relevant environment variables using the dokku config:set command. The required configuration values can be found in the env.example file.

      dokku config:set CONFIG1=value CONFIG2=value

### Important
- Set the DJANGO_DEBUG environment variable to true on the first instance to disable ingestors and for initial migrations to run. Set it to false after successfully deploying your application.

### Generate Django Secret Key
- To generate the secret key for your application, run:

      dokku config:set <app_name> DJANGO_SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 128 | head -n 1)

### Setup Sentry Data Source Name (DSN) Key
A `SENTRY_DSN_KEY` environment variable is required for Sentry to start monitoring events in the application you've just created. To get a dsn value:
- Access your Laws.Africa Sentry account, click on **Projects** then **Create Project**:

  ![Sentry Create Project](assets/img/sentry.png "Sentry Create Project")


- Upon creating a new Sentry project, a dsn value will be generated automatically. Copy the value and set it as the `SENTRY_DSN_KEY` environment variable for your dokku application.

  ![Sentry DSN Key](assets/img/sentry_dsn.png "Sentry DSN Key")

      dokku config:set <app_name> SENTRY_DSN_KEY=<dsn_value>

### Set NGINX Proxy Read timeout
- We need to increase the read timeout for NGINX to prevent timeout for long-running server tasks:

      dokku nginx:set <app_name> proxy-read-timeout 3600s

### Set File Size Upload Limit
- It is necessary for upload of large files and is done by:

      dokku nginx:set <app_name> client-max-body-size 500m

- Regenerate the dokku app's nginx config (only necessary if changed after deploying)

      dokku proxy:build-config <app_name>

## First deployment

### Disable checks (temporarily)
- It is necessary to disable checks on the dokku application you've just created before the first deployment. This will allow migrations, which are set up as a post deployment task, to run.
  They should be re-enabled once the deployment process is completed successfully.

      dokku checks:disable <app_name>

### Git push

**NOTE: this is to be run on your local machine**

- Dokku will build and deploy the application automatically on git push. First add the remote to the git

      git remote add dokku-<app_name> dokku@<your_server_domain>:<app_name>

- To trigger a build and deploy:

      git push dokku-<app_name> <branch_name>:master

### Setup Languages and Countries
- To populate countries and language data in the database you need to run:

      dokku run <app_name> python manage.py setup_countries_languages

### Create Elasticsearch Index
- To create new elasticsearch index run:

      dokku run <app_name> python manage.py search_index --create


### Enable checks
- Re-enable Zero Downtime Deploy Checks on your application by:

      dokku checks:enable <app_name>

## Post-deployment setup

### Setup SSL
- Enable LetsEncrypt for SSL/TLS. Dokku allows easy setup of SSL using the letsencrypt plugin. On the server, install the letsencrypt dokku plugin:

      sudo dokku plugin:install https://github.com/dokku/dokku-letsencrypt.git

- Configure letsencrypt with the Laws.Africa techops email address, to get reminders about renewing certificates:

      dokku config:set --no-restart <app_name> DOKKU_LETSENCRYPT_EMAIL=your@email.tld

- Install the certificate. Before you install the certificate, your website's domain name must be setup and pointing at this server, so that you can prove that you own the domain.

      dokku letsencrypt <app_name>

- Letsencrypt certificates expire every three months. Set up a cron job to renew certificates automatically:

      dokku letsencrypt:cron-job --add

- You can also manually renew a certificate when it's close to expiry:

      dokku letsencrypt:auto-renew

### Enable Background Tasks

- Peachjam runs various background tasks as separate processes. They can be specified within the Procfile.
- On the dokku server, scale up the processes to run these tasks:

      dokku ps:scale <app_name> tasks=1

### Setup common taxonomies

Most LII websites use a standard taxonomy which helps categorised documents to be made available on AfricanLII's
continent-wide taxonomy collections.

To load these taxonomies, use the following command:

    dokku run <app_name> python manage.py taxonomies --import --root "Case indexes" peachjam/fixtures/taxonomies/environmental.json

    dokku run <app_name> python manage.py taxonomies --import --root "Case indexes" peachjam/fixtures/taxonomies/commercial.json

# Using Cloudflare

Large sites will benefit from Cloudflare, for both caching and for mitigating attacks and stopping naughty bots and crawlers.

## Proxy the site with Cloudflare

This puts the site behind Cloudflare.

- Add the domain to Cloudflare but DO NOT enable DNS proxying, configure DNS only.
- Under SSL/TLS, configure **Full (Strict)** mode.
- Go to DNS and configure **proxied** for the site's A record (NOT the www record).

## Caching

This will instruct Cloudflare to obey the caching headers the site sends.

Go to Caching, Configuration:

- Caching level: standard
- Browser Cache TTL: respect existing headers

Go to Cache Rules and add a new rule to prevent caching when the request has an `hx-request` header. We need this because
Cloudflare doesn't obey Vary headers.

- Name: Cache most pages
- Custom filter expression
  - Field: request header
  - Operator: does not exist
  - Value: hx-request
- Cache eligibility: Eligible for cache
- Edge TTL: Use cache-control header if present, bypass cache if not
- Browser TTL: Respect origin TTL
- Save

## Preventing crawlers

Configure Cloudflare to ask visitors to prove they are humans for certain content based on URL patters. Commonly
this is done for gazettes and judgments.

### AI Crawl Control

Cloudflare has a handy UI for blocking common crawlers.

Go to AI Crawl Control

- Click Block alongside the bots you want to block

It's recommended to block:

- AI Search
- AI Crawler
- AI Assistant

It's NOT recommended to block:

- Search Engine Crawler

### Preventing bots for a simple path prefix

Go to Security, Security rules:

- Create rule, custom rules
- Give it a name (such as "gazettes")
- When incoming requests match…
  - Field: URI path
  - Operator: starts with
  - Value: your prefix such as `/akn/` for all documents
- Action: mananged challenge
- Save

### Preventing bots for a wildcard path

This is important for sites with multiple languages, for example

Go to Security, Security rules:

- Create rule, custom rules
- Give it a name (such as "gazettes")
- When incoming requests match…
    - Field: URI path
    - Operator: wildcard
    - Value: `*/akn/*/judgment/` (for example)
- Action: mananged challenge
- Save
