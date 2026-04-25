from flask import Flask, render_template, request, redirect, session, Response
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret"


# ---------- DATABASE AUTO CREATE ----------
if not os.path.exists("database.db"):
    conn = sqlite3.connect("database.db")
    conn.execute("CREATE TABLE users (username TEXT, password TEXT)")
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

        if data and data[1] == pwd:
            session["user"] = user
            return redirect("/dashboard")

    return render_template("login.html")


# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        conn = connect_db()
        conn.execute("INSERT INTO users VALUES (?, ?)", (user, pwd))
        conn.commit()

        return redirect("/login")

    return render_template("signup.html")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- DASHBOARD ----------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()

    search = request.form.get("search", "")
    filter_type = request.form.get("filter", "all")

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE ? OR course LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if filter_type == "paid":
        query += " AND paid >= fees"
    elif filter_type == "pending":
        query += " AND paid < fees"

    data = conn.execute(query, params).fetchall()

    total_students = len(data)
    total_fees = sum([row[3] for row in data]) if data else 0
    total_paid = sum([row[4] for row in data]) if data else 0
    total_remaining = total_fees - total_paid

    pending_count = len([row for row in data if row[4] < row[3]])

    names = [row[1] for row in data]
    paid = [row[4] for row in data]

    return render_template(
        "dashboard.html",
        data=data,
        total_students=total_students,
        total_fees=total_fees,
        total_paid=total_paid,
        total_remaining=total_remaining,
        pending_count=pending_count,
        names=names,
        paid=paid,
        search_query=search,
        filter_type=filter_type
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


# ---------- DELETE ----------
@app.route("/delete/<int:id>")
def delete_student(id):
    conn = connect_db()
    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    return redirect("/dashboard")


# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    conn = connect_db()

    if request.method == "POST":
        name = request.form["name"]
        course = request.form["course"]
        total = int(request.form["total"])
        paid = int(request.form["paid"])

        conn.execute(
            "UPDATE students SET name=?, course=?, fees=?, paid=? WHERE id=?",
            (name, course, total, paid, id)
        )
        conn.commit()

        return redirect("/dashboard")

    student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
    return render_template("edit_student.html", student=student)


# ---------- EXPORT ----------
@app.route("/export")
def export():
    if "user" not in session:
        return redirect("/login")

    conn = connect_db()
    data = conn.execute("SELECT * FROM students").fetchall()

    def generate():
        yield "Name,Course,Total,Paid,Remaining\n"
        for row in data:
            remaining = row[3] - row[4]
            yield f"{row[1]},{row[2]},{row[3]},{row[4]},{remaining}\n"

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=students.csv"})


if __name__ == "__main__":
    app.run(debug=True)
