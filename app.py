from flask import Flask, render_template, request, session, redirect, url_for
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

def get_db_connection():
    connection = pymysql.connect(
        host='127.0.0.1',
        user='root',  # Replace with your MySQL username
        password='',  # Replace with your MySQL password
        db='flight',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

def has_permission(username, permission_type):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM permission WHERE username = %s AND permission_type = %s", (username, permission_type))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result is not None

# Public Routes
@app.route('/search_flights', methods=['GET', 'POST'])
def search_flights():
    if request.method == 'POST':
        source = request.form['source']
        destination = request.form['destination']
        date = request.form['date']
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
        SELECT * FROM flight
        WHERE departure_airport = %s
        AND arrival_airport = %s
        AND DATE(departure_time) = %s
        AND status = 'upcoming'
        """
        cursor.execute(query, (source, destination, date))
        flights = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('search_results.html', flights=flights)
    return render_template('search_flights.html')

@app.route('/flight_status', methods=['GET', 'POST'])
def flight_status():
    if request.method == 'POST':
        flight_num = request.form['flight_num']
        date = request.form['date']
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
        SELECT status FROM flight
        WHERE flight_num = %s
        AND DATE(departure_time) = %s
        """
        cursor.execute(query, (flight_num, date))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        if result:
            return render_template('flight_status.html', status=result['status'])
        return render_template('flight_status.html', error="Flight not found")
    return render_template('flight_status.html')

# Registration Routes
@app.route('/register_customer', methods=['GET', 'POST'])
def register_customer():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        building_number = request.form['building_number']
        street = request.form['street']
        city = request.form['city']
        state = request.form['state']
        phone_number = request.form['phone_number']
        passport_number = request.form['passport_number']
        passport_expiration = request.form['passport_expiration']
        passport_country = request.form['passport_country']
        date_of_birth = request.form['date_of_birth']
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO customer (email, name, password, building_number, street, city, state, phone_number,
                passport_number, passport_expiration, passport_country, date_of_birth)
                VALUES (%s, %s, MD5(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (email, name, password, building_number, street, city, state, phone_number, passport_number,
                  passport_expiration, passport_country, date_of_birth))
            connection.commit()
            return redirect(url_for('login'))
        except Exception as e:
            connection.rollback()
            return render_template('register_customer.html', error=str(e))
        finally:
            cursor.close()
            connection.close()
    return render_template('register_customer.html')

@app.route('/register_booking_agent', methods=['GET', 'POST'])
def register_booking_agent():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        booking_agent_id = request.form['booking_agent_id']
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO booking_agent (email, password, booking_agent_id) VALUES (%s, MD5(%s), %s)",
                           (email, password, booking_agent_id))
            connection.commit()
            return redirect(url_for('login'))
        except Exception as e:
            connection.rollback()
            return render_template('register_booking_agent.html', error=str(e))
        finally:
            cursor.close()
            connection.close()
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
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO airline_staff (username, password, first_name, last_name, date_of_birth, airline_name)
                VALUES (%s, MD5(%s), %s, %s, %s, %s)
            """, (username, password, first_name, last_name, date_of_birth, airline_name))
            connection.commit()
            return redirect(url_for('login'))
        except Exception as e:
            connection.rollback()
            return render_template('register_airline_staff.html', error=str(e))
        finally:
            cursor.close()
            connection.close()
    return render_template('register_airline_staff.html')

# Login
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']
        connection = get_db_connection()
        cursor = connection.cursor()
        if user_type == 'customer':
            query = "SELECT * FROM customer WHERE email = %s AND password = MD5(%s)"
        elif user_type == 'booking_agent':
            query = "SELECT * FROM booking_agent WHERE email = %s AND password = MD5(%s)"
        elif user_type == 'airline_staff':
            query = "SELECT * FROM airline_staff WHERE username = %s AND password = MD5(%s)"
        else:
            return render_template('login.html', error="Invalid user type")
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        if user:
            session['username'] = username
            session['user_type'] = user_type
            if user_type == 'airline_staff':
                session['airline_name'] = user['airline_name']
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

# Home Page
@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_type = session['user_type']
    if user_type == 'customer':
        return render_template('customer_home.html', username=session['username'])
    elif user_type == 'booking_agent':
        return render_template('booking_agent_home.html', username=session['username'])
    elif user_type == 'airline_staff':
        return render_template('airline_staff_home.html', username=session['username'])
    return redirect(url_for('login'))

# Customer Features
@app.route('/my_flights')
def my_flights():
    if 'username' not in session or session['user_type'] != 'customer':
        return redirect(url_for('login'))
    customer_email = session['username']
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
    SELECT f.* FROM flight f
    JOIN ticket t ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
    JOIN purchases p ON t.ticket_id = p.ticket_id
    WHERE p.customer_email = %s
    AND f.departure_time > NOW()
    """
    cursor.execute(query, (customer_email,))
    flights = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('my_flights.html', flights=flights)

@app.route('/purchase_ticket/<airline_name>/<flight_num>', methods=['GET', 'POST'])
def purchase_ticket(airline_name, flight_num):
    if 'username' not in session or session['user_type'] != 'customer':
        return redirect(url_for('login'))
    if request.method == 'POST':
        customer_email = session['username']
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) as sold_tickets
                FROM ticket t
                WHERE t.airline_name = %s AND t.flight_num = %s
            """, (airline_name, flight_num))
            sold_tickets = cursor.fetchone()['sold_tickets']
            cursor.execute("""
                SELECT a.seats
                FROM airplane a
                JOIN flight f ON a.airline_name = f.airline_name AND a.airplane_id = f.airplane_id
                WHERE f.airline_name = %s AND f.flight_num = %s
            """, (airline_name, flight_num))
            total_seats = cursor.fetchone()['seats']
            if sold_tickets >= total_seats:
                return render_template('purchase_ticket.html', error="No seats available", airline_name=airline_name, flight_num=flight_num)
            cursor.execute("SELECT MAX(ticket_id) as max_id FROM ticket")
            max_id = cursor.fetchone()['max_id']
            new_ticket_id = max_id + 1 if max_id else 1
            cursor.execute("INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)",
                           (new_ticket_id, airline_name, flight_num))
            cursor.execute("INSERT INTO purchases (ticket_id, customer_email, purchase_date) VALUES (%s, %s, CURDATE())",
                           (new_ticket_id, customer_email))
            connection.commit()
            return redirect(url_for('my_flights'))
        except Exception as e:
            connection.rollback()
            return render_template('purchase_ticket.html', error=str(e), airline_name=airline_name, flight_num=flight_num)
        finally:
            cursor.close()
            connection.close()
    return render_template('purchase_ticket.html', airline_name=airline_name, flight_num=flight_num)

@app.route('/track_spending', methods=['GET', 'POST'])
def track_spending():
    if 'username' not in session or session['user_type'] != 'customer':
        return redirect(url_for('login'))
    customer_email = session['username']
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT SUM(f.price) as total_spent
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.customer_email = %s
        AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
    """, (customer_email,))
    total_spent = cursor.fetchone()['total_spent'] or 0
    cursor.execute("""
        SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') as month, SUM(f.price) as spent
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        WHERE p.customer_email = %s
        AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY month
        ORDER BY month
    """, (customer_email,))
    monthly_spending = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('track_spending.html', total_spent=total_spent, monthly_spending=monthly_spending)

