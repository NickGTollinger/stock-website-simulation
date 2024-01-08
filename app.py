import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
    ownedStocks = db.execute("SELECT stockSymbol, SUM(shares) AS share_sum FROM purchase_history WHERE user_id = ? GROUP BY stockSymbol HAVING shares > 0", session["user_id"])
    stock_value = 0
    grand_total = 0
    for stock in ownedStocks:

        stockInfo = lookup(stock["stockSymbol"])
        priceTemp = float(stockInfo["price"])
        stock["price"] = usd(stockInfo["price"])
        stock_value += float(priceTemp) * int(stock["share_sum"])
        grand_total += stock_value

    grand_total += cash
    return render_template("index.html", ownedStocks = ownedStocks, stock_value = usd(stock_value), cash = usd(cash), grand_total = usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        if len(symbol) == 0:
            return apology("You left the stock field blank, please enter a stock symbol")

        if lookup(symbol) == None:
            return apology("The stock symbol you entered does not exist, please enter a valid one")

        shares = request.form.get("shares")
        if shares == '' or shares.isdigit() == False:
            return apology("Please enter a value of 1 or more in the shares field")
        shares = int(shares)

        user_id = session["user_id"]
        userCash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
        stockInfo = lookup(symbol)
        price = (stockInfo["price"])
        cost = float(price) * int(shares)

        if cost > userCash:
            return apology("Sorry, you do not currently have enough funds to buy this amount of shares")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", userCash - cost, user_id)
        db.execute("INSERT INTO purchase_history (user_id, stockSymbol, shares, price_per_share, cost) VALUES(?, ?, ?, ?, ?)", user_id, symbol, shares, price, cost)
        return redirect("/")
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    purchaseInfo = db.execute("SELECT stockSymbol, shares, cost, timestamp FROM purchase_history WHERE user_id = ? ORDER BY timestamp", session["user_id"])
    cost = usd(purchaseInfo[0]["cost"])
    return render_template("history.html", purchaseInfo = purchaseInfo, cost = cost)

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = request.form.get("symbol")
        if symbol == '':
            return apology("Please enter a valid stock symbol in the Stock field")
        stockInfo = lookup(symbol)
        if stockInfo == None:
            return apology("Please enter a valid stock symbol in the Stock field")
        price = stockInfo["price"]
        return render_template("quoted.html", stockInfo = stockInfo, price = usd(price))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        #Store username, password, confirmation, and password hash in variables
        username = request.form.get("username")
        password = request.form.get("password")
        confirmationPassword = request.form.get("confirmation")
        passwordHash = generate_password_hash(password)

        #Ensure that username and password are not empty, that password and confirmation password match, and that the username is not already taken
        if len(username) == 0:
            return apology("Please fill in a username")

        data = db.execute("SELECT username FROM users WHERE username = ?", username)

        if len(data) != 0:
            return apology("Username already exists, please enter a different one")

        elif len(password) == 0:
            return apology("Please fill in a password")

        elif password != confirmationPassword:
            return apology("Please ensure passwords match")

        #Upon checking previous conditions and confirming no issues, insert the user into the users table
        else:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, passwordHash)
        #Return to homepage
        return redirect("/")
    else:
        #Show the user the register.html page when method is GET
        return render_template("register.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    ownedStocks = db.execute("SELECT stockSymbol, shares FROM purchase_history WHERE user_id = ? GROUP BY stockSymbol HAVING shares > 0", session["user_id"])
    if request.method == "POST":
        for stock in ownedStocks:
            symbol = request.form.get("symbol")

            if len(symbol) == 0:
                return apology("You must enter a valid stock, please try again")

            shares = int(request.form.get("shares"))

            if shares < 1:
                return apology("Please enter a value of 1 or more in the shares field")
            if shares > stock["shares"]:
                return apology("Sorry, you own less shares than the amount you entered, please try again")

            stockPrice = int(lookup(symbol)["price"])
            stockTotal = shares * stockPrice
            userCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
            userCash += stockTotal

            db.execute("UPDATE users SET cash = ? WHERE id = ?", userCash, session["user_id"])
            db.execute("INSERT INTO purchase_history (user_id, stockSymbol, shares, price_per_share, cost) VALUES(?, ?, -?, ?, -?)", session["user_id"], symbol, shares, usd(stockPrice), usd(stockTotal))

            return redirect("/")
    else:
        return render_template("sell.html", ownedStocks = ownedStocks)
@app.route("/addcash", methods={"GET", "POST"})
@login_required
def addcash():
    """Add cash feature"""
    userCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    if request.method == "POST":

        temp1 = str(request.form.get("cashDeposit"))
        temp2 = str(request.form.get("cashWithdrawal"))
        if temp1 == "" or temp1.isdigit == False:
            cashDeposit = 0
        else:
            cashDeposit = int(temp1)
        if temp2 == "" or temp2.isdigit == False:
            cashWithdrawal = 0
        else:
            cashWithdrawal = int(temp2)



        if cashDeposit < 0 or cashWithdrawal < 0:
            return apology("Please enter a value greater than 0 in either the Deposit Amount or Withdrawal Amount field")

        if cashDeposit > 0 and cashWithdrawal > 0:
            return apology("You cannot withdraw and deposit at the same time, please ensure you only fill in one field")

        if cashDeposit > 0:
            userCash += cashDeposit
            db.execute("UPDATE users SET cash = ? WHERE id = ?", userCash, session["user_id"])
            return redirect("/")

        if cashWithdrawal > 0:
            if cashWithdrawal > userCash:
                return apology("Sorry, your withdrawal amount exceeds your current balance. Please try again.")
            userCash -= cashWithdrawal
            db.execute("UPDATE users SET cash = ? WHERE id = ?", userCash, session["user_id"])
            return redirect("/")

        return apology("Please enter a value greater than 0 in either the Deposit Amount or Withdrawal Amount field")


    else:
        return render_template("addcash.html")


