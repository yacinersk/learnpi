from datetime import datetime
from extensions import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Core Pi Network fields
    pi_uid = db.Column(db.String(120), unique=True, index=True, nullable=False)  # UID from Pi API
    username = db.Column(db.String(120), unique=True, index=True, nullable=False)
    
    role = db.Column(db.String(20), default='student')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    courses = db.relationship('Course', backref='instructor', lazy=True)
    purchases = db.relationship('Purchase', backref='buyer', lazy=True)
    progress = db.relationship('Progress', back_populates='user', cascade='all, delete-orphan')
    certificates = db.relationship('Certificate', backref='user', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "pi_uid": self.pi_uid,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<User {self.username}>"

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    slug = db.Column(db.String(250), unique=True, index=True)
    description = db.Column(db.Text)
    price_pi = db.Column(db.Float, default=0.0)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_course_instructor_id'), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    library_id = db.Column(db.String(250))
    apikey = db.Column(db.String(250))
    
    sections = db.relationship('Section', backref='course', lazy=True, order_by="Section.order")

class Lecture(db.Model):
    __tablename__ = 'lectures'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id', name='fk_lecture_section_id'), nullable=True)
    title = db.Column(db.String(250), nullable=False)
    video_id = db.Column(db.String(250))
    duration = db.Column(db.Integer, default=0)
    order = db.Column(db.Integer, default=0)

class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_purchase_user_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', name='fk_purchase_course_id'), nullable=False)
    amount_pi = db.Column(db.Float)
    pi_tx_id = db.Column(db.String(250), nullable=True)
    status = db.Column(db.String(30), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)

class Progress(db.Model):
    __tablename__ = 'progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_progress_user_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', name='fk_progress_course_id'), nullable=False)
    lecture_id = db.Column(db.Integer, db.ForeignKey('lectures.id', name='fk_progress_lecture_id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship('User', back_populates='progress')

class Section(db.Model):
    __tablename__ = 'sections'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    order = db.Column(db.Integer, default=0)

    lectures = db.relationship('Lecture', backref='section', lazy=True, order_by="Lecture.order")

class Certificate(db.Model):
    __tablename__ = 'certificates'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_certificate_user_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', name='fk_certificate_course_id'), nullable=False)
    pdf_url = db.Column(db.String(500))
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

class Instructor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    total_earnings = db.Column(db.Float, default=0)

    user = db.relationship('User', backref='instructor', uselist=False)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1–5 stars
    review = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
