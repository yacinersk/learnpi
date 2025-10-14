from flask import Blueprint, request, jsonify, session
from extensions import db   
from functools import wraps
from .utils import verify_pi_token

bp = Blueprint('auth', __name__)



def require_auth(f):
    from models import User
    """Decorator to require Pi authentication via Bearer token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try to get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            access_token = auth_header[7:]
            pi_user = verify_pi_token(access_token)
            
            if pi_user:
                # Get or create user
                user = User.query.filter_by(pi_uid=pi_user["uid"]).first()
                if not user:
                    user = User(username=pi_user["username"], pi_uid=pi_user["uid"])
                    db.session.add(user)
                    db.session.commit()
                
                # Store in request context
                request.current_user = user
                request.current_user_token = access_token
                return f(*args, **kwargs)
        
        # Also check session as fallback
        if "user_id" in session:
            user = User.query.get(session["user_id"])
            if user:
                request.current_user = user
                return f(*args, **kwargs)
        
        return jsonify({"error": "Not authenticated"}), 401
    
    return decorated_function


@bp.route("/login", methods=["POST"])
def pi_login():
    from models import User
    try:
        data = request.get_json(force=True)
        access_token = data.get("accessToken")

        if not access_token:
            return jsonify({"error": "No token provided"}), 400

        pi_user = verify_pi_token(access_token)
        if not pi_user:
            return jsonify({"error": "Invalid or expired Pi token"}), 401

        user = User.query.filter_by(pi_uid=pi_user["uid"]).first()
        if not user:
            user = User(username=pi_user["username"], pi_uid=pi_user["uid"])
            db.session.add(user)
            db.session.commit()

        # Try to save to session (may not work in Pi Browser)
        session['accessToken'] = access_token
        session["user_id"] = user.id
        
        return jsonify({
            "success": True,
            "message": f"Welcome, {user.username}",
            "user": {"id": user.id, "username": user.username}
        })
    
    except Exception as e:
        print(f"[pi_login] Error: {e}")
        return jsonify({"error": "Server error. Check backend logs."}), 500


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out"})


@bp.route("/me", methods=["GET"])
@require_auth
def me():
    user = request.current_user
    print(request.current_user_token)
    
    print("user: ",user)
    return jsonify({
        "id": user.id,
        "username": user.username,
        "pi_uid": user.pi_uid,
        "accessToken": request.current_user_token
    })