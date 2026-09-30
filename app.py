# app.py
# ------------------------------------------------------
# Day 1: Basic Flask Setup + MySQL Database Connection
# ------------------------------------------------------

from flask import Flask, render_template, request, redirect, session, flash,url_for,make_response
from flask_mail import Mail, Message
import mysql.connector
import bcrypt
import random
import config
import razorpay
import os
import traceback
from utils.pdf_generator import generate_pdf
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
# ------------------- IMAGE UPLOAD CONFIGURATIONS -------------------
UPLOAD_FOLDER = 'static/uploads/product_images'
ADMIN_UPLOAD_FOLDER = 'static/uploads/admin_images'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER  

# ---------------- EMAIL CONFIGURATION ----------------
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD

mail = Mail(app)


# ---------------- DB CONNECTION FUNCTION --------------
def get_db_connection():
    return mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )


# ---------------------------------------------------------
# ROUTE 1: ADMIN SIGNUP (SEND OTP)
# ---------------------------------------------------------
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():

    # Show form
    if request.method == "GET":
        return render_template("admin/admin_signup.html")

    # POST → Process signup
    name = request.form['name']
    email = request.form['email']

    # 1️⃣ Check if admin email already exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT admin_id FROM admin WHERE email=%s", (email,))
    existing_admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing_admin:
        flash("This email is already registered. Please login instead.", "danger")
        return redirect('/admin-signup')

    # 2️⃣ Save user input temporarily in session
    session['signup_name'] = name
    session['signup_email'] = email

    # 3️⃣ Generate OTP and store in session
    otp = random.randint(100000, 999999)
    session['otp'] = otp

    # 4️⃣ Send OTP Email
    message = Message(
        subject="SmartCart Admin OTP",
        sender=config.MAIL_USERNAME,
        recipients=[email]
    )
    message.body = f"Your OTP for SmartCart Admin Registration is: {otp}"
    mail.send(message)

    flash("OTP sent to your email!", "success")
    return redirect('/verify-otp')



# ---------------------------------------------------------
# ROUTE 2: DISPLAY OTP PAGE
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():
    return render_template("admin/verify_otp.html")



# ---------------------------------------------------------
# ROUTE 3: VERIFY OTP + SAVE ADMIN
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():
    
    # User submitted OTP + Password
    user_otp = request.form['otp']
    password = request.form['password']

    # Compare OTP
    if str(session.get('otp')) != str(user_otp):
        flash("Invalid OTP. Try again!", "danger")
        return redirect('/verify-otp')

    # Hash password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert admin into database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin (name, email, password) VALUES (%s, %s, %s)",
        (session['signup_name'], session['signup_email'], hashed_password)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Clear temporary session data
    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash("Admin Registered Successfully!", "success")
    return redirect('/admin-signup')


# =================================================================
# ROUTE 4: ADMIN LOGIN PAGE (GET + POST)
# =================================================================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    # Show login page
    if request.method == 'GET':
        return render_template("admin/admin_login.html")

    # POST → Validate login
    email = request.form['email']
    password = request.form['password']

    # Step 1: Check if admin email exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if admin is None:
        flash("Email not found! Please register first.", "danger")
        return redirect('/admin-login')

    # Step 2: Compare entered password with hashed password
    stored_hashed_password = admin['password'].encode('utf-8')

    if not bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/admin-login')

    # Step 5: If login success → Create admin session
    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']

    flash("Login Successful!", "success")
    return redirect('/admin-dashboard')



# =================================================================
# ROUTE 5: ADMIN DASHBOARD (PROTECTED ROUTE)
# =================================================================
@app.route('/admin-dashboard')
def admin_dashboard():

    # Protect dashboard → Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login to access dashboard!", "danger")
        return redirect('/admin-login')

    # Send admin name to dashboard UI
    return render_template("admin/dashboard.html", admin_name=session['admin_name'])



