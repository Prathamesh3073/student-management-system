from flask import Flask, render_template, request, redirect, session, Response
import sqlite3
import os
import bcrypt
import razorpay
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

app = Flask(__name__)
app.secret_key = "secret"


# ---------- RAZORPAY ----------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    RAZORPAY_KEY_ID = "rzp_test_xxx"
    RAZORPAY_KEY_SECRET = "xxx"

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# ---------- DATABASE ----------
def connect_db():
    return sqlite3.connect("database.db")


def init_db():
    conn = connect_db()
    conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password BLOB)")
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
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        conn = connect_db()
        data = conn.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
        conn.close()

        if data:
            stored = data[1]
            if isinstance(stored, str):
                stored = stored.encode()

            if bcrypt.checkpw(pwd.encode(), stored):
                session["user"] = user
                return redirect("/dashboard")

    return render_template("login.html")


# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt())

        conn = connect_db()
        conn.execute("INSERT INTO users VALUES (?,?)", (user, hashed))
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")


# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()
    data = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    return render_template("dashboard.html", data=data)


# ---------- ADD ----------
@app.route("/add", methods=["GET","POST"])
def add():
    if request.method == "POST":
        name = request.form["name"]
        course = request.form["course"]
        total = int(request.form["total"])
        paid = int(request.form["paid"])

        conn = connect_db()
        conn.execute("INSERT INTO students (name,course,fees,paid) VALUES (?,?,?,?)",
                     (name,course,total,paid))
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_student.html")


# ---------- DELETE ----------
@app.route("/delete/<int:id>")
def delete(id):
    conn = connect_db()
    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")


# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    conn = connect_db()

    if request.method == "POST":
        name = request.form["name"]
        course = request.form["course"]
        total = int(request.form["total"])
        paid = int(request.form["paid"])

        conn.execute("UPDATE students SET name=?,course=?,fees=?,paid=? WHERE id=?",
                     (name,course,total,paid,id))
        conn.commit()
        conn.close()
        return redirect("/dashboard")

    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    conn.close()

    if not student:
        return "Student not found"

    return render_template("edit_student.html", student=student)


# ---------- PAYMENT ----------
@app.route("/pay/<int:id>")
def pay(id):
    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    conn.close()

    if not student:
        return "Student not found"

    remaining = student[3] - student[4]
    if remaining <= 0:
        return redirect("/dashboard")

    try:
        order = client.order.create({
            "amount": remaining * 100,
            "currency": "INR",
            "payment_capture": 1
        })
    except Exception as e:
        return f"Payment Error: {str(e)}"

    return render_template("payment.html", order=order, student=student, key=RAZORPAY_KEY_ID)


# ---------- SUCCESS ----------
@app.route("/success/<int:id>", methods=["POST"])
def success(id):
    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()

    if student:
        remaining = student[3] - student[4]
        conn.execute("UPDATE students SET paid = paid + ? WHERE id=?", (remaining,id))
        conn.commit()

    conn.close()
    return redirect("/dashboard")


# ---------- INVOICE ----------
@app.route("/invoice/<int:id>")
def invoice(id):
    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    conn.close()

    if not student:
        return "Student not found"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    content = [
        Paragraph("EduTrack Invoice", styles["Title"]),
        Paragraph(f"Name: {student[1]}", styles["Normal"]),
        Paragraph(f"Course: {student[2]}", styles["Normal"]),
        Paragraph(f"Total: {student[3]}", styles["Normal"]),
        Paragraph(f"Paid: {student[4]}", styles["Normal"]),
    ]

    doc.build(content)
    buffer.seek(0)

    return Response(buffer, mimetype="application/pdf",
                    headers={"Content-Disposition":"attachment;filename=invoice.pdf"})


if __name__ == "__main__":
    app.run(debug=True)
