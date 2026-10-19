import os
import tempfile
import zipfile
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename

import config
from publisher import AzureStaticPublisher

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Helper function to get publisher instance
def get_publisher():
    if not config.is_configured():
        return None
    try:
        return AzureStaticPublisher()
    except Exception as e:
        app.logger.error(f"Failed to initialize AzureStaticPublisher: {e}")
        return None


@app.route("/")
def index():
    publisher = get_publisher()
    configured = config.is_configured()
    sites = []
    error = None

    if configured and publisher:
        try:
            sites = publisher.list_sites()
        except Exception as e:
            error = str(e)
    elif not configured:
        error = "Azure credentials not fully configured. Please set them in your .env file."

    return render_template(
        "index.html",
        sites=sites,
        configured=configured,
        error=error,
        resource_group=config.AZURE_RESOURCE_GROUP
    )


@app.route("/deploy", methods=["GET", "POST"])
def deploy():
    publisher = get_publisher()
    if not publisher:
        flash("Azure credentials are not configured. Check your .env file.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        account_name = request.form.get("name", "").strip()
        location = request.form.get("location", config.AZURE_DEFAULT_LOCATION)
        index_doc = request.form.get("index_doc", "index.html").strip() or "index.html"
        error_doc = request.form.get("error_doc", "404.html").strip() or "404.html"

        if not account_name:
            flash("Site / storage account name is required.", "error")
            return redirect(url_for("deploy"))

        file = request.files.get("zip_file")
        folder_path = request.form.get("folder_path", "").strip()

        try:
            if file and file.filename.endswith(".zip"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                    file.save(tmp.name)
                    tmp_zip_path = tmp.name

                result = publisher.deploy_site(
                    account_name=account_name,
                    source_path=tmp_zip_path,
                    location=location,
                    index_document=index_doc,
                    error_document=error_doc
                )
                os.remove(tmp_zip_path)
            elif folder_path and os.path.isdir(folder_path):
                result = publisher.deploy_site(
                    account_name=account_name,
                    source_path=folder_path,
                    location=location,
                    index_document=index_doc,
                    error_document=error_doc
                )
            else:
                flash("Please upload a .zip archive or specify a valid local folder path.", "error")
                return redirect(url_for("deploy"))

            flash(f"Successfully deployed! Live endpoint: {result['web_endpoint']}", "success")
            return redirect(url_for("index"))

        except Exception as e:
            flash(f"Deployment failed: {str(e)}", "error")
            return redirect(url_for("deploy"))

    return render_template(
        "deploy.html",
        regions=config.AZURE_REGIONS,
        default_region=config.AZURE_DEFAULT_LOCATION
    )


@app.route("/delete/<account_name>", methods=["POST"])
def delete_site(account_name):
    publisher = get_publisher()
    if not publisher:
        flash("Azure credentials are not configured.", "error")
        return redirect(url_for("index"))

    success = publisher.delete_site(account_name)
    if success:
        flash(f"Storage account '{account_name}' was successfully deleted.", "success")
    else:
        flash(f"Failed to delete storage account '{account_name}'. Check logs for details.", "error")

    return redirect(url_for("index"))


@app.route("/api/sites")
def api_sites():
    publisher = get_publisher()
    if not publisher:
        return jsonify({"error": "Azure credentials not configured", "sites": []}), 500
    sites = publisher.list_sites()
    return jsonify({"sites": sites})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=True)
