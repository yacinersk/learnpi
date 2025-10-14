from flask import Blueprint, request, jsonify, send_file
from extensions import db
import os


import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime

from .utils import verify_pi_token  # Add this import

bp = Blueprint('certificates', __name__)

STORAGE_ZONE = os.getenv("STORAGE_ZONE")
ACCESS_KEY = os.getenv("ACCESS_KEY")
CDN_BASE_URL = os.getenv("CDN_BASE_URL")

import os
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime

STORAGE_ZONE = "thumbnailspilearn"
ACCESS_KEY = "0ba2a024-c7dc-423d-a4f9cb83c4cf-f9ff-41cf"
CDN_BASE_URL = "https://learnpi.b-cdn.net"

@bp.route("/generate", methods=["POST"])
def generate_certificate():
    from models import Certificate, Course, Progress, User, Lecture
    data = request.get_json()
    access_token = data.get("accessToken")
    course_id = data.get("course_id")

    if not access_token or not course_id:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    progress = Progress.query.filter_by(user_id=user.id, course_id=course_id, completed=True).count()
    total_lectures = Lecture.query.filter_by(course_id=course_id).count()

    print(progress)
    print(total_lectures)
    if progress < total_lectures or total_lectures == 0:
        return jsonify({"success": False, "error": "Course not fully completed"}), 403

    existing = Certificate.query.filter_by(user_id=user.id, course_id=course_id).first()
    if existing:
        return jsonify({"success": True, "certificate_url": existing.pdf_url})

    # Generate certificate PDF locally
    course = Course.query.get(course_id)
    file_name = f"certificate_{user.id}_{course.id}.pdf"
    local_path = os.path.join("temp_certificates", file_name)
    os.makedirs("temp_certificates", exist_ok=True)

    c = canvas.Canvas(local_path, pagesize=A4)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(300, 700, "Certificate of Completion")
    c.setFont("Helvetica", 16)
    c.drawCentredString(300, 650, f"This is to certify that")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(300, 610, user.username)
    c.setFont("Helvetica", 16)
    c.drawCentredString(300, 570, f"has successfully completed the course:")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(300, 530, course.title)
    c.setFont("Helvetica", 12)
    c.drawCentredString(300, 480, f"Issued on {datetime.utcnow().strftime('%Y-%m-%d')}")
    c.save()

    # Upload to Bunny.net
    bunny_url = f"https://storage.bunnycdn.com/{STORAGE_ZONE}/certificates/{file_name}"
    headers = {"AccessKey": ACCESS_KEY, "Content-Type": "application/octet-stream"}

    with open(local_path, "rb") as f:
        response = requests.put(bunny_url, headers=headers, data=f)
    
    # Remove local file
    os.remove(local_path)

    if response.status_code not in (200, 201):
        return jsonify({"success": False, "error": "Failed to upload to Bunny.net"}), 500

    cert_url = f"{CDN_BASE_URL}/certificates/{file_name}"

    cert = Certificate(user_id=user.id, course_id=course.id, pdf_url=cert_url)
    db.session.add(cert)
    db.session.commit()

    return jsonify({"success": True, "certificate_url": cert_url})

@bp.route("/my", methods=["POST"])
def my_certificates():
    from models import Certificate, Course,  User
    data = request.get_json()
    access_token = data.get("accessToken")

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    certs = Certificate.query.filter_by(user_id=user.id).all()
    return jsonify({
        "success": True,
        "certificates": [
            {
                "course_id": c.course_id,
                "course_title": Course.query.get(c.course_id).title,
                "pdf_url": c.pdf_url,
                "issued_at": c.issued_at.isoformat()
            } for c in certs
        ]
    })
