import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # username of logged in user
    results = db.execute("SELECT * FROM transactions WHERE user = :user", user = session["user_id"])

    # current cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])

    stockTotal = 0
    # Obtain purchase history, check the symbol's stock price, number of shares then display it
    for result in results:
        symbol = str(result['symbol'])
        shares = int(result['shares'])
        quote = lookup(symbol)
        currentPrice = float(quote['price'])
        name = str(quote['name'])
        result['name'] = name
        result['price'] = currentPrice
        totalValue = shares * currentPrice
        result['totalPrice'] = totalValue
        stockTotal += totalValue

    # Calculate the stock value + their current price
    realTotal = cash[0]['cash'] + stockTotal
    return render_template("index.html",results = results,cash=cash[0]['cash'], realTotal = realTotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

     # user reached route via post
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # check for valid symbol
        if quote == None:
            return apology("symbol invalid", 400)

        # check for positive shares
        shares = int(request.form.get("shares"))
        # shares.isdigit()
        if not int(shares) > 0:
            return apology("share must be 1 or bigger", 400)

        # Obtain data of the user from the database
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # Amount of money
        cashBalance = rows[0]["cash"]
        sharePrice = quote["price"]

        total = sharePrice * shares

        # Not enough money
        if cashBalance < total:
            return apology("Not enough money")

        # update user data and transaction history
        db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=total, user_id=session["user_id"])
        db.execute("INSERT INTO transactions (user, symbol, shares, price) VALUES(:user, :symbol, :shares, :price)", user=session["user_id"], symbol=request.form.get("symbol"), shares=shares, price=sharePrice)

        flash("Bought shares good job!")

        # redirect
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    myData = db.execute("SELECT symbol, shares, history, price FROM transactions WHERE user = :user ", user = session['user_id'])
    return render_template("history.html", myData = myData)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # user reached route via post
    if request.method == "POST":

        # lookup function for symbol
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        # if invalid symbol
        if quote == None:
            return apology("invalid stock", 400)
        else:
            return render_template("quoted.html", name = quote['name'], symbol = quote['symbol'], price = quote['price'])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Make sure username is ok
        if not request.form.get("username"):
            return apology("username required!", 400)

        # Make sure password is ok
        elif not request.form.get("password"):
            return apology("password required!", 400)

        # Make sure confirmation and password match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords are not matching!", 400)

        # hash the password and insert user into the database
        hashPass = generate_password_hash(request.form.get("password"))
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=hashPass)

        # Check for duplicate username
        if not result:
            return apology("already got that username", 400)

        session["user_id"] = result

        # redirect user to home
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    results = db.execute("SELECT * FROM transactions WHERE user = :user",user = session["user_id"])
    if(request.method == "POST"):
        # Obtain data from html page
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Check if all completed
        if not shares:
            return apology("Not filled in shares")
        if not symbol:
            return apology("Not filled in symbol")
        shares = int(shares)
        symbol = str(symbol)

        # Current price and value
        quote = lookup(symbol)
        price = quote['price']
        totalValue = float(price) * int(shares)

        # Check if shares are enough to sell
        for data in results:
            if shares > data['shares']:
                return apology("Shares not enough")

        # Updating amount of shares
        update = db.execute("UPDATE transactions SET shares = shares - :shares WHERE user = :user AND symbol = :symbol",shares = shares,user = session['user_id'],symbol = symbol)

        # Updating cash amount
        updateCash = db.execute("UPDATE users SET cash = cash + :totalValue WHERE id = :id",totalValue = totalValue, id = session['user_id'])
        selectShares = db.execute("SELECT * from transactions WHERE user = :user AND shares = 0",user = session['user_id'])

        # No more shares then delete it
        for data in selectShares:
            if data['shares'] == 0:
                deleteShares = db.execute("DELETE from transactions WHERE user = :user AND shares = 0", user = session['user_id'])
        return redirect("/")
    else:
        # Get rid of duplicate and display responsive symbol input fields
        results = db.execute("SELECT * FROM transactions WHERE user = :user",user = session["user_id"])
        ending = []
        for data in results:
            symbols = str(data['symbol'])
            if symbols not in ending:
                ending.append(symbols)
        return render_template("sell.html", ending = ending)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
