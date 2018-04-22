# -*- coding: utf-8 -*-
# Import all necessary packages
from flask import Flask, session, render_template, json, request, redirect, url_for, escape
from flaskext.mysql import MySQL
from werkzeug import generate_password_hash, check_password_hash
from datetime import datetime
import requests
from random import shuffle
from werkzeug.utils import secure_filename
import os
import collections

# Internal app settings
UPLOAD_FOLDER = 'static/tmp'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

# Initialize app and database connection
mysql = MySQL() 
app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'panda'
app.config['MYSQL_DATABASE_PASSWORD'] = 'coinpanda'
app.config['MYSQL_DATABASE_DB'] = 'CoinPandaDB'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
mysql.init_app(app)

#  App data settings 
appCoins = {'BTC' : 'Bitcoin',
'ETH' : 'Ethereum',
'LTC' : 'LiteCoin',
'XRP' : 'Ripple'
}
appExchanges = ['Bitstamp','Cexio','Coinbase','Exmo','Kraken']
appCoinsExchanges = {'BTC' : ['Kraken','Bitstamp','Cexio','Coinbase','Exmo'],
'ETH' : ['Kraken','Bitstamp'],
'LTC' : ['Kraken','Bitstamp','Cexio','Coinbase','Exmo'],
'XRP' : ['Kraken','Bitstamp','Cexio']
}
appCurrencies = ['USD','EUR']
appCoins = collections.OrderedDict(sorted(appCoins.items()))
appWebsites = {'Kraken' : 'https://www.kraken.com/',
'Bitstamp' : 'https://www.bitstamp.net/',
'Cexio' : 'https://cex.io/',
'Exmo' : 'https://exmo.com/',
'Coinbase' : 'https://www.coinbase.com/'
}
# --- END ------#

class ServerError(Exception):pass

# This is the home page url for the website
# Default landing page requests are handled here
@app.route('/')
def main():
    return render_template('index.html',title='CoinPanda | Home')

# This function handles Contact us page url route
@app.route('/contact')
def contact():
    return render_template('ContactUs.html',title='CoinPanda | Contact Us')

# This function handles currency comparison page requests
@app.route('/compare')
def compare():
    if 'name' not in session:
        return redirect(url_for('login'))

    _coin = request.args.get('coin')
    _currency = request.args.get('currency')
    graphCols,graphRawData,graphData = [],[],[]
    
    if not _coin:
        _coin = "BTC"
    
    if not _currency:
        _currency = "USD"

    if _coin and _currency:
        minAvg, minExc = 9999999999999,""
        for e in appExchanges:
            url = "https://min-api.cryptocompare.com/data/histoday?fsym="+ _coin + "&tsym=" + _currency + "&limit=6&e=" + e
            r = requests.get(url).json()
            
            if 'Response' in r and r['Response'] == "Error":
                pass
            else:
                resList = r['Data']
                tmp = []
                for obj in resList:
                    tmp.append(obj['close'])

                tmpAvg = reduce(lambda x, y: x + y, tmp) / len(tmp)
                
                if tmpAvg < minAvg:
                    minAvg = tmpAvg
                    minExc = e

                graphRawData.append(tmp)
                graphCols.append(e)
                
        for x in range(1,8):
            tmp =[x]
            for i,e in enumerate(graphCols):
                tmp.append(graphRawData[i][x-1])

            graphData.append(tmp)

    return render_template('compare.html',coins=appCoins,minExc=minExc,coin=_coin,currency=_currency,graphData = json.dumps(graphData),graphCols = graphCols,title='CoinPanda | Compare Currency')

# View the details of the recommended exchange for the selected cryptocurrency using this page.
@app.route('/currency_specific')
def currency_specific():
    if 'name' not in session:
        return redirect(url_for('login'))

    # Access all form values
    _coin = request.args.get('coin')
    _coinName = appCoins.get(_coin)
    _exc = request.args.get('exc')
    _currency = request.args.get('currency')
    graphData = []
    
    if _exc and _coin and _currency:
        url = "https://min-api.cryptocompare.com/data/histoday?fsym="+ _coin + "&tsym=" + _currency + "&limit=6&e=" + _exc
        r = requests.get(url).json()
            
        if 'Response' in r and r['Response'] == "Error":
            pass
        else:
            resList = r['Data']
            todayData = resList[0]
            resList = resList[::-1] # reverse the list

            for i,obj in enumerate(resList):
                graphData.append([i+1,obj['close']])

        shuffle(appExchanges)
        appWebsite = appWebsites.get(_exc,'/')

    return render_template('currency_specific.html',appWebsite=appWebsite,coinName=_coinName,exchanges= appExchanges,todayData=todayData,coin=_coin,exc = _exc,currency=_currency,graphData = json.dumps(graphData),title='CoinPanda | Currency Specific')

