from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from functools import wraps
from tempfile import gettempdir
from urllib.parse import urlparse
from decimal import *
import passlib.pwd as pwd
import sqlalchemy
import os
import psycopg2

app = Flask(__name__)

url = urlparse(os.environ["DATABASE_URL"])
conn = psycopg2.connect(
 database=url.path[1:],
 user=url.username,
 password=url.password,
 host=url.hostname,
 port=url.port
)

class SQL(object):
    """Wrap SQLAlchemy to provide a simple SQL API."""

    def __init__(self, url):
        """
        Create instance of sqlalchemy.engine.Engine.

        URL should be a string that indicates database dialect and connection arguments.

        http://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine
        """
        try:
            self.engine = sqlalchemy.create_engine(url)
        except Exception as e:
            raise RuntimeError(e)

    def execute(self, text, *multiparams, **params):
        """
        Execute a SQL statement.
        """
        try:

            # bind parameters before statement reaches database, so that bound parameters appear in exceptions
            # http://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.text
            # https://groups.google.com/forum/#!topic/sqlalchemy/FfLwKT1yQlg
            # http://docs.sqlalchemy.org/en/latest/core/connections.html#sqlalchemy.engine.Engine.execute
            # http://docs.sqlalchemy.org/en/latest/faq/sqlexpressions.html#how-do-i-render-sql-expressions-as-strings-possibly-with-bound-parameters-inlined
            statement = sqlalchemy.text(text).bindparams(*multiparams, **params)
            result = self.engine.execute(str(statement.compile(compile_kwargs={"literal_binds": True})))

            # if SELECT (or INSERT with RETURNING), return result set as list of dict objects
            if result.returns_rows:
                rows = result.fetchall()
                return [dict(row) for row in rows]

            # if INSERT, return primary key value for a newly inserted row
            elif result.lastrowid is not None:
                return result.lastrowid

            # if DELETE or UPDATE (or INSERT without RETURNING), return number of rows matched
            else:
                return result.rowcount

        # if constraint violated, return None
        except sqlalchemy.exc.IntegrityError:
            return None

        # else raise error
        except Exception as e:
            raise RuntimeError(e)



db = SQL(os.environ["DATABASE_URL"])

app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return "sorry"
        return f(*args, **kwargs)
    return decorated_function
    
@app.route("/", methods=["GET", "POST"])

def index(message=""):
    if request.method == "POST":
        exists = db.execute("SELECT EXISTS(SELECT * FROM bookings WHERE date = :date)",
                                date = request.form.get("date")
                                )
        if exists[0]['exists'] == False:
            return "booking not found"
        
        booking = db.execute("SELECT * FROM bookings WHERE date = :date",
                                date = request.form.get("date")
                                )
        if booking[0]['delcode'] != request.form.get('code'):
            return "invalid code"
            
        if session.get("tier") != 1:
            session["user_id"] = 9
            session["tier"] = 3
        
        return render_template("mq.html", bookingid = booking[0]['id'], tier = session['tier'])
        
    else:
        return render_template("signin.html")
    
@app.route("/adminlogin", methods=["GET", "POST"])
def adminlogin(message=""):
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("adminlogin.html", message = "Username required.")
        elif not request.form.get("password"):
            return render_template("adminlogin.html", message = "Password required.")
        
        ver = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username"))
        if len(ver) != 1 or not pwd_context.verify(request.form.get("password"), ver[0]["hash"]):
            return render_template("adminlogin.html", message = "Incorrect password or nonexistant Username")
        
        else:
            session["user_id"] = ver[0]["id"]
            session["tier"] = 1
            return redirect(url_for("admin"))
            
        
    else:
        if session.get('user_id') != None and session.get('tier') == 1:
            return redirect(url_for('admin'))
        
        return render_template('adminlogin.html')
    

@app.route("/logout")
def logout():
    
    session.clear()

    return redirect(url_for("index"))


@app.route("/admin", methods=["GET"])
@login_required
def admin(message=""):
    if session.get("tier") != 1:
        return "Unauthorised"
    else:
        return render_template("admin.html")


@app.route("/mq", methods=["GET", "POST"])
@login_required
def mq(message=""):
    if request.method == "POST":
        var2 = request.form.get("q4")
        return render_template("mq.html", tier = var2)
    
    tier = session['tier']
    code = pwd.genword(length = 7, charset = "hex")
    return render_template("mq.html", tier = tier, code = code)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port,debug=True)