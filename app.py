from flask import Flask, render_template, request, redirect, session, Response, abort
import sqlite3
import os
import bcrypt
import razorpay

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_change_me")


# ---------- RAZORPAY (USE ENV VARS) ----------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

# Fallback (only for quick local testing – NOT recommended for production)
if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    RAZORPAY_KEY_ID = "rzp_test_ShpURXg9OjWgyg"
    RAZORPAY_KEY_SECRET = "MXYWTfa0IcMfypb8BRMI8oxw"

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# ---------- DATABASE ----------
DB_PATH = "database.db"

def connect_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = connect_db()
    conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT UNIQUE, password BLOB)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            course TEXT,
            fees INTEGER,
            paid INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ---------- HOME ----------
@app.route("/")
def home():
    return render_template("index.html")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")

        conn = connect_db()
        data = conn.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
        conn.close()

        if data:
            stored = data[1]
            if isinstance(stored, str):
                stored = stored.encode("utf-8")

            try:
                if bcrypt.checkpw(pwd.encode("utf-8"), stored):
                    session["user"] = user
                    return redirect("/dashboard")
            except:
                pass

            # fallback for old plain text
            try:
                if stored.decode("utf-8") == pwd:
                    session["user"] = user
                    return redirect("/dashboard")
            except:
                pass

    return render_template("login.html")


# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")

        hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt())

        conn = connect_db()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, hashed))
            conn.commit()
        except:
            pass
        conn.close()

        return redirect("/login")

    return render_template("signup.html")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()
    data = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    total_students = len(data)
    total_fees = sum([row[3] for row in data]) if data else 0
    total_paid = sum([row[4] for row in data]) if data else 0
    total_remaining = total_fees - total_paid

    names = [row[1] for row in data]
    paid = [row[4] for row in data]

    return render_template(
        "dashboard.html",
        data=data,
        total_students=total_students,
        total_fees=total_fees,
        total_paid=total_paid,
        total_remaining=total_remaining,
        names=names,
        paid=paid
    )


# ---------- ADD ----------
@app.route("/add", methods=["GET", "POST"])
def add_student():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form.get("name")
        course = request.form.get("course")
        total = int(request.form.get("total", 0))
        paid = int(request.form.get("paid", 0))

        conn = connect_db()
        conn.execute(
            "INSERT INTO students (name, course, fees, paid) VALUES (?, ?, ?, ?)",
            (name, course, total, paid)
        )
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_student.html")


# ---------- DELETE ----------
@app.route("/delete/<int:id>")
def delete_student(id):
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()
    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()

    if request.method == "POST":
        name = request.form.get("name")
        course = request.form.get("course")
        total = int(request.form.get("total", 0))
        paid = int(request.form.get("paid", 0))

        conn.execute(
            "UPDATE students SET name=?, course=?, fees=?, paid=? WHERE id=?",
            (name, course, total, paid, id)
        )
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    conn.close()

    if not student:
        abort(404)

    return render_template("edit_student.html", student=student)


# ---------- PAYMENT ----------
@app.route("/pay/<int:id>")
def pay(id):
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    conn.close()

    if not student:
        abort(404)

    remaining = max(0, student[3] - student[4])
    if remaining == 0:
        return redirect("/dashboard")

    amount = remaining * 100  # paise

    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return render_template("payment.html", order=order, student=student, key=RAZORPAY_KEY_ID)


# ---------- SUCCESS ----------
@app.route("/success/<int:id>", methods=["POST"])
def success(id):
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()

    if not student:
        conn.close()
        abort(404)

    remaining = max(0, student[3] - student[4])

    conn.execute("UPDATE students SET paid = paid + ? WHERE id=?", (remaining, id))
    conn.commit()
    conn.close()

    return redirect("/dashboard")


if __name__ == "__main__":
    app.run(debug=True)