# =================================================================
# ROUTE 6: ADMIN LOGOUT
# =================================================================
@app.route('/admin-logout')
def admin_logout():

    # Clear admin session
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)

    flash("Logged out successfully.", "success")
    return redirect('/admin-login')


# =================================================================
# ROUTE 7: SHOW ADD PRODUCT PAGE (Protected Route)
# =================================================================
@app.route('/admin/add-item', methods=['GET'])
def add_item_page():

    # Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    return render_template("admin/add_item.html")




import os
from werkzeug.utils import secure_filename

# ------------------- IMAGE UPLOAD PATH -------------------
UPLOAD_FOLDER = 'static/uploads/product_images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =================================================================
# ROUTE 8: ADD PRODUCT INTO DATABASE
# =================================================================
@app.route('/admin/add-item', methods=['POST'])
def add_item():

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    # 1️⃣ Get form data
    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']
    image_file = request.files['image']

    # 2️⃣ Validate image upload
    if image_file.filename == "":
        flash("Please upload a product image!", "danger")
        return redirect('/admin/add-item')

    # 3️⃣ Secure the file name
    filename = secure_filename(image_file.filename)

    # 4️⃣ Create full path
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # 5️⃣ Save image into folder
    image_file.save(image_path)

    # 6️⃣ Insert product into database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO products (name, description, category, price, image) VALUES (%s, %s, %s, %s, %s)",
        (name, description, category, price, filename)
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Product added successfully!", "success")
    return redirect('/admin/add-item')


# =================================================================
# ROUTE 9: DISPLAY ALL PRODUCTS (Admin)
# =================================================================
@app.route('/admin/item-list')
def item_list():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Fetch category list for dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    # 2️⃣ Build dynamic query based on filters
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE %s"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = %s"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories
    )




#=================================================================
# ROUTE 10: VIEW SINGLE PRODUCT DETAILS
# =================================================================
@app.route('/admin/view-item/<int:item_id>')
def view_item(item_id):

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/view_item.html", product=product)


# =================================================================
# ROUTE 11: SHOW UPDATE FORM WITH EXISTING DATA
# =================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['GET'])
def update_item_page(item_id):

    # Check login
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # Fetch product data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/update_item.html", product=product)

