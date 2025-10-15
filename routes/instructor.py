import requests
from flask import Blueprint, request, jsonify
from extensions import db   

from .utils import verify_pi_token  # Add this import

from datetime import datetime
import re

bp = Blueprint("instructor", __name__)
import os
# --- Bunny.net configuration ---
BUNNY_API_KEY = os.getenv("BUNNY_API_KEY")
BUNNY_STORAGE_ZONE = "YOUR_STORAGE_ZONE_NAME"  # e.g. 'pi-edu-storage'
BUNNY_UPLOAD_URL = f"https://storage.bunnycdn.com/{BUNNY_STORAGE_ZONE}/"
BUNNY_LIBRARY_URL = "https://video.bunnycdn.com/library"
BUNNY_ACCOUNT_ID = "YOUR_BUNNY_ACCOUNT_ID"  # from Bunny dashboard


# --- Helper: slugify titles ---
def slugify(title):
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


# ==========================================================
#  1️⃣  Become instructor (after payment)
# ==========================================================
@bp.route("/check", methods=["POST"])
def become_instructor():
    from models import User, Instructor
    try:
        data = request.get_json()
        access_token = data.get("accessToken")

        if not access_token:
            return jsonify({"success": False, "error": "Missing access token"}), 400

        # ✅ Verify Pi token and get user data
        user_data = verify_pi_token(access_token)
        if not user_data:
            return jsonify({"success": False, "error": "Invalid Pi token"}), 401
        print(type(user_data))
        # ✅ Find the user in database
        user = User.query.filter_by(username=user_data["username"]).first()
        
        if not user:
            print("not user")
            return jsonify({"success": False, "error": "User not found"}), 404

        # ✅ Check if user already an instructor
        existing_instructor = Instructor.query.filter_by(user_id=user.id).first()
        if existing_instructor:
            return jsonify({
                "success": True,
                "alreadyInstructor": True,
                "message": "User is already an instructor",
                "instructor": {
                    "user_id": user.id,
                    "id": existing_instructor.id,
                    "total_earnings": existing_instructor.total_earnings
                }
            }), 200


        return jsonify({
            "success": True,
            "alreadyInstructor": False,
            "message": "This is User account",
            "user_id": user.id
        }), 201

    except Exception as e:
        print("Error in become_instructor:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================================
#  2️⃣  Create a new course (auto-create Bunny library)
# ==========================================================
@bp.route("/add_course", methods=["POST"])
def add_course():
    from models import User, Instructor, Course
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid token'}), 401
    
    access_token = auth_header.split(' ')[1]  
    print("token: "+access_token)
    title = request.form.get("title")
    description = request.form.get("description", "")
    price_pi = request.form.get("price_pi", 0.0)
    thumbnail = request.files.get("thumbnail")

    if not all([access_token, title, thumbnail]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403
    lacle = str()
    # --- Create Bunny video library for this course ---
    try:
        lib_payload = {"Name": title}
        headers = {"AccessKey": BUNNY_API_KEY, "Content-Type": "application/json"}
        res = requests.post(f"https://api.bunny.net/videolibrary", json=lib_payload, headers=headers)

        if res.status_code not in (200, 201):
            print(res.text)
            return jsonify({"success": False, "error": "Failed to create Bunny library", "details": res.text}), 500

        library_id = res.json().get("Id")
        lacle = res.json().get("ApiKey")
    except Exception as e:
        print("Error creating Bunny library:", e)
        return jsonify({"success": False, "error": f"Library creation failed: {str(e)}"}), 500

    # --- Upload course thumbnail to Bunny storage ---
    try:
        STORAGE_ZONE = os.getenv("STORAGE_ZONE")
        ACCESS_KEY = os.getenv("ACCESS_KEY")
        BUNNY_URL = f'https://storage.bunnycdn.com/{STORAGE_ZONE}/{thumbnail.filename}'
        
        
        headers = {"AccessKey": ACCESS_KEY, "Content-Type": "application/octet-stream"}
        response = requests.put(
            BUNNY_URL,
            headers=headers,
            data=thumbnail.read()
        )
        link = os.getenv("CDN_BASE_URL")
        if response.status_code not in (200, 201):
            return jsonify({"success": False, "error": "Failed to upload thumbnail"}), 500
        thumbnail_url = f"https://{link}/{thumbnail.filename}"
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    # --- Save course ---
    course = Course(
        title=title,
        slug=slugify(title),
        description=description,
        price_pi=price_pi,
        instructor_id=user.id,
        thumbnail_url=thumbnail_url,
        is_published=False,
        created_at=datetime.utcnow(),
        library_id=library_id,
        apikey=lacle
    )
    db.session.add(course)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Course created successfully",
        "course": {
            "id": course.id,
            "title": course.title,
            "library_id": library_id
        }
    }), 201