# Booking Agent Features
@app.route('/agent_flights')
def agent_flights():
    if 'username' not in session or session['user_type'] != 'booking_agent':
        return redirect(url_for('login'))
    booking_agent_email = session['username']
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
    SELECT f.*, p.customer_email
    FROM flight f
    JOIN ticket t ON f.airline_name = t.airline_name AND f.flight_num = t.flight_num
    JOIN purchases p ON t.ticket_id = p.ticket_id
    JOIN booking_agent ba ON p.booking_agent_id = ba.booking_agent_id
    WHERE ba.email = %s
    AND f.departure_time > NOW()
    """
    cursor.execute(query, (booking_agent_email,))
    flights = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('agent_flights.html', flights=flights)

@app.route('/agent_purchase_ticket/<airline_name>/<flight_num>', methods=['GET', 'POST'])
def agent_purchase_ticket(airline_name, flight_num):
    if 'username' not in session or session['user_type'] != 'booking_agent':
        return redirect(url_for('login'))
    booking_agent_email = session['username']
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM booking_agent_work_for WHERE email = %s AND airline_name = %s",
                   (booking_agent_email, airline_name))
    if not cursor.fetchone():
        cursor.close()
        connection.close()
        return render_template('agent_purchase_ticket.html', error="You do not work for this airline", airline_name=airline_name, flight_num=flight_num)
    if request.method == 'POST':
        customer_email = request.form['customer_email']
        cursor.execute("SELECT * FROM customer WHERE email = %s", (customer_email,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return render_template('agent_purchase_ticket.html', error="Customer not found", airline_name=airline_name, flight_num=flight_num)
        try:
            cursor.execute("""
                SELECT COUNT(*) as sold_tickets
                FROM ticket t
                WHERE t.airline_name = %s AND t.flight_num = %s
            """, (airline_name, flight_num))
            sold_tickets = cursor.fetchone()['sold_tickets']
            cursor.execute("""
                SELECT a.seats
                FROM airplane a
                JOIN flight f ON a.airline_name = f.airline_name AND a.airplane_id = f.airplane_id
                WHERE f.airline_name = %s AND f.flight_num = %s
            """, (airline_name, flight_num))
            total_seats = cursor.fetchone()['seats']
            if sold_tickets >= total_seats:
                return render_template('agent_purchase_ticket.html', error="No seats available", airline_name=airline_name, flight_num=flight_num)
            cursor.execute("SELECT booking_agent_id FROM booking_agent WHERE email = %s", (booking_agent_email,))
            booking_agent_id = cursor.fetchone()['booking_agent_id']
            cursor.execute("SELECT MAX(ticket_id) as max_id FROM ticket")
            max_id = cursor.fetchone()['max_id']
            new_ticket_id = max_id + 1 if max_id else 1
            cursor.execute("INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)",
                           (new_ticket_id, airline_name, flight_num))
            cursor.execute("INSERT INTO purchases (ticket_id, customer_email, booking_agent_id, purchase_date) VALUES (%s, %s, %s, CURDATE())",
                           (new_ticket_id, customer_email, booking_agent_id))
            connection.commit()
            return redirect(url_for('agent_flights'))
        except Exception as e:
            connection.rollback()
            return render_template('agent_purchase_ticket.html', error=str(e), airline_name=airline_name, flight_num=flight_num)
        finally:
            cursor.close()
            connection.close()
    cursor.close()
    connection.close()
    return render_template('agent_purchase_ticket.html', airline_name=airline_name, flight_num=flight_num)

@app.route('/commission_report')
def commission_report():
    if 'username' not in session or session['user_type'] != 'booking_agent':
        return redirect(url_for('login'))
    booking_agent_email = session['username']
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COUNT(*) as tickets, SUM(f.price) * 0.1 as total_commission
        FROM purchases p
        JOIN ticket t ON p.ticket_id = t.ticket_id
        JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
        JOIN booking_agent ba ON p.booking_agent_id = ba.booking_agent_id
        WHERE ba.email = %s
        AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, (booking_agent_email,))
    report = cursor.fetchone()
    total_commission = report['total_commission'] or 0
    tickets = report['tickets']
    avg_commission = total_commission / tickets if tickets > 0 else 0
    cursor.close()
    connection.close()
    return render_template('commission_report.html', total_commission=total_commission, tickets=tickets, avg_commission=avg_commission)

# Airline Staff Features
@app.route('/staff_flights', methods=['GET', 'POST'])
def staff_flights():
    if 'username' not in session or session['user_type'] != 'airline_staff':
        return redirect(url_for('login'))
    airline_name = session['airline_name']
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
    SELECT * FROM flight
    WHERE airline_name = %s
    AND departure_time BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 30 DAY)
    """
    cursor.execute(query, (airline_name,))
    flights = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('staff_flights.html', flights=flights)