# This is the first page visible to the user containing
# the dashboard / investment portfolio of the user.
@app.route('/dashboard')
def dashboard():
    if 'name' not in session:
        return redirect(url_for('login'))

    uid = session['uid']
    data1,data2,data3,data4,data5 = [],[],[],[],[]

    # Check if currencies table needs update
    conn = mysql.connect()
    cur = conn.cursor()
    _curr_time = datetime.now()
    cur.execute("SELECT UpdateDate FROM tblCurrency ORDER BY UpdateDate DESC LIMIT 1;")
    _time_since = int((_curr_time - cur.fetchone()[0]).total_seconds() / 60)
    conn.close()

    if _time_since >= 15:
        res = update_currencies()

    conn = mysql.connect()
    cur = conn.cursor()
    
    # Widget-1 data
    cur.execute("SELECT Cryptocurrency,Currency,Source,CurrentRate,Details,Symbol FROM tblCurrency ORDER BY Cryptocurrency ASC, Currency DESC;")

    for row in cur.fetchall():
        obj ={'Cryptocurrency' : row[0], 'Symbol' : row[5], 'Currency' : row[1], 'Source' : row[2], 
        'CurrentRate' : row[3], 'Details': json.loads(str(row[4]))}
        data1.append(obj)

    # Widget-2,3,4 data
    cur.execute("""
        SELECT SUM(i.InvestmentValue) as TotalInvestment 
        , SUM(i.InvestmentVolume * c.CurrentRate) as NetWorth
        , SUM(i.InvestmentVolume * c.CurrentRate)- SUM(i.InvestmentValue) as Profit
        FROM tblInvestment i
        Inner JOIN tblCurrency c ON i.CID=c.CID
        WHERE i.UID = %s
        """, format(uid))
    data2 = cur.fetchone()

    # Widget 5 data
    cur.execute("""
        SELECT UID, Cryptocurrency, SUM(InvestmentValue)
        FROM tblInvestment
        GROUP BY Cryptocurrency,UID
        HAVING UID=%s;
        """, format(uid))
    
    for row in cur.fetchall():
        data3.append(row)

    # Widget 6 data
    cur.execute("""
        SELECT i.Cryptocurrency, (i.InvestmentVolume * c.CurrentRate)- (i.InvestmentValue) as Profit
        FROM tblInvestment i
        INNER JOIN tblCurrency c ON i.CID=c.CID
        WHERE UID = %s and (i.InvestmentVolume * c.CurrentRate)- (i.InvestmentValue)>0
        """, format(uid))
    
    for row in cur.fetchall():
        data4.append(row)

    # Widget-7 data
    cur.execute("""
        SELECT c.Cryptocurrency
        , c.Symbol
        , c.Source as ExchangeName
        , i.InvestmentVolume * c.CurrentRate as TotalValue
        , i.InvestmentVolume as TotalVolume
        , i.InvestmentValue as BeforeValue
        , i.InvestmentRate as BeforeRate
        , i.InvestmentVolume * c.CurrentRate as AfterValue
        , c.CurrentRate as AfterRate
        , ((i.InvestmentVolume * c.CurrentRate)- (i.InvestmentValue)) as NetProfit
        , (((i.InvestmentVolume * c.CurrentRate)- (i.InvestmentValue))/i.InvestmentValue)*100 as NetProfitPercent
        , i.IID
        , c.Currency
        , i.InvestmentDate
        FROM tblInvestment i
        INNER JOIN tblCurrency c ON i.CID=c.CID
        WHERE UID = %s;
        """, format(uid))
    
    for row in cur.fetchall():
        data5.append(row)

    conn.close()

    return render_template('home.html',coins=appCoins,currencies=appCurrencies,appCoinsExchanges= json.dumps(appCoinsExchanges),exchanges= appExchanges,data1=data1,data2=data2,data3=data3,data4=data4,data5=data5,title='CoinPanda | My Investment Portfolio')

# This function is used to refresh/update cryptocurrencies data in an interval of 15 mins
def update_currencies():
    baseUrl = "https://min-api.cryptocompare.com/data/pricemultifull?"
    resp = []
    
    for e in appExchanges:
        coins = "fsyms=" + (",". join(appCoins))
        currencies = "&tsyms=" + (",". join(appCurrencies))
        url = baseUrl + coins + currencies + "&e=" + e
        r = requests.get(url).json()
        
        if 'Response' in r and r['Response'] == "Error":
            pass
        else:
            resObj = r['RAW']
            for _coin in appCoins:
                _detObj = resObj.get(_coin,{})

                for _currency in appCurrencies:
                    # update records in Currency table
                    conn = mysql.connect()
                    cur = conn.cursor()
                    _detCurrObj = _detObj.get(_currency,{})
                    _curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    _curr_rate = _detCurrObj.get('PRICE','N/A')

                    cur.execute("""
                    UPDATE tblCurrency SET CurrentRate = %s,
                    Details = %s,
                    UpdateDate = %s
                    WHERE (Source = %s AND Symbol = %s AND Currency = %s);             
                    """,(_curr_rate,json.dumps(_detCurrObj),_curr_time,e,_coin,_currency))
                    
                    conn.commit()
                    conn.close()
        
    return json.dumps({'error': 0, 'message' : ''})

