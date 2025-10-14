from flask import Blueprint, request, jsonify
from extensions import db   

from .utils import verify_pi_token  # Add this import

bp = Blueprint('progress', __name__)

# ----------------------
# Mark lecture as completed
# ----------------------
@bp.route('/update', methods=['PATCH'])
def update_progress():
    from models import Progress, Lecture, User
    data = request.get_json()

    access_token = data.get("accessToken")
    lecture_id = data.get("lecture_id")

    if not access_token or not lecture_id:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    lecture = Lecture.query.get(lecture_id)
    if not lecture:
        return jsonify({"success": False, "error": "Lecture not found"}), 404

    # Get course_id from section
    course_id = lecture.section.course_id if lecture.section else None
    if not course_id:
        return jsonify({"success": False, "error": "Lecture not linked to a course"}), 500

    # Check if progress exists
    progress = Progress.query.filter_by(
        user_id=user.id,
        course_id=course_id,
        lecture_id=lecture_id
    ).first()

    if not progress:
        progress = Progress(
            user_id=user.id,
            course_id=course_id,
            lecture_id=lecture_id,
            completed=True
        )
        db.session.add(progress)
    else:
        progress.completed = True

    db.session.commit()

    return jsonify({"success": True, "message": "Lecture marked as completed"}), 200


# ----------------------
# Get course progress
# ----------------------
@bp.route('/<int:course_id>', methods=['POST'])
def course_progress(course_id):
    from models import Progress, Lecture, Section, User
    data = request.get_json()
    access_token = data.get("accessToken")

    if not access_token:
        return jsonify({"success": False, "error": "No access token provided"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    # Get all lectures under this course
    lecture_ids = [l.id for l in Lecture.query.join(Section).filter(Section.course_id == course_id).all()]

    # Get user's progress
    progress_entries = Progress.query.filter(
        Progress.user_id == user.id,
        Progress.lecture_id.in_(lecture_ids)
    ).all()

    completed_lecture_ids = [p.lecture_id for p in progress_entries if p.completed]
    completed_lectures = len(completed_lecture_ids)
    total_lectures = len(lecture_ids)
    progress_percentage = (completed_lectures / total_lectures * 100) if total_lectures > 0 else 0

    return jsonify({
        "success": True,
        "course_id": course_id,
        "completed_lectures": completed_lectures,
        "total_lectures": total_lectures,
        "progress_percentage": round(progress_percentage),
        "completed_lecture_ids": completed_lecture_ids
    }), 200
