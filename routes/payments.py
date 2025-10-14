from flask import Blueprint, request, jsonify, session
from extensions import db
from datetime import datetime
import os
import requests

apikey = os.getenv("apikey")

HEADERS = {
    'Authorization': f"Key {apikey}"
}

bp = Blueprint('purchases', __name__)

@bp.route('/confirm', methods=['POST'])
def confirm_purchase():
    from models import Purchase, Course
    # ✅ Ensure user is authenticated via Flask session
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    data = request.get_json()
    course_id = data.get('course_id')
    tx_id = data.get('tx_id')  # Pi SDK returns this after payment confirmation
    price = data.get('price')

    if not course_id or not tx_id:
        return jsonify({'error': 'Missing required fields'}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    # ✅ Check if already purchased
    existing = Purchase.query.filter_by(user_id=user_id, course_id=course_id, status='confirmed').first()
    
    if existing:
        return jsonify({'message': 'Already purchased'}), 200

    # ✅ Create a confirmed purchase entry
    new_purchase = Purchase(
        user_id=user_id,
        course_id=course_id,
        amount_pi=course.price_pi,
        pi_tx_id=tx_id,
        status='confirmed',
        created_at=datetime.utcnow(),
        confirmed_at=datetime.utcnow()
    )

    db.session.add(new_purchase)
    db.session.commit()

    return jsonify({'message': 'Purchase recorded successfully'}), 201

@bp.route('/approve', methods=['POST'])
def approve_payment():
    
    try:
        print(apikey)
        data = request.get_json()
        if not data:
            return jsonify(status="error", message="No JSON data provided"), 400

        payment_id = data.get("paymentId")
        if not payment_id:
            return jsonify(status="error", message="Missing paymentId"), 400

        response = requests.post(f"https://api.minepi.com/v2/payments/{payment_id}/approve", headers=HEADERS)
        if response.status_code == 200:
            return jsonify(status="ok", message="Payment approved"), 200
        else:
            print(response.text)
            return jsonify(status="error", message="Pi API approval failed", details=response.text), response.status_code

    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

@bp.route('/complete', methods=['POST'])
def complete_payment():
    from models import Purchase, Instructor
    try:
        data = request.get_json()
        if not data:
            print("first")
            return jsonify(status="error", message="No JSON data provided"), 400

        payment_id = data.get('paymentId')
        txid = data.get('txid')
        if not payment_id or not txid:
            print("second")
            return jsonify(status="error", message="Missing paymentId or txid"), 400

        # Complete the payment with Pi API
        complete_data = {'txid': txid}
        response = requests.post(
            f"https://api.minepi.com/v2/payments/{payment_id}/complete",
            headers={**HEADERS, 'Content-Type': 'application/json'},
            json=complete_data
        )

        if response.status_code != 200:
            print("third")
            return jsonify(status="error", message="Pi API completion failed", details=response.text), response.status_code

        # Parse response and extract metadata
        payment_info = response.json()
        metadata = payment_info.get("metadata", {})
        user_id = metadata.get("user_id")
        course_data = metadata.get("currentCourse", {})
        course_id = course_data.get("id")
        price = data.get('price')

        print

        if not user_id or not course_id:
            print("forth")
            return jsonify(status="error", message="Missing user_id or course_id in metadata"), 400

        # ✅ Add purchase record to database
        existing_purchase = Purchase.query.filter_by(user_id=user_id, course_id=course_id).first()

        if not existing_purchase:
            new_purchase = Purchase(
                user_id=user_id,
                course_id=course_id,
                amount_pi=course_data.get("price_pi"),  
                pi_tx_id=txid,       
                status="completed",
                created_at=datetime.utcnow(),
                confirmed_at=datetime.utcnow()
            )
            instructor = Instructor.query.filter_by(id=course_data.get("instructor_id")).first()
            if instructor:
                instructor.total_earnings += price * 0.75
                db.session.commit()
            else:
                print("not found")
                return jsonify({"error": "Instructor not found"}), 404

            db.session.add(new_purchase)
            db.session.commit()
        return jsonify(
            status="ok",
            message="Payment completed successfully and course unlocked",
            course_id=course_id
        ), 200

    except Exception as e:
        print(str(e))
        return jsonify(status="error", message=str(e)), 500


@bp.route('/approve/instructor', methods=['POST'])
def approve_instructor_payment():
    try:
        data = request.get_json()
        if not data:
            return jsonify(status="error", message="No JSON data provided"), 400

        payment_id = data.get("paymentId")
        if not payment_id:
            return jsonify(status="error", message="Missing paymentId"), 400

        response = requests.post(f"https://api.minepi.com/v2/payments/{payment_id}/approve", headers=HEADERS)
        if response.status_code == 200:
            return jsonify(status="ok", message="Payment approved"), 200
        else:
            return jsonify(status="error", message="Pi API approval failed", details=response.text), response.status_code

    except Exception as e:
        return jsonify(status="error", message=str(e)), 500


@bp.route('/complete/instructor', methods=['POST'])
def complete_instructor_payment():
    from models import Instructor, User
    try:
        data = request.get_json()
        if not data:
            return jsonify(status="error", message="No JSON data provided"), 400

        payment_id = data.get('paymentId')
        txid = data.get('txid')
        if not payment_id or not txid:
            return jsonify(status="error", message="Missing paymentId or txid"), 400

        # Complete payment in Pi API
        complete_data = {'txid': txid}
        response = requests.post(
            f"https://api.minepi.com/v2/payments/{payment_id}/complete",
            headers={**HEADERS, 'Content-Type': 'application/json'},
            json=complete_data
        )

        if response.status_code != 200:
            return jsonify(status="error", message="Pi API completion failed", details=response.text), response.status_code

        # Extract user data from metadata
        payment_info = response.json()
        metadata = payment_info.get("metadata", {})
        user_id = metadata.get("user_id")

        if not user_id:
            return jsonify(status="error", message="Missing user_id in metadata"), 400

        # ✅ Update user role
        user = User.query.get(user_id)
        if not user:
            return jsonify(status="error", message="User not found"), 404

        user.role = "instructor"

        # ✅ Create Instructor record if not exists
        existing_instructor = Instructor.query.filter_by(user_id=user.id).first()
        if not existing_instructor:
            new_instructor = Instructor(user_id=user.id, total_earnings=0)
            db.session.add(new_instructor)

        db.session.commit()

        return jsonify({
            "status": "ok",
            "message": "Payment completed, user promoted to instructor"
        }), 200

    except Exception as e:
        return jsonify(status="error", message=str(e)), 500
    