# =================================================================
# ROUTE-12: UPDATE PRODUCT + GET FORM PRE-FILL
# =================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['GET', 'POST']) # <-- Added 'GET' here
def update_item(item_id):

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch old product data first regardless of method
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        conn.close()
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    # ─── CASE 1: USER SUBMITTED THE MODIFICATION FORM (POST) ───
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        price = request.form['price']
        new_image = request.files['image']

        old_image_name = product['image']

        # If admin uploaded a new image → replace it
        if new_image and new_image.filename != "":
            new_filename = secure_filename(new_image.filename)
            new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            new_image.save(new_image_path)

            old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image_name)
            if os.path.exists(old_image_path):
                os.remove(old_image_path)

            final_image_name = new_filename
        else:
            final_image_name = old_image_name

        # Update product in the database
        cursor.execute("""
            UPDATE products
            SET name=%s, description=%s, category=%s, price=%s, image=%s
            WHERE product_id=%s
        """, (name, description, category, price, final_image_name, item_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Product updated successfully!", "success")
        return redirect('/admin/item-list')

    # ─── CASE 2: USER IS VISITING THE PAGE TO VIEW THE EDIT FORM (GET) ───
    cursor.close()
    conn.close()
    return render_template("admin/update_item.html", product=product)

# ROUTE 13: DELETE PRODUCT  ← Write it here
# =================================================================
# ROUTE 13: DELETE PRODUCT (Fixed for Foreign Key constraints)
# =================================================================
@app.route('/admin/delete-item/<int:item_id>')
def delete_item(item_id):

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1️⃣ Fetch the product to get its image filename
        cursor.execute("SELECT image FROM products WHERE product_id=%s", (item_id,))
        product = cursor.fetchone()

        if product:
            # 2️⃣ Clear references in the cart table first to satisfy the constraint
            cursor.execute("DELETE FROM cart WHERE product_id=%s", (item_id,))
            
            # 3️⃣ Now safe to delete the product from the main table
            cursor.execute("DELETE FROM products WHERE product_id=%s", (item_id,))
            
            # 4️⃣ Commit database changes
            conn.commit()

            # 5️⃣ Remove physical file from system
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image'])
            if os.path.exists(image_path):
                os.remove(image_path)

            flash("Product deleted successfully!", "success")
        else:
            flash("Product not found!", "danger")

    except Exception as e:
        conn.rollback()
        app.logger.error("Deletion failed: %s", str(e))
        flash("Could not delete item due to an active user order history record.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect('/admin/item-list')
# =================================================================
# ROUTE 14: SHOW ADMIN PROFILE DATA
# =================================================================
@app.route('/admin/profile', methods=['GET'])
def admin_profile():
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/admin_profile.html", admin=admin)

# ROUTE 15: UPDATE ADMIN PROFILE (NAME, EMAIL, PASSWORD, IMAGE)
# =================================================================
@app.route('/admin/profile', methods=['POST'])
def admin_profile_update():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    # 1️⃣ Get form data
    name = request.form['name']
    email = request.form['email']
    new_password = request.form['password']
    new_image = request.files['profile_image']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 2️⃣ Fetch old admin data
    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cursor.fetchone()

    old_image_name = admin['profile_image']

    # 3️⃣ Update password only if entered (Added .decode('utf-8') for database compatibility)
    if new_password:
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    else:
        hashed_password = admin['password']  # keep old password

    # 4️⃣ Process new profile image if uploaded
    if new_image and new_image.filename != "":
        
        from werkzeug.utils import secure_filename
        new_filename = secure_filename(new_image.filename)

        # ─── CRITICAL FIX: AUTOMATICALLY CREATE THE DIRECTORY IF IT IS MISSING ───
        if not os.path.exists(app.config['ADMIN_UPLOAD_FOLDER']):
            os.makedirs(app.config['ADMIN_UPLOAD_FOLDER'], exist_ok=True)

        # Save new image
        image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], new_filename)
        new_image.save(image_path)

        # Delete old image safely
        if old_image_name:
            old_image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], old_image_name)
            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        final_image_name = new_filename
    else:
        final_image_name = old_image_name

    # 5️⃣ Update database
    cursor.execute("""
        UPDATE admin
        SET name=%s, email=%s, password=%s, profile_image=%s
        WHERE admin_id=%s
    """, (name, email, hashed_password, final_image_name, admin_id))

    conn.commit()
    cursor.close()
    conn.close()

    # Update session name for UI consistency
    session['admin_name'] = name  
    session['admin_email'] = email

    flash("Profile updated successfully!", "success")
    return redirect('/admin/profile')