# ==========================================================
#  3️⃣  Add a lecture (upload video to Bunny storage)
# ==========================================================
@bp.route("/add_lecture", methods=["POST"])
def add_lecture():
    from models import User, Instructor, Course, Lecture, Section
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid token'}), 401
    
    access_token = auth_header.split(' ')[1]  

    section_id = request.form.get("section_id")
    title = request.form.get("title")
    order = request.form.get("order", 0)
    video_file = request.files.get("video")

    if not all([access_token, section_id, title, video_file]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    # Verify Pi token
    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    # Validate section ownership
    section = Section.query.filter_by(id=section_id).first()
    if not section:
        return jsonify({"success": False, "error": "Section not found"}), 404

    course = Course.query.filter_by(id=section.course_id, instructor_id=user.id).first()
    if not course:
        return jsonify({"success": False, "error": "Unauthorized for this section"}), 403

    # --- Upload video to Bunny storage ---
    try:
        LIBRARY_ID = course.library_id
        API_KEY = course.apikey

        # Step 1: Create video object in Bunny
        create_url = f'https://video.bunnycdn.com/library/{LIBRARY_ID}/videos'
        create_response = requests.post(
            create_url,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'AccessKey': API_KEY
            },
            json={'title': title}
        )
        if create_response.status_code not in (200, 201):
            return jsonify({"success": False, "error": "Failed to create video", "details": create_response.text}), 500

        video_data = create_response.json()
        video_id = video_data['guid']

        # Step 2: Upload video content
        upload_url = f'https://video.bunnycdn.com/library/{LIBRARY_ID}/videos/{video_id}'
        upload_response = requests.put(
            upload_url,
            headers={'AccessKey': API_KEY},
            data=video_file.read()
        )

        if upload_response.status_code == 200:
            try:
                bunny_response = upload_response.json()
                duration = bunny_response.get("length", 0)
            except ValueError:
                duration = 0

            # Save lecture under section
            lecture = Lecture(
                title=title,
                video_id=video_id,
                section_id=section_id,
                order=order,
                duration=duration
            )
            db.session.add(lecture)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Lecture added successfully',
                'video_id': video_id,
                'lecture_id': lecture.id
            })
        else:
            # Delete video from Bunny if upload failed
            delete_url = f'https://video.bunnycdn.com/library/{LIBRARY_ID}/videos/{video_id}'
            requests.delete(delete_url, headers={'AccessKey': API_KEY})
            return jsonify({
                'success': False,
                'error': f'Failed to upload video: {upload_response.text}'
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
#  4️⃣  Get instructor dashboard overview
# ==========================================================
@bp.route("/dashboard", methods=["POST"])
def instructor_dashboard():
    from models import User, Instructor, Course
    data = request.get_json()
    access_token = data.get("accessToken")

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    courses = Course.query.filter_by(instructor_id=user.id).all()

    return jsonify({
        "success": True,
        "instructor": {
            "name": user.username,
            "total_earnings": instructor.total_earnings
        },
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "price_pi": c.price_pi,
                "created_at": c.created_at.isoformat(),
                "is_published": c.is_published,
                "thumbnail":c.thumbnail_url
            } for c in courses
        ]
    }), 200

