from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql
from secrets import token_hex
from datetime import datetime
import uuid
import os
from flask_dance.contrib.google import make_google_blueprint, google

app = Flask(__name__)
app.secret_key = token_hex(16)  # Secure random secret key for sessions

# Database connection configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Replace with your MySQL username
    'password': '',  # Replace with your MySQL password
    'db': 'flight',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}


google_bp = make_google_blueprint(
    client_id="517494029304-qefk3f2i948gb8hmhhp7nfvebof1jp4g.apps.googleusercontent.com",
    client_secret="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", 
    scope=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_to='google_login_callback'
)
app.register_blueprint(google_bp, url_prefix="/login")

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

def has_permission(username, permission_type):
    """Check if airline staff has the specified permission."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM permission WHERE username = %s AND permission_type = %s", (username, permission_type))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

@app.context_processor
def inject_home_url():
    home_url = url_for('home')
    if 'user_type' in session:
        if session['user_type'] == 'customer':
            home_url = url_for('customer_dashboard')
        elif session['user_type'] == 'booking_agent':
            home_url = url_for('booking_agent_dashboard')
        elif session['user_type'] == 'airline_staff':
            home_url = url_for('airline_staff_dashboard')
    return dict(
        home_url=home_url,
        has_permission=has_permission   # make has_permission available in Jinja
    )

# Home Route
@app.route('/')
def home():
    return render_template('index.html')

# Registration Routes
@app.route('/register_customer', methods=['GET', 'POST'])
def register_customer():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        building_number = request.form['building_number']
        street = request.form['street']
        city = request.form['city']
        state = request.form['state']
        phone_number = request.form['phone_number']
        passport_number = request.form['passport_number']
        passport_expiration = request.form['passport_expiration']
        passport_country = request.form['passport_country']
        date_of_birth = request.form['date_of_birth']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM customer WHERE email = %s", (email,))
        if cursor.fetchone():
            flash('Email already registered. Please use a different email or log in.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('register_customer'))
        cursor.execute("SELECT passport_number FROM customer WHERE passport_number = %s", (passport_number,))
        if cursor.fetchone():
            flash('Passport number already registered. Please use a different passport number.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('register_customer'))
        query = """
            INSERT INTO customer (email, name, password, building_number, street, city, state, phone_number, passport_number, passport_expiration, passport_country, date_of_birth)
            VALUES (%s, %s, MD5(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (email, name, password, building_number, street, city, state, phone_number, passport_number, passport_expiration, passport_country, date_of_birth))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register_customer.html')

@app.route('/register_google')
def register_google():
    session['google_auth_intent'] = 'register'
    return redirect(url_for('google.login'))

@app.route('/google_login_callback')
def google_login_callback():
    if not google.authorized:
        flash('Google authentication failed.', 'error')
        return redirect(url_for('login'))

    resp = google.get('/oauth2/v2/userinfo')
    if resp.ok:
        user_info = resp.json()
        email = user_info['email']
        name = user_info.get('name', '')
        intent = session.pop('google_auth_intent', None)

        if intent == 'register':
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM customer WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already registered. Please log in.', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
            else:
                session['google_user_info'] = {'email': email, 'name': name}
                cursor.close()
                conn.close()
                return redirect(url_for('complete_registration'))

        elif intent == 'login':
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM customer WHERE email = %s", (email,))
            if cursor.fetchone():
                session['user_type'] = 'customer'
                session['email'] = email
                flash('Logged in successfully via Google!', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('customer_dashboard'))
            else:
                flash('Email not registered. Please register first.', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('register_customer'))

        else:
            flash('Invalid authentication intent.', 'error')
            return redirect(url_for('home'))
    else:
        flash('Failed to fetch user info from Google.', 'error')
        return redirect(url_for('login'))

@app.route('/complete_registration', methods=['GET', 'POST'])
def complete_registration():
    if 'google_user_info' not in session:
        flash('Invalid access. Please register via Google again.', 'error')
        return redirect(url_for('register_customer'))

    if request.method == 'POST':
        building_number = request.form['building_number']
        street = request.form['street']
        city = request.form['city']
        state = request.form['state']
        phone_number = request.form['phone_number']
        passport_number = request.form['passport_number']
        passport_expiration = request.form['passport_expiration']
        passport_country = request.form['passport_country']
        date_of_birth = request.form['date_of_birth']

        email = session['google_user_info']['email']
        name = session['google_user_info']['name']
        password = token_hex(16)  # Generate a random password

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT passport_number FROM customer WHERE passport_number = %s", (passport_number,))
        if cursor.fetchone():
            flash('Passport number already registered. Please use a different passport number.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('complete_registration'))

        query = """
            INSERT INTO customer (email, name, password, building_number, street, city, state, phone_number, passport_number, passport_expiration, passport_country, date_of_birth)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (email, name, password, building_number, street, city, state, phone_number, passport_number, passport_expiration, passport_country, date_of_birth))
        conn.commit()
        cursor.close()
        conn.close()

        session.pop('google_user_info', None)
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    email = session['google_user_info']['email']
    name = session['google_user_info']['name']
    return render_template('complete_registration.html', email=email, name=name)

@app.route('/register_booking_agent', methods=['GET', 'POST'])
def register_booking_agent():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        booking_agent_id = request.form['booking_agent_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM booking_agent WHERE email = %s", (email,))
        if cursor.fetchone():
            flash('Email already registered. Please use a different email or log in.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('register_booking_agent'))
        cursor.execute("SELECT booking_agent_id FROM booking_agent WHERE booking_agent_id = %s", (booking_agent_id,))
        if cursor.fetchone():
            flash('Booking Agent ID already exists. Please use a different ID.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('register_booking_agent'))
        query = "INSERT INTO booking_agent (email, password, booking_agent_id) VALUES (%s, MD5(%s), %s)"
        cursor.execute(query, (email, password, booking_agent_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register_booking_agent.html')

@app.route('/register_airline_staff', methods=['GET', 'POST'])
def register_airline_staff():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        date_of_birth = request.form['date_of_birth']
        airline_name = request.form['airline_name']
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username FROM airline_staff WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already taken. Please choose a different username.', 'error')
                return redirect(url_for('register_airline_staff'))
            staff_query = """
                INSERT INTO airline_staff (username, password, first_name, last_name, date_of_birth, airline_name)
                VALUES (%s, MD5(%s), %s, %s, %s, %s)
            """
            cursor.execute(staff_query, (username, password, first_name, last_name, date_of_birth, airline_name))
            permission_query = "INSERT INTO permission (username, permission_type) VALUES (%s, %s)"
            cursor.execute(permission_query, (username, 'Operator'))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'Database error: {e}', 'error')
            return redirect(url_for('register_airline_staff'))
        finally:
            cursor.close()
            conn.close()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT airline_name FROM airline")
    airlines = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('register_airline_staff.html', airlines=airlines)

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['email_or_username'].lower()
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT email FROM customer WHERE LOWER(email) = LOWER(%s) AND password = MD5(%s)"
        cursor.execute(query, (identifier, password))
        customer = cursor.fetchone()
        if customer:
            session['user_type'] = 'customer'
            session['email'] = customer['email']
            flash('Logged in successfully as Customer!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('customer_dashboard'))
        query = "SELECT email FROM booking_agent WHERE LOWER(email) = LOWER(%s) AND password = MD5(%s)"
        cursor.execute(query, (identifier, password))
        agent = cursor.fetchone()
        if agent:
            session['user_type'] = 'booking_agent'
            session['email'] = agent['email']
            flash('Logged in successfully as Booking Agent!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('booking_agent_dashboard'))
        cursor.execute("SELECT username, airline_name FROM airline_staff WHERE username = %s AND password = MD5(%s)", (identifier, password))
        staff = cursor.fetchone()
        if staff:
            session['user_type'] = 'airline_staff'
            session['username'] = staff['username']
            session['airline_name'] = staff['airline_name']
            flash('Logged in successfully as Airline Staff!', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('airline_staff_dashboard'))
        flash('Invalid credentials!', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/login_google')
def login_google():
    session['google_auth_intent'] = 'login'
    return redirect(url_for('google.login'))

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

# Customer Dashboard
@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user_type' not in session or session['user_type'] != 'customer':
        flash('Please log in as a customer.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customer WHERE email = %s", (session['email'],))
    customer = cursor.fetchone()

    # Fetch customer's upcoming purchased flights for "My Flights" preview
    query_my_flights = """
        SELECT f.* FROM flight f
        JOIN ticket t ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        JOIN purchases p ON t.ticket_id = p.ticket_id
        WHERE p.customer_email = %s AND f.departure_time >= NOW() AND f.status = 'Upcoming'
        ORDER BY f.departure_time
    """
    cursor.execute(query_my_flights, (session['email'],))
    my_upcoming_flights = cursor.fetchall()

    # Fetch all upcoming flights for "Available Flights" section
    query_available_flights = """
        SELECT f.* FROM flight f 
        JOIN airport depart ON f.departure_airport = depart.airport_name 
        JOIN airport arrive ON f.arrival_airport = arrive.airport_name
        WHERE f.departure_time >= NOW() AND f.status = 'Upcoming'
        ORDER BY f.departure_time
    """
    cursor.execute(query_available_flights)
    available_flights = cursor.fetchall()

    # get the total spent by the customer (this was already for all time)
    # Renaming to grand_total_spent for clarity in template
    query_grand_total_spent = """
        SELECT SUM(f.price) as total_spent
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.customer_email = %s
    """
    cursor.execute(query_grand_total_spent, (session['email'],))
    grand_total_spent_data = cursor.fetchone()
    grand_total_spent = grand_total_spent_data['total_spent'] if grand_total_spent_data and grand_total_spent_data['total_spent'] is not None else 0

    monthly_query = """
        SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') as month, SUM(f.price) as spent
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.customer_email = %s AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY month
    """
    cursor.execute(monthly_query, (session['email'],))
    monthly_spending = cursor.fetchall()

    # get the seats left for each available flight
    for flight in available_flights:
        cursor.execute("""
            SELECT a.seats - COUNT(t.ticket_id) as seats_left
            FROM airplane a
            JOIN flight f ON a.airline_name = f.airline_name AND a.airplane_id = f.airplane_id
            LEFT JOIN ticket t ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
            WHERE f.airline_name = %s AND f.flight_num = %s
        """, (flight['airline_name'], flight['flight_num']))
        flight['seats_left'] = cursor.fetchone()['seats_left']
    cursor.close()
    conn.close()
    return render_template(
        'customer_dashboard.html',
        customer=customer,
        my_upcoming_flights=my_upcoming_flights,
        available_flights=available_flights,
        monthly_spending=monthly_spending,
        grand_total_spent=grand_total_spent  # Pass grand total spent
    )

# Customer View Flights
@app.route('/customer/flights', methods=['GET', 'POST'])
def customer_flights():
    if 'user_type' not in session or session['user_type'] != 'customer':
        flash('Please log in as a customer.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT f.* FROM flight f
        JOIN ticket t ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        JOIN purchases p ON t.ticket_id = p.ticket_id
        WHERE p.customer_email = %s AND f.departure_time >=  NOW()
    """
    params = [session['email']]
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        source = request.form.get('source')
        destination = request.form.get('destination')
        if start_date and end_date:
            query += " AND f.departure_time BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        if source:
            query += " AND f.departure_airport = %s"
            params.append(source)
        if destination:
            query += " AND f.arrival_airport = %s"
            params.append(destination)
    cursor.execute(query, tuple(params))
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('customer_flights.html', flights=flights)

# Customer Track Spending
@app.route('/customer/spending', methods=['GET', 'POST'])
def customer_spending():
    if 'user_type' not in session or session['user_type'] != 'customer':
        flash('Please log in as a customer.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
    else:
        start_date = 'DATE_SUB(NOW(), INTERVAL 1 YEAR)'
        end_date = 'NOW()'
    query = """
        SELECT SUM(f.price) as total_spent
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.customer_email = %s AND p.purchase_date BETWEEN %s AND %s
    """
    cursor.execute(query, (session['email'], start_date, end_date))
    total_spent = cursor.fetchone()['total_spent'] or 0
    monthly_query = """
        SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') as month, SUM(f.price) as spent
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.customer_email = %s AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY month
    """
    cursor.execute(monthly_query, (session['email'],))
    monthly_spending = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('customer_spending.html', total_spent=total_spent, monthly_spending=monthly_spending)

# Booking Agent Dashboard
@app.route('/booking_agent_dashboard')
def booking_agent_dashboard():
    if 'user_type' not in session or session['user_type'] != 'booking_agent':
        flash('Please log in as a booking agent.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM booking_agent WHERE email = %s", (session['email'],))
    agent = cursor.fetchone()
    query_commissions = """
        SELECT SUM(f.price * 0.1) as total_commission,
               AVG(f.price * 0.1) as avg_commission,
               COUNT(*) as ticket_count
        FROM purchases p 
        JOIN ticket t ON p.ticket_id = t.ticket_id 
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num 
        WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
        AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """
    cursor.execute(query_commissions, (session['email'],))
    commissions = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('booking_agent_dashboard.html', agent=agent, commissions=commissions)

# Booking Agent View Flights
@app.route('/booking_agent/flights', methods=['GET', 'POST'])
def booking_agent_flights():
    if 'user_type' not in session or session['user_type'] != 'booking_agent':
        flash('Please log in as a booking agent.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT f.* FROM flight f
        JOIN ticket t ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
        JOIN purchases p ON t.ticket_id = p.ticket_id
        WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
        AND f.departure_time >= NOW()
    """
    cursor.execute(query, (session['email'],))
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('booking_agent_flights.html', flights=flights)

# Booking Agent Purchase Tickets
@app.route('/booking_agent/purchase', methods=['GET', 'POST'])
def booking_agent_purchase():
    if 'user_type' not in session or session['user_type'] != 'booking_agent':
        flash('Please log in as a booking agent.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        customer_email = request.form['customer_email']
        airline_name = request.form['airline_name']
        flight_num = request.form['flight_num']
        cursor.execute("SELECT * FROM booking_agent_work_for WHERE email = %s AND airline_name = %s", (session['email'], airline_name))
        if not cursor.fetchone():
            flash('You are not authorized to book for this airline.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('booking_agent_dashboard'))
        cursor.execute("""
            SELECT f.airline_name, f.flight_num, a.seats 
            FROM flight f 
            JOIN airplane a ON f.airline_name = a.airline_name AND f.airplane_id = a.airplane_id 
            WHERE f.airline_name = %s AND f.flight_num = %s
        """, (airline_name, flight_num))
        flight = cursor.fetchone()
        if not flight:
            flash('Flight not found!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('booking_agent_dashboard'))
        query_existing_ticket = """
            SELECT 1 FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            WHERE p.customer_email = %s AND t.airline_name = %s AND t.flight_num = %s
        """
        cursor.execute(query_existing_ticket, (customer_email, airline_name, flight_num))
        if cursor.fetchone():
            flash(f'Customer {customer_email} already has a ticket for this flight.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('booking_agent_dashboard'))
        cursor.execute("SELECT COUNT(*) as ticket_count FROM ticket WHERE airline_name = %s AND flight_num = %s", (airline_name, flight_num))
        ticket_count = cursor.fetchone()['ticket_count']
        if ticket_count < flight['seats']:
            ticket_id = str(uuid.uuid1())  # Changed from uuid.uuid4()
            cursor.execute("INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)", (ticket_id, airline_name, flight_num))
            cursor.execute("""
                INSERT INTO purchases (ticket_id, customer_email, booking_agent_id, purchase_date) 
                VALUES (%s, %s, (SELECT booking_agent_id FROM booking_agent WHERE email = %s), NOW())
            """, (ticket_id, customer_email, session['email']))
            conn.commit()
            flash('Ticket purchased successfully!', 'success')
        else:
            flash('No seats available!', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('booking_agent_dashboard'))
    cursor.execute("SELECT airline_name, flight_num FROM flight WHERE airline_name IN (SELECT airline_name FROM booking_agent_work_for WHERE email = %s)", (session['email'],))
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('booking_agent_purchase.html', flights=flights)

# Booking Agent View Top Customers
@app.route('/booking_agent/top_customers')
def booking_agent_top_customers():
    if 'user_type' not in session or session['user_type'] != 'booking_agent':
        flash('Please log in as a booking agent.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    query_tickets = """
        SELECT p.customer_email, COUNT(*) as ticket_count
        FROM purchases p
        WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
        AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY p.customer_email
        ORDER BY ticket_count DESC
        LIMIT 5
    """
    cursor.execute(query_tickets, (session['email'],))
    top_customers_tickets = cursor.fetchall()
    query_commission = """
        SELECT p.customer_email, SUM(f.price * 0.1) as commission
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
        AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        GROUP BY p.customer_email
        ORDER BY commission DESC
        LIMIT 5
    """
    cursor.execute(query_commission, (session['email'],))
    top_customers_commission = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('booking_agent_top_customers.html', top_customers_tickets=top_customers_tickets, top_customers_commission=top_customers_commission)

# Airline Staff Dashboard
@app.route('/airline_staff_dashboard')
def airline_staff_dashboard():
    if 'user_type' not in session or session['user_type'] != 'airline_staff':
        flash('Please log in as airline staff.', 'error')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM airline_staff WHERE username = %s", (session['username'],))
    staff = cursor.fetchone()
    query_flights = """
        SELECT f.* FROM flight f 
        WHERE f.airline_name = %s 
        AND f.departure_time BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 30 DAY)
    """
    cursor.execute(query_flights, (session['airline_name'],))
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('airline_staff_dashboard.html', staff=staff, flights=flights)

# Airline Staff Create Flight
@app.route('/airline_staff/create_flight', methods=['GET', 'POST'])
def create_flight():
    if 'user_type' not in session or session['user_type'] != 'airline_staff' or not has_permission(session['username'], 'Admin'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if request.method == 'POST':
            airline_name = session['airline_name']
            flight_num = request.form['flight_num']
            departure_airport = request.form['departure_airport']
            departure_time = request.form['departure_time']
            arrival_airport = request.form['arrival_airport']
            arrival_time = request.form['arrival_time']
            price = request.form['price']
            status = request.form['status']
            airplane_id = request.form['airplane_id']
            cursor.execute("SELECT 1 FROM flight WHERE airline_name = %s AND flight_num = %s", (airline_name, flight_num))
            if cursor.fetchone():
                flash(f'Flight {airline_name} {flight_num} already exists.', 'error')
            else:
                cursor.execute("""
                    INSERT INTO flight (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, price, status, airplane_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, price, status, airplane_id))
                conn.commit()
                flash('Flight created successfully!', 'success')
                return redirect(url_for('airline_staff_dashboard'))
        cursor.execute("SELECT airport_name FROM airport")
        airports = cursor.fetchall()
        cursor.execute("SELECT airplane_id FROM airplane WHERE airline_name = %s", (session['airline_name'],))
        airplanes = cursor.fetchall()
        return render_template('airline_staff_create_flight.html', airports=airports, airplanes=airplanes)
    except pymysql.MySQLError as e:
        conn.rollback()
        flash(f'Database error: {e}', 'error')
        cursor.execute("SELECT airport_name FROM airport")
        airports = cursor.fetchall()
        cursor.execute("SELECT airplane_id FROM airplane WHERE airline_name = %s", (session['airline_name'],))
        airplanes = cursor.fetchall()
        return render_template('airline_staff_create_flight.html', airports=airports, airplanes=airplanes)
    finally:
        if cursor: cursor.close()

# Airline Staff Change Flight Status
@app.route('/airline_staff/change_status', methods=['GET', 'POST'])
def change_status():
    if 'user_type' not in session or session['user_type'] != 'airline_staff' or not has_permission(session['username'], 'Operator'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        airline_name = request.form['airline_name']
        flight_num = request.form['flight_num']
        new_status = request.form['new_status']
        cursor.execute("UPDATE flight SET status = %s WHERE airline_name = %s AND flight_num = %s", (new_status, airline_name, flight_num))
        conn.commit()
        flash('Flight status updated successfully!', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('airline_staff_dashboard'))
    cursor.execute("SELECT airline_name, flight_num FROM flight WHERE airline_name = %s", (session['airline_name'],))
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('airline_staff_change_status.html', flights=flights)

# Airline Staff Add Airplane
@app.route('/airline_staff/add_airplane', methods=['GET', 'POST'])
def add_airplane():
    if 'user_type' not in session or session['user_type'] != 'airline_staff' or not has_permission(session['username'], 'Admin'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    airplanes = []
    try:
        if request.method == 'POST':
            airline_name = session['airline_name']
            airplane_id = request.form['airplane_id']
            seats = request.form['seats']
            cursor.execute("SELECT 1 FROM airplane WHERE airline_name = %s AND airplane_id = %s", (airline_name, airplane_id))
            if cursor.fetchone():
                flash(f'Airplane ID {airplane_id} already exists for {airline_name}.', 'error')
            else:
                cursor.execute("INSERT INTO airplane (airline_name, airplane_id, seats) VALUES (%s, %s, %s)", (airline_name, airplane_id, seats))
                conn.commit()
                flash('Airplane added successfully!', 'success')
                cursor.execute("SELECT * FROM airplane WHERE airline_name = %s", (airline_name,))
                airplanes = cursor.fetchall()
                return render_template('airline_staff_add_airplane.html', airplanes=airplanes, added=True)
        cursor.execute("SELECT * FROM airplane WHERE airline_name = %s", (session['airline_name'],))
        airplanes = cursor.fetchall()
        return render_template('airline_staff_add_airplane.html', airplanes=airplanes)
    except pymysql.MySQLError as e:
        conn.rollback()
        flash(f'Database error: {e}', 'error')
        cursor.execute("SELECT * FROM airplane WHERE airline_name = %s", (session['airline_name'],))
        airplanes = cursor.fetchall()
        return render_template('airline_staff_add_airplane.html', airplanes=airplanes)
    finally:
        if cursor: cursor.close()

# Airline Staff Add Airport
@app.route('/airline_staff/add_airport', methods=['GET', 'POST'])
def add_airport():
    if 'user_type' not in session or session['user_type'] != 'airline_staff' or not has_permission(session['username'], 'Admin'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        airport_name = request.form['airport_name']
        airport_city = request.form['airport_city']
        try:
            cursor.execute("SELECT airport_name FROM airport WHERE airport_name = %s", (airport_name,))
            if cursor.fetchone():
                flash(f'Airport "{airport_name}" already exists.', 'error')
            else:
                cursor.execute("INSERT INTO airport (airport_name, airport_city) VALUES (%s, %s)", (airport_name, airport_city))
                conn.commit()
                flash('Airport added successfully!', 'success')
                return redirect(url_for('airline_staff_dashboard'))
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'Database error: {e}', 'error')
        finally:
            cursor.close()
        return render_template('airline_staff_add_airport.html')
    return render_template('airline_staff_add_airport.html')

# Airline Staff View Booking Agents
@app.route('/airline_staff/view_booking_agents')
def view_booking_agents():
    if 'user_type' not in session or session['user_type'] != 'airline_staff':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    query_month = """
        SELECT ba.email, COUNT(*) as ticket_count
        FROM booking_agent ba
        JOIN purchases p ON p.booking_agent_id = ba.booking_agent_id
        WHERE p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
        AND ba.email IN (SELECT email FROM booking_agent_work_for WHERE airline_name = %s)
        GROUP BY ba.email
        ORDER BY ticket_count DESC
        LIMIT 5
    """
    cursor.execute(query_month, (session['airline_name'],))
    top_agents_month = cursor.fetchall()
    query_year = """
        SELECT ba.email, SUM(f.price * 0.1) as commission
        FROM booking_agent ba
        JOIN purchases p ON p.booking_agent_id = ba.booking_agent_id
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        AND ba.email IN (SELECT email FROM booking_agent_work_for WHERE airline_name = %s)
        GROUP BY ba.email
        ORDER BY commission DESC
        LIMIT 5
    """
    cursor.execute(query_year, (session['airline_name'],))
    top_agents_year = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('airline_staff_view_booking_agents.html', top_agents_month=top_agents_month, top_agents_year=top_agents_year)

# Airline Staff View Frequent Customers
@app.route('/airline_staff/view_frequent_customers')
def view_frequent_customers():
    if 'user_type' not in session or session['user_type'] != 'airline_staff':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT p.customer_email, COUNT(*) as flight_count
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s
        AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        GROUP BY p.customer_email
        ORDER BY flight_count DESC
        LIMIT 1
    """
    cursor.execute(query, (session['airline_name'],))
    frequent_customer = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('airline_staff_view_frequent_customers.html', frequent_customer=frequent_customer)

# Airline Staff View Reports
@app.route('/airline_staff/view_reports', methods=['GET', 'POST'])
def view_reports():
    if 'user_type' not in session or session['user_type'] != 'airline_staff':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
    else:
        start_date = 'DATE_SUB(NOW(), INTERVAL 1 YEAR)'
        end_date = 'NOW()'
    query = """
        SELECT COUNT(*) as ticket_count
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s AND p.purchase_date BETWEEN %s AND %s
    """
    cursor.execute(query, (session['airline_name'], start_date, end_date))
    ticket_count = cursor.fetchone()['ticket_count']
    monthly_query = """
        SELECT DATE_FORMAT(p.purchase_date, '%%Y-%%m') as month, COUNT(*) as tickets
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s AND p.purchase_date BETWEEN %s AND %s
        GROUP BY month
    """
    cursor.execute(monthly_query, (session['airline_name'], start_date, end_date))
    monthly_tickets = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('airline_staff_view_reports.html', ticket_count=ticket_count, monthly_tickets=monthly_tickets)

# Airline Staff Compare Revenue
@app.route('/airline_staff/compare_revenue')
def compare_revenue():
    if 'user_type' not in session or session['user_type'] != 'airline_staff':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    direct_query = """
        SELECT SUM(f.price) as direct_revenue
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s AND p.booking_agent_id IS NULL
        AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
    """
    cursor.execute(direct_query, (session['airline_name'],))
    direct_revenue = cursor.fetchone()['direct_revenue'] or 0
    indirect_query = """
        SELECT SUM(f.price) as indirect_revenue
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s AND p.booking_agent_id IS NOT NULL
        AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
    """
    cursor.execute(indirect_query, (session['airline_name'],))
    indirect_revenue = cursor.fetchone()['indirect_revenue'] or 0
    cursor.close()
    conn.close()
    return render_template('airline_staff_compare_revenue.html', direct_revenue=direct_revenue, indirect_revenue=indirect_revenue)

# Airline Staff View Top Destinations
@app.route('/airline_staff/view_top_destinations')
def view_top_destinations():
    if 'user_type' not in session or session['user_type'] != 'airline_staff':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    query_3months = """
        SELECT f.arrival_airport, COUNT(*) as flight_count
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
        GROUP BY f.arrival_airport
        ORDER BY flight_count DESC
        LIMIT 3
    """
    cursor.execute(query_3months, (session['airline_name'],))
    top_destinations_3months = cursor.fetchall()
    query_year = """
        SELECT f.arrival_airport, COUNT(*) as flight_count
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE f.airline_name = %s AND p.purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        GROUP BY f.arrival_airport
        ORDER BY flight_count DESC
        LIMIT 3
    """
    cursor.execute(query_year, (session['airline_name'],))
    top_destinations_year = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('airline_staff_view_top_destinations.html', top_destinations_3months=top_destinations_3months, top_destinations_year=top_destinations_year)

# Airline Staff Grant Permission
@app.route('/airline_staff/grant_permission', methods=['GET', 'POST'])
def grant_permission():
    if 'user_type' not in session or session['user_type'] != 'airline_staff' or not has_permission(session['username'], 'Admin'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    staff = []
    try:
        if request.method == 'POST':
            username = request.form['username']
            permission_type = request.form['permission_type']
            cursor.execute("SELECT 1 FROM airline_staff WHERE username = %s AND airline_name = %s", (username, session['airline_name']))
            if not cursor.fetchone():
                flash('Staff not found or not in your airline.', 'error')
            else:
                cursor.execute("SELECT 1 FROM permission WHERE username = %s AND permission_type = %s", (username, permission_type))
                if cursor.fetchone():
                    flash(f'User {username} already has {permission_type} permission.', 'error')
                else:
                    cursor.execute("INSERT INTO permission (username, permission_type) VALUES (%s, %s)", (username, permission_type))
                    conn.commit()
                    flash('Permission granted successfully!', 'success')
                    return redirect(url_for('airline_staff_dashboard'))
        cursor.execute("SELECT username FROM airline_staff WHERE airline_name = %s", (session['airline_name'],))
        staff = cursor.fetchall()
        return render_template('airline_staff_grant_permission.html', staff=staff)
    except pymysql.MySQLError as e:
        conn.rollback()
        flash(f'Database error: {e}', 'error')
        cursor.execute("SELECT username FROM airline_staff WHERE airline_name = %s", (session['airline_name'],))
        staff = cursor.fetchall()
        return render_template('airline_staff_grant_permission.html', staff=staff)
    finally:
        if cursor: cursor.close()

# Airline Staff Add Booking Agent
@app.route('/airline_staff/add_booking_agent', methods=['GET', 'POST'])
def add_booking_agent():
    if 'user_type' not in session or session['user_type'] != 'airline_staff' or not has_permission(session['username'], 'Admin'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('airline_staff_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if request.method == 'POST':
            email = request.form['email']
            airline_name = session['airline_name']
            cursor.execute("SELECT 1 FROM booking_agent WHERE email = %s", (email,))
            if not cursor.fetchone():
                flash('Booking agent email not found.', 'error')
            else:
                cursor.execute("SELECT 1 FROM booking_agent_work_for WHERE email = %s AND airline_name = %s", (email, airline_name))
                if cursor.fetchone():
                    flash(f'Booking agent {email} already works for {airline_name}.', 'error')
                else:
                    cursor.execute("INSERT INTO booking_agent_work_for (email, airline_name) VALUES (%s, %s)", (email, airline_name))
                    conn.commit()
                    flash('Booking agent added successfully!', 'success')
                    return redirect(url_for('airline_staff_dashboard'))
        return render_template('airline_staff_add_booking_agent.html')
    except pymysql.MySQLError as e:
        conn.rollback()
        flash(f'Database error: {e}', 'error')
        return render_template('airline_staff_add_booking_agent.html')
    finally:
        if cursor: cursor.close()

# Search Flights
@app.route('/search_flights', methods=['GET', 'POST'])
def search_flights():
    if request.method == 'POST':
        source = request.form['source']
        destination = request.form['destination']
        date = request.form.get('date')
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT f.* FROM flight f 
            JOIN airport depart ON f.departure_airport = depart.airport_name 
            JOIN airport arrive ON f.arrival_airport = arrive.airport_name 
            WHERE (depart.airport_name = %s OR depart.airport_city = %s) 
            AND (arrive.airport_name = %s OR arrive.airport_city = %s)
        """
        params = (source, source, destination, destination)
        if date:
            query += " AND DATE(f.departure_time) = %s"
            params += (date,)
        cursor.execute(query, params)
        flights = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('flight_results.html', flights=flights)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM airport")
    airports = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('search_flights.html', airports=airports)

# Purchase Ticket (Customer)
@app.route('/purchase/<airline_name>/<flight_num>', methods=['POST'])
def purchase_ticket(airline_name, flight_num):
    if 'user_type' not in session or session['user_type'] != 'customer':
        flash('Please log in as a customer.', 'error')
        return redirect(url_for('login'))
    customer_email = session['email']
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query_existing_ticket = """
            SELECT 1 FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            WHERE p.customer_email = %s AND t.airline_name = %s AND t.flight_num = %s
        """
        cursor.execute(query_existing_ticket, (customer_email, airline_name, flight_num))
        if cursor.fetchone():
            flash('You already have a ticket for this flight.', 'error')
            return redirect(url_for('customer_dashboard'))
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
            return redirect(url_for('customer_dashboard'))
        query_tickets = "SELECT COUNT(*) as ticket_count FROM ticket WHERE airline_name = %s AND flight_num = %s"
        cursor.execute(query_tickets, (airline_name, flight_num))
        ticket_count = cursor.fetchone()['ticket_count']
        if ticket_count < flight['seats']:
            ticket_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)", (ticket_id, airline_name, flight_num))
            cursor.execute("INSERT INTO purchases (ticket_id, customer_email, purchase_date) VALUES (%s, %s, NOW())", (ticket_id, customer_email))
            conn.commit()
            flash('Ticket purchased successfully!', 'success')
        else:
            flash('No seats available!', 'error')
    except pymysql.MySQLError as e:
        conn.rollback()
        flash(f'Database error: {e}', 'error')
    finally:
        cursor.close()
    return redirect(url_for('customer_dashboard'))

# Public Flight Status
@app.route('/flight_status', methods=['GET', 'POST'])
def flight_status():
    if request.method == 'POST':
        airline_name = request.form['airline_name']
        flight_num = request.form['flight_num']
        date = request.form['date']
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT status FROM flight WHERE airline_name = %s AND flight_num = %s AND DATE(departure_time) = %s"
        cursor.execute(query, (airline_name, flight_num, date))
        status = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template('flight_status.html', status=status['status'] if status else 'Not Found')
    return render_template('flight_status.html')

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000, ssl_context=('localhost.pem', 'localhost-key.pem'))