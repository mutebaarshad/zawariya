from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
import sqlite3
import os
import csv
import io
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)

# ==========================================
# APP CONFIGURATION
# ==========================================
app.secret_key = "zawaria_secret_key_2026"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "zawariya.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "images")
PAYMENT_FOLDER = os.path.join(UPLOAD_FOLDER, "payments")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PAYMENT_FOLDER, exist_ok=True)


# ==========================================
# DATABASE HELPER
# ==========================================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def get_products():
    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    conn.close()
    return products


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # PRODUCTS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            cost_price REAL NOT NULL DEFAULT 0,
            image TEXT NOT NULL,
            image_side TEXT,
            image_back TEXT,
            image_detail TEXT,
            description TEXT,
            size TEXT,
            category TEXT DEFAULT 'Luxury Dress',
            stock INTEGER DEFAULT 50
        )
    """)

    # USERS TABLE (Client Portal)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ORDERS TABLE
    cursor.execute("""
         CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            city TEXT NOT NULL,
            postal_code TEXT,
            address TEXT NOT NULL,
            product_details TEXT NOT NULL,
            size TEXT,
            customization TEXT,
            total REAL NOT NULL,
            advance REAL NOT NULL,
            remaining REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_screenshot TEXT,
            transaction_id TEXT,
            status TEXT DEFAULT 'Pending Payment Verification',
            cost_total REAL NOT NULL DEFAULT 0,
            profit REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()

    # Migration check for new columns if DB existed
    db_columns = [col[1] for col in cursor.execute("PRAGMA table_info(products)").fetchall()]
    if "cost_price" not in db_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN cost_price REAL NOT NULL DEFAULT 0")
    if "image_side" not in db_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN image_side TEXT")
    if "image_back" not in db_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN image_back TEXT")
    if "image_detail" not in db_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN image_detail TEXT")
    if "stock" not in db_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 50")

    order_columns = [col[1] for col in cursor.execute("PRAGMA table_info(orders)").fetchall()]
    if "cost_total" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN cost_total REAL NOT NULL DEFAULT 0")
    if "profit" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN profit REAL NOT NULL DEFAULT 0")
    if "transaction_id" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN transaction_id TEXT")
    if "user_id" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER")

    conn.commit()

    # Populate Initial Products if table is empty or update missing image angles
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]

    initial_products = [
        (
            1,
            "Elegant Olive Frock",
            12000.0,
            6200.0,
            "olive_frock_ai_front.jpg",
            "olive_frock_ai_side.jpg",
            "olive_frock_ai_back.jpg",
            "olive_frock_ai_detail.jpg",
            """Presenting our signature masterpiece – a long olive-green frock worn gracefully by our fashion model.
Front-panel pleated detailing with a graceful flow, giving a structured yet dreamy silhouette.
Soft, lightweight chiffon material with sheer sleeves for a sophisticated look.
Includes multi-angle showcase (Front, Side, Back, and Close-Up Detail).
Attached cancan is also available for an additional PKR 1,500.""",
            "S,M,L,XL,Custom",
            "Luxury Dress",
            45
        ),
        (
            2,
            "Rang-e-Jan",
            35000.0,
            18500.0,
            "rang_e_jan_1.jpeg",
            "rang_e_jan_2 .jpeg",
            "rang_e_jan_1.jpeg",
            "rang_e_jan_1.jpeg",
            """Unveiling Rang-e-Jan 🌸
ZAWARIA's first signature launch — a pastel raw silk masterpiece, hand-embellished with delicate floral artistry and fine detailing.
A timeless 3-piece stitched set designed for the woman who embodies grace and elegance.""",
            "S,M,L,XL,Custom",
            "Signature Collection",
            30
        ),
        (
            3,
            "Siyaah",
            15000.0,
            7800.0,
            "siyaah_front.jpg",
            "siyaah_side.jpg",
            "siyaah_upper.jpg",
            "siyaah_detail.jpg",
            """Introducing Siyaah 🖤
A 3-piece stitched ensemble crafted for those who appreciate elegance with a touch of tradition.
Classic shalwar kameez stitched from a luxurious silk blend, adorned with intricate sequins and fringe detailing.""",
            "S,M,L,XL,Custom",
            "Luxury Dress",
            25
        ),
        (
            4,
            "Laal",
            20000.0,
            9500.0,
            "laal_front.jpg",
            "laal_side.jpg",
            "laal_upper.jpg",
            "laal_detail.jpg",
            """Elegant Laal Pakistani dress.
A beautiful traditional outfit designed for graceful formal and semi-formal occasions with fine gold zardozi threadwork.""",
            "S,M,L,XL,Custom",
            "Festive Stitched",
            20
        )
    ]

    if count == 0:
        cursor.executemany("""
            INSERT INTO products (id, name, price, cost_price, image, image_side, image_back, image_detail, description, size, category, stock)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_products)
        conn.commit()
    else:
        # Update existing database rows with latest images & prices
        cursor.execute("""
            UPDATE products 
            SET image = 'olive_frock_ai_front.jpg',
                image_side = 'olive_frock_ai_side.jpg',
                image_back = 'olive_frock_ai_back.jpg',
                image_detail = 'olive_frock_ai_detail.jpg'
            WHERE id = 1 OR name LIKE '%Olive%'
        """)
        cursor.execute("""
            UPDATE products 
            SET price = 20000.0,
                cost_price = 9500.0
            WHERE id = 4 OR name LIKE '%Laal%'
        """)
        conn.commit()

    conn.close()

init_db()


# ==========================================
# PUBLIC ROUTES
# ==========================================

@app.route("/")
def home():
    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("index.html", products=products)


@app.route("/collections")
def collections():
    conn = get_db()
    category = request.args.get("category")
    if category:
        products = conn.execute("SELECT * FROM products WHERE category = ? ORDER BY id ASC", (category,)).fetchall()
    else:
        products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    conn.close()
    return render_template("collections.html", products=products, selected_category=category)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    related_products = conn.execute("SELECT * FROM products WHERE id != ? LIMIT 3", (product_id,)).fetchall()
    conn.close()
    if not product:
        return redirect(url_for("collections"))
    return render_template("product_detail.html", product=product, related_products=related_products)


@app.route("/api/product/<int:product_id>")
def api_product(product_id):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if product:
        return jsonify(dict(product))
    return jsonify({"error": "Product not found"}), 404


@app.route("/jewelry")
def jewelry():
    conn = get_db()
    products = conn.execute("SELECT * FROM products WHERE category LIKE '%Jewelry%' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("jewelry.html", products=products)


@app.route("/cart")
def cart():
    return render_template("cart.html")


@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


# ==========================================
# ORDER PLACEMENT (50% ADVANCE PAYMENT)
# ==========================================

@app.route("/place-order", methods=["POST"])
def place_order():
    try:
        customer_name = request.form.get("customer_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        city = request.form.get("city")
        postal_code = request.form.get("postal_code", "")
        address = request.form.get("address")
        product_details = request.form.get("product_details")
        size = request.form.get("size")
        customization = request.form.get("customization", "")
        payment_method = request.form.get("payment_method")
        transaction_id = request.form.get("transaction_id", "")
        
        total = float(request.form.get("total", 0))
        advance = total * 0.50
        remaining = total * 0.50

        if not customer_name or not phone or not city or not address or not size or total <= 0 or not payment_method:
            return jsonify({"success": False, "message": "Please fill all required customer and size fields."})

        screenshot = request.files.get("payment_screenshot")
        filename = ""
        if screenshot and screenshot.filename != "":
            safe_name = secure_filename(screenshot.filename)
            filename = f"{int(time.time())}_{safe_name}"
            screenshot.save(os.path.join(PAYMENT_FOLDER, filename))
        else:
            return jsonify({"success": False, "message": "50% Advance Payment screenshot receipt is required to confirm your order."})

        # Calculate COGS (Cost of goods sold) & Profit
        # Estimate cost at 50% of total if item details don't match specifically
        cost_total = total * 0.50
        user_id = session.get("user_id", None)

        conn = get_db()
        cursor = conn.execute("""
            INSERT INTO orders (
                user_id, customer_name, phone, email, city, postal_code, address,
                product_details, size, customization, total, advance, remaining,
                payment_method, payment_screenshot, transaction_id, status, cost_total, profit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, customer_name, phone, email, city, postal_code, address,
            product_details, size, customization, total, advance, remaining,
            payment_method, filename, transaction_id, "Pending Payment Verification",
            cost_total, total - cost_total
        ))

        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "total": total,
            "advance": advance,
            "remaining": remaining,
            "payment_method": payment_method,
            "message": "Order placed successfully! Your 50% advance payment verification is now under review."
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"})