@app.route('/create_flight', methods=['GET', 'POST'])
def create_flight():
    if 'username' not in session or session['user_type'] != 'airline_staff':
        return redirect(url_for('login'))
    username = session['username']
    if not has_permission(username, 'Admin'):
        return render_template('create_flight.html', error="No permission to create flights")
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
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO flight (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, price, status, airplane_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, price, status, airplane_id))
            connection.commit()
            return redirect(url_for('staff_flights'))
        except Exception as e:
            connection.rollback()
            return render_template('create_flight.html', error=str(e))
        finally:
            cursor.close()
            connection.close()
    return render_template('create_flight.html')

@app.route('/change_status/<flight_num>', methods=['GET', 'POST'])
def change_status(flight_num):
    if 'username' not in session or session['user_type'] != 'airline_staff':
        return redirect(url_for('login'))
    username = session['username']
    if not has_permission(username, 'Operator'):
        return render_template('change_status.html', error="No permission to change status", flight_num=flight_num)
    airline_name = session['airline_name']
    if request.method == 'POST':
        new_status = request.form['status']
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE flight SET status = %s WHERE airline_name = %s AND flight_num = %s",
                           (new_status, airline_name, flight_num))
            connection.commit()
            return redirect(url_for('staff_flights'))
        except Exception as e:
            connection.rollback()
            return render_template('change_status.html', error=str(e), flight_num=flight_num)
        finally:
            cursor.close()
            connection.close()
    return render_template('change_status.html', flight_num=flight_num)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)