# ☁️ Azure Static Site Publisher

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Azure SDK](https://img.shields.io/badge/Azure-SDK%20for%20Python-0078D4?logo=microsoftazure&logoColor=white)](https://github.com/Azure/azure-sdk-for-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An automated **Flask Web Dashboard & CLI toolkit** to dynamically provision, configure, and publish static websites directly to **Microsoft Azure Storage Accounts** (`$web` container). 

Turn any static build folder or .zip archive into an HTTPS-enabled Azure static website in seconds.

---

## 🏗️ Architecture Workflow

```
[Local Folder / .ZIP]
         │
         ▼
[AzureStaticPublisher Engine]
         │
  1. Authenticates via Azure Service Principal (ClientSecretCredential)
  2. Ensures Resource Group exists in selected region (e.g. eastus, westeurope)
  3. Provisions Storage Account (Standard_LRS, StorageV2)
  4. Enables Static Website feature & sets index.html / 404.html
  5. Recursively uploads assets to the $web container with correct MIME types
         │
         ▼
[Live HTTPS Endpoint] ──► https://<sitename>.z13.web.core.windows.net/
```

---

## ✨ Features

* **⚡ Automated Infrastructure Provisioning:** Automatically creates the target Azure Resource Group and StorageV2 account with zero manual portal clicks.
* **🌐 Global Multi-Region Support:** Deploy across global Azure regions (US East, US West, Europe, Asia Pacific, UK, India, Brazil, etc.).
* **📁 Smart Asset Uploading:** Recursively detects content types (HTML, CSS, JS, SVG, WebP, images) and sets proper `Content-Type` headers in Azure Blob Storage.
* **📦 Flexible Inputs:** Deploy directly from a local build directory (e.g. `dist/`, `build/`) or upload a packaged `.zip` file via the Web UI.
* **🖥️ Dual Interface:**
  * **Flask Web Dashboard:** Modern, dark-mode web console with 1-click deployments, live site links, and deletion controls.
  * **Scriptable CLI:** Automate deployments in CI/CD pipelines or headless scripts.
* **🛡️ Cost Governance & Teardown:** Built-in teardown commands and dashboard buttons to permanently delete storage accounts and prevent ongoing cloud costs.

---

## 📋 Prerequisites

* **Python 3.9+** installed on your system.
* An active **Microsoft Azure Subscription**.
* **Azure CLI** installed ([Install Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)).

---

## 🔑 Azure Service Principal Setup

To allow this application to provision Azure resources securely, create an **Azure Service Principal** with `Contributor` role access scoped specifically to your target Resource Group:

1. **Log in to your Azure account:**
   ```bash
   az login
   ```

2. **List your subscription ID:**
   ```bash
   az account show --query "{subscriptionId:id, tenantId:tenantId}" --output table
   ```

3. **Create the target Resource Group:**
   ```bash
   az group create --name "rg-static-sites" --location "eastus"
   ```

4. **Create the Service Principal (scoped to the Resource Group):**
   ```bash
   az ad sp create-for-rbac --name "sp-azure-static-publisher" --role "Contributor" --scopes "/subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/rg-static-sites"
   ```

   Copy the resulting output credentials:
   * `appId` $\rightarrow$ `AZURE_CLIENT_ID`
   * `password` $\rightarrow$ `AZURE_CLIENT_SECRET`
   * `tenant` $\rightarrow$ `AZURE_TENANT_ID`
   * Subscription ID $\rightarrow$ `AZURE_SUBSCRIPTION_ID`

---

## 🚀 Installation & Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Moeez-03/azure-static-site-publisher.git
cd azure-static-site-publisher
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `.env` and fill in your Azure Service Principal credentials:
```bash
cp .env.example .env
```

```env
AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_SECRET=your-service-principal-client-secret
AZURE_SUBSCRIPTION_ID=00000000-0000-0000-0000-000000000000
AZURE_RESOURCE_GROUP=rg-static-sites
AZURE_DEFAULT_LOCATION=eastus
SECRET_KEY=secure-random-key-for-flask
```

---

## 💻 Usage

### Method 1: Web Dashboard (Flask)

> [!IMPORTANT]
> **Security Note:**  
> The dashboard has no authentication. Run it only on localhost and never expose it to the internet.

Start the local web server:
```bash
python app.py
```
Open **`http://localhost:5000`** in your browser:
* View existing static websites and their endpoints.
* Upload a `.zip` archive or specify a local directory to deploy a new site.
* Click **Teardown** to immediately delete any site and purge associated Azure storage.

### Method 2: Command Line Interface (CLI)

#### Deploy a directory or zip archive:
```bash
python publisher.py deploy mysite2026 ./sample_site --location eastus
```

#### List all deployed sites in your Resource Group:
```bash
python publisher.py list
```

#### Delete a deployed storage account:
```bash
python publisher.py delete mysite2026 --yes
```

---

## ⚠️ Cloud Cost & Safety Governance

> [!CAUTION]
> **Resource Management Notice:**  
> This toolkit provisions real Microsoft Azure storage resources (`StorageV2` accounts). While Azure Blob Storage static website hosting is very inexpensive, recurring storage and egress charges still apply.
> 
> * **Always delete test environments:** Once testing is complete, use the dashboard **Teardown** button or run `python publisher.py delete <name>` to delete the storage account.
> * **Permissions:** Limit your Service Principal scopes to specific Resource Groups (`rg-static-sites`) if managing production Azure tenancies.

---

## 👨‍💻 Author
**Abdul Moeez Nadeem**  
* GitHub: [@Moeez-03](https://github.com/Moeez-03)
* LinkedIn: [Abdul Moeez Nadeem](https://www.linkedin.com/in/abdul-moeez-nadeem-98a468205/)

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
