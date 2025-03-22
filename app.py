from flask import Flask, flash, redirect, render_template, request, session
import requests
import os
import datetime
from cs50 import SQL
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from calc import calculate_footprint, predict_future, score_reduction, find_best_tip

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///auth.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def home():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
@login_required
def calculate():
    current_footprint, contributions = calculate_footprint(request.form)
    
    now = datetime.datetime.now()
    current_date = now.date()  
    current_time = now.time()  
    db.execute(
        "INSERT INTO history(user_id, history_fprint, date, time) VALUES(?, ?, ?, ?)",
        session["user_id"], current_footprint, current_date, current_time
    )
    future_footprint = predict_future(current_footprint)
    scenario_data = dict(request.form)
    scenario_data["miles"] = str(float(request.form.get("miles", 0)) * 0.5)
    scenario_footprint, _ = calculate_footprint(scenario_data)
    scenario_future = predict_future(scenario_footprint)
    score = score_reduction(current_footprint, request.form, contributions)
    tip = find_best_tip(contributions, request.form.get("location", "us").upper(), request.form.get("vehicle_type", "petrol"))
    return render_template("index.html", 
                          current=current_footprint, 
                          future=future_footprint, 
                          scenario=scenario_future, 
                          score=score, 
                          tip=tip,
                          calculated=True,
                          original_score=score)

@app.route("/whatif", methods=["POST"])
@login_required
def whatif():
    original_current = float(request.form.get("original_current", 0))
    original_score = int(request.form.get("original_score", 0))
    whatif_footprint, contributions = calculate_footprint(request.form)
    whatif_future = predict_future(whatif_footprint)
    scenario_data = dict(request.form)
    scenario_data["miles"] = str(float(request.form.get("miles", 0)) * 0.5)
    whatif_scenario, _ = calculate_footprint(scenario_data)
    whatif_score = score_reduction(whatif_footprint, request.form, contributions)
    tip = find_best_tip(contributions, request.form.get("location", "us").upper(), request.form.get("vehicle_type", "petrol"))
    
    return render_template("index.html",
                          current=original_current,
                          future=predict_future(original_current),
                          scenario=predict_future(float(request.form.get("original_scenario", original_current))),
                          score=original_score,
                          tip=tip,
                          calculated=True,
                          original_score=original_score,
                          whatif_current=whatif_footprint,
                          whatif_future=whatif_future,
                          whatif_score=whatif_score)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")
    
@app.route("/logout")
def logout():
    """Log user out"""

    session.clear()

    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not name:
            return apology("Please enter a name")
        if not password:
            return apology("Please enter a suitable password")
        if password != confirmation:
            return apology("Passwords don't match")
        hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", name, hash)
        except:
            return apology("Name already taken")
        rows = db.execute("SELECT * FROM users WHERE username = ?", name)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("register.html")
    
@app.route("/history")
@login_required
def history():

    history_data = db.execute(
        "SELECT history_fprint, date, time FROM history WHERE user_id = ? ORDER BY date ASC, time ASC",
        session["user_id"]
    )
    
    footprints = [row["history_fprint"] for row in history_data]
    timestamps = [f"{row['date']} {row['time']}" for row in history_data] 
    return render_template("history.html", footprints=footprints, timestamps=timestamps)

if __name__ == "__main__":
    app.run(debug=True)