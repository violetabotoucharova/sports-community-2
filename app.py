import os
import re
import secrets
from datetime import datetime

from flask import Flask, request, jsonify, redirect, send_from_directory
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from models import db, User, Sport, Activity

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
PRIVATE_DIR = os.path.join(BASE_DIR, "private")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="public", static_url_path="")

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "data.db")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
db.init_app(app)
login_manager = LoginManager(app)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}
STARTER_SPORTS = ["Football", "Basketball", "Tennis", "Running", "Cycling",
                  "Swimming", "Volleyball", "Yoga", "Hiking", "Padel"]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify(error="Not logged in"), 401
    return redirect("/signin.html")


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="File is too large (max 2 MB)."), 413


def user_to_dict(u, full=False):
    d = {
        "id": u.id,
        "username": u.username,
        "avatar_url": f"/uploads/{u.avatar_filename}" if u.avatar_filename else None,
    }
    if full:
        d["city"] = u.city or ""
        d["bio"] = u.bio or ""
        d["sports"] = [{"id": s.id, "name": s.name} for s in u.sports]
    return d


def activity_to_dict(a, detail=False):
    me_id = current_user.id
    d = {
        "id": a.id,
        "title": a.title,
        "sport": {"id": a.sport.id, "name": a.sport.name},
        "location": a.location,
        "starts_at": a.starts_at.isoformat(),
        "max_participants": a.max_participants,
        "participants_count": len(a.participants),
        "joined": any(p.id == me_id for p in a.participants),
        "creator": user_to_dict(a.creator),
    }
    if detail:
        d["description"] = a.description or ""
        d["participants"] = [user_to_dict(p) for p in a.participants]
        d["is_creator"] = a.creator_id == me_id
    return d

@app.route("/")
def home():
    return send_from_directory(PUBLIC_DIR, "index.html")

PRIVATE_PAGES = ["activities", "create-activity", "activity", "profile", "edit-profile"]


def make_page(name):
    @login_required
    def page():
        return send_from_directory(PRIVATE_DIR, name + ".html")
    return page


for _name in PRIVATE_PAGES:
    app.add_url_rule(f"/{_name}.html", endpoint=f"page_{_name}", view_func=make_page(_name))


