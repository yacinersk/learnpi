from flask import Blueprint, request, jsonify
from extensions import db   
from datetime import datetime

from .utils import verify_pi_token  # Add this import


bp = Blueprint("ratings", __name__, url_prefix="/api/ratings")

# -----------------------------
# Add or update rating
# -----------------------------
@bp.route("/add", methods=["POST"])
def add_rating():
    from models import Rating, User, Course
    data = request.get_json()
    access_token = data.get("accessToken")
    course_id = data.get("course_id")
    rating_value = data.get("rating")
    review = data.get("review", "").strip()

    if not all([access_token, course_id, rating_value]):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    if review and len(review) > 100:
        return jsonify({"success": False, "error": "Review must be 100 characters or less"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"success": False, "error": "Course not found"}), 404

    # Check if user already rated
    existing = Rating.query.filter_by(user_id=user.id, course_id=course_id).first()
    if existing:
        existing.rating = rating_value
        existing.review = review
        existing.created_at = datetime.utcnow()
    else:
        new_rating = Rating(
            user_id=user.id,
            course_id=course_id,
            rating=rating_value,
            review=review
        )
        db.session.add(new_rating)

    db.session.commit()
    return jsonify({"success": True, "message": "Rating submitted"}), 200


# -----------------------------
# Get all ratings for a course
# -----------------------------
@bp.route("/get", methods=["GET"])
def get_ratings():
    from models import Rating, Course
    course_id = request.args.get("course_id")
    if not course_id:
        return jsonify({"success": False, "error": "Missing course_id"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"success": False, "error": "Course not found"}), 404

    ratings = Rating.query.filter_by(course_id=course_id).all()
    if not ratings:
        return jsonify({"success": True, "ratings": [], "average_rating": 0}), 200

    average = sum(r.rating for r in ratings) / len(ratings)
    ratings_data = [
        {
            "user_id": r.user_id,
            "rating": r.rating,
            "review": r.review,
            "created_at": r.created_at.isoformat()
        } for r in ratings
    ]

    return jsonify({"success": True, "ratings": ratings_data, "average_rating": round(average, 2)}), 200