# ==========================================================
#  5️⃣  Edit existing course (title, description, price, thumbnail)
# ==========================================================
@bp.route("/edit_course/<int:course_id>", methods=["POST"])
def edit_course(course_id):
    from models import User, Instructor, Course
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid token'}), 401
    
    access_token = auth_header.split(' ')[1]

    # ✅ Verify instructor via Pi SDK
    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    course = Course.query.filter_by(id=course_id, instructor_id=user.id).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found or unauthorized"}), 404

    # ✅ Get fields
    title = request.form.get("title")
    description = request.form.get("description")
    price_pi = request.form.get("price_pi")
    is_published = request.form.get("is_published")
    thumbnail = request.files.get("thumbnail")

    # ✅ Update text fields
    if title:
        course.title = title
        course.slug = slugify(title)
    if description:
        course.description = description
    if price_pi:
        try:
            course.price_pi = float(price_pi)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid price"}), 400
    print(is_published)
    if is_published is None:
        course.is_published = 0
    elif is_published:
        course.is_published = 1

    # ✅ Optional: Upload new thumbnail if provided
    if thumbnail:
        try:
            STORAGE_ZONE = os.getenv("STORAGE_ZONE")
            ACCESS_KEY =  os.getenv("ACCESS_KEY")
            BUNNY_URL = f'https://storage.bunnycdn.com/{STORAGE_ZONE}/{thumbnail.filename}'

            headers = {"AccessKey": ACCESS_KEY, "Content-Type": "application/octet-stream"}
            response = requests.put(BUNNY_URL, headers=headers, data=thumbnail.read())

            if response.status_code not in (200, 201):
                return jsonify({"success": False, "error": "Failed to upload new thumbnail"}), 500
            link = os.getenv("CDN_BASE_URL")
            thumbnail_url = f"https://{link}/{thumbnail.filename}"
            course.thumbnail_url = thumbnail_url
        except Exception as e:
            return jsonify({"success": False, "error": f"Thumbnail upload failed: {str(e)}"}), 500

    # ✅ Save changes
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Course updated successfully",
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "price_pi": course.price_pi,
            "is_published": course.is_published,
            "thumbnail": course.thumbnail_url
        }
    }), 200

@bp.route("/edit_lecture", methods=["POST"])
def edit_lecture():
    from models import User, Instructor, Course, Lecture
    data = request.get_json()
    access_token = data.get("accessToken")
    lecture_id = data.get("lecture_id")
    new_title = data.get("title")

    if not all([access_token, lecture_id, new_title]):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    lecture = Lecture.query.get(lecture_id)
    if not lecture:
        return jsonify({"success": False, "error": "Lecture not found"}), 404

    course = Course.query.filter_by(id=lecture.course_id, instructor_id=user.id).first()
    if not course:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    lecture.title = new_title
    db.session.commit()

    return jsonify({"success": True, "message": "Lecture title updated successfully"})

@bp.route("/update_lecture_order", methods=["POST"])
def update_lecture_order():
    from models import User, Instructor, Course, Lecture, Section
    data = request.get_json()
    access_token = data.get("accessToken")
    updates = data.get("order_updates")  # list of {lecture_id, new_order}

    if not all([access_token, updates]):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    # Verify Pi token
    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid token"}), 401

    # Find user
    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    # Ensure instructor
    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    # Update lecture order
    for item in updates:
        lecture = Lecture.query.get(item.get("lecture_id"))
        if not lecture:
            continue

        section = Section.query.get(lecture.section_id)
        if not section:
            continue

        course = Course.query.get(section.course_id)
        if not course or course.instructor_id != user.id:
            continue  # ensure this instructor owns the course

        # Update order
        new_order = item.get("new_order")
        if new_order is not None:
            lecture.order = new_order

    db.session.commit()
    return jsonify({"success": True, "message": "Lecture order updated successfully"})

