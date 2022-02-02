import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import datetime

dt = datetime.datetime.today()

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    users = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    user_cash = users[0]['cash']
    # find users stocks
    user_data = db.execute(
        "SELECT name, symbol, sum(shares) as sum_of_shares FROM purchase WHERE user_id = ? GROUP BY user_id, name, symbol HAVING sum_of_shares > 0", session["user_id"])
    # Use lookup API to get the current price of each stock
    user_data = [dict(x, **{'price': lookup(x['symbol'])['price']}) for x in user_data]
    # now let's find the total price for each stock
    user_data = [dict(x, **{'total': x['price']*x['sum_of_shares']}) for x in user_data]
    grand_total = user_cash + sum([x['total'] for x in user_data])

    return render_template("index.html", user_cash=user_cash, datas=user_data, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except ValueError:
            return apology("INVALID SHARES")
        # ensure symbol was submitted
        if not symbol:
            return apology("MISSING SYMBOL", 400)
        elif not shares:
            return apology("MISSING SHARES", 400)
        elif lookup(symbol) == None:
            return apology("INVALID SYMBOL", 400)
        elif int(shares) < 1:
            return apology("INVALID SHARE", 400)

        user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        stock_api = lookup(symbol)
        stock_price = stock_api["price"]

        if user_cash[0]["cash"] >= (stock_price * int(shares)):
            total = stock_price * int(shares)
            print(session["user_id"], stock_price, int(shares), total, dt.year, dt.month, dt.day)
            db.execute(
                "INSERT INTO purchase(user_id, symbol, name, price, shares, total, year, month, day) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",









                session["user_id"], stock_api["symbol"], stock_api["name"], stock_api["price"], int(shares), total, dt.year, dt.month, dt.day)
            # then subtract the total from the user
            db.execute("UPDATE users SET cash = ? WHERE id = ?", (user_cash[0]["cash"] - total), session["user_id"])

        else:
            return apology("YOU DO NOT HAVE ENOUGH CASH!", 400)
        flash("Bought!")

    else:
        return render_template("buy.html")

    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    purchases = db.execute("SELECT * FROM purchase WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=purchases)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Ensure Symbol is exists
        symbol = request.form.get("symbol")
        query = lookup(symbol)
        if (query) == None:
            return apology("INVALID SYMBOL")

        return render_template("quoted.html", query=query)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    def checkPass(password):
        flag1 = False
        flag2 = False
        for p in password:
            if p.isdigit():
                flag1 = True
            if p.isalpha():
                flag2 = True

        return flag1 and flag2

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)
        elif not (checkPass(password)):
            return apology("Password must contain atleast 1 letter and 1 number", 400)
        # Ensure password confirmation was submitted
        elif not confirmation:
            return apology("must provide password confimation", 400)

        elif password != confirmation:
            return apology("Passwords do not much")

        # Query database for username if aleardy taken
        rows = db.execute("SELECT username FROM users WHERE username = ?", username)

        # Ensure username exists and password is correct
        if len(rows) > 0:
            return apology("username is taken! please choose another usename.", 400)

        # Remember which user has logged in
        password = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password)
        # Query database for username
        users = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(users) != 1 or not check_password_hash(users[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = users[0]["id"]
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_symbols = db.execute("""SELECT symbol, sum(shares) as sum_of_shares
                                  FROM purchase
                                  WHERE user_id = ?
                                  GROUP BY user_id, symbol
                                  HAVING sum_of_shares > 0;""", session["user_id"])

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("MISSING SYMBOL")

        if not shares:
            return apology("MISSING SHARES")

        try:
            shares = int(shares)
        except ValueError:
            return apology("INVALID SHARES")
        # Check if shares is a positive number
        if not (shares > 0):
            return apology("INVALID SHARES")

        symbols_dict = {data['symbol']: data['sum_of_shares'] for data in user_symbols}

        if shares > symbols_dict[symbol]:
            return apology("TOO MANY SHARES")

        stock_symbol = lookup(symbol)

        # Get current users cash
        userData = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        total = usd(stock_symbol["price"] * int(shares))

        db.execute(
            "INSERT INTO purchase(user_id, symbol, name, price, shares, total, year, month, day) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            session["user_id"], stock_symbol["symbol"], stock_symbol["name"], usd(stock_symbol["price"]), int(shares), total, dt.year, dt.month, dt.day)
        # Update users cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?;",
                   (userData[0]['cash'] + (stock_symbol['price'] * shares)), session["user_id"])
        user_data1 = db.execute(
            "SELECT name, total, symbol, sum(shares) as sum_of_shares FROM purchase WHERE user_id = ? GROUP BY user_id, name, symbol HAVING sum_of_shares > 0", session["user_id"])

        user_cash = (userData[0]['cash'] + (stock_symbol['price'] * shares))
        # grand_total = user_cash + sum([x['total'] for x in user_data1])
        grand_total = user_cash + user_data1[0]["total"]
        flash("Sold!")
        return render_template("index.html", user_cash=user_cash, datas=user_data1, grand_total=grand_total)

        # return redirect("/")

    else:
        return render_template("sell.html", amountsold="56.00")
