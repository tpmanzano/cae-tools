"""
DRE License Lookup — Web Application
California Advantage Escrow — Compliance

Flask backend that proxies DRE license lookups (solves CORS)
and serves a clean frontend. Designed for Azure deployment.

Local: python app.py
Azure: deploy as Azure Function + Static Web App
"""

import re
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

DRE_URL = "https://www2.dre.ca.gov/publicasp/pplinfo.asp"
DRE_SEARCH_URL = "https://www2.dre.ca.gov/publicasp/pplinfo.asp?start=1"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/lookup", methods=["POST"])
def lookup():
    data = request.get_json()
    license_id = data.get("license_id", "").strip()

    # Validate: digits only, max 8 chars
    if not license_id or not license_id.isdigit() or len(license_id) > 8:
        return jsonify({"error": "Invalid license number. Digits only, max 8 characters."}), 400

    try:
        # POST to DRE
        resp = requests.post(
            DRE_SEARCH_URL,
            data={
                "h_nextstep": "SEARCH",
                "LICENSEE_NAME": "",
                "CITY_STATE": "",
                "LICENSE_ID": license_id,
            },
            timeout=15,
        )
        resp.raise_for_status()

        html = resp.text

        # Check for no results
        if "No records found" in html or "License Type:" not in html:
            return jsonify({"error": f"No records found for license ID: {license_id}"}), 404

        # Extract the result section from the HTML
        result_html = _extract_result(html)

        # Extract licensee name for display
        name = _extract_name(html)

        return jsonify({
            "html": result_html,
            "name": name,
            "license_id": license_id,
        })

    except requests.Timeout:
        return jsonify({"error": "DRE site timed out. Try again."}), 504
    except requests.RequestException as e:
        return jsonify({"error": f"Could not reach DRE site: {str(e)}"}), 502


def _extract_result(html):
    """
    Extract the license result table from the DRE response HTML.
    Rewrite relative URLs to absolute.
    """
    # Find the result table — everything from "License information taken"
    # to "Public information request complete"
    match = re.search(
        r"(License information taken.*?Public information request complete\s*&lt;&lt;&lt;&lt;|"
        r"License information taken.*?Public information request complete\s*<<<<)",
        html,
        re.DOTALL,
    )

    if match:
        content = match.group(0)
    else:
        # Fallback: extract from the main table
        match = re.search(r"(<table[^>]*>.*?</table>)\s*</body>", html, re.DOTALL)
        content = match.group(1) if match else html

    # Rewrite relative URLs to absolute
    content = content.replace('HREF = "/static/', 'HREF = "https://www2.dre.ca.gov/static/')
    content = content.replace('HREF = "/publicasp/', 'HREF = "https://www2.dre.ca.gov/publicasp/')
    content = content.replace("href='/static/", "href='https://www2.dre.ca.gov/static/")
    content = content.replace("href='/publicasp/", "href='https://www2.dre.ca.gov/publicasp/")

    return content


def _extract_name(html):
    """Extract licensee name from the DRE response."""
    match = re.search(r"<strong>Name:</strong>.*?</td>\s*<td>.*?>([\w,\s]+)<", html, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


if __name__ == "__main__":
    app.run(debug=True, port=5000)