# =================================================================
# ROUTE: USER REGISTRATION
# =================================================================
# =================================================================
# ROUTE: USER REGISTRATION (SENDS VERIFICATION OTP)
# =================================================================
@app.route('/user-register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'GET':
        return render_template("user/user_register.html")

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    # 1️⃣ Check if user already exists in SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    existing_user = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing_user:
        flash("Email already registered! Please login.", "danger")
        return redirect('/user-register')

    # 2️⃣ Save user parameters temporarily in session cache data blocks
    session['user_signup_name'] = name
    session['user_signup_email'] = email
    
    # Hash password using bcrypt and decode safely to a string field representation
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    session['user_signup_password'] = hashed_password

    # 3️⃣ Generate the unique verification security token code
    otp = random.randint(100000, 999999)
    session['user_otp'] = otp

    try:
        # 4️⃣ Dispatch confirmation alert mail payload via SMTP configuration blocks
        message = Message(
            subject="SmartCart User Verification OTP",
            sender=config.MAIL_USERNAME,
            recipients=[email]
        )
        message.body = f"Hello {name},\n\nYour OTP for registration on SmartCart is: {otp}\n\nPlease do not share this security token with anyone."
        mail.send(message)

        flash("Verification OTP sent to your email!", "success")
        return redirect('/user/verify-otp')
        
    except Exception as e:
        app.logger.error("Failed to execute User Registration Email dispatch: %s", str(e))
        flash("Error sending OTP. Please check your system email setup configuration.", "danger")
        return redirect('/user-register')


# =================================================================
# ROUTE: DISPLAY USER OTP INPUT MASK VIA SHARED TEMPLATE
# =================================================================
@app.route('/user/verify-otp', methods=['GET'])
def verify_user_otp_get():
    if 'user_otp' not in session:
        flash("Session expired. Please register again.", "danger")
        return redirect('/user-register')
        
    # REUSE: Serves your existing admin page layout while pointing submission action routes to the user processor
    return render_template("admin/verify_otp.html", target_url="/user/verify-otp")


# =================================================================
# ROUTE: PROCESS USER OTP VERIFICATION & INSERT INTO DATABASE
# =================================================================
@app.route('/user/verify-otp', methods=['POST'])
def verify_user_otp_post():
    if 'user_otp' not in session:
        flash("Registration session expired. Please start over.", "danger")
        return redirect('/user-register')

    submitted_otp = request.form.get('otp')

    # Compare validation handshake codes securely
    if str(session.get('user_otp')) != str(submitted_otp):
        flash("Invalid Verification OTP. Please try again!", "danger")
        return redirect('/user/verify-otp')

    # Fetch cached parameters back out of session state blocks
    name = session.get('user_signup_name')
    email = session.get('user_signup_email')
    hashed_password = session.get('user_signup_password')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Commit record into your standard SQLite database data sets
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed_password)
        )
        conn.commit()
        
        # Housekeeping: Purge memory configurations safely out of active state storage
        session.pop('user_otp', None)
        session.pop('user_signup_name', None)
        session.pop('user_signup_email', None)
        session.pop('user_signup_password', None)

        flash("Account verified successfully! Please log in.", "success")
        return redirect('/user-login')
        
    except Exception as e:
        app.logger.error("User registration execution failure sequence: %s", str(e))
        flash("An error occurred while building your profile. Try again.", "danger")
        return redirect('/user-register')
    finally:
        cursor.close()
        conn.close()

# =================================================================
# ROUTE: USER LOGIN
# =================================================================
@app.route('/user-login', methods=['GET', 'POST'])
def user_login():

    if request.method == 'GET':
        return render_template("user/user_login.html")

    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        flash("Email not found! Please register.", "danger")
        return redirect('/user-login')

    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        flash("Incorrect password!", "danger")
        return redirect('/user-login')

    # Create user session
    session['user_id'] = user['user_id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    flash("Login successful!", "success")
    return redirect('/user-dashboard')

# =================================================================
# ROUTE: USER DASHBOARD
# =================================================================
@app.route('/user-dashboard')
def user_dashboard():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    return render_template("user/user_home.html", user_name=session['user_name'])

# =================================================================
# ROUTE: USER LOGOUT
# =================================================================
@app.route('/user-logout')
def user_logout():
    
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)

    flash("Logged out successfully!", "success")
    return redirect('/user-login')

