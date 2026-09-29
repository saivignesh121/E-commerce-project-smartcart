# SmartCart deployment on Railway

This branch is prepared for a Flask + MySQL deployment on Railway.

## 1. Rotate exposed credentials first

The repository previously contained a Gmail app password and Razorpay credentials.
Rotate/revoke those old credentials before deploying. Do not commit the replacements.

## 2. Create a Railway project

1. Create a new Railway project.
2. Choose **Deploy from GitHub repo** and select this repository.
3. Configure the application service to deploy the `deployment/railway` branch.
4. Add a **MySQL** service to the same Railway project.

## 3. Add database variable references to the application service

In the application service's Variables tab, reference the MySQL service values:

```text
MYSQLHOST=${{MySQL.MYSQLHOST}}
MYSQLPORT=${{MySQL.MYSQLPORT}}
MYSQLUSER=${{MySQL.MYSQLUSER}}
MYSQLPASSWORD=${{MySQL.MYSQLPASSWORD}}
MYSQLDATABASE=${{MySQL.MYSQLDATABASE}}
```

If Railway names the database service differently, replace `MySQL` above with that service name.

## 4. Add application secrets

Set these in Railway's Variables tab:

```text
SECRET_KEY=<long-random-value>
MAIL_USERNAME=<gmail-address>
MAIL_PASSWORD=<new-google-app-password>
RAZORPAY_KEY_ID=<new-key-id>
RAZORPAY_KEY_SECRET=<new-key-secret>
```

The non-secret SMTP defaults are already configured in `config.py`.

## 5. Start command

The included `Procfile` runs:

```text
python init_db.py && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

`init_db.py` waits for MySQL and creates missing tables using `schema.sql`.

## 6. Generate a public domain

After a successful deployment, open the application service:
**Settings -> Networking -> Generate Domain**.

Health check endpoint:

```text
/health
```

## 7. Persistent uploaded images

SmartCart stores admin/product uploads under:

```text
/app/static/uploads
```

A Railway deployment filesystem is not suitable for permanent user uploads. For persistence, add a Railway Volume mounted at `/app/static/uploads`.

## Local development

Copy `.env.example` to `.env`, fill in your local values, install dependencies, initialize MySQL, and start Flask:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
python app.py
```

Never commit your real `.env` file.
