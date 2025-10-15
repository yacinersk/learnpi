from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_session import Session


from extensions import db

migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # --- Secret & session config ---
    app.config["SECRET_KEY"] = "super-secret-key"
    
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_COOKIE_SECURE"] = True  # True only with HTTPS

    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_NAME"] = "my_session"

    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_USE_SIGNER"] = True
    app.config["SESSION_FILE_DIR"] = "./flask_session"

    app.config["SESSION_KEY_PREFIX"] = "session:"
    app.config["SESSION_SERIALIZATION_FORMAT"] = "json"
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    migrate.init_app(app, db)

    # from models import User, Course, Lecture, Purchase, Progress, Certificate
    from routes.auth import bp as auth_bp
    from routes.courses import bp as courses_bp
    from routes.payments import bp as payments_bp
    from routes.progress import bp as progress_bp
    from routes.certificates import bp as certificates_bp
    from routes.instructor import bp as instructor_bp
    from routes.ratings import bp as ratings_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(courses_bp, url_prefix='/api/courses')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(progress_bp, url_prefix='/api/progress')
    app.register_blueprint(certificates_bp, url_prefix='/api/certificates')
    app.register_blueprint(instructor_bp, url_prefix='/api/instructor')
    app.register_blueprint(ratings_bp, url_prefix='/api/ratings')
    

    # Serve your frontend
    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/login')
    def auth_page():
        return render_template('login.html')

    @app.route('/student-dashboard')
    def student_dashboard():
        return render_template('studentdashboard.html')

    @app.route('/course/<int:course_id>')
    def course_details(course_id):
        return render_template('details.html', course_id=course_id)

    @app.route('/video/<int:course_id>')
    def video_player(course_id):
        return render_template('video.html', course_id=course_id)
    
    @app.route('/instructor-board')
    def dash():
        return render_template('instructor.html')
    
    @app.route('/become')
    def become():
        return render_template('become.html')
    
    @app.route('/validation-key.txt')
    def validation():
        return "550f621f9c2dee7dd2a7f98a3657cbc4b8d49879918e98daa3e89d05e2598a475fdbeaac5227d61c5afb2ff5ac0ce0e5c7855db65f4d5efaf6e3d15e3c5071c5"
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
