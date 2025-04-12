from flask import Flask, render_template, request, redirect, url_for, flash
import pymysql
from secrets import token_hex
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = token_hex(16)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'db': 'flight',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

connection = None

def get_db_connection():
    global connection
    if not connection or not connection.open:
        connection = pymysql.connect(**DB_CONFIG)
    return connection

@app.teardown_appcontext
def close_db(error):
    global connection
    if connection and connection.open:
        connection.close()

@app.route('/')
def home():
    return render_template('index.html')

# User Login Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['email']  # Use 'email' for flexibility
        password = request.form['password']
        user_type = request.form['user_type']

        conn = get_db_connection()
        cursor = conn.cursor()

        if user_type == 'customer':
            query = "SELECT * FROM customer WHERE email = %s AND password = %s"
            cursor.execute(query, (identifier, password))
            user = cursor.fetchone()
            if user:
                flash('Logged in successfully as Customer!', 'success')
                return redirect(url_for('customer_dashboard', email=identifier))
            else:
                flash('Invalid credentials!', 'error')
        elif user_type == 'booking_agent':
            query = "SELECT * FROM booking_agent WHERE email = %s AND password = %s"
            cursor.execute(query, (identifier, password))
            user = cursor.fetchone()
            if user:
                flash('Logged in successfully as Booking Agent!', 'success')
                return redirect(url_for('booking_agent_dashboard', email=identifier))
        elif user_type == 'airline_staff':
            query = "SELECT * FROM airline_staff WHERE username = %s AND password = %s"
            cursor.execute(query, (identifier, password))
            user = cursor.fetchone()
            if user:
                flash('Logged in successfully as Airline Staff!', 'success')
                return redirect(url_for('airline_staff_dashboard', username=identifier))

        cursor.close()
        return redirect(url_for('login'))

    return render_template('login.html')

# Customer Dashboard
@app.route('/customer/<email>')
def customer_dashboard(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM customer WHERE email = %s"
    cursor.execute(query, (email,))
    customer = cursor.fetchone()

    query_flights = """
        SELECT f.* FROM flight f 
        JOIN airport depart ON f.departure_airport = depart.airport_name 
        JOIN airport arrive ON f.arrival_airport = arrive.airport_name
    """
    cursor.execute(query_flights)
    flights = cursor.fetchall()

    cursor.close()
    return render_template('customer_dashboard.html', customer=customer, flights=flights)

# Booking Agent Dashboard
@app.route('/booking_agent/<email>')
def booking_agent_dashboard(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM booking_agent WHERE email = %s"
    cursor.execute(query, (email,))
    agent = cursor.fetchone()

    query_commissions = """
        SELECT SUM(f.price * 0.1) as total_commission 
        FROM purchases p 
        JOIN ticket t ON p.ticket_id = t.ticket_id 
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num 
        WHERE p.customer_email IN (
            SELECT c.email FROM customer c 
            JOIN purchases p2 ON c.email = p2.customer_email 
            WHERE p2.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
        ) AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """
    cursor.execute(query_commissions, (email,))
    commissions = cursor.fetchone()

    cursor.close()
    return render_template('booking_agent_dashboard.html', agent=agent, commissions=commissions)

# Airline Staff Dashboard
@app.route('/airline_staff/<username>')
def airline_staff_dashboard(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM airline_staff WHERE username = %s"
    cursor.execute(query, (username,))
    staff = cursor.fetchone()

    query_flights = """
        SELECT f.* FROM flight f 
        WHERE f.airline_name = (SELECT airline_name FROM airline_staff WHERE username = %s)
    """
    cursor.execute(query_flights, (username,))
    flights = cursor.fetchall()

    cursor.close()
    return render_template('airline_staff_dashboard.html', staff=staff, flights=flights)

# Search Flights
@app.route('/search_flights', methods=['GET', 'POST'])
def search_flights():
    if request.method == 'POST':
        source = request.form['source']
        destination = request.form['destination']

        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT f.* FROM flight f 
            JOIN airport depart ON f.departure_airport = depart.airport_name 
            JOIN airport arrive ON f.arrival_airport = arrive.airport_name 
            WHERE depart.airport_name = %s OR depart.airport_city = %s 
            AND (arrive.airport_name = %s OR arrive.airport_city = %s)
        """
        cursor.execute(query, (source, source, destination, destination))
        flights = cursor.fetchall()
        cursor.close()

        return render_template('flight_results.html', flights=flights)

    conn = get_db_connection()
    cursor = conn.cursor()
    query_airports = "SELECT * FROM airport"
    cursor.execute(query_airports)
    airports = cursor.fetchall()
    cursor.close()

    return render_template('search_flights.html', airports=airports)

# Purchase Ticket (Example for Customer)
@app.route('/purchase/<airline_name>/<flight_num>', methods=['POST'])
def purchase_ticket(airline_name, flight_num):
    customer_email = request.form['customer_email']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check seat availability
    query_flight = """
        SELECT f.airline_name, f.flight_num, a.seats 
        FROM flight f 
        JOIN airplane a ON f.airline_name = a.airline_name AND f.airplane_id = a.airplane_id 
        WHERE f.airline_name = %s AND f.flight_num = %s
    """
    cursor.execute(query_flight, (airline_name, flight_num))
    flight = cursor.fetchone()

    if not flight:
        flash('Flight not found!', 'error')
        cursor.close()
        return redirect(url_for('customer_dashboard', email=customer_email))

    # Count current tickets for this flight
    query_tickets = """
        SELECT COUNT(*) as ticket_count FROM ticket 
        WHERE airline_name = %s AND flight_num = %s
    """
    cursor.execute(query_tickets, (airline_name, flight_num))
    ticket_count = cursor.fetchone()['ticket_count']

    if ticket_count < flight['seats']:
        ticket_id = str(uuid.uuid4())
        query_insert = """
            INSERT INTO ticket (ticket_id, airline_name, flight_num) 
            VALUES (%s, %s, %s)
        """
        cursor.execute(query_insert, (ticket_id, airline_name, flight_num))
        # Link to purchases
        query_purchase = """
            INSERT INTO purchases (ticket_id, customer_email, purchase_date) 
            VALUES (%s, %s, NOW())
        """
        cursor.execute(query_purchase, (ticket_id, customer_email))
        conn.commit()
        flash('Ticket purchased successfully!', 'success')
    else:
        flash('No seats available!', 'error')

    cursor.close()
    return redirect(url_for('customer_dashboard', email=customer_email))

if __name__ == '__main__':
    app.run(debug=True)