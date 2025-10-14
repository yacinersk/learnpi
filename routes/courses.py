from flask import Blueprint, request, jsonify
from extensions import db

from sqlalchemy import or_

from .utils import verify_pi_token

bp = Blueprint('courses', __name__)

@bp.route('/', methods=['GET'])
def list_courses():
    from models import Course
    q = request.args.get('q')
    query = Course.query.filter_by(is_published=True)
    if q:
        query = query.filter(or_(Course.title.ilike(f'%{q}%'), Course.description.ilike(f'%{q}%')))
    courses = query.order_by(Course.created_at.desc()).all()
    print('queried')
    print(courses)
    data = []
    for c in courses:
        data.append({
            'id': c.id, 
            'title': c.title, 
            'description': c.description, 
            'price_pi': c.price_pi, 
            'instructor_id': c.instructor_id, 
            'thumbnail': c.thumbnail_url
        })
    return jsonify(data)

@bp.route('/<int:course_id>', methods=['GET'])
def course_detail(course_id):
    from models import Course
    course = Course.query.get_or_404(course_id)
    
    # Build sections with lectures
    sections_data = []
    for section in course.sections:
        lectures_data = [{
            'id': l.id, 
            'title': l.title, 
            'order': l.order, 
            'video_id': l.video_id, 
            'duration': l.duration
        } for l in section.lectures]
        
        sections_data.append({
            'id': section.id,
            'title': section.title,
            'order': section.order,
            'lectures': lectures_data
        })
    
    return jsonify({
        'id': course.id, 
        'title': course.title, 
        'description': course.description, 
        'price_pi': course.price_pi, 
        'sections': sections_data,
        'is_published': course.is_published,
        'instructor_id': course.instructor_id, 
        'library_id': course.library_id,
        'thumbnail': course.thumbnail_url
    })


@bp.route('/<int:course_id>/access', methods=['GET'])
def check_course_access(course_id):
    from models import Course, Purchase
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_id = int(auth_header.split('Bearer ')[1])
    except ValueError:
        return jsonify({"error": "Invalid user ID"}), 400
    
    # 2. Verify course exists
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    # 3. Check if user purchased it
    purchase = Purchase.query.filter_by(
        user_id=user_id,
        course_id=course_id,
        status='completed'
    ).first()

    # 4. Return access result
    return jsonify({'has_access': purchase is not None})


@bp.route("/enrolled", methods=["POST"])
def get_enrolled_courses():
    from models import Course, Purchase, User
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

    purchases = Purchase.query.filter_by(user_id=user.id).all()
    course_ids = [p.course_id for p in purchases]
    courses = Course.query.filter(Course.id.in_(course_ids)).all()
    
    result = []
    for c in courses:
        instructor = User.query.get(c.instructor_id)
        result.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "thumbnail": c.thumbnail_url,
            "instructor_id": c.instructor_id,
            "instructor_name": instructor.username if instructor else "Instructor"
        })
    
    return jsonify({
        "success": True,
        "courses": result
    })

@bp.route("/instructor/<int:instructor_id>", methods=["GET"])
def get_instructor(instructor_id):
    from models import User
    instructor = User.query.get_or_404(instructor_id)
    return jsonify({
        "id": instructor.id,
        "username": instructor.username,
    })


@bp.route("/lectures/<int:course_id>", methods=["GET"])
def get_course_lectures(course_id):
    from models import Course, Lecture, Section
    """Return all lectures for a given course_id, grouped by sections"""
    course = Course.query.get_or_404(course_id)
    
    # Get all sections for this course
    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order.asc()).all()
    
    if not sections:
        return jsonify({"success": False, "message": "No sections found for this course"}), 204
    
    # Build response with sections and their lectures
    sections_data = []
    all_lectures = []
    
    for section in sections:
        lectures = Lecture.query.filter_by(section_id=section.id).order_by(Lecture.order.asc()).all()
        
        lectures_data = [{
            "id": l.id,
            "title": l.title,
            "video_id": l.video_id,
            "duration": l.duration,
            "order": l.order,
            "section_id": l.section_id
        } for l in lectures]
        
        sections_data.append({
            "id": section.id,
            "title": section.title,
            "order": section.order,
            "lectures": lectures_data
        })
        
        # Also add to flat list for backward compatibility
        all_lectures.extend(lectures_data)
    
    return jsonify({
        "success": True,
        "sections": sections_data,
        "lectures": all_lectures  # Flat list for backward compatibility
    }), 200


@bp.route("/sections/<int:course_id>", methods=["GET"])
def get_course_sections(course_id):
    from models import Course, Lecture, Section
    """Return all sections with their lectures for a given course"""
    course = Course.query.get_or_404(course_id)
    
    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order.asc()).all()
    
    if not sections:
        return jsonify({"success": True, "sections": []}), 200
    
    sections_data = []
    for section in sections:
        lectures = Lecture.query.filter_by(section_id=section.id).order_by(Lecture.order.asc()).all()
        
        lectures_data = [{
            "id": l.id,
            "title": l.title,
            "video_id": l.video_id,
            "duration": l.duration,
            "order": l.order
        } for l in lectures]
        
        sections_data.append({
            "id": section.id,
            "title": section.title,
            "order": section.order,
            "lectures": lectures_data
        })
    
    return jsonify({
        "success": True,
        "sections": sections_data
    }), 200