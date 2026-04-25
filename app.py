from flask import Flask, render_template, request, redirect, session, Response
import sqlite3
import os
import bcrypt
import razorpay

app = Flask(__name__)
app.secret_key = "secret"


# ---------- RAZORPAY CLIENT ----------
client = razorpay.Client(auth=("rzp_test_ShpURXg9OjWgyg", "MXYWTfa0IcMfypb8BRMI8oxw"))
# ⚠️ replace with your real keys


# ---------- DATABASE ----------
if not os.path.exists("database.db"):
    conn = sqlite3.connect("database.db")
    conn.execute("CREATE TABLE users (username TEXT UNIQUE, password BLOB)")
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, course TEXT, fees INTEGER, paid INTEGER)")
    conn.commit()
    conn.close()


def connect_db():
    return sqlite3.connect("database.db")


# ---------- HOME ----------
@app.route("/")
def home():
    return render_template("index.html")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        conn = connect_db()
        data = conn.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()

        if data:
            stored_password = data[1]

            if isinstance(stored_password, str):
                stored_password = stored_password.encode("utf-8")

            try:
                if bcrypt.checkpw(pwd.encode("utf-8"), stored_password):
                    session["user"] = user
                    return redirect("/dashboard")
            except:
                pass

            try:
                if stored_password.decode("utf-8") == pwd:
                    session["user"] = user
                    return redirect("/dashboard")
            except:
                pass

    return render_template("login.html")


# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt())

        conn = connect_db()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, hashed))
        conn.commit()

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


# ---------- ADD STUDENT ----------
@app.route("/add", methods=["GET", "POST"])
def add_student():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        course = request.form["course"]
        total = int(request.form["total"])
        paid = int(request.form["paid"])

        conn = connect_db()
        conn.execute(
            "INSERT INTO students (name, course, fees, paid) VALUES (?, ?, ?, ?)",
            (name, course, total, paid)
        )
        conn.commit()

        return redirect("/dashboard")

    return render_template("add_student.html")


# ---------- PAYMENT ----------
@app.route("/pay/<int:id>")
def pay(id):
    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()

    remaining = student[3] - student[4]
    amount = remaining * 100  # paise

    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return render_template("payment.html", order=order, student=student, key="YOUR_KEY_ID")


# ---------- PAYMENT SUCCESS ----------
@app.route("/success/<int:id>", methods=["POST"])
def success(id):
    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()

    remaining = student[3] - student[4]

    conn.execute("UPDATE students SET paid = paid + ? WHERE id=?", (remaining, id))
    conn.commit()

    return redirect("/dashboard")


if __name__ == "__main__":
    app.run(debug=True)
