# Vercel Deployment Guide

This document provides instructions for deploying the `converter_service` and `card_platform_service` to Vercel.

## 1. Environment Variables Setup

Before deploying, you must set up the following environment variables in your Vercel project's dashboard under **Settings > Environment Variables**. Create one for each item below, ensuring you select the "Secret" type for sensitive values.

| Environment Variable      | Description                                     | Example Value                                  |
| ------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| `STRIGA_WEBHOOK_SECRET`   | The secret key for Striga webhooks.             | `1xgGgRC...` (Your secret)                     |
| `STRIGA_API_KEY`          | The API key for the Striga API.                 | `Sj7v5Lg...` (Your key)                        |
| `STRIGA_API_BASE_URL`     | The base URL for the Striga API.                | `https://api.striga.com/v1`                    |
| `CONVERTER_INTERNAL_URL`  | The public URL to the converter service.        | `https://your-project.vercel.app/api/converter` |
| `DB_HOST`                 | The public IP address of your PostgreSQL DB.    | `34.68.95.172`                                 |
| `DB_PORT`                 | The port of the PostgreSQL DB.                  | `5432`                                         |
| `DB_NAME`                 | The name of your PostgreSQL database.           | `card_platform_db`                             |
| `DB_USER`                 | The username for the PostgreSQL DB.             | `postgres`                                     |
| `DB_PASSWORD`             | The password for your PostgreSQL DB.            | `your-strong-password` (Your secret)           |

**Note on `CONVERTER_INTERNAL_URL`**: Vercel does not support private inter-service communication in the same way as Google Cloud Run. You must use the public URL of your Vercel deployment, pointing to the converter's API path.

## 2. CRITICAL: Database Security Configuration

**WARNING: This is the most critical step for securing your application.**

Because Vercel deployments do not have static IP addresses on standard plans, you must configure your Google Cloud SQL instance to be accessible from the public internet (`0.0.0.0/0`). This makes your database a potential target for attackers.

To secure your data, you **MUST** enforce two layers of protection:
1.  **Use a strong, unique password** for your database.
2.  **Enforce SSL/TLS encryption** on all database connections to protect your credentials and data in transit.

### Step 2.1: Enforce SSL on Google Cloud SQL

1.  **Open the Google Cloud Console** and navigate to your `staging-db-instance`.
2.  Go to the **Connections** tab.
3.  Under the **SSL/TLS** section, ensure that **"Allow only SSL/TLS connections"** is enabled. This is a critical server-side protection.

### Step 2.2: Authorize Vercel's IP Addresses

1.  On the same **Connections** page, find the **Authorized networks** section.
2.  Click **Add a network**.
    *   **Name:** `Vercel Public Access`
    *   **Network:** `0.0.0.0/0`
3.  Click **Done** and **Save** your changes.

By completing both of these steps, you have configured your database to accept public connections but to reject any that are not encrypted. Our application code is already configured to connect with `sslmode='require'`.

## 3. Deploying to Vercel

1.  **Create a New Vercel Project** and connect your Git repository.
2.  **Configure Environment Variables** as described in Step 1.
3.  **Deploy the Project.** Vercel will use the `vercel.json` file to automatically build and route your services.

Your endpoints will be available at the URLs provided in the Vercel deployment summary.