# This function is used to ADD new investments or EDIT existing investments for a given user 
@app.route('/save_investment/<edit>',methods=['POST'])
def save_investment(edit):
    if 'name' not in session:
        return redirect(url_for('login')) 
    try:
        if request.method == 'POST':
            conn = mysql.connect()
            cur = conn.cursor()

            # Access all form values
            _coin = request.form['coin']
            _exchange = request.form['exchange']
            _currency = request.form['currency']
            _units = float(request.form['units'])
            _value_unit = float(request.form['value_unit'])
            _purchased_date = request.form['purchased_date']

            _curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # validate the received values
            if _coin and _exchange and _currency and _units and _value_unit and _purchased_date:   
                if edit == "1":
                    # Get and verify investment id
                    _invId = request.form['invId']
                    cur.execute("SELECT COUNT(1) FROM tblInvestment WHERE IID = %s;", format(_invId))

                    if not cur.fetchone()[0]:
                        conn.close()
                        return json.dumps({'error': 1, 'message' : ''})

                    # Update investment with id
                    cur.execute("""
                    UPDATE tblInvestment SET 
                    InvestmentValue = %s,
                    InvestmentVolume= %s,
                    InvestmentDate= %s,
                    InvestmentRate= %s,
                    UpdateDate= %s 
                    WHERE IID = %s;
                    """, 
                    ((_units*_value_unit),_units,_purchased_date,_value_unit,_curr_time,format(_invId)))

                else:
                    # Get CID
                    cur.execute("SELECT CID,Cryptocurrency FROM tblCurrency WHERE (Source=%s AND Symbol=%s AND Currency = %s);", 
                    (_exchange,_coin,_currency,))
                    
                    currObj = cur.fetchone()
                    _cid = currObj[0]
                    _crypto = currObj[1]

                    if not _cid:
                        conn.close()
                        return json.dumps({'error': 1, 'message' : ''})

                    # Create new record in the investment table
                    cur.execute("""
                    INSERT INTO tblInvestment(UID,CID,Cryptocurrency,Currency,InvestmentValue,
                    InvestmentVolume,InvestmentDate,InvestmentRate,InsertDate,UpdateDate) 
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                    (session['uid'],_cid,_crypto,_currency,(_units*_value_unit),_units,_purchased_date,_value_unit,
                    _curr_time,_curr_time,))
                
                conn.commit()
                conn.close()

                return json.dumps({'error': 0, 'message' : ''})
            else:
                conn.close()
                return json.dumps({'error': 2, 'message' : ''})
    except Exception as e:
        conn.close()
        return json.dumps({'error': 3, 'message' : str(e)})

    conn.close()

# This function is used to DELETE existing investments for a given user 
@app.route('/delete_investment/',methods=['POST'])
def delete_investment():
    if 'name' not in session:
        return redirect(url_for('login')) 
    try:
        if request.method == 'POST':
            conn = mysql.connect()
            cur = conn.cursor()
            
            _invId = request.form['invId']

            # Verify if record exists in the investment table
            cur.execute("SELECT COUNT(1) FROM tblInvestment WHERE IID = %s;", format(_invId))

            if not cur.fetchone()[0]:
                conn.close()
                return json.dumps({'error': 1, 'message' : ''})

            # Delete record from the investment table
            cur.execute("DELETE FROM tblInvestment WHERE IID = %s;", format(_invId))
            
            # Commit changes and close DB connection
            conn.commit()
            conn.close()

            return json.dumps({'error': 0, 'message' : ''})
        else:
            conn.close()
            return json.dumps({'error': 2, 'message' : ''})
    except Exception as e:
        conn.close()
        return json.dumps({'error': 3, 'message' : str(e)})

    conn.close()

# This page lets the user VIEW and EDIT user profile details
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'name' not in session:
        return redirect(url_for('login'))

    uid = str(session['uid'])

    try:
        conn = mysql.connect()
        cur = conn.cursor()

        if request.method == 'POST':
            # Upload user image from file
            if 'Image' in request.files:
                file = request.files['Image']
                if file and allowed_file(file.filename):
                    # Upload user image and update record 
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    
                    cur.execute("""
                        UPDATE tblUser SET 
                        Image = %s
                        WHERE UID= %s;
                        """,(filename,uid,))
            else:
                # Update details in the user record table
                cur.execute("""
                        UPDATE tblUser SET 
                        FName = %s,
                        Lname= %s,
                        Company= %s,
                        Address1= %s,
                        Address2= %s,
                        TimeZone = %s
                        WHERE UID = %s;
                        """, (request.form['FName'],request.form['LName'],request.form['Company'],
                        request.form['Address1'],request.form['Address2'],request.form['TimeZone'],
                        uid,))
            
                # update password
                _password = request.form['Password']
                _passwordm = request.form['PasswordMatch']
                if _passwordm and _password and _passwordm!='' and _password!='':
                    _hashed_password = generate_password_hash(_password)
                    cur.execute("UPDATE tblUser SET Password = %s WHERE UID = %s;", (_hashed_password,uid))
        
        # Commit changes and close DB connection
        conn.commit()
        conn.close()

        # Fetch user profile record
        conn = mysql.connect()
        cur = conn.cursor()

        cur.execute("""SELECT FName,Lname,Email,Company,Address1,
            Address2,TimeZone,Image
            FROM tblUser
            WHERE UID = %s;
            """,format(uid))

        userData = cur.fetchone()

    except ServerError as e:
        return json.dumps({'error': 1, 'message' : str(e)})

    conn.close()

    return render_template('edit.html',userData=userData,title='CoinPanda | Edit Profile')

# Converts the name of the uploaded file to escape space and other characters
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# This function is used for to displaying user login page and
# verifying user credentials to authenticate user
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'name' in session:
        return redirect(url_for('dashboard'))

    error = None

    try:
        conn = mysql.connect()
        cur = conn.cursor()

        if request.method == 'POST':
            email_form  = request.form['email']

            # Check if user email exists in the database
            cur.execute("SELECT COUNT(1) FROM tblUser WHERE Email = %s;", format(email_form))

            if not cur.fetchone()[0]:
                conn.close()
                return render_template('login.html', log_error=1, message='Invalid Email',title='CoinPanda | Login')

            password_form  = request.form['password']
            cur.execute("SELECT Password,FName,LName,UID FROM tblUser WHERE Email = %s;", format(email_form))

            for row in cur.fetchall():
                # Verfify user login credential for login
                if check_password_hash(row[0],password_form):
                    session['email'] = request.form['email']
                    session['name'] = row[1] + " " + row[2]
                    session['uid'] = row[3]

                    conn.close()
                    return redirect(url_for('dashboard'))

            conn.close()
            return render_template('login.html', log_error =2, message='Invalid password',title='CoinPanda | Login')
    except ServerError as e:
        error = str(e)

    conn.close()
    return render_template('login.html',log_error=3,title='CoinPanda | Login')

# This function used to implement the Logout functionality
@app.route('/logout')
def logout():
    # Clear all session variables
    session.pop('email', None)
    session.pop('name', None)
    session.pop('uid', None)

    return redirect(url_for('login'))

# This function is used for to displaying user signup page and create new user record in DB
@app.route('/register',methods=['POST','GET'])
def signUp():
    try:
        if request.method == 'POST':
            conn = mysql.connect()
            cur = conn.cursor()

            # Get all form values
            _fname = request.form['fName']
            _lname = request.form['lName']
            _email = request.form['Email']
            _password = request.form['Password']

            # validate the received values
            if _fname and _lname and _email and _password:
                # All Good, let's call MySQL
                _hashed_password = generate_password_hash(_password)
                cur.execute("INSERT INTO tblUser(FName,LName,Email,Password) values (%s,%s,%s,%s)", 
                (_fname,_lname, _email, _hashed_password))
                
                # Commit changes and close DB connection
                conn.commit()
                conn.close()

                return render_template('login.html', reg_error=0, message='Signup was successful! Please login using your credentials ...',title='CoinPanda | Sign Up')
                
            else:
                conn.close()
                return render_template('login.html', reg_error=1, message='Error! Please fill in all details!',title='CoinPanda | Sign Up')

    except Exception as e:
        conn.close()
        return render_template('login.html', reg_error = 2, message = str(e),title='CoinPanda | Sign Up')

    conn.close()
    return render_template('login.html',reg_error=3,title='CoinPanda | Sign Up')

# 404 page error route
@app.errorhandler(404)
def error(e):
    return render_template('404.html',title='CoinPanda | ERROR')

# Lanch the app on port 8080
if __name__ == "__main__":
    app.run(port=8080, host='0.0.0.0',debug=True,threaded=True)