from flask import Flask, render_template, request, redirect, url_for, flash
import pymysql
from secrets import token_hex
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = token_hex(16)  # Secure random secret key

# Database connection configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Replace with your MySQL username
    'password': '',  # Replace with your MySQL password
    'db': 'flight',  # Replace with your database name
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor  # Returns results as dictionaries
}

# Global connection (for simplicity; use connection pooling in production)
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
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']  # Could be 'customer', 'booking_agent', or 'airline_staff'

        conn = get_db_connection()
        cursor = conn.cursor()

        if user_type == 'customer':
            query = "SELECT * FROM Customer WHERE email = %s AND password = %s"
            cursor.execute(query, (email, password))
            user = cursor.fetchone()
            if user:
                flash('Logged in successfully as Customer!', 'success')
                return redirect(url_for('customer_dashboard', email=email))
            else:
                flash('Invalid credentials!', 'error')
        elif user_type == 'booking_agent':
            query = "SELECT * FROM BookingAgent WHERE email = %s AND password = %s"
            cursor.execute(query, (email, password))
            user = cursor.fetchone()
            if user:
                flash('Logged in successfully as Booking Agent!', 'success')
                return redirect(url_for('booking_agent_dashboard', email=email))
        elif user_type == 'airline_staff':
            query = "SELECT * FROM AirlineStaff WHERE username = %s AND password = %s"
            cursor.execute(query, (email, password))
            user = cursor.fetchone()
            if user:
                flash('Logged in successfully as Airline Staff!', 'success')
                return redirect(url_for('airline_staff_dashboard', username=email))

        cursor.close()
        return redirect(url_for('login'))

    return render_template('login.html')

# Customer Dashboard
@app.route('/customer/<email>')
def customer_dashboard(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Customer WHERE email = %s"
    cursor.execute(query, (email,))
    customer = cursor.fetchone()

    query_flights = "SELECT * FROM Flight"
    cursor.execute(query_flights)
    flights = cursor.fetchall()

    cursor.close()
    return render_template('customer_dashboard.html', customer=customer, flights=flights)

# Booking Agent Dashboard
@app.route('/booking_agent/<email>')
def booking_agent_dashboard(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM BookingAgent WHERE email = %s"
    cursor.execute(query, (email,))
    agent = cursor.fetchone()

    # Example query for commissions (simplified)
    query_commissions = """
        SELECT SUM(f.price * 0.1) as total_commission 
        FROM Ticket t 
        JOIN Flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num 
        WHERE t.booking_agent_email = %s AND t.purchase_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
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
    query = "SELECT * FROM AirlineStaff WHERE username = %s"
    cursor.execute(query, (username,))
    staff = cursor.fetchone()

    query_flights = "SELECT * FROM Flight WHERE airline_name = (SELECT airline_name FROM staff_works_for WHERE staff_username = %s)"
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
            SELECT f.* FROM Flight f
            JOIN Airport depart ON f.depart_airport_name = depart.name
            JOIN Airport arrive ON f.arrive_airport_name = arrive.name
            WHERE (depart.name = %s OR depart.city = %s)
            AND (arrive.name = %s OR arrive.city = %s)
        """
        cursor.execute(query, (source, source, destination, destination))
        flights = cursor.fetchall()
        cursor.close()

        return render_template('flight_results.html', flights=flights)

    conn = get_db_connection()
    cursor = conn.cursor()
    query_airports = "SELECT * FROM Airport"
    cursor.execute(query_airports)
    airports = cursor.fetchall()
    cursor.close()

    return render_template('search_flights.html', airports=airports)

# Purchase Ticket (Example for Customer)
@app.route('/purchase/<flight_id>', methods=['POST'])
def purchase_ticket(flight_id):
    customer_email = request.form['customer_email']  # Assume customer is logged in

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check seat availability
    query_flight = "SELECT airline_name, flight_num, seats FROM Flight NATURAL JOIN airplane WHERE CONCAT(airline_name, flight_num) = %s"
    cursor.execute(query_flight, (flight_id,))
    flight = cursor.fetchone()

    if not flight:
        flash('Flight not found!', 'error')
        cursor.close()
        return redirect(url_for('customer_dashboard', email=customer_email))

    # Count current tickets for this flight
    query_tickets = "SELECT COUNT(*) as ticket_count FROM Ticket WHERE airline_name = %s AND flight_num = %s"
    cursor.execute(query_tickets, (flight['airline_name'], flight['flight_num']))
    ticket_count = cursor.fetchone()['ticket_count']

    if ticket_count < flight['seats']:
        ticket_id = str(uuid.uuid4())
        query_insert = """
            INSERT INTO Ticket (ticket_id, airline_name, flight_num, customer_email, booking_agent_email) 
            VALUES (%s, %s, %s, %s, NULL)
        """
        cursor.execute(query_insert, (ticket_id, flight['airline_name'], flight['flight_num'], customer_email))
        conn.commit()
        flash('Ticket purchased successfully!', 'success')
    else:
        flash('No seats available!', 'error')

    cursor.close()
    return redirect(url_for('customer_dashboard', email=customer_email))

if __name__ == '__main__':
    app.run(debug=True)