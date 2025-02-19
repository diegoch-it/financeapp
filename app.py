import os
import requests

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
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
    # Query portfolio of companies for the user
    query = db.execute("SELECT symbol, SUM(qty) as total_qty FROM transactions WHERE id_user = ? AND (tx_id == 1 OR tx_id == 2) GROUP BY symbol", session["user_id"])

    if len(query) == 0:
        return apology("start buying and selling with your initial 10 grand for free")

    portfolio = {}
    for i in range(len(query)):
                   portfolio[i] = query[i]


    # Getting current prices
    b = []
    c = []
    for i in range(len(query)):
        b.append(query[i]["symbol"])
        c.append(query[i]["total_qty"])

    curr_prices = []
    curr_amount = []
    for key in b:
        curr_prices.append(lookup(key)['price'])

    for i in range(len(curr_prices)):
        curr_amount.append(curr_prices[i]*c[i])

    # Adding the current prices to the portfolio dict
    holdings = 0
    for i in portfolio:
        portfolio[i]['price'] = curr_prices[i]
        portfolio[i]['amount'] = curr_amount[i]
        holdings = holdings + curr_amount[i]

    cash = db.execute(
            "SELECT cash FROM users WHERE id= ?", session["user_id"])
    cash = float(cash[0]['cash'])

    grand_total = cash + holdings

    return render_template("/index.html", portfolio=portfolio, cash=cash, grand_total=grand_total, holdings=holdings)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        """ Quotation """
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("must provide valid stock symbol", 403)
        symbinfo = lookup(symbol)
        price = symbinfo['price']


        """ Shares to buy """
        qty = request.form.get("shares")
        if not request.form.get("shares") or float(qty) < 0:
            return apology("enter a positive number of shares", 403)
        # calculate total amount
        amount = price * float(qty)

        # check enough funds from users table and return apology

        balance = db.execute(
            "SELECT cash FROM users WHERE id= ?", session["user_id"])
        balance = float(balance[0]['cash'])

        #print("this is the type of balance: " + str(type(balance[0][0])))
        if balance < amount:
            return apology("not enough funds for this buy")
        elif balance > amount:
            txid = db.execute(
                "SELECT id FROM tx_type WHERE type = 'buy'"
            )
            txid = txid[0]['id']
            # record in buy in transaction table
            db.execute(
            "INSERT INTO transactions (id_user, symbol, tx_id, price_usd, qty, amount_usd) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], symbol, txid, price, qty, amount)
            # decuct amount from user's balance
            db.execute(
            "UPDATE users SET 'cash' = ? WHERE id = ?", (balance - amount), session["user_id"])

        return redirect("/")
    return render_template("/buy.html")

@app.route("/buyindex")
@login_required
def buyindex():
    sym = request.args.get('symb')
    return render_template("/buy.html", symb=sym)

@app.route("/sellindex")
@login_required
def sellindex():
    sym = request.args.get('symb')
    query = db.execute("SELECT symbol FROM transactions WHERE id_user = ? GROUP BY symbol", session["user_id"])

    if len(query) == 0:
        return apology("start buying and selling with your initial 10 grand for free")

    stocks = []
    for i in range(len(query)):
        stocks.append(query[i]["symbol"])
    return render_template("/sell.html", symb=sym, stocks=stocks)

@app.route('/quote2')
def quote2():
    symbol = request.args.get('symbol')
    response = requests.get(f"https://finance.cs50.io/quote?symbol={symbol}")
    return jsonify(response.json())

@app.route("/search")
def search():
    q = request.args.get("q")
    if q:
        companies = db.execute("SELECT * FROM shows WHERE title LIKE ? LIMIT 50", "%" + q + "%")
    else:
        companies = []
    return render_template("search.html", comanies=companies)

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # show full list of user transactions with symbol, type of tx, price, number of shares, timestamp,
     # Query portfolio of companies for the user
    query = db.execute("SELECT a.symbol, ABS(a.qty) as qty , a.Timestamp, a.price_usd as price, ABS(a.amount_usd) as amount, UPPER(b.type) as type FROM transactions as a JOIN tx_type as b ON a.tx_id = b.id WHERE id_user = ?", session["user_id"])

    if len(query) == 0:
        return apology("start buying and selling with your initial 10 grand for free")

    txs = {}
    for i in range(len(query)):
                   txs[i] = query[i]

    return render_template("/history.html", txs=txs)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("must provide valid stock symbol", 403)
        symbinfo = lookup(symbol)
        symbinfo['price'] = usd(symbinfo['price'])
        return render_template("/quoted.html", symbinfo=symbinfo)
    return render_template("/quote.html")

@app.route("/add_balance", methods=["GET", "POST"])
@login_required
def add_balance():
    balance = db.execute(
            "SELECT cash FROM users WHERE id= ?", session["user_id"])
    balance = float(balance[0]['cash'])

    if request.method == "POST":
        increase = request.form.get("money")

        if increase == '':
            return apology("enter a positive amount", 403)

        increase = float(increase)

        if increase <= 0:
            return apology("enter a positive amount", 403)

        db.execute(
            "UPDATE users SET 'cash' = ? WHERE id = ?", (balance + increase), session["user_id"])
        stock = "-"
        txid=3
        shares=0

        db.execute(
            "INSERT INTO transactions (id_user, symbol, tx_id, price_usd, qty, amount_usd) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], stock, txid, increase, shares, increase)

        return render_template("/buy.html")
    return render_template("/add_balance.html", balance=balance)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            return apology("NAME MISSING", 403)
        password = request.form.get("password")
        if not password:
            return apology("password missing", 403)
        conf = request.form.get("confirmation")
        if not conf:
            return apology("confirmation password missing", 403)
        if not password == conf:
            return apology("enter same passwords", 403)

        hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)
            return redirect("/")
        except ValueError:
            return apology("existent username", 403)

    return render_template("register.html")


@app.route("/chpass", methods=["GET", "POST"])
def chpass():
    if request.method == "POST":
        pastpassword = request.form.get("pastpassword")
        if not pastpassword:
            return apology("Current password missing", 403)

        regpassword = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        if not check_password_hash(
            regpassword[0]["hash"], pastpassword
            ):
            return apology("Incorrect Current Password", 403)

        newpassword = request.form.get("newpassword")
        if not newpassword:
            return apology("New password missing", 403)
        conf = request.form.get("confirmation")
        if not conf:
            return apology("confirmation password missing", 403)
        if not newpassword == conf:
            return apology("enter same new and confirmation passwords", 403)

        hash = generate_password_hash(newpassword)
        try:
            db.execute(
                "UPDATE users SET 'hash' = ? WHERE id = ?", hash, session["user_id"])
            return redirect("/")
        except ValueError:
            return apology("existent username", 403)

    return render_template("chpass.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    query = db.execute("SELECT symbol FROM transactions WHERE id_user = ? GROUP BY symbol", session["user_id"])

    if len(query) == 0:
        return apology("start buying and selling with your initial 10 grand for free")

    stocks = []
    for i in range(len(query)):
        stocks.append(query[i]["symbol"])

    """Sell shares of stock"""
    if request.method == "POST":

        stock = request.form.get("symbol")

        if not stock in stocks:
            return apology("SELECT AN EXISTENT STOCK, PLEASE")

        shares = request.form.get("shares")
        shares = float(shares)

        if shares < 0:
            return apology("Enter a positive number")

        hold = db.execute(
            "SELECT SUM(qty) AS qty FROM transactions WHERE id_user = ? AND symbol = ? GROUP BY symbol", session["user_id"], stock)

        if shares > hold[0]['qty']:
            return apology("Not enough shares in your portfolio for this sell")

        price = lookup(stock)
        price = price['price']

        amount = - price * shares

        txid = db.execute(
                "SELECT id FROM tx_type WHERE type = 'sell'"
            )
        txid = txid[0]['id']

        # record in buy in transaction table
        db.execute(
            "INSERT INTO transactions (id_user, symbol, tx_id, price_usd, qty, amount_usd) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], stock, txid, price, -shares, amount)
            # decuct amount from user's balance

        balance = db.execute(
            "SELECT cash FROM users WHERE id= ?", session["user_id"])
        balance = float(balance[0]['cash'])

        db.execute(
            "UPDATE users SET 'cash' = ? WHERE id = ?", (balance + (-amount)), session["user_id"])


        return redirect("/")

    return render_template("sell.html", stocks=stocks)

#if __name__ == "__main__":
#    app.run()

#@app.route("/deregister", methods=["POST"])
#def deregister():
#    # Forget registrant
#    id = request.form.get("id")
#    if id:
#        db.execute("DELETE FROM users WHERE id = ?", id)
#    return redirect("/registrants")