@app.route("/uploads/<path:filename>")
@login_required
def uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not EMAIL_RE.match(email):
        return jsonify(error="Please enter a valid email."), 400
    if not (3 <= len(username) <= 30):
        return jsonify(error="Username must be 3-30 characters."), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with this email already exists."), 409
    if User.query.filter_by(username=username).first():
        return jsonify(error="This username is taken."), 409

    user = User(email=email, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify(message="Account created."), 201


@app.route("/api/signin", methods=["POST"])
def signin():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify(error="Invalid email or password."), 401
    login_user(user)
    return jsonify(message="Signed in."), 200


@app.route("/api/signout", methods=["POST"])
@login_required
def signout():
    logout_user()
    return jsonify(message="Signed out."), 200


@app.route("/api/me")
def me():
    if current_user.is_authenticated:
        return jsonify(loggedIn=True, id=current_user.id, username=current_user.username)
    return jsonify(loggedIn=False)

@app.route("/api/sports")
@login_required
def sports():
    return jsonify([{"id": s.id, "name": s.name} for s in Sport.query.order_by(Sport.name)])


@app.route("/api/profile/<username>")
@login_required
def get_profile(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        return jsonify(error="User not found."), 404
    d = user_to_dict(user, full=True)
    d["is_me"] = user.id == current_user.id
    return jsonify(d)


@app.route("/api/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    bio = (data.get("bio") or "").strip()
    sport_ids = data.get("sport_ids") or []

    if len(city) > 80:
        return jsonify(error="City is too long (max 80)."), 400
    if len(bio) > 500:
        return jsonify(error="Bio is too long (max 500)."), 400
    if not isinstance(sport_ids, list) or not all(isinstance(i, int) for i in sport_ids):
        return jsonify(error="Invalid sports list."), 400

    user = current_user._get_current_object()
    user.city = city
    user.bio = bio
    user.sports = Sport.query.filter(Sport.id.in_(sport_ids)).all()
    db.session.commit()
    return jsonify(message="Profile saved.")


@app.route("/api/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    file = request.files.get("avatar")
    if file is None or file.filename == "":
        return jsonify(error="No file selected."), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify(error="Only png, jpg and webp images are allowed."), 400

    filename = secrets.token_hex(16) + "." + ext
    file.save(os.path.join(UPLOAD_DIR, filename))

    user = current_user._get_current_object()
    if user.avatar_filename:
        old = os.path.join(UPLOAD_DIR, user.avatar_filename)
        if os.path.exists(old):
            os.remove(old)
    user.avatar_filename = filename
    db.session.commit()
    return jsonify(avatar_url=f"/uploads/{filename}")

@app.route("/api/activities", methods=["GET"])
@login_required
def list_activities():
    q = Activity.query.filter(Activity.starts_at >= datetime.now())
    sport_id = request.args.get("sport", type=int)
    if sport_id:
        q = q.filter_by(sport_id=sport_id)
    return jsonify([activity_to_dict(a) for a in q.order_by(Activity.starts_at).all()])


@app.route("/api/activities", methods=["POST"])
@login_required
def create_activity():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    location = (data.get("location") or "").strip()

    if not (3 <= len(title) <= 100):
        return jsonify(error="Title must be 3-100 characters."), 400
    if len(description) > 1000:
        return jsonify(error="Description is too long (max 1000)."), 400
    if not (2 <= len(location) <= 120):
        return jsonify(error="Location must be 2-120 characters."), 400

    sport = db.session.get(Sport, data.get("sport_id")) if isinstance(data.get("sport_id"), int) else None
    if sport is None:
        return jsonify(error="Please choose a sport."), 400

    try:
        starts_at = datetime.strptime(data.get("starts_at") or "", "%Y-%m-%dT%H:%M")
    except ValueError:
        return jsonify(error="Please choose a valid date and time."), 400
    if starts_at < datetime.now():
        return jsonify(error="The start time must be in the future."), 400

    max_p = data.get("max_participants")
    if not isinstance(max_p, int) or not (2 <= max_p <= 100):
        return jsonify(error="Max participants must be between 2 and 100."), 400

    user = current_user._get_current_object()
    activity = Activity(title=title, description=description, location=location,
                        starts_at=starts_at, max_participants=max_p,
                        sport_id=sport.id, creator_id=user.id)
    activity.participants.append(user)
    db.session.add(activity)
    db.session.commit()
    return jsonify(id=activity.id), 201


@app.route("/api/activities/<int:activity_id>")
@login_required
def get_activity(activity_id):
    a = db.session.get(Activity, activity_id)
    if a is None:
        return jsonify(error="Activity not found."), 404
    return jsonify(activity_to_dict(a, detail=True))


@app.route("/api/activities/<int:activity_id>/join", methods=["POST"])
@login_required
def join_activity(activity_id):
    a = db.session.get(Activity, activity_id)
    if a is None:
        return jsonify(error="Activity not found."), 404
    user = current_user._get_current_object()
    if a.starts_at < datetime.now():
        return jsonify(error="This activity has already started."), 400
    if any(p.id == user.id for p in a.participants):
        return jsonify(error="You already joined this activity."), 409
    if len(a.participants) >= a.max_participants:
        return jsonify(error="This activity is full."), 409
    a.participants.append(user)
    db.session.commit()
    return jsonify(message="Joined.")


@app.route("/api/activities/<int:activity_id>/leave", methods=["POST"])
@login_required
def leave_activity(activity_id):
    a = db.session.get(Activity, activity_id)
    if a is None:
        return jsonify(error="Activity not found."), 404
    user = current_user._get_current_object()
    if a.creator_id == user.id:
        return jsonify(error="The creator can't leave. Delete the activity instead."), 400
    a.participants = [p for p in a.participants if p.id != user.id]
    db.session.commit()
    return jsonify(message="Left.")


@app.route("/api/activities/<int:activity_id>", methods=["DELETE"])
@login_required
def delete_activity(activity_id):
    a = db.session.get(Activity, activity_id)
    if a is None:
        return jsonify(error="Activity not found."), 404
    if a.creator_id != current_user.id:
        return jsonify(error="Only the creator can delete this activity."), 403
    db.session.delete(a)
    db.session.commit()
    return jsonify(message="Deleted.")


def seed_sports():
    for name in STARTER_SPORTS:
        if not Sport.query.filter_by(name=name).first():
            db.session.add(Sport(name=name))
    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_sports()
    app.run(debug=True, port=5001)