@bp.route("/add_section", methods=["POST"])
def add_section():
    from models import User, Course, Section
    data = request.get_json()
    access_token = data.get("accessToken")
    course_id = data.get("course_id")
    title = data.get("title")
    order = data.get("order", 0)

    if not all([access_token, course_id, title]):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    course = Course.query.filter_by(id=course_id, instructor_id=user.id).first()
    if not course:
        return jsonify({"success": False, "error": "Course not found or unauthorized"}), 403

    section = Section(course_id=course.id, title=title, order=order)
    db.session.add(section)
    db.session.commit()

    return jsonify({
        "success": True,
        "section": {
            "id": section.id,
            "title": section.title,
            "order": section.order
        }
    }), 201


# ====================================
# 2️⃣ Edit a section
# ====================================
@bp.route("/edit_section", methods=["PATCH"])
def edit_section():
    from models import User, Course, Section
    data = request.get_json()
    access_token = data.get("accessToken")
    section_id = data.get("section_id")
    title = data.get("title")
    order = data.get("order")

    if not access_token or not section_id:
        return jsonify({"success": False, "error": "Missing fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    section = Section.query.get(section_id)
    if not section:
        return jsonify({"success": False, "error": "Section not found"}), 404

    course = Course.query.get(section.course_id)
    if course.instructor_id != user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if title:
        section.title = title
    if order is not None:
        section.order = order

    db.session.commit()

    return jsonify({
        "success": True,
        "section": {
            "id": section.id,
            "title": section.title,
            "order": section.order
        }
    }), 200


@bp.route("/update_section_order", methods=["POST"])
def update_section_order():
    from models import User, Instructor, Course, Section
    data = request.get_json()
    access_token = data.get("accessToken")
    updates = data.get("order_updates")  # list of {section_id, new_order}

    if not all([access_token, updates]):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    for item in updates:
        section = Section.query.get(item.get("section_id"))
        if section:
            course = Course.query.filter_by(id=section.course_id, instructor_id=user.id).first()
            if course:
                section.order = item.get("new_order", section.order)

    db.session.commit()

    return jsonify({"success": True, "message": "Section order updated successfully"}), 200


@bp.route("/earnings/<int:user_id>", methods=["GET"])
def get_instructor_earnings(user_id):
    from models import Instructor, Course, Purchase
    instructor = Instructor.query.filter_by(user_id=user_id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Instructor not found"}), 404

    # Get all courses by this instructor
    courses = Course.query.filter_by(instructor_id=instructor.id).all()

    courses_data = []
    

    for course in courses:
        # Get confirmed purchases only
        purchases = Purchase.query.filter_by(course_id=course.id, status="completed").all()
        students_count = len(purchases)
        course_earnings = sum(p.amount_pi for p in purchases if p.amount_pi)

        
        courses_data.append({
            "course_id": course.id,
            "title": course.title,
            "students": students_count,
            "earnings": course_earnings * 0.75
        })

    return jsonify({
        "success": True,
        "instructor_id": instructor.id,
        "total_earnings": instructor.total_earnings,
        "courses": courses_data
    })

@bp.route("/students", methods=["POST"])
def get_instructor_students():
    from models import User,Purchase, Instructor, Course
    data = request.get_json()
    access_token = data.get("accessToken")

    # --- Verify Pi token ---
    user_data = verify_pi_token(access_token)
    if not user_data:
        return jsonify({"success": False, "error": "Invalid Pi token"}), 401

    user = User.query.filter_by(pi_uid=user_data["uid"]).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    instructor = Instructor.query.filter_by(user_id=user.id).first()
    if not instructor:
        return jsonify({"success": False, "error": "Not an instructor"}), 403

    # --- Get instructor courses ---
    courses = Course.query.filter_by(instructor_id=user.id).all()

    total_students = 0
    course_data = []

    for course in courses:
        students_count = (
            Purchase.query.filter_by(course_id=course.id, status="completed").count()
        )
        total_students += students_count
        course_data.append({
            "course_id": course.id,
            "title": course.title,
            "students": students_count
        })

    return jsonify({
        "success": True,
        "total_students": total_students,
        "courses": course_data
    })


