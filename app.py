import threading
import subprocess
import sys
import os
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
from flask_migrate import Migrate
import time
import logging
from werkzeug.security import generate_password_hash, check_password_hash  # Added for proper password handling

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask application
def initialize_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///honey_db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'parames@123'
    return app

# Initialize app first, then database
app = initialize_app()
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Define models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    orders = db.relationship('Order', backref='user', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    items = db.relationship('OrderItem', backref='order', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Log HTTP requests and responses
@app.before_request
def log_request_info():
    logging.info(f"Request: {request.method} {request.url} from {request.remote_addr}")

@app.after_request
def log_response_info(response):
    logging.info(f"Response: {response.status_code}, Body: {response.get_data(as_text=True)[:100]}")
    return response

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Access denied.')
            return redirect(url_for('home'))  # Changed to 'home' for consistency
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('dashboard'))
            return redirect(url_for('buy'))
        
        flash('Invalid credentials.')
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email is already in use.')
            logging.warning(f"Attempted signup with existing email: {email}")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password, role='user')

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Signup successful! Please log in.')
            logging.info(f"New user {email} signed up successfully.")
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Error during signup. Please try again.')
            logging.error(f"Error saving new user: {e}")
    return render_template('index.html')

@app.route('/logout')
def logout():
    user_id = session.pop('user_id', None)
    session.pop('role', None)
    session.pop('cart', None)
    logging.info(f"User {user_id} logged out.")
    return redirect(url_for('home'))

@app.route('/buy')
@login_required
def buy():
    products = Product.query.filter(Product.stock > 0).all()
    
    total = 0
    if 'cart' in session and session['cart']:
        total = sum(item['price'] * item['quantity'] for item in session['cart'])
    
    return render_template('buy.html', products=products, total=total)

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form['product_id']
    product = Product.query.get(product_id)

    if not product:
        flash('Product not found.')
        return redirect(url_for('buy'))

    if product.stock <= 0:
        flash('Product is out of stock.')
        logging.warning(f"Attempt to add out-of-stock product {product.name} to cart by user {session['user_id']}.")
        return redirect(url_for('buy'))

    cart_item = {
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'quantity': 1
    }

    if 'cart' not in session:
        session['cart'] = []

    for item in session['cart']:
        if item['id'] == product.id:
            if product.stock < item['quantity'] + 1:
                flash(f'Only {product.stock} {product.name} left in stock.')
                return redirect(url_for('buy'))
            item['quantity'] += 1
            break
    else:
        session['cart'].append(cart_item)

    session.modified = True
    flash(f'{product.name} added to cart.')
    logging.info(f"Product {product.name} added to cart by user {session['user_id']}.")
    return redirect(url_for('buy'))

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    try:
        if 'cart' not in session or not session['cart']:
            flash('Cart is empty.')
            return redirect(url_for('buy'))

        # Verify stock one last time
        for item in session['cart']:
            product = Product.query.get(item['id'])
            if product.stock < item['quantity']:
                flash(f'Not enough stock for {product.name}. Only {product.stock} available.')
                return redirect(url_for('buy'))

        total_amount = sum(item['price'] * item['quantity'] for item in session['cart'])
        new_order = Order(user_id=session['user_id'], total_amount=total_amount, status='pending')
        db.session.add(new_order)
        db.session.flush()

        for item in session['cart']:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item['id'],
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)

            product = Product.query.get(item['id'])
            product.stock -= item['quantity']

        db.session.commit()
        session.pop('cart')
        flash('Order placed successfully.')
        logging.info(f"Order {new_order.id} placed by user {session['user_id']}.")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error placing order: {e}")
        flash('Error placing order.')
    return redirect(url_for('buy'))

@app.route('/dashboard')
@admin_required
def dashboard():
    products = Product.query.all()
    return render_template('dashboard.html', products=products)

@app.route('/product', methods=['POST'])
@admin_required
def product():
    try:
        name = request.form['name']
        price = request.form['price']
        stock = request.form['stock']
        product_id = request.form.get('product_id')

        # Input validation
        try:
            price = float(price)
            stock = int(stock)
            if price < 0 or stock < 0:
                raise ValueError
        except ValueError:
            flash('Price and stock must be positive numbers.')
            return redirect(url_for('dashboard'))

        if product_id:
            product = Product.query.get(product_id)
            if not product:
                flash('Product not found.')
                return redirect(url_for('dashboard'))
            product.name = name
            product.price = price
            product.stock = stock
        else:
            new_product = Product(name=name, price=price, stock=stock)
            db.session.add(new_product)

        db.session.commit()
        flash('Product saved successfully.')
        logging.info(f"Product {name} saved/updated successfully.")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving product: {e}")
        flash('Error saving product.')
    return redirect(url_for('dashboard'))

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    try:
        product = Product.query.get(product_id)
        if not product:
            flash('Product not found.')
            return redirect(url_for('dashboard'))
        
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully.')
        logging.info(f"Product {product_id} deleted.")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting product: {e}")
        flash('Error deleting product.')
    return redirect(url_for('dashboard'))

# Start Flask app with monitoring
def run_custom_db2():
    """Run the database management script (custom_db2.py)"""
    while True:
        try:
            subprocess.run([sys.executable, 'custom_db2.py'], check=True)
            time.sleep(120)
        except subprocess.CalledProcessError as e:
            logging.error(f"Database refresh error: {e}")
            time.sleep(60)
        except Exception as e:
            logging.error(f"Unexpected error in DB thread: {e}")
            time.sleep(60)

# Start Flask app with monitoring
def start_app():
    try:
        # Create and start the DB thread
        db_thread = threading.Thread(target=run_custom_db2, daemon=True)
        db_thread.start()
        
        # Start Flask app
        logging.info("Starting Flask application...")
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    
    except KeyboardInterrupt:
        logging.info("Shutting down application...")
    except Exception as e:
        logging.error(f"Error in main thread: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_app()
