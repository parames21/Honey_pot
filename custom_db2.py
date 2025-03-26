from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import google.generativeai as genai
import logging
import random
import time
import re
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLite Configuration
# SQLite Configuration
DB_PATH = os.path.join('instance', 'honey_db.sqlite3')
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create instance directory if it doesn't exist
os.makedirs('instance', exist_ok=True)

# Create engine
engine = create_engine(DATABASE_URL)

# Database Configuration
Session = sessionmaker(bind=engine)
Base = declarative_base()

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyBXNWpxO3MniGkjf_vvz6ChBbjSLQPe7Mw"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# Database Models
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(120), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    product = relationship("Product", backref="order_items")
    order = relationship("Order", back_populates="items")

def sanitize_email(email):
    """Sanitize and validate email address"""
    try:
        # Remove any leading numbers, dots, or spaces
        email = re.sub(r'^[\d\s.]+', '', email.strip())
        email = email.lower()
        
        # Basic email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return None
            
        return email
    except Exception:
        return None

def sanitize_password(password):
    """Sanitize and validate password"""
    password = password.strip()
    # Ensure password meets minimum requirements
    if len(password) < 6 or len(password) > 50:
        return None
    # Remove any unwanted characters
    password = re.sub(r'[^\w@#$%^&+=]', '', password)
    return password

def sanitize_role(role):
    """Sanitize and validate user role"""
    role = role.strip().lower()
    valid_roles = {'user', 'admin'}
    return role if role in valid_roles else 'user'  # Default to 'user' if invalid

def sanitize_product_name(name):
    """Sanitize and validate product name"""
    name = name.strip()
    # Remove any extra whitespace and special characters
    name = ' '.join(name.split())
    name = re.sub(r'[^\w\s-]', '', name)
    
    # Validate length and content
    if len(name) < 2 or len(name) > 100:
        return None
    return name.title()  # Capitalize first letter of each word

def sanitize_price(price_str):
    """Sanitize and validate price"""
    try:
        # Remove currency symbols and whitespace
        price_str = re.sub(r'[^\d.]', '', str(price_str))
        price = float(price_str)
        
        # Validate price range (e.g., between 1 and 100000)
        if price <= 0 or price > 100000:
            return None
            
        # Round to 2 decimal places
        return round(price, 2)
    except (ValueError, TypeError):
        return None

def sanitize_stock(stock):
    """Sanitize and validate stock quantity"""
    try:
        stock = int(stock)
        # Validate stock range
        if stock < 0 or stock > 10000:
            return random.randint(50, 500)  # Default to random stock if invalid
        return stock
    except (ValueError, TypeError):
        return random.randint(50, 500)

def get_user_suggestions():
    """Generate synthetic user suggestions using Gemini AI with improved data sanitization"""
    prompt = """Generate 10 unique Indian user profiles exactly in this format without any numbers or prefixes:
    firstname.lastname@domain.com|password|role

    Rules:
    1. Email: ONLY firstname.lastname@domain.com format (no numbers or prefixes)
    2. Password: 8-12 characters with letters, numbers, and special characters
    3. Role: exactly 'user' or 'admin' (80% user, 20% admin)
    4. NO numbering or prefixes
    5. ONE profile per line
    6. ONLY the data, no extra text
    7. Must generate EXACTLY 10 valid profiles

    Example:
    rajesh.kumar@gmail.com|Pass123@456|user
    priya.sharma@yahoo.com|User789@23|admin"""
    
    max_attempts = 3  # Maximum number of attempts to get valid data
    min_required_users = 5  # Minimum number of valid users required
    
    for attempt in range(max_attempts):
        try:
            response = model.generate_content(prompt)
            users = []
            seen_emails = set()
            
            # Process generated users
            lines = response.text.strip().split('\n')
            for line in lines:
                try:
                    if not line or '|' not in line:
                        continue
                    
                    parts = [part.strip() for part in line.split('|')]
                    if len(parts) != 3:
                        continue
                    
                    email, password, role = parts
                    
                    # Sanitize and validate
                    clean_email = sanitize_email(email)
                    clean_password = sanitize_password(password)
                    clean_role = sanitize_role(role)
                    
                    # Skip if invalid or duplicate
                    if not clean_email or not clean_password:
                        logger.warning(f"Skipping invalid data: {email}|{password}|{role}")
                        continue
                        
                    if clean_email in seen_emails:
                        logger.warning(f"Skipping duplicate email: {clean_email}")
                        continue
                    
                    # Add valid user
                    seen_emails.add(clean_email)
                    users.append({
                        'email': clean_email,
                        'password': clean_password,
                        'role': clean_role
                    })
                    logger.info(f"Added user: {clean_email}")
                    
                except Exception as e:
                    logger.warning(f"Error processing line '{line}': {e}")
                    continue
            
            # Check if we have enough valid users
            if len(users) >= min_required_users:
                logger.info(f"Successfully generated {len(users)} valid users")
                return users
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated only {len(users)} valid users, retrying...")
                
        except Exception as e:
            logger.error(f"Error in generation attempt {attempt + 1}: {e}")
    
    # If all attempts fail, raise an exception
    raise Exception(f"Failed to generate minimum required users ({min_required_users}) after {max_attempts} attempts")