# =================================================================
# ROUTE: USER PRODUCT LISTING (SEARCH + FILTER)
# =================================================================
@app.route('/user/products')
def user_products():
    # Optional: restrict only logged-in users
    if 'user_id' not in session:
        flash("Please login to view products!", "danger")
        return redirect('/user-login')

    # 1. Capture the query parameters from the URL strings cleanly
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 2. Fetch distinct categories and extract them into a clean string list
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
    raw_categories = cursor.fetchall()
    categories = [row['category'] for row in raw_categories]  # Converts dict rows to simple string list

    # 3. Build dynamic SQL query structure
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        # Search against both name and description for an enhanced shopping experience
        query += " AND (name LIKE %s OR description LIKE %s)"
        params.extend(["%" + search + "%", "%" + search + "%"])

    if category_filter:
        query += " AND category = %s"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    # 4. CRITICAL FIX: Pass state variables back so frontend can track active filters
    return render_template(
        "user/user_products.html",
        products=products,
        categories=categories,
        search_query=search,
        selected_category=category_filter
    )
# =================================================================
# ROUTE: USER PRODUCT DETAILS PAGE
# =================================================================
@app.route('/user/product/<int:product_id>')
def user_product_details(product_id):

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    return render_template("user/product_details.html", product=product)

# =================================================================
# ADD ITEM TO CART
# =================================================================
@app.route('/user/add-to-cart/<int:product_id>')
def add_to_cart(product_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    # Create cart if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    # Fetch product
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM products WHERE product_id=%s",
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    pid = str(product_id)

    # Increase quantity if already exists
    if pid in cart:
        cart[pid]['quantity'] += 1
    else:
        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart

    flash("Item added to cart successfully!", "success")

    return redirect(url_for('user_product_details', product_id=product_id))

# =================================================================
# VIEW CART PAGE
# =================================================================
@app.route('/user/cart')
def view_cart():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    cart = session.get('cart', {})

    # Calculate total
    grand_total = sum(item['price'] * item['quantity'] for item in cart.values())

    return render_template("user/cart.html", cart=cart, grand_total=grand_total)

# =================================================================
# INCREASE QUANTITY
# =================================================================
@app.route('/user/cart/increase/<pid>')
def increase_quantity(pid):

    cart = session.get('cart', {})

    if pid in cart:
        cart[pid]['quantity'] += 1

    session['cart'] = cart
    return redirect('/user/cart')
# =================================================================
# DECREASE QUANTITY
# =================================================================
@app.route('/user/cart/decrease/<pid>')
def decrease_quantity(pid):

    cart = session.get('cart', {})

    if pid in cart:
        cart[pid]['quantity'] -= 1

        # If quantity becomes 0 → remove item
        if cart[pid]['quantity'] <= 0:
            cart.pop(pid)

    session['cart'] = cart
    return redirect('/user/cart')

# =================================================================
# REMOVE ITEM
# =================================================================
@app.route('/user/cart/remove/<pid>')
def remove_from_cart(pid):

    cart = session.get('cart', {})

    if pid in cart:
        cart.pop(pid)

    session['cart'] = cart

    flash("Item removed!", "success")
    return redirect('/user/cart')

# ---------------------- CHECKOUT ----------------------

@app.route("/user/checkout", methods=["POST"])
def checkout():

    selected_products = request.form.getlist("selected_products")

    if not selected_products:
        flash("Please select at least one product.", "error")
        return redirect("/user/cart")

    cart = session.get("cart", {})

    checkout_items = {}
    total = 0

    for pid in selected_products:
        if pid in cart:
            checkout_items[pid] = cart[pid]
            total += float(cart[pid]["price"]) * int(cart[pid]["quantity"])

    session["checkout_items"] = checkout_items
    session["checkout_total"] = total

    return redirect("/user/address")


# ---------------------- ADDRESS PAGE ----------------------

@app.route("/user/address")
def address():

    return render_template(
        "user/address.html",
        checkout_items=session.get("checkout_items", {}),
        total=session.get("checkout_total", 0)
    )


# ---------------------- SAVE ADDRESS ----------------------

@app.route("/user/save_address", methods=["POST"])
def save_address():

    session["address"] = {
        "fullname": request.form["fullname"],
        "mobile": request.form["mobile"],
        "address": request.form["address"],
        "city": request.form["city"],
        "state": request.form["state"],
        "pincode": request.form["pincode"]
    }

    return redirect("/user/payment")


# ---------------------- PAYMENT PAGE ----------------------

@app.route("/user/payment")
def payment():

    if "user_id" not in session:
        flash("Please login first!", "danger")
        return redirect("/user-login")

    return render_template(
        "user/payment.html",
        address=session.get("address"),
        checkout_items=session.get("checkout_items", {}),
        total=session.get("checkout_total", 0)
    )


# ---------------------- PLACE ORDER ----------------------

@app.route("/user/place_order", methods=["POST"])
def place_order():

    cart = session.get("cart", {})
    checkout_items = session.get("checkout_items", {})

    # Remove purchased products from cart
    for pid in checkout_items.keys():
        cart.pop(pid, None)

    session["cart"] = cart

    # Clear checkout session
    session.pop("checkout_items", None)
    session.pop("checkout_total", None)
    session.pop("address", None)
    session.pop("razorpay_order_id", None)

    flash("Order placed successfully!", "success")
    return redirect("/user/products")


# ---------------------- RAZORPAY CLIENT ----------------------

razorpay_client = razorpay.Client(
    auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)
)


