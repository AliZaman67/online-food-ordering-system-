-- Crave: Online Food Ordering System -- SQLite schema (10 tables, 3 views, 4 triggers)
PRAGMA foreign_keys = ON;

CREATE TABLE Users (
  user_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  phone TEXT,
  address TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','admin')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE Restaurants (
  restaurant_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  cuisine TEXT NOT NULL,
  address TEXT,
  phone TEXT,
  emoji TEXT NOT NULL DEFAULT '🍽️',
  delivery_fee NUMERIC NOT NULL DEFAULT 0 CHECK (delivery_fee >= 0),
  min_order NUMERIC NOT NULL DEFAULT 0 CHECK (min_order >= 0),
  eta_minutes INTEGER NOT NULL DEFAULT 30 CHECK (eta_minutes > 0),
  is_open INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0,1))
);
CREATE TABLE Categories (
  category_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE Menu_Items (
  item_id INTEGER PRIMARY KEY,
  restaurant_id INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  emoji TEXT NOT NULL DEFAULT '🍴',
  price NUMERIC NOT NULL CHECK (price >= 0),
  is_veg INTEGER NOT NULL DEFAULT 0 CHECK (is_veg IN (0,1)),
  is_available INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0,1)),
  FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id),
  FOREIGN KEY (category_id) REFERENCES Categories(category_id)
);
CREATE TABLE Delivery_Riders (
  rider_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  availability_status TEXT NOT NULL DEFAULT 'Available'
    CHECK (availability_status IN ('Available','Busy','Offline'))
);
CREATE TABLE Coupons (
  code TEXT PRIMARY KEY,
  discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 90),
  min_order NUMERIC NOT NULL DEFAULT 0 CHECK (min_order >= 0),
  expires_on TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);
CREATE TABLE Orders (
  order_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  restaurant_id INTEGER NOT NULL,
  rider_id INTEGER,
  coupon_code TEXT,
  order_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'Pending'
    CHECK (status IN ('Pending','Confirmed','Preparing','Out for Delivery','Delivered','Cancelled')),
  subtotal NUMERIC NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
  discount NUMERIC NOT NULL DEFAULT 0 CHECK (discount >= 0),
  delivery_fee NUMERIC NOT NULL DEFAULT 0 CHECK (delivery_fee >= 0),
  total_amount NUMERIC NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
  delivery_address TEXT,
  notes TEXT,
  FOREIGN KEY (user_id) REFERENCES Users(user_id),
  FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id),
  FOREIGN KEY (rider_id) REFERENCES Delivery_Riders(rider_id),
  FOREIGN KEY (coupon_code) REFERENCES Coupons(code)
);
CREATE TABLE Order_Items (
  order_item_id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC NOT NULL CHECK (unit_price >= 0),
  FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES Menu_Items(item_id)
);
CREATE TABLE Payments (
  payment_id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL UNIQUE,
  amount NUMERIC NOT NULL CHECK (amount >= 0),
  method TEXT NOT NULL CHECK (method IN ('Cash','Card','Wallet')),
  status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','Paid','Failed')),
  payment_date TEXT,
  FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE
);
CREATE TABLE Order_Status_History (
  history_id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE
);
CREATE TABLE Reviews (
  review_id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL UNIQUE,
  user_id INTEGER NOT NULL,
  restaurant_id INTEGER NOT NULL,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES Orders(order_id),
  FOREIGN KEY (user_id) REFERENCES Users(user_id),
  FOREIGN KEY (restaurant_id) REFERENCES Restaurants(restaurant_id)
);

-- Indexes for the queries the app runs most
CREATE INDEX idx_orders_status ON Orders(status);
CREATE INDEX idx_orders_user ON Orders(user_id);
CREATE INDEX idx_orders_rest ON Orders(restaurant_id);
CREATE INDEX idx_items_order ON Order_Items(order_id);
CREATE INDEX idx_menu_rest ON Menu_Items(restaurant_id);
CREATE INDEX idx_hist_order ON Order_Status_History(order_id);
CREATE INDEX idx_reviews_rest ON Reviews(restaurant_id);

-- Triggers: status history is written by the database itself, so it can never be skipped
CREATE TRIGGER trg_order_created AFTER INSERT ON Orders
BEGIN
  INSERT INTO Order_Status_History(order_id, status) VALUES (NEW.order_id, NEW.status);
END;
CREATE TRIGGER trg_order_status AFTER UPDATE OF status ON Orders
WHEN OLD.status <> NEW.status
BEGIN
  INSERT INTO Order_Status_History(order_id, status) VALUES (NEW.order_id, NEW.status);
END;
CREATE TRIGGER trg_rider_busy AFTER UPDATE OF rider_id ON Orders
WHEN NEW.rider_id IS NOT NULL AND NEW.status NOT IN ('Delivered','Cancelled')
BEGIN
  UPDATE Delivery_Riders SET availability_status='Busy' WHERE rider_id=NEW.rider_id;
END;
CREATE TRIGGER trg_rider_free AFTER UPDATE OF status ON Orders
WHEN NEW.status IN ('Delivered','Cancelled') AND NEW.rider_id IS NOT NULL
BEGIN
  UPDATE Delivery_Riders SET availability_status='Available'
  WHERE rider_id=NEW.rider_id AND availability_status='Busy';
END;

-- Views
CREATE VIEW Order_Summary AS
SELECT o.order_id, o.order_date, o.status, o.total_amount,
       u.name AS customer_name, r.name AS restaurant_name
FROM Orders o JOIN Users u ON u.user_id=o.user_id JOIN Restaurants r ON r.restaurant_id=o.restaurant_id;

CREATE VIEW Restaurant_Ratings AS
SELECT r.restaurant_id, ROUND(AVG(v.rating),1) AS avg_rating, COUNT(v.review_id) AS review_count
FROM Restaurants r LEFT JOIN Reviews v ON v.restaurant_id=r.restaurant_id GROUP BY r.restaurant_id;

CREATE VIEW Daily_Revenue AS
SELECT date(order_date) AS day, COUNT(*) AS orders, SUM(total_amount) AS revenue
FROM Orders WHERE status='Delivered' GROUP BY date(order_date);