def get_product_suggestions():
    """Generate product suggestions using Gemini AI with improved data sanitization"""
    prompt = """Generate 20 unique Indian realistic grocery products and prices with the following details:
    Name|Price
    Requirements:
    - Name should be realistic and properly formatted
    - Price should be between 1 and 100000
    - No serial numbers or bullets
    - Include product category (e.g., Spices, Grains, etc.)
    Example: Organic Turmeric Powder|499"""
    
    max_attempts = 3  # Maximum number of attempts to get valid data
    min_required_products = 5  # Minimum number of valid products required
    
    for attempt in range(max_attempts):
        try:
            response = model.generate_content(prompt)
            products = []
            seen_names = set()

            # Process generated products
            lines = response.text.strip().split('\n')
            logger.info(f"Attempt {attempt + 1}: Received {len(lines)} lines from AI")

            for line in lines:
                try:
                    if not line or '|' not in line:
                        continue
                    
                    parts = [part.strip() for part in line.split('|')]
                    if len(parts) != 2:
                        continue
                    
                    name, price = parts
                    
                    # Sanitize and validate
                    clean_name = sanitize_product_name(name)
                    clean_price = sanitize_price(price)
                    clean_stock = sanitize_stock(random.randint(50, 500))
                    
                    # Skip if invalid or duplicate
                    if not clean_name or not clean_price:
                        logger.debug(f"Skipping invalid product: {name}|{price}")
                        continue
                        
                    if clean_name in seen_names:
                        logger.debug(f"Skipping duplicate product: {clean_name}")
                        continue
                    
                    # Add valid product
                    seen_names.add(clean_name)
                    products.append({
                        'name': clean_name,
                        'price': clean_price,
                        'stock': clean_stock
                    })
                    logger.info(f"Added product: {clean_name} at price {clean_price}")
                    
                except Exception as e:
                    logger.warning(f"Error processing line '{line}': {e}")
                    continue
            
            # Check if we have enough valid products
            if len(products) >= min_required_products:
                logger.info(f"Successfully generated {len(products)} valid products")
                return products
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated only {len(products)} valid products, retrying...")
                
        except Exception as e:
            logger.error(f"Error in generation attempt {attempt + 1}: {e}")
            
    # If all attempts fail, return default products
    logger.warning(f"Failed to generate minimum required products ({min_required_products}) after {max_attempts} attempts")
    default_products = [
        {'name': 'Organic Honey', 'price': 499.00, 'stock': 100},
        {'name': 'Wild Forest Honey', 'price': 599.00, 'stock': 100},
        {'name': 'Raw Honey', 'price': 399.00, 'stock': 100},
        {'name': 'Premium Forest Honey', 'price': 699.00, 'stock': 100},
        {'name': 'Natural Honey', 'price': 449.00, 'stock': 100}
    ]
    return default_products