# ---------------------- CREATE RAZORPAY ORDER ----------------------

@app.route("/user/pay")
def user_pay():

    if "user_id" not in session:
        flash("Please login first!", "danger")
        return redirect("/user-login")

    checkout_items = session.get("checkout_items", {})

    if not checkout_items:
        flash("No products selected for checkout!", "danger")
        return redirect("/user/cart")

    # Calculate total amount
    total_amount = sum(
        item["price"] * item["quantity"]
        for item in checkout_items.values()
    )

    if total_amount <= 0:
        flash("Invalid payment amount.", "danger")
        return redirect("/user/cart")

    try:
        # Create Razorpay Order
        razorpay_order = razorpay_client.order.create({
            "amount": int(total_amount * 100),   # Amount in paise
            "currency": "INR",
            "payment_capture": 1
        })

        session["checkout_total"] = total_amount
        session["razorpay_order_id"] = razorpay_order["id"]

        return render_template(
            "user/payment.html",
            address=session.get("address"),
            checkout_items=checkout_items,
            total=total_amount,
            key_id=config.RAZORPAY_KEY_ID,
            order_id=razorpay_order["id"]
        )

    except Exception as e:
        print("Razorpay Error:", e)
        flash(f"Razorpay Error: {e}", "danger")
        return redirect("/user/cart")

# ---------------------- PAYMENT SUCCESS ----------------------

@app.route("/payment-success")
def payment_success():

    payment_id = request.args.get("payment_id")
    order_id = request.args.get("order_id")

    if not payment_id:
        flash("Payment failed!", "danger")
        return redirect("/user/cart")

    return render_template(
        "user/payment_success.html",
        payment_id=payment_id,
        order_id=order_id
    )
