-- Crave: 15 reporting & integrity queries (run in DB Browser for SQLite or `sqlite3 database/food_ordering.db`)
-- 1  Orders with customer and restaurant (JOIN)
SELECT o.order_id,u.name,r.name,o.total_amount,o.status FROM Orders o JOIN Users u ON u.user_id=o.user_id JOIN Restaurants r ON r.restaurant_id=o.restaurant_id ORDER BY o.order_date DESC;
-- 2  Delivered sales by restaurant (GROUP BY)
SELECT r.name,SUM(o.total_amount) delivered_sales FROM Restaurants r JOIN Orders o ON o.restaurant_id=r.restaurant_id WHERE o.status='Delivered' GROUP BY r.restaurant_id ORDER BY delivered_sales DESC;
-- 3  Most ordered items
SELECT m.name,SUM(oi.quantity) units FROM Order_Items oi JOIN Menu_Items m ON m.item_id=oi.item_id JOIN Orders o ON o.order_id=oi.order_id WHERE o.status<>'Cancelled' GROUP BY m.item_id ORDER BY units DESC;
-- 4  Repeat customers (HAVING)
SELECT u.name,COUNT(*) n FROM Users u JOIN Orders o ON o.user_id=u.user_id GROUP BY u.user_id HAVING n>1;
-- 5  Active orders
SELECT order_id,order_date,status,total_amount FROM Orders WHERE status IN ('Pending','Confirmed','Preparing','Out for Delivery') ORDER BY order_date;
-- 6  Never-ordered items (LEFT JOIN ... IS NULL)
SELECT m.name FROM Menu_Items m LEFT JOIN Order_Items oi ON oi.item_id=m.item_id WHERE oi.item_id IS NULL;
-- 7  Payment status per order
SELECT o.order_id,o.total_amount,p.method,p.status FROM Orders o LEFT JOIN Payments p ON p.order_id=o.order_id;
-- 8  Average order value by restaurant
SELECT r.name,ROUND(AVG(o.total_amount)) avg_value,COUNT(*) n FROM Restaurants r JOIN Orders o ON o.restaurant_id=r.restaurant_id WHERE o.status<>'Cancelled' GROUP BY r.restaurant_id;
-- 9  Orders per customer, including zero (LEFT JOIN)
SELECT u.name,COUNT(o.order_id) n FROM Users u LEFT JOIN Orders o ON o.user_id=u.user_id WHERE u.role='customer' GROUP BY u.user_id;
-- 10 Rider workload
SELECT d.name,d.availability_status,COUNT(o.order_id) assigned FROM Delivery_Riders d LEFT JOIN Orders o ON o.rider_id=d.rider_id GROUP BY d.rider_id ORDER BY assigned DESC;
-- 11 Restaurant ratings (view)
SELECT r.name,x.avg_rating,x.review_count FROM Restaurant_Ratings x JOIN Restaurants r ON r.restaurant_id=x.restaurant_id;
-- 12 Daily revenue (view)
SELECT * FROM Daily_Revenue ORDER BY day;
-- 13 Coupon usage and money given away
SELECT coupon_code,COUNT(*) uses,SUM(discount) total_discount FROM Orders WHERE coupon_code IS NOT NULL GROUP BY coupon_code;
-- 14 Full status timeline of one order (written by triggers)
SELECT order_id,status,changed_at FROM Order_Status_History WHERE order_id=1 ORDER BY history_id;
-- 15 Integrity checks -- each should return 0 rows
SELECT order_id FROM Orders WHERE total_amount <> subtotal - discount + delivery_fee;
SELECT o.order_id FROM Orders o JOIN Order_Items oi ON oi.order_id=o.order_id GROUP BY o.order_id HAVING SUM(oi.quantity*oi.unit_price)<>o.subtotal;
SELECT order_id FROM Orders WHERE status='Out for Delivery' AND rider_id IS NULL;