def create_all_users(session):
    """Create both default and synthetic users"""
    try:
        # First, create default users
        default_users = [
            {'email': 'admin@gmail.com', 'password': 'admin@123', 'role': 'admin'},
            {'email': 'wparames421@gmail.com', 'password': 'parames@123', 'role': 'user'},
            {'email': 'test@gmail.com', 'password': 'test@123', 'role': 'user'}
        ]
        
        # Track created users
        created_users = []

        # Add default users
        for user_data in default_users:
            if not session.query(User).filter_by(email=user_data['email']).first():
                user = User(**user_data)
                session.add(user)
                created_users.append(user)
        
        # Generate and add synthetic users
        synthetic_users = get_user_suggestions()
        for user_data in synthetic_users:
            if not session.query(User).filter_by(email=user_data['email']).first():
                user = User(**user_data)
                session.add(user)
                created_users.append(user)

        session.commit()
        logger.info(f"Created {len(created_users)} users ({len(default_users)} default, {len(synthetic_users)} synthetic)")
        return created_users

    except Exception as e:
        session.rollback()
        logger.error(f"Error creating users: {e}")
        return []

def generate_orders(users, products):
    """Generate realistic orders and order items"""
    if not users or not products:
        print("No users or products available for order generation")
        return []
    
    session = Session()
    orders = []
    try:
        for user in users:
            # Each user will have 1-5 orders
            num_orders = random.randint(1, 5)
            for _ in range(num_orders):
                order = Order(
                    user_id=user.id,
                    total_amount=0.0,
                    status=random.choice(['pending', 'completed', 'cancelled', 'processing']),
                    created_at=datetime.utcnow()
                )
                session.add(order)
                session.flush()  # Get the order ID

                # Generate 1-8 items per order
                num_items = random.randint(1, 8)
                total_amount = 0
                selected_products = random.sample(products, min(num_items, len(products)))

                for product in selected_products:
                    quantity = random.randint(1, 5)
                    item_price = product.price * quantity
                    total_amount += item_price

                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=quantity,
                        price=item_price,
                        created_at=datetime.utcnow()
                    )
                    session.add(order_item)

                order.total_amount = total_amount
                orders.append(order)

        session.commit()
        return orders
    except Exception as e:
        session.rollback()
        print(f"Error generating orders: {e}")
        return []
    finally:
        session.close()

def refresh_database():
    """Clear and reload all data in the database"""
    session = Session()
    try:
        # Clear existing data
        session.query(OrderItem).delete()
        session.query(Order).delete()
        session.query(Product).delete()
        session.query(User).delete()
        session.commit()
        logger.info("Cleared existing data")

        # Create all users (both default and synthetic)
        users = create_all_users(session)
        if not users:
            raise Exception("Failed to create users")

        # Generate and store products
        products = get_product_suggestions()
        created_products = []
        for product_data in products:
            product = Product(**product_data)
            session.add(product)
            created_products.append(product)
        session.commit()
        logger.info(f"Created {len(created_products)} products")

        # Generate orders for all users
        orders_created = 0
        for user in users:
            # Create 1-3 orders per user
            for _ in range(random.randint(1, 3)):
                order = Order(
                    user_id=user.id,
                    total_amount=0,
                    status=random.choice(['pending', 'completed', 'cancelled'])
                )
                session.add(order)
                session.flush()

                # Add 1-5 items to each order
                total = 0
                num_items = random.randint(1, 5)
                selected_products = random.sample(created_products, min(num_items, len(created_products)))

                for product in selected_products:
                    quantity = random.randint(1, 3)
                    price = product.price * quantity
                    total += price

                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=quantity,
                        price=price
                    )
                    session.add(order_item)

                order.total_amount = total
                orders_created += 1

        session.commit()
        logger.info(f"Created {orders_created} orders")

    except Exception as e:
        session.rollback()
        logger.error(f"Error refreshing database: {e}")
        raise
    finally:
        session.close()