# ------------------------------
# Route: Verify Payment and Store Order
# ------------------------------
@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        flash("Please login to complete the payment.", "danger")
        return redirect('/user-login')

    # Read values posted from frontend
    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_signature = request.form.get('razorpay_signature')

    if not (razorpay_payment_id and razorpay_order_id and razorpay_signature):
        flash("Payment verification failed (missing data).", "danger")
        return redirect('/user/cart')

    # Build verification payload required by Razorpay client.utility
    payload = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        # This will raise an error if signature invalid
        razorpay_client.utility.verify_payment_signature(payload)
    except Exception as e:
        # Verification failed
        app.logger.error("Razorpay signature verification failed: %s", str(e))
        flash("Payment verification failed. Please contact support.", "danger")
        return redirect('/user/cart')

    # ─── UPDATED ORDER CONTEXT STORAGE AND PROCESSING CHANNELS ───
    user_id = session['user_id']
    
    # Switch lookups from 'cart' to the active 'checkout_items' staging queue
    checkout_items = session.get('checkout_items', {})

    if not checkout_items:
        flash("Checkout data missing. Cannot create order.", "danger")
        return redirect('/user/products')

    # Calculate total amount based on the active items targeted for checkout
    total_amount = sum(float(item['price']) * int(item['quantity']) for item in checkout_items.values())

    # Get address data fields out of the session parameters (or map default values)
    addr_data = session.get('address', {})
    fullname = addr_data.get('fullname', 'Mani')
    mobile = addr_data.get('mobile', '9123413543')
    address_text = addr_data.get('address', '985-28/243, Chakripuram')
    city = addr_data.get('city', 'Hyderabad')
    state = addr_data.get('state', 'Telangana')
    pincode = addr_data.get('pincode', '500063')

    # DB insert: orders and order_items
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert into orders table including shipping tracking parameters
        cursor.execute("""
            INSERT INTO orders (
                user_id, razorpay_order_id, razorpay_payment_id, amount, payment_status,
                fullname, mobile, address, city, state, pincode
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, razorpay_order_id, razorpay_payment_id, total_amount, 'paid',
            fullname, mobile, address_text, city, state, pincode
        ))

        order_db_id = cursor.lastrowid  # newly created order's primary key

        # Insert items from checkout items loop mapping
        for pid_str, item in checkout_items.items():
            product_id = int(pid_str)
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                VALUES (%s, %s, %s, %s, %s)
            """, (order_db_id, product_id, item['name'], item['quantity'], item['price']))

        # Commit transaction explicitly to disk registers
        conn.commit()

        # Clear standard storage mapping ONLY for the variations that were just purchased
        cart = session.get('cart', {})
        for pid in checkout_items.keys():
            cart.pop(pid, None)

        session['cart'] = cart
        session.pop('checkout_items', None)
        session.pop('checkout_total', None)
        session.pop('address', None)
        session.pop('razorpay_order_id', None)

        flash("Payment successful and order placed!", "success")
        return redirect(f"/user/order-success/{order_db_id}")

    except Exception as e:
        # Rollback and log error
        conn.rollback()
        app.logger.error("Order storage failed: %s\n%s", str(e), traceback.format_exc())
        flash("There was an error saving your order. Contact support.", "danger")
        return redirect('/user/cart')

    finally:
        cursor.close()
        conn.close()

@app.route('/user/order-success/<int:order_db_id>')
def order_success(order_db_id):
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s", (order_db_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_db_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/products')

    return render_template("user/order_success.html", order=order, items=items)

@app.route('/user/my-orders')
def my_orders():
    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC", (session['user_id'],))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("user/my_orders.html", orders=orders)

# ----------------------------
# GENERATE INVOICE PDF
# ----------------------------
@app.route("/user/download-invoice/<int:order_id>")
def download_invoice(order_id):

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    # Fetch order
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE order_id=%s AND user_id=%s",
                   (order_id, session['user_id']))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect('/user/my-orders')

    # Render invoice HTML
    html = render_template("user/invoice.html", order=order, items=items)

    pdf = generate_pdf(html)
    if not pdf:
        flash("Error generating PDF", "danger")
        return redirect('/user/my-orders')

    # Prepare response
    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f"attachment; filename=invoice_{order_id}.pdf"

    return response


# =================================================================
# NEW: DIRECT ADD-TO-CART FROM CATALOG FEED WALL
# =================================================================
@app.route('/user/add-to-cart-direct/<int:product_id>')
def add_to_cart_direct(product_id):
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    pid = str(product_id)
    if pid in cart:
        cart[pid]['quantity'] += 1
    else:
        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart
    flash(f"🛒 Added {product['name']} to your cart!", "success")
    return redirect('/user/products')