@app.route("/order-success/<int:order_id>")
def order_success(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    if not order:
        return redirect(url_for("home"))
    return render_template("order_success.html", order=order)


# ==========================================
# CLIENT AUTHENTICATION & MY ACCOUNT
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")

        if not name or not email or not phone or not password:
            flash("All fields are required.", "danger")
            return render_template("client_register.html")

        conn = get_db()
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("client_login"))

        cursor = conn.execute("""
            INSERT INTO users (name, email, phone, password)
            VALUES (?, ?, ?, ?)
        """, (name, email, phone, password))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        session["user_id"] = user_id
        session["user_name"] = name
        session["user_email"] = email
        session["user_phone"] = phone

        flash("Account created successfully!", "success")
        return redirect(url_for("my_account"))

    return render_template("client_register.html")


@app.route("/client-login", methods=["GET", "POST"])
def client_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password)).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_phone"] = user["phone"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("my_account"))

        flash("Invalid email or password.", "danger")

    return render_template("client_login.html")


@app.route("/client-logout")
def client_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)
    session.pop("user_phone", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@app.route("/my-account")
def my_account():
    if not session.get("user_id") and not session.get("user_phone"):
        return redirect(url_for("client_login"))

    conn = get_db()
    user_id = session.get("user_id")
    user_phone = session.get("user_phone")

    if user_id:
        orders = conn.execute("SELECT * FROM orders WHERE user_id = ? OR phone = ? ORDER BY created_at DESC", (user_id, user_phone)).fetchall()
    else:
        orders = conn.execute("SELECT * FROM orders WHERE phone = ? ORDER BY created_at DESC", (user_phone,)).fetchall()
    
    conn.close()
    return render_template("my_account.html", orders=orders)


# ==========================================
# ADMIN AUTHENTICATION & ANALYTICS
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password in ["12345", "zawaria2026"]:
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Invalid Username or Password.", "danger")

    return render_template("login.html")


@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()

    # Calculate Business Profit & Financial Analytics
    total_sales = conn.execute("SELECT SUM(total) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    total_advance = conn.execute("SELECT SUM(advance) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    pending_cod = conn.execute("SELECT SUM(remaining) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    total_cost = conn.execute("SELECT SUM(cost_total) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    net_profit = conn.execute("SELECT SUM(profit) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    
    profit_margin = ((net_profit / total_sales) * 100) if total_sales > 0 else 0.0
    pending_verifications = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending Payment Verification'").fetchone()[0] or 0

    analytics = {
        "total_sales": total_sales,
        "total_advance": total_advance,
        "pending_cod": pending_cod,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "profit_margin": round(profit_margin, 1),
        "total_orders": len(orders),
        "pending_verifications": pending_verifications
    }

    conn.close()
    return render_template("admin.html", products=products, orders=orders, analytics=analytics)


@app.route("/update-order/<int:order_id>", methods=["POST"])
def update_order(order_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    status = request.form.get("status")
    conn = get_db()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

    flash(f"Order #{order_id} status updated to '{status}'.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/profit-margin")
def admin_profit():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    raw_products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()

    products_margin = []
    total_inventory_cost = 0.0
    total_potential_revenue = 0.0

    for p in raw_products:
        p_dict = dict(p)
        price = float(p_dict.get('price', 0) or 0)
        cost = float(p_dict.get('cost_price', 0) or 0)
        stock = int(p_dict.get('stock', 0) or 0)
        profit_per_unit = price - cost
        margin_pct = ((profit_per_unit / price) * 100) if price > 0 else 0.0
        markup_pct = ((profit_per_unit / cost) * 100) if cost > 0 else 0.0

        total_inventory_cost += (cost * stock)
        total_potential_revenue += (price * stock)

        p_dict['stock'] = stock
        p_dict['profit_per_unit'] = profit_per_unit
        p_dict['margin_pct'] = round(margin_pct, 1)
        p_dict['markup_pct'] = round(markup_pct, 1)
        products_margin.append(p_dict)

    # Calculate Business Profit & Financial Analytics
    total_sales = conn.execute("SELECT SUM(total) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    total_advance = conn.execute("SELECT SUM(advance) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    pending_cod = conn.execute("SELECT SUM(remaining) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    total_cost = conn.execute("SELECT SUM(cost_total) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    net_profit = conn.execute("SELECT SUM(profit) FROM orders WHERE status != 'Cancelled'").fetchone()[0] or 0.0
    
    profit_margin = ((net_profit / total_sales) * 100) if total_sales > 0 else 0.0

    analytics = {
        "total_sales": total_sales,
        "total_advance": total_advance,
        "pending_cod": pending_cod,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "profit_margin": round(profit_margin, 1),
        "total_orders": len(orders),
        "total_inventory_cost": total_inventory_cost,
        "total_potential_revenue": total_potential_revenue
    }

    conn.close()
    return render_template("admin_profit.html", products=products_margin, orders=orders, analytics=analytics)


@app.route("/add-product", methods=["POST"])
def add_product():
    if not session.get("admin"):
        return redirect(url_for("login"))

    name = request.form.get("name")
    price = request.form.get("price")
    cost_price = request.form.get("cost_price", 0) or 0
    description = request.form.get("description", "")
    size = request.form.get("size", "S,M,L,XL,Custom")
    category = request.form.get("category", "Luxury Dress")
    stock = request.form.get("stock", 50) or 50

    main_img = request.files.get("image")
    side_img = request.files.get("image_side")
    back_img = request.files.get("image_back")
    detail_img = request.files.get("image_detail")

    if not name or not price or not main_img or main_img.filename == "":
        flash("Please provide product name, price and main product image.", "danger")
        return redirect(url_for("admin"))

    main_filename = secure_filename(main_img.filename)
    main_img.save(os.path.join(app.config["UPLOAD_FOLDER"], main_filename))

    side_filename = main_filename
    if side_img and side_img.filename:
        side_filename = secure_filename(side_img.filename)
        side_img.save(os.path.join(app.config["UPLOAD_FOLDER"], side_filename))

    back_filename = main_filename
    if back_img and back_img.filename:
        back_filename = secure_filename(back_img.filename)
        back_img.save(os.path.join(app.config["UPLOAD_FOLDER"], back_filename))

    detail_filename = main_filename
    if detail_img and detail_img.filename:
        detail_filename = secure_filename(detail_img.filename)
        detail_img.save(os.path.join(app.config["UPLOAD_FOLDER"], detail_filename))

    conn = get_db()
    conn.execute("""
        INSERT INTO products (name, price, cost_price, image, image_side, image_back, image_detail, description, size, category, stock)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, float(price), float(cost_price), main_filename, side_filename, back_filename, detail_filename, description, size, category, int(stock)))
    conn.commit()
    conn.close()

    flash(f"New luxury product '{name}' added successfully and published on website!", "success")
    redirect_target = request.form.get("redirect_to") or request.referrer or url_for("admin")
    return redirect(redirect_target)


@app.route("/edit-product/<int:product_id>", methods=["POST"])
def edit_product(product_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    name = request.form.get("name")
    price = request.form.get("price")
    cost_price = request.form.get("cost_price")
    stock = request.form.get("stock")

    conn = get_db()
    conn.execute("""
        UPDATE products
        SET name = ?, price = ?, cost_price = ?, stock = ?
        WHERE id = ?
    """, (name, float(price), float(cost_price), int(stock), product_id))
    conn.commit()
    conn.close()

    flash(f"Product #{product_id} updated.", "success")
    return redirect(url_for("admin"))


@app.route("/delete-product/<int:product_id>")
def delete_product(product_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

    flash("Product deleted.", "warning")
    return redirect(url_for("admin"))


@app.route("/full-edit-product/<int:product_id>", methods=["POST"])
def full_edit_product(product_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price")
    cost_price = request.form.get("cost_price", 0) or 0
    stock = request.form.get("stock", 50) or 50
    size = request.form.get("size", "S,M,L,XL,Custom")
    description = request.form.get("description", "")

    main_img = request.files.get("image")
    side_img = request.files.get("image_side")
    back_img = request.files.get("image_back")
    detail_img = request.files.get("image_detail")

    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        flash("Product not found.", "danger")
        return redirect(url_for("admin"))

    main_filename = product["image"]
    if main_img and main_img.filename:
        main_filename = secure_filename(main_img.filename)
        main_img.save(os.path.join(app.config["UPLOAD_FOLDER"], main_filename))

    side_filename = product["image_side"] or main_filename
    if side_img and side_img.filename:
        side_filename = secure_filename(side_img.filename)
        side_img.save(os.path.join(app.config["UPLOAD_FOLDER"], side_filename))

    back_filename = product["image_back"] or main_filename
    if back_img and back_img.filename:
        back_filename = secure_filename(back_img.filename)
        back_img.save(os.path.join(app.config["UPLOAD_FOLDER"], back_filename))

    detail_filename = product["image_detail"] or main_filename
    if detail_img and detail_img.filename:
        detail_filename = secure_filename(detail_img.filename)
        detail_img.save(os.path.join(app.config["UPLOAD_FOLDER"], detail_filename))

    conn.execute("""
        UPDATE products
        SET name = ?, category = ?, price = ?, cost_price = ?, stock = ?, size = ?, description = ?,
            image = ?, image_side = ?, image_back = ?, image_detail = ?
        WHERE id = ?
    """, (name, category, float(price), float(cost_price), int(stock), size, description,
          main_filename, side_filename, back_filename, detail_filename, product_id))
    conn.commit()
    conn.close()

    flash(f"Full product details for '{name}' updated successfully!", "success")
    return redirect(url_for("admin"))


@app.route("/admin/order-invoice/<int:order_id>")
def order_invoice(order_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("admin"))

    return render_template("order_invoice.html", order=order)


@app.route("/admin/export-orders")
def export_orders():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order ID", "Date", "Customer Name", "Phone", "Email", "City", "Address",
        "Product Details", "Size", "Customization", "Total (PKR)", "50% Advance", "Remaining COD",
        "Payment Method", "Transaction ID", "Status", "COGS Cost", "Profit"
    ])

    for o in orders:
        writer.writerow([
            o["id"], o["created_at"], o["customer_name"], o["phone"], o["email"], o["city"], o["address"],
            o["product_details"], o["size"], o["customization"], o["total"], o["advance"], o["remaining"],
            o["payment_method"], o["transaction_id"], o["status"], o["cost_total"], o["profit"]
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ZAWARIA_Orders_Report.csv"}
    )


@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("login"))


# ==========================================
# INFORMATIONAL PAGES
# ==========================================

@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)