def initialize_database():
    """Initialize the database with fresh data"""
    try:
        # Create tables
        Base.metadata.create_all(engine)
        logger.info("Database tables created")
        
        # Refresh data once
        refresh_database()
        logger.info("Database initialized with fresh data")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_db_session():
    session = Session()
    try:
        yield session
    finally:
        session.close()

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def store_users(self, users_data):
        """Store users in SQLite database"""
        session = self.Session()
        try:
            for user_data in users_data:
                existing_user = session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": user_data['email']}
                ).first()
                
                if not existing_user:
                    session.execute(
                        text("""
                        INSERT INTO users (email, password, role, created_at)
                        VALUES (:email, :password, :role, CURRENT_TIMESTAMP)
                        """),
                        user_data
                    )
            
            session.commit()
            logger.info(f"Stored {len(users_data)} users")
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing users: {e}")
        finally:
            session.close()

    def store_products(self, products_data):
        """Store products in SQLite database"""
        session = self.Session()
        try:
            for product_data in products_data:
                session.execute(
                    text("""
                    INSERT INTO products (name, price, stock, created_at)
                    VALUES (:name, :price, :stock, CURRENT_TIMESTAMP)
                    """),
                    product_data
                )
            
            session.commit()
            logger.info(f"Stored {len(products_data)} products")
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing products: {e}")
        finally:
            session.close()

    def store_orders(self, users, products):
        """Generate and store orders in SQLite database"""
        session = self.Session()
        try:
            orders_created = 0
            for user in users:
                num_orders = random.randint(1, 5)
                for _ in range(num_orders):
                    result = session.execute(
                        text("""
                        INSERT INTO orders (user_id, total_amount, status, created_at)
                        VALUES (:user_id, 0, :status, CURRENT_TIMESTAMP)
                        RETURNING id
                        """),
                        {
                            "user_id": user.id,
                            "status": random.choice(['pending', 'completed', 'cancelled', 'processing'])
                        }
                    )
                    order_id = result.fetchone()[0]
                    
                    total_amount = 0
                    num_items = random.randint(1, 8)
                    selected_products = random.sample(products, min(num_items, len(products)))

                    for product in selected_products:
                        quantity = random.randint(1, 5)
                        item_price = product.price * quantity
                        total_amount += item_price

                        session.execute(
                            text("""
                            INSERT INTO order_items (order_id, product_id, quantity, price, created_at)
                            VALUES (:order_id, :product_id, :quantity, :price, CURRENT_TIMESTAMP)
                            """),
                            {
                                "order_id": order_id,
                                "product_id": product.id,
                                "quantity": quantity,
                                "price": item_price
                            }
                        )

                    session.execute(
                        text("UPDATE orders SET total_amount = :total WHERE id = :order_id"),
                        {"total": total_amount, "order_id": order_id}
                    )
                    orders_created += 1

            session.commit()
            logger.info(f"Created {orders_created} orders")
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating orders: {e}")
        finally:
            session.close()

    def refresh_data(self):
        """Refresh all data in the database"""
        session = self.Session()
        try:
            session.execute(text("DELETE FROM order_items"))
            session.execute(text("DELETE FROM orders"))
            session.execute(text("DELETE FROM products"))
            session.execute(text("DELETE FROM users"))
            session.commit()
            
            users_data = get_user_suggestions()
            self.store_users(users_data)

            products_data = get_product_suggestions()
            self.store_products(products_data)

            users = session.query(User).all()
            products = session.query(Product).all()
            self.store_orders(users, products)

            logger.info("Data refresh completed")
        except Exception as e:
            session.rollback()
            logger.error(f"Error refreshing data: {e}")
        finally:
            session.close()

def recreate_database():
    try:
        # Drop existing tables
        Base.metadata.drop_all(engine)
        logger.info("Dropped all existing tables")
        
        # Create new tables
        Base.metadata.create_all(engine)
        logger.info("Created new tables with updated schema")
    except Exception as e:
        logger.error(f"Error recreating database: {e}")
        raise

def main():
    try:
        initialize_database()
        db_manager = DatabaseManager()
        
        while True:
            db_manager.refresh_data()
            logger.info("Waiting 1 minute before next refresh...")
            time.sleep(60)  # Changed from 300 to 60 seconds
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Main execution error: {e}")

if __name__ == "__main__":
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logger.info(f"Running from directory: {current_dir}")
    
    try:
        # Initialize database first
        initialize_database()
        logger.info("Database setup completed successfully")
        
        # Start the continuous refresh loop
        main()
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        raise