# =================================================================
# NEW: INSTANT "BUY NOW" EXPRESS PIPELINE
# =================================================================
@app.route('/user/buy-now/<int:product_id>')
def buy_now_express(product_id):
    if 'user_id' not in session:
        flash("Please login to purchase items directly!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1️⃣ Fetch product specs instantly out of your master inventory table
    cursor.execute("SELECT * FROM products WHERE product_id=%s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    pid = str(product_id)
    total_amount = float(product['price'])

    # 2️⃣ Build structural express payload tracking maps directly in the Session state cache
    session["checkout_items"] = {
        pid: {
            'name': product['name'],
            'price': total_amount,
            'image': product['image'],
            'quantity': 1
        }
    }
    session["checkout_total"] = total_amount

    try:
        # 3️⃣ Create Razorpay transaction order parameters on-the-fly
        razorpay_order = razorpay_client.order.create({
            "amount": int(total_amount * 100),   # Value parameters mapped in Paise
            "currency": "INR",
            "payment_capture": 1
        })

        session["razorpay_order_id"] = razorpay_order["id"]

        # 4️⃣ RENDER CHANNELS: Serve payment checkout script layers immediately
        return render_template(
            "user/payment.html",
            address=session.get("address", {}), # Injects blank or fallback parameters safely
            checkout_items=session["checkout_items"],
            total=total_amount,
            key_id=config.RAZORPAY_KEY_ID,
            order_id=razorpay_order["id"]
        )
    except Exception as e:
        app.logger.error("Express Razorpay Initialization Failure: %s", str(e))
        flash("Payment gateway connection timed out. Please try again.", "danger")
        return redirect("/user/products")
    


@app.route('/user/verify-payment', methods=['POST', 'GET'])
def verify_payment_and_place_order():
    if 'user_id' not in session:
        flash("Session expired!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']
    
    # ─── NOTE: Get your Razorpay details from request (form, args, or json) ───
    # Depending on how your gateway sends it, it might be request.form or request.args
    razorpay_payment_id = request.values.get('razorpay_payment_id')
    razorpay_order_id = request.values.get('razorpay_order_id', 'pay_mock_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ FIRST: Fetch what is inside the cart BEFORE doing anything else
    cursor.execute("""
        SELECT c.*, p.name as product_name, p.price 
        FROM cart c 
        JOIN products p ON c.product_id = p.product_id 
        WHERE c.user_id = %s
    """, (user_id,))
    cart_items = cursor.fetchall()

    # If the user has refreshed the page or cart drops completely out of sync
    if not cart_items:
        cursor.close()
        conn.close()
        flash("Cart is empty. Cannot create order.", "danger")
        return redirect('/user/products')

    # 2️⃣ Calculate the Grand total sum value parameters safely
    grand_total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)

    # 3️⃣ Create a new master record in the 'orders' table
    cursor.execute("""
        INSERT INTO orders (user_id, razorpay_payment_id, amount, status) 
        VALUES (%s, %s, %s, 'Paid')
    """, (user_id, razorpay_payment_id, grand_total))
    
    # Capture the auto-generated unique Order ID
    new_order_id = cursor.lastrowid

    # 4️⃣ Move the item list out of the cart and into the permanent 'order_items' table
    for item in cart_items:
        cursor.execute("""
            INSERT INTO order_items (order_id, product_name, quantity, price) 
            VALUES (%s, %s, %s, %s)
        """, (new_order_id, item['product_name'], item['quantity'], item['price']))

    # 5️⃣ CRITICAL CORRECTION: Clear the user's cart ONLY AFTER copying the items safely
    cursor.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))
    
    # Commit changes permanently to the database
    conn.commit()
    cursor.close()
    conn.close()

    # 6️⃣ SUCCESSFUL PIPELINE ROUTING DISPLAY REDIRECT
    # Send the user to the success view with the exact newly created order primary key ID
    return redirect(f'/user/order-success/{new_order_id}')
# ------------------------- RUN APPARATUS SERVER ------------------------

if __name__ == '__main__':
    app.run(debug=True)